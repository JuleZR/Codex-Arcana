export function initWalletTooltip() {
  if (document.body.dataset.walletTooltipBound === "1") {
    return;
  }
  document.body.dataset.walletTooltipBound = "1";

  let hideTimeoutId = null;
  const show = () => {
    const tooltip = document.querySelector(".wallet_inline_tooltip");
    if (!(tooltip instanceof HTMLElement)) {
      return;
    }
    if (hideTimeoutId) {
      window.clearTimeout(hideTimeoutId);
      hideTimeoutId = null;
    }
    tooltip.classList.add("is-visible");
  };
  const hide = () => {
    const tooltip = document.querySelector(".wallet_inline_tooltip");
    if (!(tooltip instanceof HTMLElement)) {
      return;
    }
    if (hideTimeoutId) {
      window.clearTimeout(hideTimeoutId);
    }
    hideTimeoutId = window.setTimeout(() => {
      tooltip.classList.remove("is-visible");
      hideTimeoutId = null;
    }, 120);
  };

  document.addEventListener("mouseover", (event) => {
    if (event.target instanceof Element && event.target.closest(".js-wallet-coin")) {
      show();
    }
  });
  document.addEventListener("mouseout", (event) => {
    if (event.target instanceof Element && event.target.closest(".js-wallet-coin")) {
      hide();
    }
  });
}
