"use strict";

(() => {
  const form = document.getElementById("privacy-export-form");
  if (!form || typeof window.showSaveFilePicker !== "function") return;

  const status = document.getElementById("privacy-download-status");
  const formats = {
    pdf: ["PDF-Bericht", "application/pdf"],
    json: ["JSON-Daten", "application/json"],
    zip: ["ZIP-Exportpaket", "application/zip"],
  };

  let pending = false;
  form.addEventListener("submit", async (event) => {
    if (event.submitter?.value !== "download") return;
    event.preventDefault();
    if (pending) return;
    if (!form.elements.request_verified.checked) {
      status.textContent = "Bitte zuerst die Anfragenprüfung bestätigen.";
      return;
    }

    const kind = form.elements.format.value;
    const [description, mime] = formats[kind];
    const data = new FormData(form);
    data.set("action", "download");
    const buttons = [...form.querySelectorAll("button[type=submit]")];
    pending = true;
    buttons.forEach((button) => { button.disabled = true; });
    try {
      // Open on the user's gesture, before an asynchronous network request.
      const handle = await window.showSaveFilePicker({
        suggestedName: `codex-arcana-auskunft.${kind}`,
        types: [{ description, accept: { [mime]: [`.${kind}`] } }],
      });
      status.textContent = "Auskunft wird erstellt und lokal gespeichert …";
      const response = await fetch(form.action, {
        method: "POST",
        body: data,
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
      });
      if (!response.ok || !response.body ||
          response.headers.get("Content-Type")?.split(";")[0] !== mime) {
        throw new Error("export_failed");
      }
      // Stream directly to the selected local file; no large browser blob.
      await response.body.pipeTo(await handle.createWritable());
      status.textContent = "Auskunft lokal gespeichert. Keine Exportdatei auf dem Server angelegt.";
    } catch (error) {
      status.textContent = error.name === "AbortError"
        ? "Speichern abgebrochen."
        : "Auskunft konnte nicht gespeichert werden. Prüfe die Eingaben mit der Kategorienvorschau und versuche es erneut.";
    } finally {
      pending = false;
      buttons.forEach((button) => { button.disabled = false; });
    }
  });
})();
