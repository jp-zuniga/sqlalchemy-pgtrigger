document$.subscribe(function () {
  const isHidden = localStorage.getItem("zen-mode") === "true";

  document.body.setAttribute("data-zen-mode", isHidden);

  const keybind = "h";
  const toggleZenMode = () => {
    const newState = !(localStorage.getItem("zen-mode") === "true");

    localStorage.setItem("zen-mode", newState);
    document.body.setAttribute("data-zen-mode", newState);
  };

  if (!document.querySelector(".zen-mode-toggle")) {
    const btn = document.createElement("button");

    btn.className = "zen-mode-toggle md-icon";
    btn.innerHTML = `
      <svg class="zen-icon icon-expand" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-minimize2-icon lucide-minimize-2"><path d="m14 10 7-7"/><path d="M20 10h-6V4"/><path d="m3 21 7-7"/><path d="M4 14h6v6"/></svg>
      <svg class="zen-icon icon-collapse" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-maximize2-icon lucide-maximize-2"><path d="M15 3h6v6"/><path d="m21 3-7 7"/><path d="m3 21 7-7"/><path d="M9 21H3v-6"/></svg>
    `;

    document.body.appendChild(btn);

    btn.addEventListener("click", toggleZenMode);
  }

  if (!window.zenKeybindInitialized) {
    window.addEventListener(
      "keydown",
      (e) => {
        const activeElement = document.activeElement;

        if (
          activeElement &&
          (activeElement.tagName === "INPUT" ||
            activeElement.tagName === "TEXTAREA" ||
            activeElement.isContentEditable)
        ) {
          return;
        }

        if (
          e.key &&
          e.key.toLowerCase() === keybind &&
          !e.ctrlKey &&
          !e.altKey &&
          !e.metaKey
        ) {
          e.preventDefault();
          e.stopPropagation();
          toggleZenMode();
        }
      },
      true,
    );

    window.zenKeybindInitialized = true;
  }
});
