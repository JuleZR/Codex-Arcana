(() => {
  const appleTouchDevice = /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const safari = navigator.vendor === "Apple Computer, Inc."
    && /Version\/.*Safari\//.test(navigator.userAgent);
  const standalone = navigator.standalone === true
    || window.matchMedia("(display-mode: standalone)").matches;
  if (!appleTouchDevice || !safari || standalone) return;

  const viewport = document.querySelector('meta[name="viewport"]');
  if (!viewport) return;
  // iOS Safari honors this for focus zoom, while allowing manual pinch zoom.
  // Other browsers and embedded web views must retain their scale limits.
  const directives = viewport.content.split(",")
    .map((directive) => directive.trim())
    .filter((directive) => !/^(maximum-scale|user-scalable)\s*=/i.test(directive));
  viewport.content = [...directives, "maximum-scale=1", "user-scalable=yes"].join(", ");
})();
