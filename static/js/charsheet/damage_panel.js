export function initDamagePanel() {
  const form = document.querySelector(".damage_actions");
  const circleWrap = document.querySelector(".damage_circle_wrap");
  const actionInput = document.querySelector(".damage_action_input");
  const amountInput = document.querySelector(".damage_amount_input");
  if (!form || !circleWrap || !actionInput || !amountInput) {
    return;
  }
  if (form.dataset.damageBound === "1") {
    return;
  }
  form.dataset.damageBound = "1";

  let glowTimeoutId = null;
  const triggerGlow = (action) => {
    circleWrap.classList.remove("effect-heal", "effect-damage");
    void circleWrap.offsetWidth;
    circleWrap.classList.add(action === "heal" ? "effect-heal" : "effect-damage");
    if (glowTimeoutId) {
      window.clearTimeout(glowTimeoutId);
    }
    glowTimeoutId = window.setTimeout(() => {
      circleWrap.classList.remove("effect-heal", "effect-damage");
      glowTimeoutId = null;
    }, 460);
  };

  form.querySelectorAll(".damage_action_btn[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.getAttribute("data-action");
      const amount = button.getAttribute("data-amount") || "1";
      if (action !== "heal" && action !== "damage") {
        return;
      }
      actionInput.value = action;
      amountInput.value = amount;
      triggerGlow(action);
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
        return;
      }
      form.submit();
    });
  });
}
