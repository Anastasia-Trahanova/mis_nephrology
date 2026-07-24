/*
Назначение файла
----------------
Дополняет форму приёма изменениями раздела исследований и блока диагнозов,
не вмешиваясь в существующие таблицы, серверное сохранение и общий стиль страниц.

Что выполняет файл
------------------
1. Меняет только видимую подпись «Категория СКФ» на
   «Стадия ХБП по СКФ».
2. Показывает категорию A1/A2/A3 по суточной экскреции альбумина, когда ACR
   не рассчитан. Итог перед сохранением всё равно повторно определяет сервер.
3. Добавляет поле суточной экскреции в новый динамический столбец
   альбуминурии повторного приёма.
4. Подставляет основной диагноз прошлого приёма непосредственно в поле
   основного диагноза и выделяет его как перенесённое значение.
5. Ставит системное осложнение по текущей стадии ХБП первым, без жёлтой
   подсветки, и обновляет его сразу при изменении креатинина или даты анализа.
6. Оставляет осложнения и сопутствующие заболевания прошлого приёма ниже
   системного осложнения и выделяет их как перенесённые значения.
7. Снимает жёлтую подсветку сразу после редактирования перенесённого диагноза.
8. При щелчке по перенесённому диагнозу выделяет его текст целиком, чтобы
   врач мог заменить или удалить значение одной клавишей.

Что здесь не меняется
---------------------
- серверное сохранение диагнозов и таблицы базы данных;
- расчёт СКФ и матрица KDIGO;
- структура ОАК, ОАМ и биохимии;
- лекарства, диета, рекомендации и дата следующего приёма;
- шрифты, цвета и базовый CSS страницы.
*/

