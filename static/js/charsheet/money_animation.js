export function readWalletBalance() {
  const value = document.querySelector("#sheetWalletPanel .wallet_total__value");
  const parsed = Number.parseInt(String(value?.textContent || "").replace(/[^\d-]/g, ""), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

export function animateMoneyBalance(from, to) {
  return new Promise((resolve) => {
    const headerBalance = document.getElementById("shopHeaderBalance");
    const walletValue = document.querySelector("#sheetWalletPanel .wallet_total__value");
    const updateBalance = (value) => {
      const formatted = Number(value).toLocaleString("de-DE");
      if (headerBalance) headerBalance.textContent = `${formatted} KS`;
      if (walletValue) walletValue.textContent = formatted;
    };
    if (from === to || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      updateBalance(to);
      resolve();
      return;
    }
    const purses = [headerBalance?.closest(".market_wallet"), walletValue?.closest(".wallet_total")].filter(Boolean);
    purses.forEach((purse) => {
      purse.classList.add("is-counting");
      purse.classList.toggle("negative", to < from);
      purse.classList.toggle("positive", to > from);
    });
    updateBalance(from);
    const start = performance.now();
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / 1000);
      const eased = progress * progress * (3 - 2 * progress);
      updateBalance(Math.round(from + (to - from) * eased));
      if (progress < 1) window.requestAnimationFrame(tick);
      else {
        updateBalance(to);
        purses.forEach((purse) => { purse.classList.remove("is-counting"); });
        resolve();
      }
    };
    window.requestAnimationFrame(tick);
  });
}
