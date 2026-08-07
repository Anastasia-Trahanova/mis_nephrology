/*
 * Live kidney preview for appointment forms.
 *
 * Medical calculations are performed by POST /api/kidney-preview. This module
 * only collects raw form values, renders the server response and stores the
 * identifier of the KDIGO combination explicitly selected by the doctor.
 */
(function () {
    "use strict";

    if (window.__kidneyServerPreviewV2Initialized) return;
    window.__kidneyServerPreviewV2Initialized = true;

    const root = document.getElementById("kdigoRiskPreview");
    if (!root) return;

    const optionsContainer = document.getElementById("kdigoCurrentVisitOptions");
    const selectedConclusion = document.getElementById("kdigoSelectedConclusionText");
    const selectedPairInput = document.getElementById("kdigoSelectedPair") || createSelectedPairInput();
    const selectedPairKeyInput = document.getElementById("kdigoSelectedPairKey") || createSelectedPairKeyInput();
    const previousGfr = readJson("kdigoPreviousGfrData");
    const previousAlbuminuria = readJson("kdigoPreviousAlbuminuriaData");

    let debounceTimer = null;
    let requestSerial = 0;
    let activeController = null;
    let lastResponse = null;
    let previewDirty = false;
    let resubmittingAfterPreview = false;
    let selectedPair = "";
    let selectedPairKey = "";
    let selectionWasExplicit = false;
    let lastSourceCounts = { gfr: 0, albuminuria: 0 };

    function createSelectedPairInput() {
        const input = document.createElement("input");
        input.type = "hidden";
        input.id = "kdigoSelectedPair";
        input.name = "kdigo_selected_pair";
        root.appendChild(input);
        return input;
    }

    function createSelectedPairKeyInput() {
        const input = document.createElement("input");
        input.type = "hidden";
        input.id = "kdigoSelectedPairKey";
        input.name = "kdigo_selected_pair_key";
        root.appendChild(input);
        return input;
    }

    function readJson(id) {
        const node = document.getElementById(id);
        if (!node) return [];
        try {
            const parsed = JSON.parse(node.textContent || "[]");
            return Array.isArray(parsed) ? parsed : [];
        } catch (_) {
            return [];
        }
    }

    function value(selector) {
        const node = document.querySelector(selector);
        return node ? node.value : "";
    }

    function currentGender() {
        if (root.dataset.patientGender !== undefined && root.dataset.patientGender !== "") {
            return root.dataset.patientGender;
        }
        const checked = document.querySelector('[name="gender"]:checked');
        return checked ? checked.value : value('[name="gender"]');
    }

    function values(name) {
        return Array.from(document.querySelectorAll(`[name="${name}"]`)).map((node) => node.value || "");
    }

    function at(items, index, fallback = "") {
        return index < items.length ? items[index] : fallback;
    }

    function collectBiochemistry() {
        const dates = values("biochemistry_investigation_date");
        const creatinine = values("creatinine");
        return creatinine.map((item, index) => ({
            key: `biochemistry-${index}`,
            investigation_date: at(dates, index, value('[name="appointment_date"]')),
            creatinine: item,
        }));
    }

    function collectAlbuminuria() {
        const dates = values("albuminuria_investigation_date");
        const albumin = values("urine_albumin");
        const albuminUnits = values("urine_albumin_unit");
        const creatinine = values("urine_creatinine");
        const creatinineUnits = values("urine_creatinine_unit");
        const daily = values("daily_albumin_excretion");
        const count = Math.max(
            dates.length,
            albumin.length,
            albuminUnits.length,
            creatinine.length,
            creatinineUnits.length,
            daily.length
        );
        const result = [];
        for (let index = 0; index < count; index += 1) {
            result.push({
                key: `albuminuria-${index}`,
                investigation_date: at(dates, index, value('[name="appointment_date"]')),
                urine_albumin: at(albumin, index),
                urine_albumin_unit: at(albuminUnits, index, "mg_l") || "mg_l",
                urine_creatinine: at(creatinine, index),
                urine_creatinine_unit: at(creatinineUnits, index, "mmol_l") || "mmol_l",
                daily_albumin_excretion: at(daily, index),
            });
        }
        return result;
    }

    function buildPayload() {
        return {
            birth_date: root.dataset.patientBirthDate || value('[name="birth_date"]'),
            gender: currentGender(),
            weight_kg: value('[name="weight"]'),
            appointment_date: value('[name="appointment_date"]'),
            biochemistry: collectBiochemistry(),
            albuminuria: collectAlbuminuria(),
            previous_gfr: previousGfr,
            previous_albuminuria: previousAlbuminuria,
        };
    }

    function hasKidneyInput(payload) {
        const hasCreatinine = payload.biochemistry.some((row) => String(row.creatinine || "").trim() !== "");
        const hasAlbuminuria = payload.albuminuria.some((row) =>
            [row.urine_albumin, row.urine_creatinine, row.daily_albumin_excretion]
                .some((item) => String(item || "").trim() !== "")
        );
        return hasCreatinine || hasAlbuminuria;
    }

    function dateLabel(isoDate) {
        if (!isoDate) return "Новый расчёт";
        const parts = String(isoDate).slice(0, 10).split("-");
        return parts.length === 3 ? `${parts[2]}.${parts[1]}.${parts[0]}` : isoDate;
    }

    function clearMetricsPreview() {
        document.querySelectorAll(".kidney-preview-metrics, .new-metrics-column").forEach((node) => node.remove());
    }

    function appendMetricCell(row, text) {
        const cell = document.createElement("td");
        cell.className = "text-center table-success kidney-preview-metrics";
        cell.textContent = text === null || text === undefined || text === "" ? "—" : String(text);
        row.appendChild(cell);
    }

    function sortMetricsTable() {
        const rows = ["metricsHeaderRow", "egfrRow", "cockcroftRow", "ckdStageRow"]
            .map((id) => document.getElementById(id));
        if (rows.some((row) => !row)) return;

        const columns = Array.from(rows[0].children).slice(1).map((header, index) => ({
            date: header.dataset.date || "9999-12-31",
            index,
            cells: rows.map((row) => Array.from(row.children).slice(1)[index]),
        }));
        columns.sort((a, b) => a.date === b.date ? a.index - b.index : a.date.localeCompare(b.date));
        columns.forEach((column) => column.cells.forEach((cell, rowIndex) => rows[rowIndex].appendChild(cell)));
    }

    function renderMetrics(rows) {
        document.querySelectorAll("#biochemistryContainer .lab-analysis-card").forEach((card) => {
            [".biochemistry-egfr", ".biochemistry-cockcroft", ".biochemistry-stage"].forEach((selector) => {
                const field = card.querySelector(selector);
                if (field) field.value = "";
            });
        });

        const header = document.getElementById("metricsHeaderRow");
        const egfrRow = document.getElementById("egfrRow");
        const cockcroftRow = document.getElementById("cockcroftRow");
        const stageRow = document.getElementById("ckdStageRow");
        if (header && egfrRow && cockcroftRow && stageRow) {
            clearMetricsPreview();
            rows.forEach((item) => {
                const th = document.createElement("th");
                th.className = "text-center table-success kidney-preview-metrics";
                th.dataset.date = item.investigation_date || "";
                th.textContent = dateLabel(item.investigation_date);
                header.appendChild(th);
                appendMetricCell(egfrRow, item.egfr_ckdepi);
                appendMetricCell(cockcroftRow, item.crcl_cockcroft_gault);
                appendMetricCell(stageRow, item.ckd_stage);
            });
            sortMetricsTable();
        }

        const cards = document.querySelectorAll("#biochemistryContainer .lab-analysis-card");
        rows.forEach((item, index) => {
            const sourceIndex = sourceIndexFromKey(item.key, "biochemistry", index);
            const card = cards[sourceIndex];
            if (!card) return;
            const egfr = card.querySelector(".biochemistry-egfr");
            const cockcroft = card.querySelector(".biochemistry-cockcroft");
            const stage = card.querySelector(".biochemistry-stage");
            if (egfr) egfr.value = item.egfr_ckdepi ?? "";
            if (cockcroft) cockcroft.value = item.crcl_cockcroft_gault ?? "";
            if (stage) stage.value = item.ckd_stage ?? "";
        });
    }

    function sourceIndexFromKey(key, prefix, fallback) {
        const match = String(key || "").match(new RegExp(`^${prefix}-(\\d+)$`));
        return match ? Number(match[1]) : fallback;
    }

    function albuminuriaOutputFields() {
        const acr = Array.from(document.querySelectorAll(
            '[data-field="acr"], .albuminuria-acr, input[name="albumin_creatinine_ratio"]'
        ));
        const category = Array.from(document.querySelectorAll(
            '[data-field="category"], .albuminuria-category, input[name="albuminuria_category"]'
        ));
        return { acr, category };
    }

    function renderAlbuminuria(rows) {
        const outputs = albuminuriaOutputFields();
        outputs.acr.forEach((field) => { field.value = ""; });
        outputs.category.forEach((field) => { field.value = ""; });
        rows.forEach((item, index) => {
            const sourceIndex = sourceIndexFromKey(item.key, "albuminuria", index);
            if (outputs.acr[sourceIndex]) outputs.acr[sourceIndex].value = item.albumin_creatinine_ratio ?? "";
            if (outputs.category[sourceIndex]) outputs.category[sourceIndex].value = item.albuminuria_category ?? "";
        });
    }

    function calculatedAssessments(assessments) {
        return assessments.filter((item) => item.status === "calculated");
    }

    function writeSelection(assessment) {
        selectedPair = assessment?.selection_key || "";
        selectedPairKey = assessment?.pair_key || "";
        selectedPairInput.value = selectedPair;
        selectedPairKeyInput.value = selectedPairKey;
        if (selectedConclusion) selectedConclusion.value = assessment?.display_text || "";
    }

    function renderKdigo(assessments) {
        if (!optionsContainer) return;
        optionsContainer.replaceChildren();

        const calculated = calculatedAssessments(assessments);
        const sourceCounts = {
            gfr: Array.isArray(lastResponse?.metrics) ? lastResponse.metrics.length : 0,
            albuminuria: Array.isArray(lastResponse?.albuminuria)
                ? lastResponse.albuminuria.filter((item) => item.albuminuria_category).length
                : 0,
        };
        const sourceCountChanged =
            sourceCounts.gfr !== lastSourceCounts.gfr ||
            sourceCounts.albuminuria !== lastSourceCounts.albuminuria;
        lastSourceCounts = sourceCounts;

        if (calculated.length === 0) {
            selectionWasExplicit = false;
            writeSelection(null);
        } else if (calculated.length === 1) {
            selectionWasExplicit = false;
            writeSelection(calculated[0]);
        } else {
            const selectedStillExists = calculated.some((item) => item.selection_key === selectedPair);
            if (sourceCountChanged && !selectionWasExplicit) {
                writeSelection(null);
            } else if (!selectedStillExists) {
                selectionWasExplicit = false;
                writeSelection(null);
            }
        }

        assessments.forEach((assessment) => {
            const row = document.createElement("label");
            row.className = assessment.status === "calculated"
                ? `kdigo-current-option kdigo-risk-${assessment.prognosis_level || "unknown"}`
                : "kdigo-current-option kdigo-current-option-neutral";

            const radio = document.createElement("input");
            radio.type = "radio";
            radio.name = "kdigo_selected_current_option";
            radio.className = "form-check-input mt-0";
            radio.disabled = assessment.status !== "calculated";
            radio.checked = assessment.status === "calculated" && assessment.selection_key === selectedPair;
            radio.value = assessment.selection_key || "";
            radio.addEventListener("change", function () {
                if (!radio.checked || assessment.status !== "calculated") return;
                selectionWasExplicit = true;
                writeSelection(assessment);
            });

            const text = document.createElement("span");
            text.className = "kdigo-current-option-text";
            text.textContent = assessment.display_text || "";

            row.appendChild(radio);
            row.appendChild(text);
            optionsContainer.appendChild(row);
        });

        if (calculated.length > 1 && !selectedPair) {
            const hint = document.createElement("div");
            hint.className = "text-danger small mt-2";
            hint.dataset.kdigoSelectionHint = "1";
            hint.textContent = "Выберите один вариант прогноза, который будет сохранён с приёмом.";
            optionsContainer.appendChild(hint);
        }
    }

    function render(data) {
        lastResponse = data || {};
        renderMetrics(Array.isArray(lastResponse.metrics) ? lastResponse.metrics : []);
        renderAlbuminuria(Array.isArray(lastResponse.albuminuria) ? lastResponse.albuminuria : []);
        renderKdigo(Array.isArray(lastResponse.kdigo_assessments) ? lastResponse.kdigo_assessments : []);
    }

    function clearCurrentPreview() {
        lastResponse = { metrics: [], albuminuria: [], kdigo_assessments: [] };
        lastSourceCounts = { gfr: 0, albuminuria: 0 };
        selectionWasExplicit = false;
        render(lastResponse);
    }

    async function refresh() {
        window.clearTimeout(debounceTimer);
        debounceTimer = null;
        const payload = buildPayload();
        if (!hasKidneyInput(payload)) {
            if (activeController) activeController.abort();
            clearCurrentPreview();
            previewDirty = false;
            return true;
        }

        const serial = ++requestSerial;
        if (activeController) activeController.abort();
        activeController = new AbortController();
        try {
            const response = await fetch("/api/kidney-preview", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
                signal: activeController.signal,
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (serial !== requestSerial) return false;
            render(data);
            previewDirty = false;
            return true;
        } catch (error) {
            if (error?.name === "AbortError") return false;
            console.error("Kidney preview failed", error);
            clearCurrentPreview();
            if (optionsContainer) {
                optionsContainer.textContent = "Не удалось обновить расчётные показатели. Проверьте соединение и повторите ввод.";
            }
            return false;
        } finally {
            if (serial === requestSerial) activeController = null;
        }
    }

    function scheduleRefresh(delay = 120) {
        previewDirty = true;
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(refresh, delay);
    }

    const watchedNames = new Set([
        "birth_date", "gender", "weight", "appointment_date",
        "biochemistry_investigation_date", "creatinine",
        "albuminuria_investigation_date", "urine_albumin", "urine_albumin_unit",
        "urine_creatinine", "urine_creatinine_unit", "daily_albumin_excretion",
    ]);

    function watched(target) {
        return (target instanceof HTMLInputElement || target instanceof HTMLSelectElement)
            && watchedNames.has(target.name);
    }

    function clearLegacyAlbuminuriaOutput(target) {
        const columnId = target?.dataset?.albuminuriaColumn;
        if (!columnId) return;
        document.querySelectorAll(
            `[data-albuminuria-column="${columnId}"][data-field="acr"], ` +
            `[data-albuminuria-column="${columnId}"][data-field="category"]`
        ).forEach((field) => { field.value = ""; });
    }

    document.addEventListener("input", function (event) {
        if (!watched(event.target)) return;
        clearLegacyAlbuminuriaOutput(event.target);
        scheduleRefresh();
    });
    document.addEventListener("change", function (event) {
        if (!watched(event.target)) return;
        clearLegacyAlbuminuriaOutput(event.target);
        scheduleRefresh(40);
    });

    // The shared appointment script still owns dynamic-column creation. Its old
    // manual metrics button must not become a second medical calculator: route
    // that action through the same server preview instead.
    document.addEventListener("click", function (event) {
        const metricsButton = event.target.closest("#updateMetricsTableBtn");
        if (metricsButton) {
            event.preventDefault();
            event.stopImmediatePropagation();
            scheduleRefresh(0);
            return;
        }
        if (event.target.closest("#addBiochemistryColumnBtn, #addAlbuminuriaColumnBtn, [data-add-lab], .remove-lab-card")) {
            scheduleRefresh(80);
        }
    }, true);

    const form = root.closest("form") || document.querySelector("form");
    if (form) {
        form.addEventListener("submit", async function (event) {
            if (resubmittingAfterPreview) return;

            // Перед сохранением всегда синхронизируем preview с текущими полями.
            // Это закрывает гонку: врач может нажать «Сохранить» раньше, чем
            // закончится debounce/HTTP-запрос после последнего изменения анализа.
            event.preventDefault();
            event.stopPropagation();

            const refreshed = await refresh();
            if (!refreshed) return;

            const calculated = calculatedAssessments(lastResponse?.kdigo_assessments || []);
            if (calculated.length > 1 && !selectedPair) {
                const hint = optionsContainer?.querySelector('[data-kdigo-selection-hint="1"]');
                (hint || optionsContainer || root).scrollIntoView({ behavior: "smooth", block: "center" });
                return;
            }

            // requestSubmit() нельзя вызывать синхронно из обработчика текущего
            // submit: Chrome может подавить реентерабельную отправку формы.
            // Переносим повторную отправку в следующий task, когда исходное
            // submit-событие уже полностью завершилось.
            const submitter = event.submitter || null;
            resubmittingAfterPreview = true;
            window.setTimeout(function () {
                try {
                    if (submitter && typeof form.requestSubmit === "function") {
                        form.requestSubmit(submitter);
                    } else if (typeof form.requestSubmit === "function") {
                        form.requestSubmit();
                    } else {
                        HTMLFormElement.prototype.submit.call(form);
                    }
                } finally {
                    resubmittingAfterPreview = false;
                }
            }, 0);
        });
    }

    const historyButton = document.getElementById("kdigoToggleHistoryButton");
    const historyPanel = document.getElementById("kdigoHistoryPanel");
    if (historyButton && historyPanel) {
        historyButton.addEventListener("click", function () {
            historyPanel.hidden = !historyPanel.hidden;
        });
    }

    clearCurrentPreview();
})();
