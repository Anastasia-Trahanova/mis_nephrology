(function () {
    "use strict";

    const tableAdders = {
        addCbcColumnBtn: "cbcHeaderRow",
        addBiochemistryColumnBtn: "biochemistryHeaderRow",
        addUrinalysisColumnBtn: "urinalysisHeaderRow",
        addUltrasoundColumnBtn: "ultrasoundHeaderRow",
        addAlbuminuriaColumnBtn: "albuminuriaHeaderRow"
    };

    function lastOf(items) {
        return items.length ? items[items.length - 1] : null;
    }

    function focusAddedAnalysis(button) {
        window.setTimeout(() => {
            let dateInput = null;
            const headerId = tableAdders[button.id];
            if (headerId) {
                const header = document.getElementById(headerId);
                dateInput = header ? lastOf(header.querySelectorAll('input[type="date"]')) : null;
            } else if (button.dataset.addLab) {
                const container = document.getElementById(button.dataset.addLab);
                const cards = container ? container.querySelectorAll(".lab-analysis-card") : [];
                dateInput = cards.length ? lastOf(cards).querySelector('input[type="date"]') : null;
            }
            if (!dateInput) return;

            const scroller = dateInput.closest(".table-responsive");
            if (scroller) {
                scroller.scrollTo({ left: scroller.scrollWidth, behavior: "smooth" });
            }
            dateInput.scrollIntoView({ behavior: "smooth", block: "center", inline: "end" });
            window.setTimeout(() => dateInput.focus({ preventScroll: true }), 300);
        }, 0);
    }

    document.addEventListener("click", (event) => {
        const button = event.target.closest(
            "#addCbcColumnBtn, #addBiochemistryColumnBtn, #addUrinalysisColumnBtn, " +
            "#addUltrasoundColumnBtn, #addAlbuminuriaColumnBtn, [data-add-lab]"
        );
        if (button) focusAddedAnalysis(button);
    });

    function numberValue(value) {
        const normalized = String(value ?? "").trim().replace(",", ".").replace(/\s+/g, "");
        if (!normalized) return null;
        const result = Number(normalized);
        return Number.isFinite(result) ? result : null;
    }

    function categorySource(acrValue, dailyValue) {
        const acr = numberValue(acrValue);
        if (acr !== null && acr >= 0) {
            return `Категория рассчитана по ACR: ${acrValue} мг/ммоль.`;
        }
        const daily = numberValue(dailyValue);
        if (daily !== null && daily >= 0) {
            return `Категория рассчитана по суточной экскреции альбумина: ${dailyValue} мг/сут.`;
        }
        return "";
    }

    function updatePrimarySource(block) {
        const source = block.querySelector(".albuminuria-category-source");
        if (!source) return;
        source.textContent = categorySource(
            block.querySelector(".albuminuria-acr")?.value,
            block.querySelector('[name="daily_albumin_excretion"]')?.value
        );
    }

    function updateColumnSource(columnId) {
        if (!columnId) return;
        const category = document.querySelector(
            `[data-albuminuria-column="${columnId}"][data-field="category"]`
        );
        if (!category) return;
        let source = category.parentElement.querySelector(".albuminuria-category-source");
        if (!source) {
            source = document.createElement("div");
            source.className = "small text-muted mt-1 albuminuria-category-source";
            category.insertAdjacentElement("afterend", source);
        }
        source.textContent = categorySource(
            document.querySelector(`[data-albuminuria-column="${columnId}"][data-field="acr"]`)?.value,
            document.querySelector(`[data-albuminuria-column="${columnId}"][data-field="daily_excretion"]`)?.value
        );
    }

    function updateAlbuminuriaSources(target) {
        const block = target?.closest?.(".albuminuria-block");
        if (block) updatePrimarySource(block);
        const columnId = target?.dataset?.albuminuriaColumn;
        if (columnId) updateColumnSource(columnId);
    }

    function refreshAllAlbuminuriaSources() {
        document.querySelectorAll(".albuminuria-block").forEach(updatePrimarySource);
        const ids = new Set();
        document.querySelectorAll("[data-albuminuria-column]").forEach((field) => {
            if (field.dataset.albuminuriaColumn) ids.add(field.dataset.albuminuriaColumn);
        });
        ids.forEach(updateColumnSource);
    }

    document.addEventListener("input", (event) => {
        if (event.target.matches(
            '.albuminuria-albumin, .albuminuria-creatinine, .albuminuria-acr, ' +
            '[name="daily_albumin_excretion"], [data-albuminuria-column]'
        )) {
            window.setTimeout(() => updateAlbuminuriaSources(event.target), 0);
        }
    });
    document.addEventListener("change", (event) => {
        if (event.target.matches(
            '.albuminuria-albumin-unit, .albuminuria-creatinine-unit, [data-albuminuria-column]'
        )) {
            window.setTimeout(() => updateAlbuminuriaSources(event.target), 0);
        }
    });

    function isCkdDiagnosis(value) {
        const text = String(value || "").trim();
        return /\bN18(?:\.\d+)?\b/i.test(text) || /хроническ\w*\s+болезн\w*\s+почек/i.test(text);
    }

    let reconcilingCkd = false;
    function reconcilePreviousCkd() {
        if (reconcilingCkd) return;
        const container = document.getElementById("icd10ComplicationsContainer");
        if (!container) return;
        reconcilingCkd = true;
        try {
            const metadata = document.getElementById("appointmentPreviousCkdData");
            let previousDiagnosis = metadata?.dataset.diagnosis?.trim() || "";
            const previousDate = metadata?.dataset.date?.trim() || "";

            container.querySelectorAll(".icd10-diagnosis-row").forEach((row) => {
                const input = row.querySelector('[name="icd10_complication_diagnosis"]');
                if (!input || input.dataset.ckdAutofilledComplication === "true") return;
                if (!isCkdDiagnosis(input.value)) return;
                if (!previousDiagnosis) previousDiagnosis = input.value.trim();
                row.remove();
            });

            const currentInput = container.querySelector(
                '[name="icd10_complication_diagnosis"][data-ckd-autofilled-complication="true"]'
            );
            const currentRow = currentInput?.closest(".icd10-diagnosis-row");
            if (!currentRow || !previousDiagnosis) return;

            let note = currentRow.querySelector('[data-previous-ckd-note="true"]');
            if (!note) {
                note = document.createElement("div");
                note.className = "form-text text-muted mt-2";
                note.dataset.previousCkdNote = "true";
                const wrapper = currentInput.closest(".icd10-search-wrapper");
                (wrapper || currentInput).insertAdjacentElement("afterend", note);
            }
            note.textContent = `В прошлом приёме${previousDate ? ` (${previousDate})` : ""} было: ${previousDiagnosis}`;
        } finally {
            reconcilingCkd = false;
        }
    }

    function diagnosisKey(value) {
        const text = String(value || "").trim();
        if (!text) return "";
        const code = text.toUpperCase().match(/\b[A-ZА-Я]\d{2}(?:\.\d+)?\b/);
        return code ? `code:${code[0]}` : `text:${text.toLowerCase().replace(/[\s—–-]+/g, " ")}`;
    }

    function clearDuplicateState(input) {
        input.setCustomValidity("");
        input.classList.remove("is-invalid");
        input.closest(".icd10-search-wrapper")?.querySelector(".duplicate-diagnosis-feedback")?.remove();
    }

    function markDuplicate(input) {
        input.setCustomValidity("Этот диагноз уже указан в текущем приёме");
        input.classList.add("is-invalid");
        const wrapper = input.closest(".icd10-search-wrapper") || input.parentElement;
        if (!wrapper.querySelector(".duplicate-diagnosis-feedback")) {
            const feedback = document.createElement("div");
            feedback.className = "invalid-feedback d-block duplicate-diagnosis-feedback";
            feedback.textContent = "Этот диагноз уже указан в текущем приёме.";
            wrapper.appendChild(feedback);
        }
    }

    function validateDiagnosisDuplicates() {
        const inputs = Array.from(document.querySelectorAll(
            '[name="icd10_main_diagnosis"], ' +
            '[name="icd10_complication_diagnosis"], ' +
            '[name="icd10_comorbidity_diagnosis"]'
        ));
        inputs.forEach(clearDuplicateState);
        const firstByKey = new Map();
        let firstDuplicate = null;
        inputs.forEach((input) => {
            const key = diagnosisKey(input.value);
            if (!key) return;
            if (firstByKey.has(key)) {
                const first = firstByKey.get(key);
                markDuplicate(first);
                markDuplicate(input);
                firstDuplicate ||= input;
            } else {
                firstByKey.set(key, input);
            }
        });
        return firstDuplicate;
    }

    document.addEventListener("input", (event) => {
        if (event.target.matches(
            '[name="icd10_main_diagnosis"], [name="icd10_complication_diagnosis"], [name="icd10_comorbidity_diagnosis"]'
        )) {
            validateDiagnosisDuplicates();
        }
    });

    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (!form.matches('form[action*="appointments"]')) return;
        reconcilePreviousCkd();
        const duplicate = validateDiagnosisDuplicates();
        if (!duplicate) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        duplicate.scrollIntoView({ behavior: "smooth", block: "center" });
        window.setTimeout(() => {
            duplicate.focus();
            duplicate.reportValidity();
        }, 250);
    }, true);

    document.addEventListener("DOMContentLoaded", () => {
        refreshAllAlbuminuriaSources();
        window.setTimeout(() => {
            reconcilePreviousCkd();
            validateDiagnosisDuplicates();
            refreshAllAlbuminuriaSources();
        }, 80);

        const albuminuriaRoot = document.getElementById("albuminuriaContainer") ||
            document.getElementById("albuminuriaHeaderRow")?.closest("table");
        if (albuminuriaRoot) {
            new MutationObserver(() => window.setTimeout(refreshAllAlbuminuriaSources, 0))
                .observe(albuminuriaRoot, { childList: true, subtree: true });
        }

        const complications = document.getElementById("icd10ComplicationsContainer");
        if (complications) {
            new MutationObserver(() => window.setTimeout(reconcilePreviousCkd, 0))
                .observe(complications, { childList: true, subtree: true });
        }
    });
}());
