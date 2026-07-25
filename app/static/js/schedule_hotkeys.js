(function () {
    "use strict";

    const root = document.getElementById("scheduleApp");
    if (!root || window.__scheduleHotkeysInitialized) return;
    window.__scheduleHotkeysInitialized = true;

    function isVisible(element) {
        return Boolean(element && !element.hidden && element.getClientRects().length);
    }

    function isEditable(element) {
        return Boolean(element && element.closest(
            "input, textarea, select, [contenteditable='true'], .dropdown-menu"
        ));
    }

    function panelIsOpen() {
        const panel = document.getElementById("scheduleBookingWorkspace");
        return Boolean(panel && !panel.classList.contains("d-none") && isVisible(panel));
    }

    function actionButton(action) {
        return root.querySelector(`[data-action="${action}"]:not([disabled])`);
    }

    function showNotice(text) {
        const notice = document.getElementById("hotkeysNotice");
        if (!notice) return;
        notice.textContent = text;
        notice.hidden = false;
        window.clearTimeout(showNotice.timer);
        showNotice.timer = window.setTimeout(() => { notice.hidden = true; }, 2200);
    }

    function prepareCards() {
        root.querySelectorAll(".schedule-entry").forEach((card) => {
            if (!card.hasAttribute("tabindex")) card.tabIndex = 0;
            card.setAttribute("aria-label", card.textContent.replace(/\s+/g, " ").trim());
        });
    }

    function cards() {
        prepareCards();
        return Array.from(root.querySelectorAll(".schedule-entry")).filter(isVisible);
    }

    function focusCard(direction) {
        const items = cards();
        if (!items.length) return false;
        const activeCard = document.activeElement?.closest?.(".schedule-entry");
        let index = items.indexOf(activeCard);
        if (index < 0) index = direction > 0 ? -1 : 0;
        index = (index + direction + items.length) % items.length;
        items[index].focus({ preventScroll: true });
        items[index].scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
        return true;
    }

    function openFocusedCard() {
        const card = document.activeElement?.closest?.(".schedule-entry");
        if (!card) return false;
        if (card.dataset.editable === "true") {
            card.click();
        } else {
            const link = card.querySelector("a.schedule-entry__patient, a[href]");
            if (link) link.click();
        }
        return true;
    }

    function stop(event) {
        event.preventDefault();
        event.stopImmediatePropagation();
    }

    window.addEventListener("keydown", function (event) {
        if (event.isComposing || document.getElementById("hotkeysHelpModal")?.classList.contains("show")) return;
        const code = event.code;

        if (event.ctrlKey && !event.altKey && !event.shiftKey
            && !isEditable(event.target) && (code === "ArrowLeft" || code === "ArrowRight")) {
            stop(event);
            const next = code === "ArrowRight";
            const action = panelIsOpen()
                ? (next ? "next-day" : "previous-day")
                : (next ? "next-week" : "previous-week");
            actionButton(action)?.click();
            return;
        }

        if (event.ctrlKey && !event.altKey && !event.shiftKey && code === "Enter") {
            stop(event);
            const form = document.getElementById("scheduleBookingForm");
            if (panelIsOpen() && form) form.requestSubmit();
            else showNotice("Сначала откройте форму записи пациента.");
            return;
        }

        if (!event.ctrlKey && !event.altKey && !event.metaKey && !event.shiftKey
            && (code === "Slash" || event.key === "/") && !isEditable(event.target)) {
            stop(event);
            const doctor = document.getElementById("scheduleDoctorFilter");
            doctor?.focus();
            return;
        }

        if (event.ctrlKey || event.altKey || event.metaKey || event.shiftKey || isEditable(event.target)) return;

        if (code === "ArrowUp" || code === "ArrowDown") {
            if (focusCard(code === "ArrowDown" ? 1 : -1)) stop(event);
            return;
        }

        if (code === "Enter" && openFocusedCard()) stop(event);
    }, true);

    const style = document.createElement("style");
    style.textContent = ".schedule-entry:focus{outline:3px solid var(--bs-primary);outline-offset:2px;}";
    document.head.appendChild(style);

    prepareCards();
    new MutationObserver(prepareCards).observe(root, { childList: true, subtree: true });
})();
