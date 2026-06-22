export function onReady(callback) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", callback, { once: true });
    return;
  }
  callback();
}

export function readInt(value, fallback = 0) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

export function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function getCsrfToken() {
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("csrftoken="));
  return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
}

export function loadJsonStorage(key, fallback = null) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (_error) {
    return fallback;
  }
}

export function saveJsonStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (_error) {
    // no-op
  }
}

export function initPersistentDetails(selector, storageKey) {
  const details = Array.from(document.querySelectorAll(selector))
    .filter((entry) => entry instanceof HTMLDetailsElement);
  const stored = loadJsonStorage(storageKey, {});
  const state = stored && typeof stored === "object" && !Array.isArray(stored) ? stored : {};

  const keyFor = (entry) => String(entry.getAttribute("data-collapse-key") || "").trim();
  const restore = (entry) => {
    const key = keyFor(entry);
    entry.open = key ? state[key] === true : false;
  };

  details.forEach((entry) => {
    restore(entry);
    const summary = entry.querySelector(":scope > summary");
    summary?.addEventListener("click", () => {
      window.setTimeout(() => {
        const key = keyFor(entry);
        if (!key) {
          return;
        }
        state[key] = entry.open;
        saveJsonStorage(storageKey, state);
      }, 0);
    });
  });

  return {
    restore,
    restoreAll() {
      details.forEach(restore);
    },
  };
}

export function parseJsonScript(scriptId, fallback) {
  const script = document.getElementById(scriptId);
  if (!script) {
    return fallback;
  }
  try {
    return JSON.parse(script.textContent || JSON.stringify(fallback));
  } catch (_error) {
    return fallback;
  }
}
