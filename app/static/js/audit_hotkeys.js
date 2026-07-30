(function () {
    "use strict";

    const root = document.getElementById("auditPage");
    if (!root || window.__auditHotkeysInitialized) return;
    window.__auditHotkeysInitialized = true;

    const filtersForm = document.getElementById("auditFiltersForm");
    const resetLink = document.getElementById("auditResetFilters");
    const csvForm = document.getElementById("auditCsvForm");

    function isEditable(element) {
        return Boolean(element && element.closest("input, textarea, select, [contenteditable='true']"));
    }

    function visibleRows() {
        return Array.from(root.querySelectorAll("[data-audit-event-row]"))
            .filter((row) => row.getClientRects().length > 0);
    }

    function selectRow(direction) {
        const rows = visibleRows();
        if (!rows.length) return false;

        const active = document.activeElement?.closest?.("[data-audit-event-row]");
        let index = rows.indexOf(active);
        if (index < 0) index = direction > 0 ? -1 : 0;
        index = (index + direction + rows.length) % rows.length;

        rows.forEach((row) => row.classList.remove("table-active"));
        const row = rows[index];
        row.classList.add("table-active");
        row.focus({ preventScroll: true });
        row.scrollIntoView({ behavior: "smooth", block: "nearest" });
        return true;
    }

    function openSelectedRow() {
        const selected = document.activeElement?.closest?.("[data-audit-event-row]")
            || root.querySelector("[data-audit-event-row].table-active")
            || root.querySelector("[data-audit-event-row]");
        const link = selected?.querySelector("[data-audit-open]");
        if (!link) return false;
        link.click();
        return true;
    }

    function pageButton(direction) {
        return root.querySelector(`[data-audit-page="${direction}"]:not([disabled])`);
    }

    function stop(event) {
        event.preventDefault();
        event.stopImmediatePropagation();
    }

    window.addEventListener("keydown", function (event) {
        if (event.isComposing || document.getElementById("hotkeysHelpModal")?.classList.contains("show")) return;

        const code = event.code;
        const inFilters = Boolean(event.target?.closest?.("#auditFiltersForm"));

        if (!event.ctrlKey && !event.altKey && !event.metaKey && !event.shiftKey
            && code === "Enter" && inFilters) {
            stop(event);
            filtersForm?.requestSubmit();
            return;
        }

        if (event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
            if (code === "KeyS") {
                stop(event);
                filtersForm?.requestSubmit();
                return;
            }
            if (code === "KeyR") {
                stop(event);
                resetLink?.click();
                return;
            }
            if (code === "KeyC") {
                stop(event);
                csvForm?.requestSubmit();
                return;
            }
            if (code === "KeyO") {
                if (openSelectedRow()) stop(event);
                return;
            }
        }

        if (event.ctrlKey && !event.altKey && !event.metaKey && !event.shiftKey
            && !isEditable(event.target) && (code === "ArrowLeft" || code === "ArrowRight")) {
            const direction = code === "ArrowRight" ? "next" : "previous";
            const button = pageButton(direction);
            if (button) {
                stop(event);
                button.click();
            }
            return;
        }

        if (!event.ctrlKey && !event.altKey && !event.metaKey && !event.shiftKey
            && !isEditable(event.target) && (code === "ArrowUp" || code === "ArrowDown")) {
            if (selectRow(code === "ArrowDown" ? 1 : -1)) stop(event);
        }
    }, true);
})();