(function () {
    "use strict";

    function parseNumber(value) {
        const normalized = String(value ?? "")
            .trim()
            .replace(",", ".")
            .replace(/\s+/g, "");
        if (!normalized) return null;

        const parsed = Number(normalized);
        return Number.isFinite(parsed) ? parsed : null;
    }

    function dailyAlbuminuriaCategory(value) {
        const daily = parseNumber(value);
        if (daily === null || daily < 0) return "";

        if (daily < 30) return "A1";
        if (daily <= 300) return "A2";
        return "A3";
    }

    function renameCkdStageLabels() {
        document.querySelectorAll("strong, label, th, td").forEach((element) => {
            if (element.children.length > 0) return;
            if (element.textContent.trim() === "Категория СКФ") {
                element.textContent = "Стадия ХБП по СКФ";
            }
        });
    }

    function updatePrimaryAlbuminuriaBlock(block) {
        if (!block) return;

        const dailyInput = block.querySelector('[name="daily_albumin_excretion"]');
        const acrInput = block.querySelector(".albuminuria-acr");
        const categoryInput = block.querySelector(".albuminuria-category");
        if (!dailyInput || !categoryInput) return;

        if (parseNumber(acrInput?.value) !== null) {
            return;
        }

        categoryInput.value = dailyAlbuminuriaCategory(dailyInput.value);
    }

    function addDailyFieldToLatestRepeatColumn() {
        const dailyRow = document.getElementById("albuminuria_daily_excretion_row");
        if (!dailyRow) return;

        const categoryInputs = Array.from(
            document.querySelectorAll(
                '[data-albuminuria-column][data-field="category"]'
            )
        );
        const latestCategory = categoryInputs.at(-1);
        const columnId = latestCategory?.dataset?.albuminuriaColumn;
        if (!columnId) return;

        if (
            document.querySelector(
                `[data-albuminuria-column="${columnId}"][data-field="daily_excretion"]`
            )
        ) {
            return;
        }

        const cell = document.createElement("td");
        cell.className = "table-success";
        cell.innerHTML = `
            <input
                type="text"
                name="daily_albumin_excretion"
                class="form-control form-control-sm"
                data-albuminuria-column="${columnId}"
                data-field="daily_excretion"
            >
        `;
        dailyRow.appendChild(cell);
    }

    function updateRepeatAlbuminuriaColumn(columnId) {
        if (!columnId) return;

        const dailyInput = document.querySelector(
            `[data-albuminuria-column="${columnId}"][data-field="daily_excretion"]`
        );
        const acrInput = document.querySelector(
            `[data-albuminuria-column="${columnId}"][data-field="acr"]`
        );
        const categoryInput = document.querySelector(
            `[data-albuminuria-column="${columnId}"][data-field="category"]`
        );
        if (!dailyInput || !categoryInput) return;

        if (parseNumber(acrInput?.value) !== null) {
            return;
        }

        categoryInput.value = dailyAlbuminuriaCategory(dailyInput.value);
    }

    function updateAlbuminuriaForTarget(target) {
        const primaryBlock = target.closest?.(".albuminuria-block");
        if (primaryBlock) {
            updatePrimaryAlbuminuriaBlock(primaryBlock);
        }

        const columnId = target.dataset?.albuminuriaColumn;
        if (columnId) {
            updateRepeatAlbuminuriaColumn(columnId);
        }
    }

    function getMainDiagnosisElements() {
        const input = document.querySelector(
            '[name="icd10_main_diagnosis"]'
        );
        const block = input?.closest(".mb-3");
        const help = block?.querySelector(".icd10-autofill-note");
        const note = block?.parentElement?.querySelector(
            '[name="icd10_main_note"]'
        );

        return { input, help, note };
    }

    function extractPreviousMainDiagnosis(helpElement) {
        const text = String(helpElement?.textContent || "")
            .replace(/\s+/g, " ")
            .trim();
        if (!text) return "";

        const match = text.match(
            /В прошлом при[её]ме(?:\s*\([^)]*\))?\s*:\s*(.+)$/i
        );
        return match ? match[1].trim() : "";
    }

    function syncMainDiagnosisAuditState(input, userEdited) {
        const autofilledHidden = document.querySelector(
            '[name="icd10_main_diagnosis_autofilled_value"]'
        );
        const userEditedHidden = document.querySelector(
            '[name="icd10_main_diagnosis_user_edited"]'
        );

        input.dataset.autofilledValue = "";
        input.dataset.userEdited = userEdited ? "true" : "false";

        if (autofilledHidden) autofilledHidden.value = "";
        if (userEditedHidden) {
            userEditedHidden.value = userEdited ? "true" : "false";
        }
    }

    function prefillMainDiagnosisFromPreviousVisit() {
        const { input, help, note } = getMainDiagnosisElements();
        if (!input) return;

        const previousDiagnosis = extractPreviousMainDiagnosis(help);
        if (previousDiagnosis && !input.value.trim()) {
            input.value = previousDiagnosis;
            input.classList.add("prefilled-field");
            syncMainDiagnosisAuditState(input, true);

            if (note?.value?.trim()) {
                note.classList.add("prefilled-field");
            }
        }

        help?.remove();
    }

    function isPrefilledDiagnosisInput(element) {
        if (!(element instanceof HTMLInputElement)) return false;
        if (!element.classList.contains("prefilled-field")) return false;

        return element.matches(
            '[name="icd10_main_diagnosis"], ' +
            '#icd10ComplicationsContainer .icd10-search-input, ' +
            '#icd10ComorbiditiesContainer .icd10-search-input'
        );
    }

    function selectWholePrefilledDiagnosis(event) {
        const target = event.target;
        if (!isPrefilledDiagnosisInput(target)) return;

        event.preventDefault();
        target.focus();
        target.select();
    }

    function confirmEditedPrefilledValue(target) {
        if (!(target instanceof HTMLElement)) return;
        if (!target.classList.contains("prefilled-field")) return;

        target.classList.remove("prefilled-field");

        if (target.matches('[name="icd10_main_diagnosis"]')) {
            syncMainDiagnosisAuditState(target, true);
        }
    }

    function markPreviousDiagnosisRows() {
        const selectors = [
            "#icd10ComplicationsContainer",
            "#icd10ComorbiditiesContainer"
        ];

        selectors.forEach((selector) => {
            document
                .querySelectorAll(`${selector} .icd10-diagnosis-row`)
                .forEach((row) => {
                    const input = row.querySelector(
                        ".icd10-search-input"
                    );
                    if (!input?.value?.trim()) return;

                    row.dataset.previousDiagnosis = "true";
                    input.classList.add("prefilled-field");

                    const note = row.querySelector("textarea");
                    if (note?.value?.trim()) {
                        note.classList.add("prefilled-field");
                    }
                });
        });
    }

    function rewriteComplicationHelpText() {
        const container = document.getElementById(
            "icd10ComplicationsContainer"
        );
        const block = container?.closest(".mb-3");
        const label = block?.querySelector("label.form-label.fw-bold");
        if (!block || !label) return;

        let help = block.querySelector(
            '[data-ckd-complication-help="true"]'
        );
        if (!help) {
            help = document.createElement("div");
            help.className = "form-text text-muted mb-2";
            help.dataset.ckdComplicationHelp = "true";
            label.insertAdjacentElement("afterend", help);
        }

        help.textContent =
            "Осложнение основного диагноза проставляется автоматически " +
            "в соответствии со стадией ХБП, определённой по СКФ.";
    }

    function getCkdDiagnosisFromCurrentForm() {
        let stage = "";

        if (
            typeof window.getLatestCurrentCkdStageFromForm === "function"
        ) {
            stage = window.getLatestCurrentCkdStageFromForm() || "";
        }

        let code = "";
        if (
            stage &&
            typeof window.getIcd10CodeForCkdStage === "function"
        ) {
            code = window.getIcd10CodeForCkdStage(stage) || "";
        }

        let diagnosis = "";
        if (
            code &&
            typeof window.findDictionaryCkdDiagnosis === "function"
        ) {
            diagnosis = window.findDictionaryCkdDiagnosis(code) || "";
        }

        if (diagnosis) return diagnosis;

        const fallbackByStage = {
            "С1": "N18.1 — Хроническая болезнь почек, стадия 1",
            "С2": "N18.2 — Хроническая болезнь почек, стадия 2",
            "С3а": "N18.3 — Хроническая болезнь почек, стадия 3",
            "С3б": "N18.3 — Хроническая болезнь почек, стадия 3",
            "С4": "N18.4 — Хроническая болезнь почек, стадия 4",
            "С5": "N18.5 — Хроническая болезнь почек, стадия 5"
        };

        return fallbackByStage[String(stage || "").trim()] || "";
    }

    function ensureAutomaticComplicationInput() {
        const container = document.getElementById(
            "icd10ComplicationsContainer"
        );
        if (!container) return null;

        let input = container.querySelector(
            '[name="icd10_complication_diagnosis"]' +
            '[data-ckd-autofilled-complication="true"]'
        );

        if (!input) {
            const emptyRow = Array.from(
                container.querySelectorAll(".icd10-diagnosis-row")
            ).find((row) => {
                const candidate = row.querySelector(
                    '[name="icd10_complication_diagnosis"]'
                );
                return (
                    candidate &&
                    !candidate.value.trim() &&
                    row.dataset.previousDiagnosis !== "true"
                );
            });

            let row = emptyRow;
            if (!row) {
                const addButton = document.getElementById(
                    "addIcd10ComplicationBtn"
                );
                addButton?.click();
                row = Array.from(
                    container.querySelectorAll(".icd10-diagnosis-row")
                ).at(-1);
            }

            input = row?.querySelector(
                '[name="icd10_complication_diagnosis"]'
            );
            if (!input) return null;

            input.dataset.ckdAutofilledComplication = "true";
        }

        const row = input.closest(".icd10-diagnosis-row");
        if (row && container.firstElementChild !== row) {
            container.prepend(row);
        }

        row?.removeAttribute("data-previous-diagnosis");
        input.classList.remove("prefilled-field");

        const note = row?.querySelector(
            '[name="icd10_complication_note"]'
        );
        note?.classList.remove("prefilled-field");

        return input;
    }

    function clearSystemSuggestionFromMain(diagnosis) {
        const mainInput = document.querySelector(
            '[name="icd10_main_diagnosis"]'
        );
        if (!mainInput) return;

        const systemValue =
            mainInput.dataset.autofilledValue ||
            document.querySelector(
                '[name="icd10_main_diagnosis_autofilled_value"]'
            )?.value ||
            "";

        if (
            systemValue &&
            mainInput.value.trim() === systemValue.trim()
        ) {
            mainInput.value = "";
            mainInput.classList.remove("prefilled-field");
            syncMainDiagnosisAuditState(mainInput, false);
            return;
        }

        if (
            !mainInput.classList.contains("prefilled-field") &&
            diagnosis &&
            mainInput.value.trim() === diagnosis.trim() &&
            mainInput.dataset.userEdited !== "true"
        ) {
            mainInput.value = "";
            syncMainDiagnosisAuditState(mainInput, false);
        }
    }

    function updateAutomaticCkdComplication() {
        const diagnosis = getCkdDiagnosisFromCurrentForm();
        const input = ensureAutomaticComplicationInput();
        if (!input) return;

        input.value = diagnosis;
        input.dataset.ckdAutofilledValue = diagnosis;
        input.dataset.ckdAutofilledComplication = "true";
        input.dataset.userEdited = "false";
        input.dataset.autofilledValue = diagnosis;
        input.classList.remove("prefilled-field");

        const row = input.closest(".icd10-diagnosis-row");
        row?.querySelector(
            '[name="icd10_complication_note"]'
        )?.classList.remove("prefilled-field");

        clearSystemSuggestionFromMain(diagnosis);
    }

    function scheduleDiagnosisSync() {
        window.requestAnimationFrame(() => {
            window.setTimeout(updateAutomaticCkdComplication, 0);
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        renameCkdStageLabels();
        prefillMainDiagnosisFromPreviousVisit();
        markPreviousDiagnosisRows();
        rewriteComplicationHelpText();

        document
            .querySelectorAll(".albuminuria-block")
            .forEach(updatePrimaryAlbuminuriaBlock);

        const addAlbuminuriaButton = document.getElementById(
            "addAlbuminuriaColumnBtn"
        );
        addAlbuminuriaButton?.addEventListener("click", () => {
            addDailyFieldToLatestRepeatColumn();
        });

        scheduleDiagnosisSync();
    });

    document.addEventListener("pointerdown", selectWholePrefilledDiagnosis);

    document.addEventListener("input", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;

        confirmEditedPrefilledValue(target);

        if (
            target.matches(
                '[name="daily_albumin_excretion"], ' +
                '[data-albuminuria-column], ' +
                ".albuminuria-albumin, " +
                ".albuminuria-creatinine, " +
                ".albuminuria-albumin-unit, " +
                ".albuminuria-creatinine-unit"
            )
        ) {
            updateAlbuminuriaForTarget(target);
        }

        if (
            target.matches(
                '[name="creatinine"], ' +
                '[name="biochemistry_investigation_date"], ' +
                '[name="birth_date"], ' +
                '[name="gender"], ' +
                '[name="appointment_date"]'
            )
        ) {
            scheduleDiagnosisSync();
        }

    });

    document.addEventListener("change", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;

        if (
            target.matches(
                '[name="daily_albumin_excretion"], [data-albuminuria-column]'
            )
        ) {
            updateAlbuminuriaForTarget(target);
        }

        if (
            target.matches(
                '[name="creatinine"], ' +
                '[name="biochemistry_investigation_date"], ' +
                '[name="birth_date"], ' +
                '[name="gender"], ' +
                '[name="appointment_date"]'
            )
        ) {
            scheduleDiagnosisSync();
        }
    });
})();
