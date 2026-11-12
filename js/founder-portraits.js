(() => {
  "use strict";

  document.querySelectorAll(".founder-photo--swap").forEach((button) => {
    const name = button.dataset.founderName || "this founder";

    const setAlternate = (showAlternate) => {
      button.setAttribute("aria-pressed", String(showAlternate));
      button.setAttribute("aria-label", `Show ${showAlternate ? "original" : "alternate"} portrait of ${name}`);
    };

    button.addEventListener("click", () => {
      setAlternate(button.getAttribute("aria-pressed") !== "true");
    });

    button.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && button.getAttribute("aria-pressed") === "true") {
        setAlternate(false);
        event.preventDefault();
      }
    });
  });
})();
