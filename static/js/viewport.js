(() => {
  const root = document.documentElement;
  const mobile = window.matchMedia("(max-width: 900px), (pointer: coarse)");
  const visualViewport = window.visualViewport;
  const updateWindowBounds = () => {
    if (!mobile.matches || (visualViewport?.scale || 1) > 1.01) return;
    const style = window.getComputedStyle(root);
    const inset = (side) => Number.parseFloat(style[`scrollPadding${side}`]) || 0;
    const left = (visualViewport?.offsetLeft || 0) + inset("Left") + 8;
    const top = (visualViewport?.offsetTop || 0) + inset("Top") + 8;
    const width = Math.max(0, (visualViewport?.width || window.innerWidth)
      - inset("Left") - inset("Right") - 16);
    const height = Math.max(0, (visualViewport?.height || window.innerHeight)
      - inset("Top") - inset("Bottom") - 16);
    for (const [key, value] of Object.entries({ left, top, width, height })) {
      root.style.setProperty(`--app-window-${key}`, `${value}px`);
    }
  };
  updateWindowBounds();
  window.addEventListener("resize", updateWindowBounds);
  window.addEventListener("pageshow", updateWindowBounds);
  visualViewport?.addEventListener("resize", updateWindowBounds);
  visualViewport?.addEventListener("scroll", updateWindowBounds);

  const appleTouchDevice = /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  if (!appleTouchDevice || !/AppleWebKit\//.test(navigator.userAgent)) return;

  const viewport = document.querySelector('meta[name="viewport"]');
  if (!viewport) return;
  const directives = viewport.content.split(",")
    .map((directive) => directive.trim())
    .filter((directive) => !/^(maximum-scale|user-scalable)\s*=/i.test(directive));
  const manualZoom = [...directives, "user-scalable=yes"].join(", ");
  let pinching = false;
  const preventFocusZoom = () => {
    if (pinching) return;
    const scale = Math.max(1, visualViewport?.scale || 1);
    viewport.content = `${manualZoom}, maximum-scale=${scale}`;
  };
  const allowManualZoom = () => { viewport.content = manualZoom; };
  const textControl = (target) => {
    const control = target?.closest?.("input, textarea, select, [contenteditable]")
      || target?.closest?.("label")?.control;
    if (!control || control.disabled || control.readOnly) return null;
    if (control.tagName === "INPUT"
      && /^(button|submit|reset|checkbox|radio|range|color|file|hidden|image)$/.test(control.type)) return null;
    if (control.hasAttribute("contenteditable") && !control.isContentEditable) return null;
    return control;
  };
  const beforeFocus = (event) => {
    if (textControl(event.target)) preventFocusZoom();
  };
  document.addEventListener("pointerdown", beforeFocus, true);
  document.addEventListener("focusin", beforeFocus, true);
  document.addEventListener("touchstart", (event) => {
    if (event.touches.length > 1) {
      pinching = true;
      allowManualZoom();
    } else {
      beforeFocus(event);
    }
  }, { capture: true, passive: true });
  const endPinch = (event) => { pinching = event.touches.length > 1; };
  document.addEventListener("touchend", endPinch, { capture: true, passive: true });
  document.addEventListener("touchcancel", endPinch, { capture: true, passive: true });
  document.addEventListener("gesturestart", allowManualZoom, { capture: true, passive: true });
  window.addEventListener("pageshow", preventFocusZoom);
  preventFocusZoom();
})();
