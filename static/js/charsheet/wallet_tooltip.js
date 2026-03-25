export function initWalletTooltip() {
  const walletTooltip = document.querySelector(".wallet_inline_tooltip");
  const walletCoins = document.querySelectorAll(".js-wallet-coin");
  if (!walletTooltip || !walletCoins.length) {
    return;
  }

  let hideTimeoutId = null;
  const show = () => {
    if (hideTimeoutId) {
      window.clearTimeout(hideTimeoutId);
      hideTimeoutId = null;
    }
    walletTooltip.classList.add("is-visible");
  };
  const hide = () => {
    if (hideTimeoutId) {
      window.clearTimeout(hideTimeoutId);
    }
    hideTimeoutId = window.setTimeout(() => {
      walletTooltip.classList.remove("is-visible");
      hideTimeoutId = null;
    }, 120);
  };

  walletCoins.forEach((coin) => {
    coin.addEventListener("mouseenter", show);
    coin.addEventListener("mouseleave", hide);
  });
}
