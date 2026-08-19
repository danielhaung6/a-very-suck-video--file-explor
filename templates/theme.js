(function () {
    const storageKey = "video-manager-theme";
    let theme = "light";

    try {
        const savedTheme = localStorage.getItem(storageKey);
        if (savedTheme === "light" || savedTheme === "dark") {
            theme = savedTheme;
        }
    } catch (error) {
        // The theme still works for this page when storage is unavailable.
    }

    document.documentElement.dataset.theme = theme;

    document.addEventListener("DOMContentLoaded", function () {
        const button = document.querySelector("[data-theme-toggle]");
        const label = button && button.querySelector("[data-theme-label]");
        if (!button || !label) return;

        function updateButton() {
            const dark = document.documentElement.dataset.theme === "dark";
            label.textContent = dark ? "亮色模式" : "深色模式";
            button.setAttribute("aria-pressed", String(dark));
        }

        button.addEventListener("click", function () {
            const nextTheme = document.documentElement.dataset.theme === "dark"
                ? "light"
                : "dark";
            document.documentElement.dataset.theme = nextTheme;
            try {
                localStorage.setItem(storageKey, nextTheme);
            } catch (error) {
                // Keep the selected theme for the current page.
            }
            updateButton();
        });

        updateButton();
    });
})();
