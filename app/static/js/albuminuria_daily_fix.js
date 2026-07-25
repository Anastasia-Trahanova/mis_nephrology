(function () {
    "use strict";
    if (window.__albuminuriaDailyFixInitialized) return;
    window.__albuminuriaDailyFixInitialized = true;

    function number(value) {
        const text = String(value ?? "").trim().replace(/\s+/g, "").replace(",", ".");
        if (!text || !/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) return null;
        const result = Number(text);
        return Number.isFinite(result) ? result : null;
    }

    function albuminMgL(value, unit) {
        const result = number(value);
        if (result === null || result < 0) return null;
        if (unit === "mg_l") return result;
        if (unit === "g_l") return result * 1000;
        return null;
    }

    function creatinineMmolL(value, unit) {
        const result = number(value);
        if (result === null || result <= 0) return null;
        if (unit === "mmol_l") return result;
        if (unit === "umol_l") return result / 1000;
        return null;
    }

    function categoryFromAcr(value) {
        if (value === null) return "";
        if (value < 3) return "A1";
        if (value <= 30) return "A2";
        return "A3";
    }

    function categoryFromDaily(value) {
        const result = number(value);
        if (result === null || result < 0) return "";
        if (result < 30) return "A1";
        if (result <= 300) return "A2";
        return "A3";
    }

    let refreshQueued = false;
    function refreshKdigo() {
        if (refreshQueued) return;
        refreshQueued = true;
        window.setTimeout(() => {
            refreshQueued = false;
            document.body.dispatchEvent(new Event("input", { bubbles: true }));
        }, 0);
    }

    function assign(field, value) {
        if (!field || field.value === value) return false;
        field.value = value;
        return true;
    }

    function updateCard(block) {
        const albumin = block.querySelector(".albuminuria-albumin, [name='urine_albumin']");
        const albuminUnit = block.querySelector(".albuminuria-albumin-unit, [name='urine_albumin_unit']");
        const creatinine = block.querySelector(".albuminuria-creatinine, [name='urine_creatinine']");
        const creatinineUnit = block.querySelector(".albuminuria-creatinine-unit, [name='urine_creatinine_unit']");
        const daily = block.querySelector(".albuminuria-daily-excretion, [name='daily_albumin_excretion']");
        const acrField = block.querySelector(".albuminuria-acr, [data-field='acr']");
        const categoryField = block.querySelector(".albuminuria-category, [data-field='category']");
        if (!acrField || !categoryField) return;

        const alb = albuminMgL(albumin?.value, albuminUnit?.value || "mg_l");
        const cr = creatinineMmolL(creatinine?.value, creatinineUnit?.value || "mmol_l");
        const acr = alb !== null && cr !== null ? alb / cr : null;
        const category = acr !== null ? categoryFromAcr(acr) : categoryFromDaily(daily?.value);
        const changed = assign(acrField, acr === null ? "" : (Math.round(acr * 100) / 100).toFixed(2))
            | assign(categoryField, category);
        if (changed) refreshKdigo();
    }

    function field(columnId, kind) {
        return document.querySelector(`[data-albuminuria-column="${CSS.escape(columnId)}"][data-field="${kind}"]`);
    }

    function updateColumn(columnId) {
        const albumin = field(columnId, "albumin");
        const albuminUnit = field(columnId, "albumin_unit");
        const creatinine = field(columnId, "creatinine");
        const creatinineUnit = field(columnId, "creatinine_unit");
        const daily = field(columnId, "daily_excretion");
        const acrField = field(columnId, "acr");
        const categoryField = field(columnId, "category");
        if (!acrField || !categoryField) return;

        const alb = albuminMgL(albumin?.value, albuminUnit?.value || "mg_l");
        const cr = creatinineMmolL(creatinine?.value, creatinineUnit?.value || "mmol_l");
        const acr = alb !== null && cr !== null ? alb / cr : null;
        const category = acr !== null ? categoryFromAcr(acr) : categoryFromDaily(daily?.value);
        const changed = assign(acrField, acr === null ? "" : (Math.round(acr * 100) / 100).toFixed(2))
            | assign(categoryField, category);
        if (changed) refreshKdigo();
    }

    function ensureDailyCells() {
        const row = document.getElementById("albuminuria_daily_excretion_row");
        if (!row) return;
        document.querySelectorAll("[data-albuminuria-column][data-field='category']").forEach((categoryField) => {
            const columnId = categoryField.dataset.albuminuriaColumn;
            if (!columnId || field(columnId, "daily_excretion")) return;
            const cell = document.createElement("td");
            cell.className = categoryField.closest("td")?.className || "table-success";
            const input = document.createElement("input");
            input.type = "text";
            input.name = "daily_albumin_excretion";
            input.className = "form-control form-control-sm albuminuria-daily-excretion";
            input.dataset.albuminuriaColumn = columnId;
            input.dataset.field = "daily_excretion";
            cell.appendChild(input);
            row.appendChild(cell);
        });
    }

    function updateTarget(target) {
        const block = target.closest?.(".albuminuria-block");
        if (block) updateCard(block);
        const columnField = target.closest?.("[data-albuminuria-column]");
        if (columnField?.dataset.albuminuriaColumn) updateColumn(columnField.dataset.albuminuriaColumn);
    }

    function syncAll() {
        ensureDailyCells();
        document.querySelectorAll(".albuminuria-block").forEach(updateCard);
        const ids = new Set();
        document.querySelectorAll("[data-albuminuria-column]").forEach((item) => {
            if (item.dataset.albuminuriaColumn) ids.add(item.dataset.albuminuriaColumn);
        });
        ids.forEach(updateColumn);
    }

    document.addEventListener("DOMContentLoaded", () => {
        /* Эти обработчики регистрируются после встроенной логики формы, чтобы
           итоговый расчёт по суточной экскреции не был очищен старым ACR-кодом. */
        document.addEventListener("input", (event) => updateTarget(event.target));
        document.addEventListener("change", (event) => updateTarget(event.target));
        syncAll();
        const roots = [
            document.getElementById("albuminuriaContainer"),
            document.getElementById("albuminuriaHeaderRow")?.closest("table"),
        ].filter(Boolean);
        roots.forEach((root) => new MutationObserver(syncAll).observe(root, { childList: true, subtree: true }));
    });
})();
