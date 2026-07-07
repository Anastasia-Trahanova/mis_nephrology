/*
Назначение файла: live-расчёт прогноза KDIGO в формах нового пациента и повторного приёма.

Что делает этот файл:
- читает текущие значения СКФ/категории СКФ прямо из заполняемой формы до сохранения в БД;
- читает текущие значения альбуминурии/категории A1-A3 прямо из формы до сохранения в БД;
- если в текущем приёме есть только СКФ, берёт последнюю подходящую альбуминурию из прошлых данных пациента;
- если в текущем приёме есть только альбуминурия, берёт последнюю подходящую СКФ из прошлых данных пациента;
- если в текущем приёме нет ни СКФ, ни альбуминурии, показывает одну нейтральную фразу о невозможности оценки;
- при изменении полей формы автоматически пересчитывает прогноз без кнопки «Обновить»;
- если вариантов несколько, даёт врачу выбрать один radio-кружочком;
- выбранную фразу записывает в textarea «Формулировка для заключения»;
- для невыбранных рассчитанных вариантов создаёт hidden-поля kdigo_excluded_pair, чтобы backend не сохранял шум;
- раскрывает/скрывает историю прошлых прогнозов по кнопке.

Как это работает:
- текущий приём никогда не строится как полная матрица СКФ × альбуминурия;
- один текущий показатель СКФ даёт один вариант прогноза;
- две текущие СКФ дают два варианта прогноза;
- если текущих альбуминурий несколько, они сопоставляются с СКФ по порядку строк, а не создают все пересечения;
- старые данные используются только как fallback для отсутствующего показателя, но не создают прогнозы сами по себе при открытии формы.

Что можно редактировать:
- точные короткие фразы для врача;
- правила выбора текущей альбуминурии для текущей СКФ;
- CSS-классы вариантов.

Что не редактировать здесь:
- серверное сохранение ckd_prognosis_results;
- SQL-запросы;
- расчёт eGFR и ACR, который выполняется существующими скриптами формы.
*/
(function () {
  "use strict";

  if (window.__kdigoLiveCurrentVisitV2Initialized) return;
  window.__kdigoLiveCurrentVisitV2Initialized = true;

  const RISK_MATRIX = {
    "С1": { A1: ["low", "низкий риск"], A2: ["moderate", "умеренно повышенный риск"], A3: ["high", "высокий риск"] },
    "С2": { A1: ["low", "низкий риск"], A2: ["moderate", "умеренно повышенный риск"], A3: ["high", "высокий риск"] },
    "С3а": { A1: ["moderate", "умеренно повышенный риск"], A2: ["high", "высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С3б": { A1: ["high", "высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С4": { A1: ["very_high", "очень высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С5": { A1: ["very_high", "очень высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] }
  };

  const MAX_INTERVAL_BY_RISK = {
    low: 365,
    moderate: 180,
    high: 90,
    very_high: 90
  };

  const RISK_ORDER = { low: 1, moderate: 2, high: 3, very_high: 4 };
  const EMPTY_TEXT = "Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии и СКФ не предоставлены.";

  function readJsonScript(id) {
    const node = document.getElementById(id);
    if (!node) return [];
    try {
      const parsed = JSON.parse(node.textContent || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function normalizeNumber(value) {
    if (value === null || value === undefined) return null;
    const text = String(value).trim().replace(/\s+/g, "").replace(",", ".");
    if (!text) return null;
    const number = Number(text);
    return Number.isFinite(number) ? number : null;
  }

  function normalizeDate(value) {
    if (!value) return "";
    const text = String(value).trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
    const ru = text.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (ru) return `${ru[3]}-${ru[2]}-${ru[1]}`;
    return "";
  }

  function parseIsoDate(value) {
    const normalized = normalizeDate(value);
    if (!normalized) return null;
    const parts = normalized.split("-").map(Number);
    return new Date(parts[0], parts[1] - 1, parts[2]);
  }

  function daysBetween(a, b) {
    const dateA = parseIsoDate(a);
    const dateB = parseIsoDate(b);
    if (!dateA || !dateB) return null;
    return Math.abs(Math.round((dateA.getTime() - dateB.getTime()) / 86400000));
  }

  function formatRuDate(value) {
    const normalized = normalizeDate(value);
    if (!normalized) return "—";
    const [year, month, day] = normalized.split("-");
    return `${day}.${month}.${year}`;
  }

  function normalizeGfrCategory(value) {
    if (!value) return "";
    let text = String(value).trim();
    text = text.replace(/^G/i, "С").replace(/^C/, "С");
    text = text.replace("3A", "3а").replace("3a", "3а");
    text = text.replace("3B", "3б").replace("3b", "3б");
    return ["С1", "С2", "С3а", "С3б", "С4", "С5"].includes(text) ? text : "";
  }

  function gfrCategoryFromEgfr(value) {
    const egfr = normalizeNumber(value);
    if (egfr === null) return "";
    if (egfr >= 90) return "С1";
    if (egfr >= 60) return "С2";
    if (egfr >= 45) return "С3а";
    if (egfr >= 30) return "С3б";
    if (egfr >= 15) return "С4";
    return "С5";
  }

  function normalizeAlbuminuriaCategory(value) {
    if (!value) return "";
    const text = String(value).trim().toUpperCase().replace("А", "A");
    return ["A1", "A2", "A3"].includes(text) ? text : "";
  }

  function albuminuriaCategoryFromAcr(value) {
    const acr = normalizeNumber(value);
    if (acr === null) return "";
    if (acr < 3) return "A1";
    if (acr <= 30) return "A2";
    return "A3";
  }

  function calculateRisk(gfrCategory, albuminuriaCategory) {
    const gfr = normalizeGfrCategory(gfrCategory);
    const albuminuria = normalizeAlbuminuriaCategory(albuminuriaCategory);
    if (!gfr || !albuminuria) return null;
    const risk = RISK_MATRIX[gfr] && RISK_MATRIX[gfr][albuminuria];
    if (!risk) return null;
    return {
      gfrCategory: gfr,
      albuminuriaCategory: albuminuria,
      combinedCategory: `${gfr}${albuminuria}`,
      level: risk[0],
      text: risk[1]
    };
  }

  function monthWord(months) {
    const lastTwo = months % 100;
    if (lastTwo >= 11 && lastTwo <= 14) return "месяцев";
    const last = months % 10;
    if (last === 1) return "месяц";
    if (last >= 2 && last <= 4) return "месяца";
    return "месяцев";
  }

  function elapsedMonthsText(intervalDays) {
    if (!Number.isFinite(intervalDays)) return "давно";
    const months = Math.max(1, Math.round(intervalDays / 30.44));
    return `${months} ${monthWord(months)} назад`;
  }

  function missingPhrase(missing) {
    if (missing === "both") return EMPTY_TEXT;
    if (missing === "gfr") return "Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по СКФ не предоставлены.";
    return "Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии не предоставлены.";
  }

  function stalePhrase(source, intervalDays) {
    if (source === "gfr") {
      return `Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по СКФ были получены ${elapsedMonthsText(intervalDays)}, рекомендовано повторить исследование.`;
    }
    return `Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии были получены ${elapsedMonthsText(intervalDays)}, рекомендовано повторить исследование.`;
  }

  function riskPhrase(risk, gfrDate, albuminuriaDate) {
    return `По KDIGO: ${risk.combinedCategory} — ${risk.text} прогрессирования ХБП и развития ХПН (рассчитано по СКФ от ${formatRuDate(gfrDate)}, альбуминурия от ${formatRuDate(albuminuriaDate)})`;
  }

  function pairKey(gfrDate, gfrCategory, albuminuriaDate, albuminuriaCategory) {
    return [normalizeDate(gfrDate), normalizeGfrCategory(gfrCategory), normalizeDate(albuminuriaDate), normalizeAlbuminuriaCategory(albuminuriaCategory)].join("|");
  }

  function getEditableCards(containerSelector, dateName, valueSelectors) {
    const container = document.querySelector(containerSelector);
    if (!container) return [];

    const dateInputs = Array.from(container.querySelectorAll(`input[name="${dateName}"]`));
    return dateInputs
      .map((dateInput) => {
        const card = dateInput.closest(".lab-analysis-card, .biochemistry-block, .albuminuria-block, .card, .border, div") || dateInput.parentElement;
        return { card, dateInput };
      })
      .filter(({ card }) => card && valueSelectors.some((selector) => card.querySelector(selector)));
  }

  function dedupeSources(sources) {
    const seen = new Set();
    const result = [];
    sources.forEach((item) => {
      const key = `${item.date}|${item.category}`;
      if (seen.has(key)) return;
      seen.add(key);
      result.push(item);
    });
    return result;
  }

  function readCurrentGfrSources() {
    const cards = getEditableCards(
      "#biochemistryContainer",
      "biochemistry_investigation_date",
      [".biochemistry-egfr", ".biochemistry-stage"]
    );

    const result = cards.map(({ card, dateInput }, index) => {
      const date = normalizeDate(dateInput.value);
      const stageInput = card.querySelector(".biochemistry-stage");
      const egfrInput = card.querySelector(".biochemistry-egfr");
      const category = normalizeGfrCategory(stageInput && stageInput.value) || gfrCategoryFromEgfr(egfrInput && egfrInput.value);
      return date && category ? { date, category, index, source: "current_appointment" } : null;
    }).filter(Boolean);

    return dedupeSources(result);
  }

  function readCurrentAlbuminuriaSources() {
    const cards = getEditableCards(
      "#albuminuriaContainer",
      "albuminuria_investigation_date",
      [".albuminuria-category", ".albuminuria-acr"]
    );

    const result = cards.map(({ card, dateInput }, index) => {
      const date = normalizeDate(dateInput.value);
      const categoryInput = card.querySelector(".albuminuria-category");
      const acrInput = card.querySelector(".albuminuria-acr");
      const category = normalizeAlbuminuriaCategory(categoryInput && categoryInput.value) || albuminuriaCategoryFromAcr(acrInput && acrInput.value);
      return date && category ? { date, category, index, source: "current_appointment" } : null;
    }).filter(Boolean);

    return dedupeSources(result);
  }

  function loadPreviousGfrSources() {
    return readJsonScript("kdigoPreviousGfrData")
      .map((item) => ({ date: normalizeDate(item.date), category: normalizeGfrCategory(item.category), source: "previous_appointment" }))
      .filter((item) => item.date && item.category);
  }

  function loadPreviousAlbuminuriaSources() {
    return readJsonScript("kdigoPreviousAlbuminuriaData")
      .map((item) => ({ date: normalizeDate(item.date), category: normalizeAlbuminuriaCategory(item.category), source: "previous_appointment" }))
      .filter((item) => item.date && item.category);
  }

  function latestPreviousBeforeOrOn(sources, targetDate) {
    const target = parseIsoDate(targetDate);
    if (!target) return null;
    return sources
      .filter((item) => {
        const date = parseIsoDate(item.date);
        return date && date <= target;
      })
      .sort((a, b) => parseIsoDate(b.date) - parseIsoDate(a.date))[0] || null;
  }

  function albuminuriaForGfr(gfrSource, currentAlbuminuria, previousAlbuminuria) {
    if (currentAlbuminuria.length) {
      return currentAlbuminuria[gfrSource.index] || currentAlbuminuria[0] || null;
    }
    return latestPreviousBeforeOrOn(previousAlbuminuria, gfrSource.date);
  }

  function gfrForAlbuminuria(albuminuriaSource, previousGfr) {
    return latestPreviousBeforeOrOn(previousGfr, albuminuriaSource.date);
  }

  function assessmentFromPair(gfrSource, albuminuriaSource, staleSourceWhenOld) {
    const risk = calculateRisk(gfrSource.category, albuminuriaSource.category);
    if (!risk) return null;

    const intervalDays = daysBetween(gfrSource.date, albuminuriaSource.date);
    const maxDays = MAX_INTERVAL_BY_RISK[risk.level] || 90;
    const key = pairKey(gfrSource.date, risk.gfrCategory, albuminuriaSource.date, risk.albuminuriaCategory);

    if (intervalDays === null || intervalDays > maxDays) {
      return {
        status: "stale",
        key,
        level: null,
        text: stalePhrase(staleSourceWhenOld, intervalDays)
      };
    }

    return {
      status: "calculated",
      key,
      level: risk.level,
      text: riskPhrase(risk, gfrSource.date, albuminuriaSource.date)
    };
  }

  function buildCurrentVisitAssessments() {
    const currentGfr = readCurrentGfrSources();
    const currentAlbuminuria = readCurrentAlbuminuriaSources();
    const previousGfr = loadPreviousGfrSources();
    const previousAlbuminuria = loadPreviousAlbuminuriaSources();
    const assessments = [];

    if (!currentGfr.length && !currentAlbuminuria.length) {
      return [{ status: "missing", key: "missing-both", level: null, text: missingPhrase("both") }];
    }

    if (currentGfr.length) {
      currentGfr.forEach((gfr) => {
        const albuminuria = albuminuriaForGfr(gfr, currentAlbuminuria, previousAlbuminuria);
        if (!albuminuria) {
          assessments.push({ status: "missing", key: `missing-albuminuria-${gfr.date}-${gfr.category}`, level: null, text: missingPhrase("albuminuria") });
          return;
        }
        const assessment = assessmentFromPair(gfr, albuminuria, "albuminuria");
        if (assessment) assessments.push(assessment);
      });
      return dedupeAssessments(assessments);
    }

    currentAlbuminuria.forEach((albuminuria) => {
      const previous = gfrForAlbuminuria(albuminuria, previousGfr);
      if (!previous) {
        assessments.push({ status: "missing", key: `missing-gfr-${albuminuria.date}-${albuminuria.category}`, level: null, text: missingPhrase("gfr") });
        return;
      }
      const assessment = assessmentFromPair(previous, albuminuria, "gfr");
      if (assessment) assessments.push(assessment);
    });

    return dedupeAssessments(assessments);
  }

  function dedupeAssessments(assessments) {
    const seen = new Set();
    const result = [];
    assessments.forEach((assessment) => {
      const key = assessment.key || assessment.text;
      if (seen.has(key)) return;
      seen.add(key);
      result.push(assessment);
    });
    return result;
  }

  function bestCalculatedKey(assessments) {
    let best = null;
    assessments.forEach((assessment) => {
      if (assessment.status !== "calculated") return;
      if (!best || (RISK_ORDER[assessment.level] || 0) > (RISK_ORDER[best.level] || 0)) {
        best = assessment;
      }
    });
    return best ? best.key : "";
  }

  function selectedRadioValue() {
    const selected = document.querySelector('input[name="kdigo_selected_current_option"]:checked');
    return selected ? selected.value : "";
  }

  function writeExcludedPairs(assessments, selectedKey) {
    const container = document.getElementById("kdigoHiddenFields");
    if (!container) return;
    container.innerHTML = "";

    assessments.forEach((assessment) => {
      if (assessment.status !== "calculated" || !assessment.key || assessment.key === selectedKey) return;
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "kdigo_excluded_pair";
      input.value = assessment.key;
      container.appendChild(input);
    });
  }

  function renderAssessments(preferredSelectedKey) {
    const optionsContainer = document.getElementById("kdigoCurrentVisitOptions");
    const conclusionText = document.getElementById("kdigoSelectedConclusionText");
    if (!optionsContainer || !conclusionText) return;

    const previousSelectedKey = preferredSelectedKey || selectedRadioValue();
    const assessments = buildCurrentVisitAssessments();
    const hasCalculated = assessments.some((item) => item.status === "calculated");

    let selectedKey = "";
    if (hasCalculated && assessments.some((item) => item.status === "calculated" && item.key === previousSelectedKey)) {
      selectedKey = previousSelectedKey;
    } else if (hasCalculated) {
      selectedKey = bestCalculatedKey(assessments);
    } else {
      selectedKey = assessments[0] ? assessments[0].key : "missing-both";
    }

    optionsContainer.innerHTML = "";

    assessments.forEach((assessment) => {
      const row = document.createElement("label");
      row.className = "kdigo-current-option";
      if (assessment.status === "calculated" && assessment.level) {
        row.classList.add(`kdigo-risk-${assessment.level}`);
      } else {
        row.classList.add("kdigo-current-option-neutral");
      }

      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "kdigo_selected_current_option";
      radio.value = assessment.key;
      radio.checked = assessment.key === selectedKey;
      radio.addEventListener("change", () => renderAssessments(assessment.key));
      row.appendChild(radio);

      const text = document.createElement("div");
      text.className = "kdigo-current-option-text";
      text.textContent = assessment.text;
      row.appendChild(text);

      optionsContainer.appendChild(row);
    });

    const selectedAssessment = assessments.find((item) => item.key === selectedKey) || assessments[0];
    conclusionText.value = selectedAssessment ? selectedAssessment.text : EMPTY_TEXT;
    writeExcludedPairs(assessments, selectedKey);
  }

  function toggleHistory() {
    const panel = document.getElementById("kdigoHistoryPanel");
    const button = document.getElementById("kdigoToggleHistoryButton");
    if (!panel || !button) return;
    const shouldShow = panel.hidden;
    panel.hidden = !shouldShow;
    button.textContent = shouldShow ? "Скрыть историю прогнозов по KDIGO" : "Посмотреть историю прогнозов по KDIGO";
  }

  let renderTimer = null;
  function scheduleRender() {
    if (renderTimer) window.clearTimeout(renderTimer);
    renderTimer = window.setTimeout(() => renderAssessments(), 80);
  }

  function init() {
    if (!document.getElementById("kdigoRiskPreview")) return;

    const historyButton = document.getElementById("kdigoToggleHistoryButton");
    if (historyButton) historyButton.addEventListener("click", toggleHistory);

    document.addEventListener("input", scheduleRender, true);
    document.addEventListener("change", scheduleRender, true);
    document.addEventListener("click", scheduleRender, true);

    renderAssessments();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
