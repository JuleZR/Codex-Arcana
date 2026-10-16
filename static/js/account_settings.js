/* Productive account settings; form ownership stays server controlled. */
document.addEventListener("DOMContentLoaded", function () {
        const dddiceCheckbox = document.getElementById("id_dddice_enabled");
        const dddiceFields = document.getElementById("dddice_fields");
        const passwordInput = document.getElementById("id_new_password1");
        const passwordStrength = document.getElementById("accountPasswordStrength");
        document.getElementById("resetCriticalTexts")?.addEventListener("click", () => {
          document.getElementById("id_critical_success_text").value = "KRITISCHER ERFOLG";
          document.getElementById("id_critical_failure_text").value = "KRITISCHER FEHLSCHLAG";
        });
        document.getElementById("resetMwTexts")?.addEventListener("click", () => {
          document.getElementById("id_mw_success_text").value = "Erfolgreich";
          document.getElementById("id_mw_failure_text").value = "Nicht erfolgreich";
        });
        document.getElementById("resetSpecialFailureText")?.addEventListener("click", () => {
          document.getElementById("id_special_failure_text").value = "Fehlschlag";
        });

        const updatePasswordStrength = function () {
          if (!passwordInput || !passwordStrength) return;
          const value = passwordInput.value || "";
          let score = 0;
          if (value.length >= 8) score += 1;
          if (value.length >= 12) score += 1;
          if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
          if (/\d/.test(value)) score += 1;
          if (/[^A-Za-z0-9]/.test(value)) score += 1;
          if (/(.)\1\1/.test(value)) score -= 1;

          let strength = "empty";
          let message = "Neues Passwort eingeben.";
          if (value) {
            if (score <= 1) {
              strength = "weak";
              message = "Schwaches Passwort. Nutze mehr Länge und Zeichenvielfalt.";
            } else if (score <= 3) {
              strength = "fair";
              message = "Mittelstarkes Passwort. Länger oder mit Sonderzeichen wird es besser.";
            } else if (score === 4) {
              strength = "good";
              message = "Gutes Passwort.";
            } else {
              strength = "strong";
              message = "Starkes Passwort.";
            }
          }
          passwordStrength.dataset.strength = strength;
          const label = passwordStrength.querySelector("p");
          if (label) label.textContent = message;
          const status = passwordStrength.querySelector(".dashboard_password_strength_header strong");
          if (status) {
            status.textContent = {
              empty: "Bereit",
              weak: "Schwach",
              fair: "Mittel",
              good: "Gut",
              strong: "Stark",
            }[strength] || "Bereit";
          }
        };

        if (passwordInput) {
          passwordInput.addEventListener("input", updatePasswordStrength);
          updatePasswordStrength();
        }

        function updateDDDdiceFields() {
          if (!dddiceCheckbox || !dddiceFields) return;
        
          if (dddiceCheckbox.checked) {
            dddiceFields.style.display = "";
          } else {
            dddiceFields.open = false;
            dddiceFields.style.display = "none";
          }
        }

if (dddiceCheckbox) {
  dddiceCheckbox.addEventListener("change", updateDDDdiceFields);
  updateDDDdiceFields();
}
        const openAccountBtn = document.getElementById("openAccountSettings");
        const accountWin = document.getElementById("dashboardAccountWindow");
        const accountHandle = document.getElementById("dashboardAccountHandle");
        const accountCloseBtn = document.getElementById("dashboardAccountClose");
        const accountCancelBtn = document.getElementById("dashboardAccountCancel");
        const accountBackdrop = document.getElementById("dashboardAccountBackdrop");
        const accountBody = accountWin ? accountWin.querySelector(".dashboard_account_content") : null;
        const accountNav = accountWin ? Array.from(accountWin.querySelectorAll("[data-account-page]")) : [];
        const accountPanels = accountWin ? Array.from(accountWin.querySelectorAll("[data-account-panel]")) : [];
        const navigateAccount = function (id) {
          closeDetail();
          accountPanels.forEach(function (panel) { panel.hidden = panel.id !== id; });
          accountNav.forEach(function (button) {
            if (button.dataset.accountPage === id) button.setAttribute("aria-current", "page");
            else button.removeAttribute("aria-current");
          });
          if (accountBody) accountBody.scrollTop = 0;
        };
        accountNav.forEach(function (button, index) {
          button.addEventListener("click", function () { navigateAccount(button.dataset.accountPage); });
          button.addEventListener("keydown", function (event) {
            let next;
            if (event.key === "ArrowDown" || event.key === "ArrowRight") next = (index + 1) % accountNav.length;
            if (event.key === "ArrowUp" || event.key === "ArrowLeft") next = (index + accountNav.length - 1) % accountNav.length;
            if (event.key === "Home") next = 0;
            if (event.key === "End") next = accountNav.length - 1;
            if (next === undefined) return;
            event.preventDefault();
            accountNav[next].focus();
            navigateAccount(accountNav[next].dataset.accountPage);
          });
        });

        let activeDetail = null;
        let detailTrigger = null;
        const disclosures = Array.from(accountWin.querySelectorAll("details.dashboard_account_disclosure"));
        function closeDetail() {
          if (!activeDetail) return;
          activeDetail.open = false;
          activeDetail.classList.remove("is-active-detail");
          accountWin.classList.remove("has-account-detail");
          accountWin.querySelectorAll("[data-account-inert]").forEach(function (element) {
            element.inert = false;
            element.removeAttribute("data-account-inert");
          });
          activeDetail = null;
          detailTrigger?.focus();
        }
        function openDetail(detail) {
          if (activeDetail === detail) return;
          closeDetail();
          const panel = detail.closest("[data-account-panel]");
          navigateAccount(panel.id);
          activeDetail = detail;
          detailTrigger = detail.querySelector("summary");
          disclosures.forEach(function (other) { other.open = other === detail; });
          detail.classList.add("is-active-detail");
          accountWin.classList.add("has-account-detail");
          // Keep the original fields in their forms; only the focused view is interactive.
          let branch = detail;
          const nav = accountWin.querySelector(".dashboard_account_nav");
          nav.inert = true;
          nav.setAttribute("data-account-inert", "");
          while (branch && branch !== accountBody) {
            Array.from(branch.parentElement.children).forEach(function (sibling) {
              if (sibling !== branch && !sibling.inert) {
                sibling.inert = true;
                sibling.setAttribute("data-account-inert", "");
              }
            });
            branch = branch.parentElement;
          }
          detail.querySelector("[data-account-back]").focus();
        }
        disclosures.forEach(function (detail) {
          const summary = detail.querySelector("summary");
          const back = document.createElement("button");
          back.type = "button";
          back.className = "dashboard_button dashboard_account_back";
          back.setAttribute("data-account-back", "");
          back.textContent = "← Zurück zur Übersicht";
          detail.insertBefore(back, summary.nextSibling);
          back.addEventListener("click", closeDetail);
          summary.addEventListener("click", function (event) {
            event.preventDefault();
            if (activeDetail === detail) closeDetail();
            else openDetail(detail);
          });
        });
        navigateAccount("accountProfile");
        function revealField(field) {
          const panel = field.closest("[data-account-panel]");
          if (panel) navigateAccount(panel.id);
          const detail = field.closest("details.dashboard_account_disclosure");
          if (detail) openDetail(detail);
        }
        accountWin.addEventListener("invalid", function (event) {
          revealField(event.target);
        }, true);

        window.addEventListener("resize", function () {
          if (accountWin && accountWin.classList.contains("is-open")) {
            const rect = accountWin.getBoundingClientRect();
            const maxLeft = Math.max(12, window.innerWidth - rect.width - 12);
            const maxTop = Math.max(12, window.innerHeight - rect.height - 12);
            const left = Math.min(maxLeft, Math.max(12, rect.left));
            const top = Math.min(maxTop, Math.max(12, rect.top));
            accountWin.style.left = left + "px";
            accountWin.style.top = top + "px";
          }
        });

        if (openAccountBtn && accountWin && accountHandle && accountCloseBtn && accountCancelBtn && accountBackdrop) {
          const placeAccountCentered = function () {
            const rect = accountWin.getBoundingClientRect();
            const maxLeft = Math.max(12, window.innerWidth - rect.width - 12);
            const maxTop = Math.max(12, window.innerHeight - rect.height - 12);
            const left = Math.min(maxLeft, Math.max(12, (window.innerWidth - rect.width) / 2));
            const top = Math.min(maxTop, 92);
            accountWin.style.left = left + "px";
            accountWin.style.top = top + "px";
          };


          const mainForm = accountWin.querySelector(".dashboard_account_form");
          const status = document.getElementById("accountSaveStatus");
          const errors = document.getElementById("accountFormErrors");
          const saveButton = document.getElementById("accountSave");
          let saving = false;
          let leaving = false;
          const fields = () => Array.from(accountWin.querySelectorAll("input:not([type=hidden]), select, textarea"));
          const snapshot = () => fields().map(field => ({
            field, value: field.value, checked: field.checked, readOnly: field.readOnly,
          }));
          let accountSnapshot = snapshot();
          const changed = entry => entry.field.value !== entry.value || entry.field.checked !== entry.checked;
          const dirty = () => accountSnapshot.some(changed);
          const mainDirty = () => accountSnapshot.some(entry => entry.field.form === mainForm && changed(entry));
          const updateSaveState = function () {
            const pending = dirty();
            status.textContent = saving ? "Wird gespeichert …" : pending
              ? (mainDirty() ? "Nicht gespeicherte Änderungen" : "Sicherheitsangaben noch nicht bestätigt")
              : "Keine ausstehenden Änderungen";
            status.classList.toggle("is-dirty", pending);
            saveButton.disabled = saving || !mainDirty();
            accountCancelBtn.disabled = saving || !pending;
          };
          accountWin.addEventListener("input", updateSaveState);
          accountWin.addEventListener("change", updateSaveState);
          accountWin.addEventListener("click", function () { queueMicrotask(updateSaveState); });
          updateSaveState();
          window.addEventListener("beforeunload", function (event) {
            if (!leaving && dirty()) {
              event.preventDefault();
              event.returnValue = "";
            }
          });

          const openAccountWindow = function () {
            accountBackdrop.classList.add("is-open");
            accountWin.classList.add("is-open");
            accountWin.setAttribute("aria-hidden", "false");
            if (accountBody) {
              accountBody.scrollTop = 0;
            }
            placeAccountCentered();
            accountNav.find(function (button) { return button.hasAttribute("aria-current"); })?.focus();
          };

          const discardChanges = function (mainOnly = false) {
            if (mainOnly !== true) closeDetail();
            accountSnapshot.forEach(function ({field, value, checked, readOnly}) {
              if (mainOnly === true && field.form !== mainForm) return;
              if (field.tagName === "SELECT" && value && !Array.from(field.options).some(function (option) { return option.value === value; })) {
                field.add(new Option("Gespeichertes Würfelset", value));
              }
              field.value = value;
              field.checked = checked;
              if (readOnly !== undefined) field.readOnly = readOnly;
              if (field === document.getElementById("id_dddice_theme")) field.dataset.currentValue = value;
            });
            updateDDDdiceFields();
            updatePasswordStrength();
            errors.hidden = true;
            mainForm.querySelectorAll("[aria-invalid]").forEach(field => field.removeAttribute("aria-invalid"));
            updateSaveState();
          };
          const closeAccountWindow = function () {
            if (saving || !accountWin.classList.contains("is-open")) return;
            if (dirty() && !window.confirm("Nicht gespeicherte Änderungen verwerfen und das Fenster schließen?")) return;
            discardChanges();
            closeDetail();
            accountWin.classList.remove("is-open");
            accountWin.setAttribute("aria-hidden", "true");
            accountBackdrop.classList.remove("is-open");
            openAccountBtn.focus();
          };

          let accountDragPointerId = null;
          let accountDragOffsetX = 0;
          let accountDragOffsetY = 0;
          const accountIsInteractiveTarget = function (target) {
            return Boolean(target && target.closest("button, a, input, select, textarea, label"));
          };

          accountHandle.addEventListener("pointerdown", function (event) {
            const isPrimaryPointer = event.pointerType !== "mouse" || event.button === 0;
            if (!isPrimaryPointer || !accountWin.classList.contains("is-open") || accountIsInteractiveTarget(event.target)) {
              return;
            }
            const rect = accountWin.getBoundingClientRect();
            accountDragPointerId = event.pointerId;
            accountDragOffsetX = event.clientX - rect.left;
            accountDragOffsetY = event.clientY - rect.top;
            accountHandle.setPointerCapture(event.pointerId);
            accountWin.classList.add("is-dragging");
          });

          accountHandle.addEventListener("pointermove", function (event) {
            if (accountDragPointerId !== event.pointerId) {
              return;
            }
            const rect = accountWin.getBoundingClientRect();
            const maxLeft = Math.max(12, window.innerWidth - rect.width - 12);
            const maxTop = Math.max(12, window.innerHeight - rect.height - 12);
            const left = Math.min(maxLeft, Math.max(12, event.clientX - accountDragOffsetX));
            const top = Math.min(maxTop, Math.max(12, event.clientY - accountDragOffsetY));
            accountWin.style.left = left + "px";
            accountWin.style.top = top + "px";
          });

          const stopAccountDragging = function (event) {
            if (accountDragPointerId !== event.pointerId) {
              return;
            }
            accountWin.classList.remove("is-dragging");
            try {
              accountHandle.releasePointerCapture(event.pointerId);
            } catch (_error) {
            }
            accountDragPointerId = null;
          };

          accountHandle.addEventListener("pointerup", stopAccountDragging);
          accountHandle.addEventListener("pointercancel", stopAccountDragging);

          openAccountBtn.addEventListener("click", openAccountWindow);
          const initialAccount = new URLSearchParams(window.location.search).get("account");
          if (accountWin.dataset.openSecurity === "true" || initialAccount === "security" || initialAccount === "data") {
            navigateAccount(initialAccount === "data" ? "accountData" : "accountSecurity");
            openAccountWindow();
          }
          const initialDetail = disclosures.find(detail => detail.open);
          if (initialDetail) openDetail(initialDetail);

          mainForm.addEventListener("submit", async function (event) {
            if (event.submitter?.hasAttribute("formaction")) return;
            event.preventDefault();
            if (saving) return;
            if (accountSnapshot.some(entry => entry.field.form !== mainForm && changed(entry)) &&
                !window.confirm("Die unbestätigten Sicherheitsangaben werden nicht mitgespeichert. Einstellungen jetzt speichern?")) return;
            saving = true;
            mainForm.inert = true;
            updateSaveState();
            errors.hidden = true;
            mainForm.querySelectorAll("[aria-invalid]").forEach(field => field.removeAttribute("aria-invalid"));
            try {
              const response = await fetch(mainForm.action, {
                method: "POST", body: new FormData(mainForm), credentials: "same-origin",
                headers: {"X-Requested-With": "XMLHttpRequest"},
              });
              const result = await response.json();
              if (!response.ok) {
                if (!result.errors) throw new Error("save-failed");
                errors.textContent = Object.values(result.errors).flat().join(" ");
                errors.hidden = false;
                const first = Object.keys(result.errors).map(name => mainForm.elements.namedItem(name)).find(Boolean);
                Object.keys(result.errors).forEach(function (name) {
                  mainForm.elements.namedItem(name)?.setAttribute("aria-invalid", "true");
                });
                if (first) { revealField(first); mainForm.inert = false; first.focus(); }
              } else {
                leaving = true;
                window.location.assign(result.redirect);
              }
            } catch (_error) {
              errors.textContent = "Die Einstellungen konnten nicht gespeichert werden. Deine Eingaben bleiben erhalten. Bitte erneut versuchen.";
              errors.hidden = false;
            } finally {
              saving = false;
              mainForm.inert = false;
              updateSaveState();
            }
          });
          // Separate security forms keep their native validation and confirmations.
          accountWin.addEventListener("submit", function (event) {
            if (event.defaultPrevented || (event.target === mainForm && !event.submitter?.hasAttribute("formaction"))) return;
            if (mainDirty() && !window.confirm("Diese Aktion verlässt die Einstellungen. Nicht gespeicherte Änderungen verwerfen und fortfahren?")) {
              event.preventDefault();
              return;
            }
            leaving = true;
            setTimeout(function () { leaving = false; }, 0);
          });
          accountWin.addEventListener("click", function (event) {
            if (!event.target.closest("[data-passkey-register-button]") || !mainDirty()) return;
            if (!window.confirm("Vor der Passkey-Registrierung nicht gespeicherte Einstellungen verwerfen?")) {
              event.preventDefault();
              event.stopImmediatePropagation();
            } else {
              discardChanges(true);
            }
          }, true);
          const twoFactorSetupToggle = document.getElementById("twoFactorSetupToggle");
          const twoFactorEnrollment = document.getElementById("twoFactorEnrollment");
          const twoFactorSetupQr = document.getElementById("twoFactorSetupQr");
          const twoFactorSetupSecret = document.getElementById("twoFactorSetupSecret");
          const twoFactorSetupCode = document.getElementById("twoFactorSetupCode");
          const twoFactorSetupCancel = document.getElementById("twoFactorSetupCancel");
          const twoFactorSetupStartForm = document.getElementById("twoFactorSetupStartForm");
          const twoFactorSetupCancelForm = document.getElementById("twoFactorSetupCancelForm");

          if (twoFactorSetupToggle && twoFactorEnrollment && twoFactorSetupStartForm) {
            twoFactorSetupToggle.addEventListener("click", async function () {
              twoFactorSetupToggle.disabled = true;
              try {
                const response = await fetch(twoFactorSetupStartForm.action, {
                  method: "POST",
                  body: new FormData(twoFactorSetupStartForm),
                  credentials: "same-origin",
                  headers: {"X-Requested-With": "XMLHttpRequest"},
                });
                if (!response.ok) {
                  throw new Error("setup-start-failed");
                }
                const setup = await response.json();
                twoFactorSetupQr.src = setup.qr_data_uri;
                twoFactorSetupSecret.textContent = setup.secret;
                twoFactorEnrollment.hidden = false;
                twoFactorSetupToggle.hidden = true;
                twoFactorSetupToggle.setAttribute("aria-expanded", "true");
                twoFactorSetupCode.focus();
              } catch (error) {
                twoFactorSetupToggle.disabled = false;
                window.alert("Die 2FA-Einrichtung konnte nicht gestartet werden.");
              }
            });
          }

          if (twoFactorSetupCancel && twoFactorSetupCancelForm) {
            twoFactorSetupCancel.addEventListener("click", async function () {
              twoFactorSetupCancel.disabled = true;
              try {
                const response = await fetch(twoFactorSetupCancelForm.action, {
                  method: "POST",
                  body: new FormData(twoFactorSetupCancelForm),
                  credentials: "same-origin",
                  headers: {"X-Requested-With": "XMLHttpRequest"},
                });
                if (!response.ok) {
                  throw new Error("setup-cancel-failed");
                }
                twoFactorEnrollment.hidden = true;
                twoFactorSetupQr.removeAttribute("src");
                twoFactorSetupSecret.textContent = "";
                twoFactorSetupCode.value = "";
                twoFactorSetupToggle.hidden = false;
                twoFactorSetupToggle.disabled = false;
                twoFactorSetupToggle.setAttribute("aria-expanded", "false");
              } catch (error) {
                window.alert("Die 2FA-Einrichtung konnte nicht abgebrochen werden.");
              } finally {
                twoFactorSetupCancel.disabled = false;
              }
            });
          }
          accountCloseBtn.addEventListener("click", closeAccountWindow);
          accountCancelBtn.addEventListener("click", function () { discardChanges(); });
          accountBackdrop.addEventListener("click", closeAccountWindow);
          window.addEventListener("keydown", function (event) {
            if (!accountWin.classList.contains("is-open")) return;
            if (event.key === "Escape") {
              event.preventDefault();
              if (activeDetail) closeDetail();
              else closeAccountWindow();
            }
            if (event.key === "Tab") {
              const focusable = Array.from(accountWin.querySelectorAll("button, a[href], input, select, textarea, summary, [tabindex='0']"))
                .filter(function (element) { return !element.disabled && !element.closest("[inert]") && element.getClientRects().length > 0; });
              const first = focusable[0];
              const last = focusable[focusable.length - 1];
              if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
              if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
            }
          });
        }


});

