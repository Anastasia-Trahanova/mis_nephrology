/*
Назначение файла: live-просмотр прогноза KDIGO в формах первого и повторного приёма.

Что делает файл:
- держит в интерфейсе одну строку «невозможно оценить…», пока данных недостаточно;
- пересчитывает эту строку при вводе СКФ/альбуминурии без накопления дублей;
- создаёт новую строку прогноза для каждой новой строки/колонки СКФ или альбуминурии;
- подсвечивает только строки прогноза цветами KDIGO;
- даёт врачу выбрать radio-кружочком один рассчитанный прогноз;
- передаёт backend hidden-поля kdigo_excluded_pair для рассчитанных строк, которые врач не выбрал;
- раскрывает историю прошлых прогнозов только по кнопке и не смешивает её с текущим заключением.

Правило сопоставления текущих данных:
- первая текущая СКФ сопоставляется с первой текущей альбуминурией;
- вторая текущая СКФ сопоставляется со второй текущей альбуминурией;
- если добавлен второй показатель только одного типа, создаётся вторая строка с первой доступной парой второго типа;
- если для новой СКФ ещё нет своей альбуминурии, временно берётся первая текущая альбуминурия;
- если для новой альбуминурии ещё нет своей СКФ, временно берётся первая текущая СКФ;
- если в текущем приёме есть только один тип показателя, второй берётся из последнего подходящего прошлого исследования;
- если данных недостаточно, строка остаётся нейтральной и обновляется, а не дублируется.
*/
(function () {
    "use strict";

    if (window.__kdigoLiveCurrentVisitV7Initialized) {
        return;
    }
    window.__kdigoLiveCurrentVisitV7Initialized = true;

    const EMPTY_BOTH_TEXT = "Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии и СКФ не предоставлены.";
    const MISSING_ALBUMINURIA_TEXT = "Невозможно оценить риск прогрессирования ХБП и развития ХПН: добавьте стадию альбуминурии.";
    const MISSING_GFR_TEXT = "Невозможно оценить риск прогрессирования ХБП и развития ХПН: добавьте стадию ХБП/СКФ.";
    const STALE_TEXT = "Невозможно оценить риск прогрессирования ХБП и развития ХПН: интервал между СКФ и альбуминурией превышает допустимый.";
    const UNKNOWN_RISK_TEXT = "Невозможно оценить риск прогрессирования ХБП и развития ХПН: проверьте категории СКФ и альбуминурии.";

    const MAX_INTERVAL_DAYS = 180;

    const RISK_MATRIX = {
        "С1": { A1: "low", A2: "moderate", A3: "high" },
        "С2": { A1: "low", A2: "moderate", A3: "high" },
        "С3а": { A1: "moderate", A2: "high", A3: "very_high" },
        "С3б": { A1: "high", A2: "very_high", A3: "very_high" },
        "С4": { A1: "very_high", A2: "very_high", A3: "very_high" },
        "С5": { A1: "very_high", A2: "very_high", A3: "very_high" }
    };

    const RISK_TEXT = {
        low: "низкий риск прогрессирования ХБП и развития ХПН",
        moderate: "умеренный риск прогрессирования ХБП и развития ХПН",
        high: "высокий риск прогрессирования ХБП и развития ХПН",
        very_high: "очень высокий риск прогрессирования ХБП и развития ХПН"
    };

    let renderTimer = null;
    let lastSelectedKey = "";

    function root() {
        return document.getElementById("kdigoRiskPreview");
    }

    function normalizeNumber(value) {
        if (value === null || value === undefined) {
            return null;
        }
        const normalized = String(value).replace(",", ".").replace(/[^0-9.\-]/g, "");
        if (normalized === "" || normalized === "." || normalized === "-") {
            return null;
        }
        const number = Number(normalized);
        return Number.isFinite(number) ? number : null;
    }

    function normalizeDate(value) {
        if (!value) {
            return "";
        }
        const text = String(value).trim();
        const match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (match) {
            return `${match[1]}-${match[2]}-${match[3]}`;
        }
        const ruMatch = text.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
        if (ruMatch) {
            return `${ruMatch[3]}-${ruMatch[2]}-${ruMatch[1]}`;
        }
        return "";
    }

    function todayIso() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function fallbackInvestigationDate() {
        const appointmentDate = document.querySelector("[name='appointment_date'], [name='visit_date'], [name='admission_date']");
        return normalizeDate(appointmentDate ? appointmentDate.value : "") || todayIso();
    }

    function parseIsoDate(value) {
        const normalized = normalizeDate(value);
        if (!normalized) {
            return null;
        }
        const date = new Date(`${normalized}T00:00:00`);
        return Number.isNaN(date.getTime()) ? null : date;
    }

    function daysBetween(first, second) {
        const firstDate = parseIsoDate(first);
        const secondDate = parseIsoDate(second);
        if (!firstDate || !secondDate) {
            return null;
        }
        return Math.round(Math.abs(secondDate.getTime() - firstDate.getTime()) / 86400000);
    }

    function formatRuDate(value) {
        const normalized = normalizeDate(value);
        if (!normalized) {
            return "—";
        }
        const parts = normalized.split("-");
        return `${parts[2]}.${parts[1]}.${parts[0]}`;
    }

    function controls(selector) {
        const kdigoRoot = root();
        return Array.from(document.querySelectorAll(selector)).filter((node) => {
            if (kdigoRoot && kdigoRoot.contains(node)) {
                return false;
            }
            return !node.disabled;
        });
    }

    function readableNodes(selector) {
        const kdigoRoot = root();
        return Array.from(document.querySelectorAll(selector)).filter((node) => {
            if (kdigoRoot && kdigoRoot.contains(node)) {
                return false;
            }
            return !node.disabled;
        });
    }

    function nodeValue(node) {
        if (!node) {
            return "";
        }
        const tag = String(node.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") {
            if (node.type === "checkbox" || node.type === "radio") {
                return node.checked ? node.value : "";
            }
            return node.value || "";
        }
        return node.textContent || node.getAttribute("data-value") || "";
    }

    function nodeValues(selector) {
        return readableNodes(selector).map((node) => nodeValue(node));
    }

    function controlValues(selector) {
        return controls(selector).map((node) => nodeValue(node));
    }

    function firstNonEmptyValues(selectors) {
        for (const selector of selectors) {
            const values = nodeValues(selector).map((value) => String(value || "").trim());
            if (values.some((value) => value !== "" && value !== "—")) {
                return values;
            }
        }
        return [];
    }

    function firstValueIn(context, selectors) {
        if (!context) {
            return "";
        }
        for (const selector of selectors) {
            const node = context.querySelector(selector);
            const value = String(nodeValue(node) || "").trim();
            if (value && value !== "—") {
                return value;
            }
        }
        return "";
    }

    function patientBirthDateValue() {
        const kdigoRoot = root();
        return normalizeDate(
            (kdigoRoot && kdigoRoot.dataset.patientBirthDate) ||
            firstValueIn(document, ["[name='birth_date']", "[name='patient_birth_date']"])
        );
    }

    function patientGenderValue() {
        const kdigoRoot = root();
        return (
            (kdigoRoot && kdigoRoot.dataset.patientGender) ||
            firstValueIn(document, ["[name='gender']", "[name='patient_gender']"])
        );
    }

    function normalizeGfrCategory(value) {
        if (!value) {
            return "";
        }
        let text = String(value).trim();
        text = text.replace(/G/gi, "С").replace(/C/g, "С");
        text = text.replace(/с/g, "С").replace(/a/gi, "а").replace(/b/gi, "б");
        text = text.replace(/\s+/g, "");
        const aliases = {
            "1": "С1",
            "2": "С2",
            "3А": "С3а",
            "3а": "С3а",
            "3Б": "С3б",
            "3б": "С3б",
            "4": "С4",
            "5": "С5"
        };
        if (aliases[text]) {
            return aliases[text];
        }
        const match = text.match(/С?(1|2|3а|3б|4|5)/i);
        if (!match) {
            return "";
        }
        return `С${match[1].replace(/А/i, "а").replace(/Б/i, "б")}`;
    }

    function normalizeAlbuminuriaCategory(value) {
        if (!value) {
            return "";
        }
        let text = String(value).trim().toUpperCase().replace(/А/g, "A").replace(/\s+/g, "");
        const match = text.match(/A(1|2|3)/);
        return match ? `A${match[1]}` : "";
    }

    function gfrCategoryFromEgfr(value) {
        const egfr = normalizeNumber(value);
        if (egfr === null) {
            return "";
        }
        if (egfr >= 90) {
            return "С1";
        }
        if (egfr >= 60) {
            return "С2";
        }
        if (egfr >= 45) {
            return "С3а";
        }
        if (egfr >= 30) {
            return "С3б";
        }
        if (egfr >= 15) {
            return "С4";
        }
        return "С5";
    }

    function albuminuriaCategoryFromAcr(value) {
        const acr = normalizeNumber(value);
        if (acr === null) {
            return "";
        }
        if (acr < 30) {
            return "A1";
        }
        if (acr <= 300) {
            return "A2";
        }
        return "A3";
    }

    function yearsBetween(birthDate, investigationDate) {
        const birth = parseIsoDate(birthDate);
        const investigation = parseIsoDate(investigationDate) || new Date();
        if (!birth) {
            return null;
        }
        let years = investigation.getFullYear() - birth.getFullYear();
        const monthDelta = investigation.getMonth() - birth.getMonth();
        if (monthDelta < 0 || (monthDelta === 0 && investigation.getDate() < birth.getDate())) {
            years -= 1;
        }
        return years;
    }

    function normalizeGender(value) {
        const text = String(value || "").trim().toLowerCase();
        if (["м", "муж", "мужской", "male", "m"].includes(text)) {
            return "male";
        }
        if (["ж", "жен", "женский", "female", "f"].includes(text)) {
            return "female";
        }
        return "";
    }

    function calculateEgfrCkdEpiCreatinine(creatinineRaw, investigationDate) {
        const kdigoRoot = root();
        const creatinine = normalizeNumber(creatinineRaw);
        if (creatinine === null || !kdigoRoot) {
            return null;
        }
        const age = yearsBetween(patientBirthDateValue(), investigationDate);
        const gender = normalizeGender(patientGenderValue());
        if (!age || age <= 0 || !gender) {
            return null;
        }
        const creatinineMgDl = creatinine > 20 ? creatinine / 88.4 : creatinine;
        const kappa = gender === "female" ? 0.7 : 0.9;
        const alpha = gender === "female" ? -0.241 : -0.302;
        const minPart = Math.min(creatinineMgDl / kappa, 1) ** alpha;
        const maxPart = Math.max(creatinineMgDl / kappa, 1) ** -1.2;
        const sexMultiplier = gender === "female" ? 1.012 : 1;
        return 142 * minPart * maxPart * (0.9938 ** age) * sexMultiplier;
    }

    function calculateAcr(albuminRaw, creatinineRaw, unitRaw) {
        const albumin = normalizeNumber(albuminRaw);
        const creatinine = normalizeNumber(creatinineRaw);
        if (albumin === null || creatinine === null || creatinine === 0) {
            return null;
        }
        const unit = String(unitRaw || "").trim().toLowerCase();
        if (unit.includes("ммоль") || unit.includes("mmol")) {
            return albumin / creatinine * 8.84;
        }
        return albumin / creatinine;
    }

    function radioGroupValueByIndex(name, index) {
        const checked = controls(`input[name='${name}']:checked`);
        if (checked[index]) {
            return checked[index].value || "";
        }
        const all = controls(`input[name='${name}']`);
        if (all[index]) {
            return all[index].value || "";
        }
        return "";
    }

    function readPrevious(scriptId, categoryNormalizer) {
        const script = document.getElementById(scriptId);
        if (!script) {
            return [];
        }
        try {
            const parsed = JSON.parse(script.textContent || "[]");
            return parsed
                .map((item, index) => ({
                    index,
                    source: "previous_appointment",
                    date: normalizeDate(item.date || item.investigation_date || ""),
                    category: categoryNormalizer(item.category || item.gfr_category || item.albuminuria_category || "")
                }))
                .filter((item) => item.date && item.category)
                .sort((a, b) => a.date.localeCompare(b.date));
        } catch (error) {
            return [];
        }
    }

    function readCurrentGfrSources() {
        const sources = [];
        const seenCards = new Set();

        const cardCandidates = readableNodes(".lab-analysis-card").filter((card) => (
            card.querySelector("[name='creatinine'], [name='serum_creatinine'], .biochemistry-stage, .biochemistry-egfr")
        ));

        cardCandidates.forEach((card, index) => {
            seenCards.add(card);
            const date = normalizeDate(firstValueIn(card, [
                "[name='biochemistry_investigation_date']",
                "[name='gfr_investigation_date']",
                "[name='creatinine_investigation_date']"
            ])) || fallbackInvestigationDate();
            let category = normalizeGfrCategory(firstValueIn(card, [
                "[name='gfr_category']",
                "[name='egfr_category']",
                ".biochemistry-stage",
                "[data-gfr-category]"
            ]));
            if (!category) {
                category = gfrCategoryFromEgfr(firstValueIn(card, [
                    "[name='egfr_ckd_epi']",
                    "[name='calculated_egfr']",
                    "[name='egfr']",
                    ".biochemistry-egfr"
                ]));
            }
            if (!category) {
                const creatinine = firstValueIn(card, ["[name='creatinine']", "[name='serum_creatinine']"]);
                if (creatinine) {
                    category = gfrCategoryFromEgfr(calculateEgfrCkdEpiCreatinine(creatinine, date));
                }
            }
            if (category) {
                sources.push({
                    index,
                    source: "current_appointment",
                    date,
                    category,
                    uid: `gfr-card-${index}`
                });
            }
        });

        if (sources.length) {
            return sources;
        }

        const dateValues = firstNonEmptyValues([
            "[name='biochemistry_investigation_date']",
            "[name='gfr_investigation_date']",
            "[name='creatinine_investigation_date']"
        ]);
        const categoryValues = firstNonEmptyValues([
            "[name='gfr_category']",
            "[name='egfr_category']",
            ".biochemistry-stage",
            "#ckdStageRow .new-metrics-column",
            "[data-gfr-category]"
        ]);
        const egfrValues = firstNonEmptyValues([
            "[name='egfr_ckd_epi']",
            "[name='calculated_egfr']",
            "[name='egfr']",
            ".biochemistry-egfr",
            "#egfrRow .new-metrics-column"
        ]);
        const creatinineNodes = controls("[name='creatinine'], [name='serum_creatinine']");
        const creatinineValues = creatinineNodes.map((node) => nodeValue(node));

        const count = Math.max(dateValues.length, categoryValues.length, egfrValues.length, creatinineValues.length);
        for (let index = 0; index < count; index += 1) {
            const date = normalizeDate(dateValues[index] || "") || fallbackInvestigationDate();
            let category = normalizeGfrCategory(categoryValues[index] || "");
            if (!category) {
                category = gfrCategoryFromEgfr(egfrValues[index] || "");
            }
            if (!category && creatinineValues[index]) {
                const egfr = calculateEgfrCkdEpiCreatinine(creatinineValues[index], date);
                category = gfrCategoryFromEgfr(egfr);
            }
            if (category) {
                sources.push({
                    index,
                    source: "current_appointment",
                    date,
                    category,
                    uid: `gfr-row-${index}`
                });
            }
        }
        return sources;
    }

    function readCurrentAlbuminuriaSources() {
        const sources = [];

        const cardCandidates = readableNodes(".lab-analysis-card").filter((card) => (
            card.querySelector("[name='urine_albumin'], [name='urine_creatinine'], .albuminuria-category, [name='albuminuria_category']")
        ));

        cardCandidates.forEach((card, index) => {
            const date = normalizeDate(firstValueIn(card, [
                "[name='albuminuria_investigation_date']",
                "[name='urine_investigation_date']"
            ])) || fallbackInvestigationDate();
            let category = normalizeAlbuminuriaCategory(firstValueIn(card, [
                "[name='albuminuria_category']",
                ".albuminuria-category",
                "[data-albuminuria-category]"
            ]));
            if (!category) {
                category = albuminuriaCategoryFromAcr(firstValueIn(card, [
                    "[name='albumin_creatinine_ratio']",
                    "[name='acr']",
                    ".albuminuria-acr"
                ]));
            }
            if (!category) {
                const albumin = firstValueIn(card, ["[name='urine_albumin']", "[name='albumin']"]);
                const creatinine = firstValueIn(card, ["[name='urine_creatinine']"]);
                if (albumin && creatinine) {
                    const acr = calculateAcr(
                        albumin,
                        creatinine,
                        firstValueIn(card, ["[name='urine_creatinine_unit']", "[name='albuminuria_creatinine_unit']"])
                    );
                    category = albuminuriaCategoryFromAcr(acr);
                }
            }
            if (category) {
                sources.push({
                    index,
                    source: "current_appointment",
                    date,
                    category,
                    uid: `albuminuria-card-${index}`
                });
            }
        });

        if (sources.length) {
            return sources;
        }

        const dateValues = firstNonEmptyValues([
            "[name='albuminuria_investigation_date']",
            "[name='urine_investigation_date']"
        ]);
        const categoryValues = firstNonEmptyValues([
            "[name='albuminuria_category']",
            ".albuminuria-category",
            "#albuminuria_category_row .table-success input",
            "#albuminuria_category_row td:not(:first-child) input",
            "[data-albuminuria-column][data-field='category']",
            "[data-albuminuria-category]"
        ]);
        const acrValues = firstNonEmptyValues([
            "[name='albumin_creatinine_ratio']",
            "[name='acr']",
            ".albuminuria-acr",
            "#albuminuria_acr_row .table-success input",
            "[data-albuminuria-column][data-field='acr']"
        ]);
        const albuminValues = firstNonEmptyValues([
            "[name='urine_albumin']",
            "[name='albumin']"
        ]);
        const creatinineValues = firstNonEmptyValues([
            "[name='urine_creatinine']"
        ]);
        const unitValues = firstNonEmptyValues([
            "[name='urine_creatinine_unit']",
            "[name='albuminuria_creatinine_unit']"
        ]);

        const count = Math.max(dateValues.length, categoryValues.length, acrValues.length, albuminValues.length, creatinineValues.length);
        for (let index = 0; index < count; index += 1) {
            const date = normalizeDate(dateValues[index] || "") || fallbackInvestigationDate();
            let category = normalizeAlbuminuriaCategory(categoryValues[index] || "");
            if (!category) {
                category = albuminuriaCategoryFromAcr(acrValues[index] || "");
            }
            if (!category && albuminValues[index] && creatinineValues[index]) {
                const acr = calculateAcr(albuminValues[index], creatinineValues[index], unitValues[index] || radioGroupValueByIndex("urine_creatinine_unit", index));
                category = albuminuriaCategoryFromAcr(acr);
            }
            if (category) {
                sources.push({
                    index,
                    source: "current_appointment",
                    date,
                    category,
                    uid: `albuminuria-row-${index}`
                });
            }
        }
        return sources;
    }

    function latestBeforeOrOn(sources, date) {
        const normalizedDate = normalizeDate(date);
        const suitable = sources
            .filter((source) => source.date && (!normalizedDate || source.date <= normalizedDate))
            .sort((a, b) => b.date.localeCompare(a.date));
        return suitable[0] || null;
    }

    function pairKey(gfrSource, albuminuriaSource) {
        return [
            normalizeDate(gfrSource.date),
            normalizeGfrCategory(gfrSource.category),
            normalizeDate(albuminuriaSource.date),
            normalizeAlbuminuriaCategory(albuminuriaSource.category)
        ].join("|");
    }

    function rowKey(rowIndex, gfrSource, albuminuriaSource) {
        return [
            "row",
            String(rowIndex),
            pairKey(gfrSource, albuminuriaSource)
        ].join("|");
    }

    function calculateRisk(gfrCategory, albuminuriaCategory) {
        const normalizedGfr = normalizeGfrCategory(gfrCategory);
        const normalizedAlbuminuria = normalizeAlbuminuriaCategory(albuminuriaCategory);
        if (!RISK_MATRIX[normalizedGfr]) {
            return "";
        }
        return RISK_MATRIX[normalizedGfr][normalizedAlbuminuria] || "";
    }

    function riskPhrase(gfrCategory, albuminuriaCategory, riskLevel) {
        const normalizedGfr = normalizeGfrCategory(gfrCategory);
        const normalizedAlbuminuria = normalizeAlbuminuriaCategory(albuminuriaCategory);
        const combined = `${normalizedGfr}${normalizedAlbuminuria}`;
        const text = RISK_TEXT[riskLevel] || UNKNOWN_RISK_TEXT;
        return `По KDIGO: ${combined} — ${text}.`;
    }

    function sourceMeta(gfrSource, albuminuriaSource) {
        return `СКФ: ${gfrSource.category} от ${formatRuDate(gfrSource.date)}; альбуминурия: ${albuminuriaSource.category} от ${formatRuDate(albuminuriaSource.date)}`;
    }

    function buildCalculatedAssessment(gfrSource, albuminuriaSource, rowIndex) {
        const interval = daysBetween(gfrSource.date, albuminuriaSource.date);
        const key = pairKey(gfrSource, albuminuriaSource);
        const uniqueRowKey = rowKey(rowIndex, gfrSource, albuminuriaSource);
        if (interval !== null && interval > MAX_INTERVAL_DAYS) {
            return {
                key: `stale|${uniqueRowKey}`,
                status: "stale",
                rowIndex,
                text: STALE_TEXT,
                meta: sourceMeta(gfrSource, albuminuriaSource),
                riskLevel: ""
            };
        }
        const riskLevel = calculateRisk(gfrSource.category, albuminuriaSource.category);
        if (!riskLevel) {
            return {
                key: `unknown|${uniqueRowKey}`,
                status: "unknown",
                rowIndex,
                text: UNKNOWN_RISK_TEXT,
                meta: sourceMeta(gfrSource, albuminuriaSource),
                riskLevel: ""
            };
        }
        return {
            key: uniqueRowKey,
            pairKey: key,
            rowKey: uniqueRowKey,
            status: "calculated",
            rowIndex,
            text: riskPhrase(gfrSource.category, albuminuriaSource.category, riskLevel),
            meta: sourceMeta(gfrSource, albuminuriaSource),
            riskLevel
        };
    }

    function missingAssessment(kind, rowIndex, source) {
        const sourceSuffix = source ? `|${source.date}|${source.category}` : "";
        if (kind === "albuminuria") {
            return {
                key: `missing-albuminuria|${rowIndex}${sourceSuffix}`,
                status: "missing",
                rowIndex,
                text: MISSING_ALBUMINURIA_TEXT,
                meta: source ? `СКФ: ${source.category} от ${formatRuDate(source.date)}` : "",
                riskLevel: ""
            };
        }
        if (kind === "gfr") {
            return {
                key: `missing-gfr|${rowIndex}${sourceSuffix}`,
                status: "missing",
                rowIndex,
                text: MISSING_GFR_TEXT,
                meta: source ? `Альбуминурия: ${source.category} от ${formatRuDate(source.date)}` : "",
                riskLevel: ""
            };
        }
        return {
            key: "missing-both",
            status: "missing",
            rowIndex: 0,
            text: EMPTY_BOTH_TEXT,
            meta: "",
            riskLevel: ""
        };
    }

    function compactMissingAssessments(assessments) {
        const calculatedLike = assessments.filter((item) => item.status === "calculated" || item.status === "stale" || item.status === "unknown");
        if (calculatedLike.length) {
            return assessments;
        }
        return assessments.length ? [assessments[0]] : [missingAssessment("both", 0, null)];
    }

    function buildCurrentVisitAssessments() {
        const currentGfr = readCurrentGfrSources();
        const currentAlbuminuria = readCurrentAlbuminuriaSources();
        const previousGfr = readPrevious("kdigoPreviousGfrData", normalizeGfrCategory);
        const previousAlbuminuria = readPrevious("kdigoPreviousAlbuminuriaData", normalizeAlbuminuriaCategory);
        const assessments = [];

        if (!currentGfr.length && !currentAlbuminuria.length) {
            return [missingAssessment("both", 0, null)];
        }

        if (currentGfr.length && currentAlbuminuria.length) {
            const rowsCount = Math.max(currentGfr.length, currentAlbuminuria.length);
            for (let index = 0; index < rowsCount; index += 1) {
                const gfrSource = currentGfr[index] || currentGfr[0];
                const albuminuriaSource = currentAlbuminuria[index] || currentAlbuminuria[0];
                assessments.push(buildCalculatedAssessment(gfrSource, albuminuriaSource, index));
            }
            return assessments;
        }

        if (currentGfr.length) {
            currentGfr.forEach((gfrSource, index) => {
                const albuminuriaSource = latestBeforeOrOn(previousAlbuminuria, gfrSource.date);
                if (!albuminuriaSource) {
                    assessments.push(missingAssessment("albuminuria", index, gfrSource));
                    return;
                }
                assessments.push(buildCalculatedAssessment(gfrSource, albuminuriaSource, index));
            });
            return compactMissingAssessments(assessments);
        }

        currentAlbuminuria.forEach((albuminuriaSource, index) => {
            const gfrSource = latestBeforeOrOn(previousGfr, albuminuriaSource.date);
            if (!gfrSource) {
                assessments.push(missingAssessment("gfr", index, albuminuriaSource));
                return;
            }
            assessments.push(buildCalculatedAssessment(gfrSource, albuminuriaSource, index));
        });
        return compactMissingAssessments(assessments);
    }

    function selectedAssessment(assessments, preferredKey) {
        const calculated = assessments.filter((item) => item.status === "calculated");
        if (preferredKey) {
            const preferred = assessments.find((item) => item.key === preferredKey);
            if (preferred) {
                return preferred;
            }
        }
        if (lastSelectedKey) {
            const previous = assessments.find((item) => item.key === lastSelectedKey);
            if (previous) {
                return previous;
            }
        }
        if (calculated.length) {
            return calculated[0];
        }
        return assessments[0];
    }

    function writeSelectedText(assessment) {
        const field = document.getElementById("kdigoSelectedConclusionText");
        if (!field) {
            return;
        }
        field.value = assessment ? assessment.text : EMPTY_BOTH_TEXT;
    }

    function writeExcludedPairs(assessments, selected) {
        const container = document.getElementById("kdigoExcludedPairsContainer");
        if (!container) {
            return;
        }
        container.innerHTML = "";
        const selectedKey = selected ? selected.key : "";
        assessments
            .filter((item) => item.status === "calculated" && item.key !== selectedKey)
            .forEach((item) => {
                const input = document.createElement("input");
                input.type = "hidden";
                input.name = "kdigo_excluded_pair";
                input.value = item.rowKey || item.key || item.pairKey;
                container.appendChild(input);
            });
    }

    function renderAssessments(preferredKey) {
        const container = document.getElementById("kdigoCurrentVisitOptions");
        if (!container) {
            return;
        }
        const assessments = buildCurrentVisitAssessments();
        const selected = selectedAssessment(assessments, preferredKey);
        lastSelectedKey = selected ? selected.key : "";

        container.innerHTML = "";
        assessments.forEach((assessment) => {
            const label = document.createElement("label");
            label.className = "kdigo-current-option";
            if (assessment.status === "calculated" && assessment.riskLevel) {
                label.classList.add(`kdigo-risk-${assessment.riskLevel}`);
            } else {
                label.classList.add("kdigo-current-option-neutral");
            }

            const radio = document.createElement("input");
            radio.type = "radio";
            radio.name = "kdigo_selected_current_option";
            radio.value = assessment.key;
            radio.checked = Boolean(selected && selected.key === assessment.key);
            radio.disabled = assessment.status !== "calculated";
            radio.addEventListener("change", () => {
                if (radio.checked) {
                    renderAssessments(assessment.key);
                }
            });

            const text = document.createElement("span");
            text.className = "kdigo-current-option-text";
            text.textContent = assessment.text;
            if (assessment.meta) {
                const meta = document.createElement("span");
                meta.className = "kdigo-current-option-meta";
                meta.textContent = assessment.meta;
                text.appendChild(meta);
            }

            label.appendChild(radio);
            label.appendChild(text);
            container.appendChild(label);
        });

        writeSelectedText(selected);
        writeExcludedPairs(assessments, selected);
    }

    function scheduleRender() {
        window.clearTimeout(renderTimer);
        renderTimer = window.setTimeout(() => renderAssessments(""), 80);
    }

    function initHistoryToggle() {
        const button = document.getElementById("kdigoToggleHistoryButton");
        const panel = document.getElementById("kdigoHistoryPanel");
        if (!button || !panel) {
            return;
        }
        button.addEventListener("click", () => {
            panel.hidden = !panel.hidden;
            button.textContent = panel.hidden
                ? "Посмотреть историю прогнозов по KDIGO"
                : "Скрыть историю прогнозов по KDIGO";
        });
    }

    function initObservers() {
        document.addEventListener("input", (event) => {
            const kdigoRoot = root();
            if (kdigoRoot && kdigoRoot.contains(event.target)) {
                return;
            }
            scheduleRender();
        }, true);

        document.addEventListener("change", (event) => {
            const kdigoRoot = root();
            if (kdigoRoot && kdigoRoot.contains(event.target)) {
                return;
            }
            scheduleRender();
        }, true);

        const observer = new MutationObserver((mutations) => {
            const kdigoRoot = root();
            if (kdigoRoot && mutations.every((mutation) => kdigoRoot.contains(mutation.target))) {
                return;
            }
            scheduleRender();
        });
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true,
            attributes: true
        });
    }

    function init() {
        if (!root()) {
            return;
        }
        initHistoryToggle();
        initObservers();
        renderAssessments("");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
