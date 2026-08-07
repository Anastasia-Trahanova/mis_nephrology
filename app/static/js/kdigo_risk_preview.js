/*
 * Live kidney calculations for appointment forms.
 * Medical formulas live only on the Python server. This file sends raw form
 * values to /api/kidney-preview and renders the returned eGFR/ACR/KDIGO data.
 */
(function () {
    "use strict";

    if (window.__kidneyServerPreviewV1Initialized) return;
    window.__kidneyServerPreviewV1Initialized = true;

    const root = document.getElementById("kdigoRiskPreview");
    if (!root) return;

    const optionsContainer = document.getElementById("kdigoCurrentVisitOptions");
    const selectedConclusion = document.getElementById("kdigoSelectedConclusionText");
    const excludedContainer = document.getElementById("kdigoExcludedPairsContainer");
    const previousGfr = readJson("kdigoPreviousGfrData");
    const previousAlbuminuria = readJson("kdigoPreviousAlbuminuriaData");

    let debounceTimer = null;
    let requestSerial = 0;
    let activeController = null;
    let selectedRowKey = null;
    let lastResponse = null;

    function readJson(id) {
        const node = document.getElementById(id);
        if (!node) return [];
        try {
            const value = JSON.parse(node.textContent || "[]");
            return Array.isArray(value) ? value : [];
        } catch (_) {
            return [];
        }
    }

    function value(selector) {
        const node = document.querySelector(selector);
        return node ? node.value : "";
    }

    function dateLabel(isoDate) {
        if (!isoDate) return "Новый расчёт";
        const parts = String(isoDate).slice(0, 10).split("-");
        return parts.length === 3 ? `${parts[2]}.${parts[1]}.${parts[0]}` : isoDate;
    }

    function currentGender() {
        if (root.dataset.patientGender !== undefined && root.dataset.patientGender !== "") {
            return root.dataset.patientGender;
        }
        const checked = document.querySelector('[name="gender"]:checked');
        if (checked) return checked.value;
        return value('[name="gender"]');
    }

    function collectBiochemistry() {
        if (root.dataset.formMode === "new_appointment") {
            const dates = Array.from(
                document.querySelectorAll('#biochemistryHeaderRow input[name="biochemistry_investigation_date"]')
            );
            const creatinine = Array.from(
                document.querySelectorAll('#bio_creatinine_row input[name="creatinine"]')
            );
            return creatinine.map((input, index) => ({
                key: `table-biochemistry-${index}`,
                investigation_date: dates[index] ? dates[index].value : value('[name="appointment_date"]'),
                creatinine: input.value,
            }));
        }

        return Array.from(document.querySelectorAll("#biochemistryContainer .lab-analysis-card")).map((card, index) => ({
            key: `card-biochemistry-${index}`,
            investigation_date: card.querySelector('[name="biochemistry_investigation_date"]')?.value || value('[name="appointment_date"]'),
            creatinine: card.querySelector('[name="creatinine"]')?.value || "",
        }));
    }

    function appointmentDateOrToday() {
        const current = value('[name="appointment_date"]');
        if (current) return current;
        const now = new Date();
        return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    }

    function appendBiochemistryCell(rowId, name) {
        const row = document.getElementById(rowId);
        if (!row) return;
        const cell = document.createElement("td");
        cell.className = "table-success";
        const input = document.createElement("input");
        input.type = "text";
        input.name = name;
        input.className = "form-control form-control-sm";
        cell.appendChild(input);
        row.appendChild(cell);
    }

    function addBiochemistryColumn() {
        const header = document.getElementById("biochemistryHeaderRow");
        if (!header) return;
        const th = document.createElement("th");
        th.className = "text-center table-success";
        th.style.minWidth = "150px";
        th.innerHTML = `
            <div class="small fw-bold mb-1">Новый анализ</div>
            <input type="date" name="biochemistry_investigation_date"
                   class="form-control form-control-sm" value="${appointmentDateOrToday()}">
        `;
        header.appendChild(th);
        [
            ["bio_creatinine_row", "creatinine"],
            ["bio_urea_row", "urea"],
            ["bio_uric_acid_row", "uric_acid"],
            ["bio_glucose_row", "glucose"],
            ["bio_total_protein_row", "total_protein"],
            ["bio_albumin_row", "albumin"],
            ["bio_potassium_row", "potassium"],
            ["bio_calcium_row", "calcium"],
            ["bio_phosphorus_row", "phosphorus"],
            ["bio_ferritin_row", "ferritin"],
            ["bio_ptg_row", "ptg"],
        ].forEach(([rowId, name]) => appendBiochemistryCell(rowId, name));
        scheduleRefresh(0);
    }

    function replaceBiochemistryAddButton() {
        const oldButton = document.getElementById("addBiochemistryColumnBtn");
        if (!oldButton || oldButton.dataset.kidneyServerOwned === "1") return;
        const button = oldButton.cloneNode(true);
        button.dataset.kidneyServerOwned = "1";
        oldButton.replaceWith(button);
        button.addEventListener("click", addBiochemistryColumn);
    }

    function appendAlbuminuriaCell(rowId, html) {
        const row = document.getElementById(rowId);
        if (!row) return;
        const cell = document.createElement("td");
        cell.className = "table-success";
        cell.innerHTML = html;
        row.appendChild(cell);
    }

    function addAlbuminuriaColumn() {
        const header = document.getElementById("albuminuriaHeaderRow");
        if (!header) return;
        const columnId = `albuminuria_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
        const number = header.querySelectorAll(".new-albuminuria-date").length + 1;

        const th = document.createElement("th");
        th.className = "text-center table-success";
        th.style.minWidth = "220px";
        th.innerHTML = `
            <div class="small fw-bold mb-1">Новая альбуминурия ${number}</div>
            <input type="date" name="albuminuria_investigation_date"
                   class="form-control form-control-sm new-albuminuria-date"
                   value="${appointmentDateOrToday()}">
        `;
        header.appendChild(th);

        appendAlbuminuriaCell("albuminuria_albumin_row", `
            <div class="d-flex gap-2 align-items-center">
                <input type="text" name="urine_albumin" class="form-control form-control-sm"
                       data-albuminuria-column="${columnId}" data-field="albumin">
                <select name="urine_albumin_unit" class="form-select form-select-sm"
                        style="min-width:90px;max-width:100px;"
                        data-albuminuria-column="${columnId}" data-field="albumin_unit">
                    <option value="mg_l" selected>мг/л</option><option value="g_l">г/л</option>
                </select>
            </div>
        `);
        appendAlbuminuriaCell("albuminuria_creatinine_row", `
            <div class="d-flex gap-2 align-items-center">
                <input type="text" name="urine_creatinine" class="form-control form-control-sm"
                       data-albuminuria-column="${columnId}" data-field="creatinine">
                <select name="urine_creatinine_unit" class="form-select form-select-sm"
                        style="min-width:110px;max-width:120px;"
                        data-albuminuria-column="${columnId}" data-field="creatinine_unit">
                    <option value="mmol_l" selected>ммоль/л</option><option value="umol_l">мкмоль/л</option>
                </select>
            </div>
        `);
        appendAlbuminuriaCell("albuminuria_acr_row", `
            <input type="text" class="form-control form-control-sm" readonly
                   data-albuminuria-column="${columnId}" data-field="acr">
        `);
        appendAlbuminuriaCell("albuminuria_daily_excretion_row", `
            <input type="text" name="daily_albumin_excretion" class="form-control form-control-sm albuminuria-daily-excretion"
                   data-albuminuria-column="${columnId}" data-field="daily_excretion">
        `);
        appendAlbuminuriaCell("albuminuria_category_row", `
            <input type="text" class="form-control form-control-sm albuminuria-category" readonly
                   data-albuminuria-column="${columnId}" data-field="category">
        `);
        scheduleRefresh(0);
    }

    function replaceAlbuminuriaAddButton() {
        const oldButton = document.getElementById("addAlbuminuriaColumnBtn");
        if (!oldButton || oldButton.dataset.kidneyServerOwned === "1") return;
        // _scripts.html historically attached a second client-side ACR calculator
        // to this button. Cloning after DOMContentLoaded drops that listener while
        // preserving the same id/classes; this module becomes the sole owner.
        const button = oldButton.cloneNode(true);
        button.dataset.kidneyServerOwned = "1";
        oldButton.replaceWith(button);
        button.addEventListener("click", addAlbuminuriaColumn);
    }

    function collectAlbuminuria() {
        if (root.dataset.formMode === "new_appointment") {
            const dates = Array.from(
                document.querySelectorAll('#albuminuriaHeaderRow input[name="albuminuria_investigation_date"]')
            );
            const albuminInputs = Array.from(
                document.querySelectorAll('[data-albuminuria-column][data-field="albumin"]')
            );
            return albuminInputs.map((albuminInput, index) => {
                const columnId = albuminInput.dataset.albuminuriaColumn;
                const fields = Array.from(document.querySelectorAll("[data-albuminuria-column]"))
                    .filter((node) => node.dataset.albuminuriaColumn === columnId);
                const field = (name) => fields.find((node) => node.dataset.field === name);
                return {
                    key: `table-albuminuria-${columnId}`,
                    column_id: columnId,
                    investigation_date: dates[index] ? dates[index].value : value('[name="appointment_date"]'),
                    urine_albumin: albuminInput.value,
                    urine_albumin_unit: field("albumin_unit")?.value || "mg_l",
                    urine_creatinine: field("creatinine")?.value || "",
                    urine_creatinine_unit: field("creatinine_unit")?.value || "mmol_l",
                    daily_albumin_excretion: field("daily_excretion")?.value || "",
                };
            });
        }

        return Array.from(document.querySelectorAll("#albuminuriaContainer .albuminuria-block")).map((card, index) => ({
            key: `card-albuminuria-${index}`,
            investigation_date: card.querySelector('[name="albuminuria_investigation_date"]')?.value || value('[name="appointment_date"]'),
            urine_albumin: card.querySelector('[name="urine_albumin"]')?.value || "",
            urine_albumin_unit: card.querySelector('[name="urine_albumin_unit"]')?.value || "mg_l",
            urine_creatinine: card.querySelector('[name="urine_creatinine"]')?.value || "",
            urine_creatinine_unit: card.querySelector('[name="urine_creatinine_unit"]')?.value || "mmol_l",
            daily_albumin_excretion: card.querySelector('[name="daily_albumin_excretion"]')?.value || "",
        }));
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

    function clearMetricsTablePreview() {
        document.querySelectorAll(".kidney-preview-metrics, .new-metrics-column").forEach((node) => node.remove());
    }

    function appendMetricCell(row, text) {
        const cell = document.createElement("td");
        cell.className = "text-center table-success kidney-preview-metrics";
        cell.textContent = text === null || text === undefined || text === "" ? "—" : String(text);
        row.appendChild(cell);
    }

    function sortMetricsTable() {
        const rows = ["metricsHeaderRow", "egfrRow", "cockcroftRow", "ckdStageRow"].map((id) => document.getElementById(id));
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
            clearMetricsTablePreview();
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

        rows.forEach((item) => {
            const match = /^card-biochemistry-(\d+)$/.exec(item.key || "");
            if (!match) return;
            const cards = document.querySelectorAll("#biochemistryContainer .lab-analysis-card");
            const card = cards[Number(match[1])];
            if (!card) return;
            const egfr = card.querySelector(".biochemistry-egfr");
            const cockcroft = card.querySelector(".biochemistry-cockcroft");
            const stage = card.querySelector(".biochemistry-stage");
            if (egfr) egfr.value = item.egfr_ckdepi ?? "";
            if (cockcroft) cockcroft.value = item.crcl_cockcroft_gault ?? "";
            if (stage) stage.value = item.ckd_stage ?? "";
        });
    }

    function findAlbuminuriaField(columnId, fieldName) {
        return Array.from(document.querySelectorAll("[data-albuminuria-column]"))
            .find((node) => node.dataset.albuminuriaColumn === columnId && node.dataset.field === fieldName);
    }

    function renderAlbuminuria(rows) {
        document.querySelectorAll("#albuminuriaContainer .albuminuria-block").forEach((card) => {
            const acr = card.querySelector(".albuminuria-acr");
            const category = card.querySelector(".albuminuria-category");
            const source = card.querySelector(".albuminuria-category-source");
            if (acr) acr.value = "";
            if (category) category.value = "";
            if (source) source.textContent = "";
        });

        rows.forEach((item) => {
            if ((item.key || "").startsWith("table-albuminuria-")) {
                const columnId = item.key.slice("table-albuminuria-".length);
                const acr = findAlbuminuriaField(columnId, "acr");
                const category = findAlbuminuriaField(columnId, "category");
                if (acr) acr.value = item.albumin_creatinine_ratio ?? "";
                if (category) category.value = item.albuminuria_category ?? "";
                return;
            }

            const match = /^card-albuminuria-(\d+)$/.exec(item.key || "");
            if (!match) return;
            const cards = document.querySelectorAll("#albuminuriaContainer .albuminuria-block");
            const card = cards[Number(match[1])];
            if (!card) return;
            const acr = card.querySelector(".albuminuria-acr");
            const category = card.querySelector(".albuminuria-category");
            const source = card.querySelector(".albuminuria-category-source");
            if (acr) acr.value = item.albumin_creatinine_ratio ?? "";
            if (category) category.value = item.albuminuria_category ?? "";
            if (source) {
                if (item.category_source === "acr" && item.albumin_creatinine_ratio !== null) {
                    source.textContent = `Категория рассчитана по ACR: ${item.albumin_creatinine_ratio} мг/ммоль.`;
                } else if (item.category_source === "daily" && item.daily_albumin_excretion) {
                    source.textContent = `Категория рассчитана по суточной экскреции: ${item.daily_albumin_excretion} мг/сут.`;
                }
            }
        });
    }

    function calculatedAssessments() {
        return (lastResponse?.kdigo_assessments || []).filter((item) => item.status === "calculated");
    }

    function selectedAssessment() {
        const calculated = calculatedAssessments();
        return calculated.find((item) => item.row_key === selectedRowKey) || calculated[0] || null;
    }

    function writeExcludedPairs() {
        if (!excludedContainer) return;
        excludedContainer.replaceChildren();
        const selected = selectedAssessment();
        const selectedKey = selected?.row_key || null;
        calculatedAssessments()
            .filter((item) => item.row_key !== selectedKey)
            .forEach((item) => {
                const input = document.createElement("input");
                input.type = "hidden";
                input.name = "kdigo_excluded_pair";
                input.value = item.pair_key || item.row_key;
                excludedContainer.appendChild(input);
            });
    }

    function writeSelectedConclusion() {
        const selected = selectedAssessment();
        if (selectedConclusion) {
            selectedConclusion.value = selected?.display_text || lastResponse?.kdigo_assessments?.[0]?.display_text || "";
        }
        writeExcludedPairs();
    }

    function renderKdigo(assessments) {
        if (!optionsContainer) return;
        optionsContainer.replaceChildren();
        const calculated = assessments.filter((item) => item.status === "calculated");
        if (!calculated.some((item) => item.row_key === selectedRowKey)) {
            selectedRowKey = calculated[0]?.row_key || null;
        }

        assessments.forEach((assessment) => {
            const row = document.createElement("div");
            row.className = assessment.status === "calculated"
                ? `kdigo-current-option kdigo-risk-${assessment.prognosis_level || "unknown"}`
                : "kdigo-current-option kdigo-current-option-neutral";

            const radio = document.createElement("input");
            radio.type = "radio";
            radio.name = "kdigo_selected_current_option";
            radio.className = "form-check-input mt-0";
            radio.disabled = assessment.status !== "calculated";
            radio.checked = assessment.status === "calculated" && assessment.row_key === selectedRowKey;
            radio.value = assessment.row_key || "";
            radio.addEventListener("change", function () {
                if (!radio.checked) return;
                selectedRowKey = assessment.row_key;
                writeSelectedConclusion();
            });

            const text = document.createElement("span");
            text.className = "kdigo-current-option-text";
            text.textContent = assessment.display_text || "";

            row.appendChild(radio);
            row.appendChild(text);
            optionsContainer.appendChild(row);
        });
        writeSelectedConclusion();
    }

    function render(data) {
        lastResponse = data || {};
        renderMetrics(Array.isArray(data.metrics) ? data.metrics : []);
        renderAlbuminuria(Array.isArray(data.albuminuria) ? data.albuminuria : []);
        renderKdigo(Array.isArray(data.kdigo_assessments) ? data.kdigo_assessments : []);
    }

    async function refresh() {
        const serial = ++requestSerial;
        if (activeController) activeController.abort();
        activeController = new AbortController();
        try {
            const response = await fetch("/api/kidney-preview", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(buildPayload()),
                signal: activeController.signal,
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (serial !== requestSerial) return;
            render(data);
        } catch (error) {
            if (error?.name === "AbortError") return;
            console.error("Kidney preview failed", error);
            if (optionsContainer) {
                optionsContainer.textContent = "Не удалось обновить расчётные показатели. Проверьте соединение и повторите ввод.";
            }
        }
    }

    function scheduleRefresh(delay) {
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(refresh, delay ?? 120);
    }

    const watchedNames = new Set([
        "birth_date", "gender", "weight", "appointment_date",
        "biochemistry_investigation_date", "creatinine",
        "albuminuria_investigation_date", "urine_albumin", "urine_albumin_unit",
        "urine_creatinine", "urine_creatinine_unit", "daily_albumin_excretion",
    ]);

    function isWatched(target) {
        return target instanceof HTMLInputElement || target instanceof HTMLSelectElement
            ? watchedNames.has(target.name)
            : false;
    }

    document.addEventListener("input", function (event) {
        if (isWatched(event.target)) scheduleRefresh();
    });
    document.addEventListener("change", function (event) {
        if (isWatched(event.target)) scheduleRefresh(50);
    });
    document.addEventListener("click", function (event) {
        if (event.target.closest("#addBiochemistryColumnBtn, #addAlbuminuriaColumnBtn, [data-add-lab], .remove-lab-card")) {
            scheduleRefresh(80);
        }
    });

    document.addEventListener("DOMContentLoaded", function () {
        // Run after every DOMContentLoaded handler so legacy calculation/add-column
        // listeners from _scripts.html are removed from the two kidney input buttons.
        window.setTimeout(function () {
            replaceBiochemistryAddButton();
            replaceAlbuminuriaAddButton();
        }, 0);
    });

    const historyButton = document.getElementById("kdigoToggleHistoryButton");
    const historyPanel = document.getElementById("kdigoHistoryPanel");
    if (historyButton && historyPanel) {
        historyButton.addEventListener("click", function () {
            historyPanel.hidden = !historyPanel.hidden;
        });
    }

    scheduleRefresh(0);
})();
