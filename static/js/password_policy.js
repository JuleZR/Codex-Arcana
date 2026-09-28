(function () {
  "use strict";

  document.querySelectorAll("[data-password-policy-url]").forEach(function (form) {
    const passwordInput = form.querySelector(
      '[name="password1"], [name="new_password1"]'
    );
    const confirmationInput = form.querySelector(
      '[name="password2"], [name="new_password2"]'
    );
    const emailInput = form.querySelector('[name="email"]');
    const strength = form.querySelector("[data-password-strength]");
    if (!passwordInput || !confirmationInput || !strength) return;

    const label = strength.querySelector("[data-password-strength-label]");
    const levels = ["empty", "weak", "medium", "strong"];
    const strengthRules = ["length", "uppercase", "special"];
    let validationTimer = null;
    let validationRequest = 0;

    function getRule(name) {
      return form.querySelector('[data-password-rule="' + name + '"]');
    }

    function updateRule(name, isValid) {
      const rule = getRule(name);
      if (!rule) return;
      rule.classList.toggle("is-valid", isValid);
      rule.querySelector(".password_policy_icon").textContent = isValid ? "✓" : "×";
    }

    function updateLocalRule(name, isValid) {
      const rule = getRule(name);
      if (!rule) return;
      updateRule(name, isValid);
      rule.hidden = isValid;
    }

    function showServerWarning(name, shouldShow) {
      const rule = getRule(name);
      if (!rule) return;
      rule.hidden = !shouldShow;
      updateRule(name, false);
    }

    function updateStrengthLabel() {
      const password = passwordInput.value;
      let level = "empty";
      let text = "Noch nicht bewertet";
      if (password) {
        const validRuleCount = strengthRules.filter(function (name) {
          const rule = getRule(name);
          return rule && rule.classList.contains("is-valid");
        }).length;
        level = validRuleCount <= 1 ? "weak" : validRuleCount === 2 ? "medium" : "strong";
        text = level === "weak" ? "Schwach" : level === "medium" ? "Mittel" : "Stark";
      }
      levels.forEach(function (knownLevel) {
        strength.classList.toggle("is-" + knownLevel, level === knownLevel);
      });
      strength.dataset.level = level;
      label.textContent = text;
    }

    function updateLocalRules() {
      const password = passwordInput.value;
      updateLocalRule("length", password.length >= 8 && password.length <= 24);
      updateLocalRule("uppercase", password.toLowerCase() !== password);
      updateLocalRule("special", /[^\p{L}\p{N}\s]/u.test(password));
      updateLocalRule(
        "confirmation",
        Boolean(password) && confirmationInput.value === password
      );
      updateStrengthLabel();
    }

    function scheduleServerRules() {
      window.clearTimeout(validationTimer);
      validationRequest += 1;
      const currentRequest = validationRequest;
      const password = passwordInput.value;
      showServerWarning("common-password", false);
      showServerWarning("email-similarity", false);
      updateStrengthLabel();
      const localRulesValid = (
        password.length >= 8
        && password.length <= 24
        && password.toLowerCase() !== password
        && /[^\p{L}\p{N}\s]/u.test(password)
      );
      if (!localRulesValid) return;

      validationTimer = window.setTimeout(function () {
        const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]').value;
        const payload = new URLSearchParams({
          password: password,
          email: emailInput ? emailInput.value : ""
        });
        fetch(form.dataset.passwordPolicyUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken
          },
          body: payload.toString()
        })
          .then(function (response) {
            if (!response.ok) throw new Error("password policy check failed");
            return response.json();
          })
          .then(function (result) {
            if (currentRequest !== validationRequest) return;
            showServerWarning("common-password", result.common_password !== true);
            showServerWarning(
              "email-similarity",
              (form.dataset.passwordPolicyUserBound === "true"
                || Boolean(emailInput && emailInput.value.trim()))
                && result.email_similarity !== true
            );
            updateStrengthLabel();
          })
          .catch(function () {
            if (currentRequest !== validationRequest) return;
            showServerWarning("common-password", false);
            showServerWarning("email-similarity", false);
            updateStrengthLabel();
          });
      }, 300);
    }

    passwordInput.addEventListener("input", function () {
      updateLocalRules();
      scheduleServerRules();
    });
    confirmationInput.addEventListener("input", updateLocalRules);
    if (emailInput) emailInput.addEventListener("input", scheduleServerRules);
    updateLocalRules();
    scheduleServerRules();
  });
}());
