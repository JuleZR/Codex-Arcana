(function () {
  "use strict";

  const supported = Boolean(
    window.PublicKeyCredential && navigator.credentials
  );

  const decodeBase64url = function (value) {
    const padding = "=".repeat((4 - value.length % 4) % 4);
    const binary = window.atob((value + padding).replace(/-/g, "+").replace(/_/g, "/"));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes.buffer;
  };

  const encodeBase64url = function (value) {
    if (value === null || value === undefined) return null;
    const bytes = new Uint8Array(value);
    let binary = "";
    bytes.forEach(function (byte) {
      binary += String.fromCharCode(byte);
    });
    return window.btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  };

  const csrfToken = function (root) {
    const form = root.closest("form") || document;
    const input = form.querySelector("input[name='csrfmiddlewaretoken']")
      || document.querySelector("input[name='csrfmiddlewaretoken']");
    return input ? input.value : "";
  };

  const requestOptions = async function (url, formData, root) {
    const response = await fetch(url, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: {"X-CSRFToken": csrfToken(root)},
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.message || "Die Passkey-Anfrage ist fehlgeschlagen.");
    }
    return payload;
  };

  const verifyCredential = async function (url, credential, root) {
    const response = await fetch(url, {
      method: "POST",
      body: JSON.stringify(credential),
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(root),
      },
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.message || "Der Passkey konnte nicht bestätigt werden.");
    }
    return payload;
  };

  const registrationCredentialJSON = function (credential) {
    return {
      id: credential.id,
      rawId: encodeBase64url(credential.rawId),
      type: credential.type,
      authenticatorAttachment: credential.authenticatorAttachment,
      clientExtensionResults: credential.getClientExtensionResults(),
      response: {
        attestationObject: encodeBase64url(credential.response.attestationObject),
        clientDataJSON: encodeBase64url(credential.response.clientDataJSON),
        transports: typeof credential.response.getTransports === "function"
          ? credential.response.getTransports()
          : [],
      },
    };
  };

  const authenticationCredentialJSON = function (credential) {
    return {
      id: credential.id,
      rawId: encodeBase64url(credential.rawId),
      type: credential.type,
      authenticatorAttachment: credential.authenticatorAttachment,
      clientExtensionResults: credential.getClientExtensionResults(),
      response: {
        authenticatorData: encodeBase64url(credential.response.authenticatorData),
        clientDataJSON: encodeBase64url(credential.response.clientDataJSON),
        signature: encodeBase64url(credential.response.signature),
        userHandle: encodeBase64url(credential.response.userHandle),
      },
    };
  };

  const showError = function (root, message) {
    const target = root.querySelector("[data-passkey-error]");
    if (!target) return;
    target.textContent = message;
    target.hidden = !message;
  };

  document.querySelectorAll("[data-passkey-login]").forEach(function (root) {
    if (!supported) return;
    root.hidden = false;
    const button = root.querySelector("[data-passkey-login-button]");
    button.addEventListener("click", async function () {
      button.disabled = true;
      showError(root, "");
      try {
        const formData = new FormData();
        formData.append("next", root.dataset.next || "");
        const options = await requestOptions(root.dataset.optionsUrl, formData, root);
        options.challenge = decodeBase64url(options.challenge);
        (options.allowCredentials || []).forEach(function (descriptor) {
          descriptor.id = decodeBase64url(descriptor.id);
        });
        const credential = await navigator.credentials.get({publicKey: options});
        const result = await verifyCredential(
          root.dataset.verifyUrl,
          authenticationCredentialJSON(credential),
          root
        );
        window.location.assign(result.redirect);
      } catch (error) {
        const message = error.name === "NotAllowedError"
          ? "Die Passkey-Auswahl wurde abgebrochen oder ist abgelaufen."
          : error.message;
        showError(root, message);
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-passkey-registration]").forEach(function (root) {
    const button = root.querySelector("[data-passkey-register-button]");
    const form = document.getElementById("passkeyRegistrationForm");
    if (!supported) {
      button.disabled = true;
      showError(root, "Dieser Browser unterstützt Passkeys nicht.");
      return;
    }
    button.addEventListener("click", async function () {
      form.querySelectorAll("input[readonly]").forEach(function (input) {
        input.removeAttribute("readonly");
      });
      if (!form.reportValidity()) return;
      button.disabled = true;
      showError(root, "");
      try {
        const options = await requestOptions(
          root.dataset.optionsUrl,
          new FormData(form),
          root
        );
        options.challenge = decodeBase64url(options.challenge);
        options.user.id = decodeBase64url(options.user.id);
        (options.excludeCredentials || []).forEach(function (descriptor) {
          descriptor.id = decodeBase64url(descriptor.id);
        });
        const credential = await navigator.credentials.create({publicKey: options});
        const result = await verifyCredential(
          root.dataset.verifyUrl,
          registrationCredentialJSON(credential),
          root
        );
        window.location.assign(result.redirect);
      } catch (error) {
        const message = error.name === "NotAllowedError"
          ? "Die Passkey-Einrichtung wurde abgebrochen oder ist abgelaufen."
          : error.message;
        showError(root, message);
        button.disabled = false;
      }
    });
  });
}());
