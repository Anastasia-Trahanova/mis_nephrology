/*
Назначение файла: live-предпросмотр риска по KDIGO в форме приёма.

Что выполняет файл:
- читает текущие СКФ и альбуминурию из формы;
- если одного показателя нет, берёт последний подходящий показатель из истории пациента;
- показывает варианты прогноза текущего приёма через radio-выбор;
- записывает в поле заключения только выбранную врачом фразу;
- передаёт backend скрытые kdigo_excluded_pair для невыбранных рассчитанных вариантов;
- раскрывает/скрывает историю прошлых прогнозов по KDIGO.

Что редактировать здесь:
- правила чтения полей формы;
- точные короткие фразы для врача;
- поведение кнопок «Обновить» и «Посмотреть историю».

Что не редактировать здесь:
- серверное сохранение ckd_prognosis_results;
- медицинскую матрицу KDIGO на backend;
- расчёт ACR/eGFR, который уже делает существующий код формы.
*/

(function () {
  "use strict";

  if (window.__kdigoRiskPreviewLoaded) {
    return;
  }
  window.__kdigoRiskPreviewLoaded = true;

  const RISK_MATRIX = {
    "С1": { A1: ["low", "низкий риск"], A2: ["moderate", "умеренно повышенный риск"], A3: ["high", "высокий риск"] },
    "С2": { A1: ["low", "низкий риск"], A2: ["moderate", "умеренно повышенный риск"], A3: ["high", "высокий риск"] },
    "С3а": { A1: ["moderate", "умеренно повышенный риск"], A2: ["high", "высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С3б": { A1: ["high", "высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С4": { A1: ["very_high", "очень высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С5": { A1: ["very_high", "очень высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] },
  };

  const MAX_INTERVAL_BY_RISK = {
    low: 365,
    moderate: 180,
    high: 90,
    very_high: 90,
  };

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
    if (/^\d{2}\.\d{2}\.\d{4}$/.test(text)) {
      const [day, month, year] = text.split(".");
      return `${year}-${month}-${day}`;
    }
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

  function dateDistance(a, b) {
    const dateA = parseIsoDate(a);
    const dateB = parseIsoDate(b);
    if (!dateA || !dateB) return Number.MAX_SAFE_INTEGER;
    return Math.abs(dateA.getTime() - dateB.getTime());
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
    text = text.replace(/^G/i, "С").replace(/^C/i, "С");
    text = text.replace("3A", "3а").replace("3a", "3а").replace("3А", "3а");
    text = text.replace("3B", "3б").replace("3b", "3б").replace("3Б", "3б");
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
    const row = RISK_MATRIX[gfr] || {};
    const risk = row[albuminuria];
    if (!risk) return null;
    return {
      gfrCategory: gfr,
      albuminuriaCategory: albuminuria,
      combinedCategory: `${gfr}${albuminuria}`,
      level: risk[0],
      text: risk[1],
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

  function pairKey(gfrDate, gfrCategory, albuminuriaDate, albuminuriaCategory) {
    return [
      normalizeDate(gfrDate),
      normalizeGfrCategory(gfrCategory),
      normalizeDate(albuminuriaDate),
      normalizeAlbuminuriaCategory(albuminuriaCategory),
    ].join("|");
  }

  function riskPhrase(risk, gfrDate, albuminuriaDate) {
    return `По KDIGO: ${risk.combinedCategory} — ${risk.text} прогрессирования ХБП и развития ХПН (рассчитано по СКФ от ${formatRuDate(gfrDate)}, альбуминурия от ${formatRuDate(albuminuriaDate)})`;
  }

  function missingPhrase(missing) {
    if (missing === "both") {
      return "Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии и СКФ не предоставлены.";
    }
    if (missing === "gfr") {
      return "Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по СКФ не предоставлены.";
    }
    return "Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии не предоставлены.";
  }

  function stalePhrase(source, intervalDays) {
    if (source === "gfr") {
      return `Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по СКФ были получены ${elapsedMonthsText(intervalDays)}, рекомендовано повторить исследование.`;
    }
    return `Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии были получены ${elapsedMonthsText(intervalDays)}, рекомендовано повторить исследование.`;
  }

  function readCurrentGfrSources() {
    const result = [];
    const cards = Array.from(document.querySelectorAll("#biochemistryContainer .lab-analysis-card, #biochemistryContainer .biochemistry-block"));
    cards.forEach((card) => {
      const date = normalizeDate(card.querySelector('[name="biochemistry_investigation_date"]')?.value);
      const stageInput = card.querySelector(".biochemistry-stage");
      const egfrInput = card.querySelector(".biochemistry-egfr");
      const category = normalizeGfrCategory(stageInput?.value) || gfrCategoryFromEgfr(egfrInput?.value);
      if (date && category) {
        result.push({ date, category, source: "current_appointment" });
      }
    });
    return deduplicateSources(result);
  }

  function readCurrentAlbuminuriaSources() {
    const result = [];
    const cards = Array.from(document.querySelectorAll("#albuminuriaContainer .albuminuria-block, #albuminuriaContainer .lab-analysis-card"));
    cards.forEach((card) => {
      const date = normalizeDate(card.querySelector('[name="albuminuria_investigation_date"]')?.value);
      const categoryInput = card.querySelector(".albuminuria-category");
      const acrInput = card.querySelector(".albuminuria-acr");
      const category = normalizeAlbuminuriaCategory(categoryInput?.value) || albuminuriaCategoryFromAcr(acrInput?.value);
      if (date && category) {
        result.push({ date, category, source: "current_appointment" });
      }
    });
    return deduplicateSources(result);
  }

  function loadPreviousGfrSources() {
    return readJsonScript("kdigoPreviousGfrData")
      .map((item) => ({
        date: normalizeDate(item.date),
        category: normalizeGfrCategory(item.category),
        source: "previous_appointment",
      }))
      .filter((item) => item.date && item.category);
  }

  function loadPreviousAlbuminuriaSources() {
    return readJsonScript("kdigoPreviousAlbuminuriaData")
      .map((item) => ({
        date: normalizeDate(item.date),
        category: normalizeAlbuminuriaCategory(item.category),
        source: "previous_appointment",
      }))
      .filter((item) => item.date && item.category);
  }

  function deduplicateSources(sources) {
    const result = [];
    const seen = new Set();
    sources.forEach((source) => {
      const key = `${source.date}|${source.category}`;
      if (seen.has(key)) return;
      seen.add(key);
      result.push(source);
    });
    return result;
  }

  function latestPreviousBeforeOrOn(sources, targetDate) {
    const target = parseIsoDate(targetDate);
    if (!target) return null;
    return sources
      .filter((item) => normalizeDate(item.date) && parseIsoDate(item.date) <= target)
      .sort((a, b) => parseIsoDate(b.date) - parseIsoDate(a.date))[0] || null;
  }

  function closestCurrentSource(sources, targetDate) {
    if (!sources.length) return null;
    return [...sources].sort((a, b) => dateDistance(a.date, targetDate) - dateDistance(b.date, targetDate))[0];
  }

  function buildAssessment(gfrSource, albuminuriaSource, staleSourceWhenOld) {
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
        text: stalePhrase(staleSourceWhenOld, intervalDays),
      };
    }
    return {
      status: "calculated",
      key,
      level: risk.level,
      text: riskPhrase(risk, gfrSource.date, albuminuriaSource.date),
      gfrDate: gfrSource.date,
      gfrCategory: risk.gfrCategory,
      albuminuriaDate: albuminuriaSource.date,
      albuminuriaCategory: risk.albuminuriaCategory,
    };
  }

  function buildCurrentVisitOptions() {
    const currentGfr = readCurrentGfrSources();
    const currentAlbuminuria = readCurrentAlbuminuriaSources();
    const previousGfr = loadPreviousGfrSources();
    const previousAlbuminuria = loadPreviousAlbuminuriaSources();
    const options = [];

    if (currentGfr.length) {
      currentGfr.forEach((gfr) => {
        const albuminuria = closestCurrentSource(currentAlbuminuria, gfr.date) || latestPreviousBeforeOrOn(previousAlbuminuria, gfr.date);
        if (!albuminuria) {
          options.push({ status: "missing", level: null, text: missingPhrase("albuminuria") });
          return;
        }
        const staleSource = albuminuria.source === "previous_appointment" ? "albuminuria" : "albuminuria";
        const option = buildAssessment(gfr, albuminuria, staleSource);
        if (option) options.push(option);
      });
    } else if (currentAlbuminuria.length) {
      currentAlbuminuria.forEach((albuminuria) => {
        const gfr = latestPreviousBeforeOrOn(previousGfr, albuminuria.date);
        if (!gfr) {
          options.push({ status: "missing", level: null, text: missingPhrase("gfr") });
          return;
        }
        const option = buildAssessment(gfr, albuminuria, "gfr");
        if (option) options.push(option);
      });
    } else {
      options.push({ status: "missing", level: null, text: missingPhrase("both") });
    }

    const deduplicated = [];
    const seen = new Set();
    options.forEach((option) => {
      const key = option.key || option.text;
      if (seen.has(key)) return;
      seen.add(key);
      deduplicated.push(option);
    });
    return deduplicated;
  }

  function selectedPairValue() {
    return document.querySelector('input[name="kdigo_current_choice"]:checked')?.value || "";
  }

  function setSelectedPair(value) {
    const selectedInput = document.getElementById("kdigoSelectedPair");
    if (selectedInput) selectedInput.value = value || "";
  }

  function updateExcludedPairs(options, selectedKey) {
    const container = document.getElementById("kdigoExcludedPairs");
    if (!container) return;
    container.innerHTML = "";
    options
      .filter((option) => option.status === "calculated" && option.key && option.key !== selectedKey)
      .forEach((option) => {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "kdigo_excluded_pair";
        input.value = option.key;
        container.appendChild(input);
      });
  }

  function updateConclusion(text) {
    const textarea = document.getElementById("kdigoConclusionText");
    if (textarea) textarea.value = text || "";
  }

  function updateBlockColor(level) {
    const block = document.getElementById("kdigoRiskPreview");
    if (!block) return;
    block.classList.remove(
      "kdigo-risk-empty",
      "kdigo-risk-low",
      "kdigo-risk-moderate",
      "kdigo-risk-high",
      "kdigo-risk-very_high"
    );
    block.classList.add(level ? `kdigo-risk-${level}` : "kdigo-risk-empty");
  }

  function renderCurrentVisitOptions(preferredSelectedKey) {
    const container = document.getElementById("kdigoCurrentVisitOptions");
    if (!container) return;

    const options = buildCurrentVisitOptions();
    const calculatedOptions = options.filter((option) => option.status === "calculated" && option.key);
    let selectedKey = preferredSelectedKey || selectedPairValue();

    if (!calculatedOptions.some((option) => option.key === selectedKey)) {
      selectedKey = calculatedOptions[0]?.key || "";
    }

    container.innerHTML = "";

    if (!calculatedOptions.length) {
      const option = options[0] || { text: missingPhrase("both"), level: null };
      const row = document.createElement("div");
      row.className = "kdigo-risk-line kdigo-risk-line-empty";
      row.textContent = option.text;
      container.appendChild(row);
      updateConclusion(option.text);
      setSelectedPair("");
      updateExcludedPairs(options, "");
      updateBlockColor(null);
      return;
    }

    calculatedOptions.forEach((option, index) => {
      const label = document.createElement("label");
      label.className = `kdigo-choice kdigo-choice-${option.level}`;

      const input = document.createElement("input");
      input.type = "radio";
      input.name = "kdigo_current_choice";
      input.value = option.key;
      input.checked = option.key === selectedKey;
      input.addEventListener("change", () => {
        renderCurrentVisitOptions(option.key);
      });

      const text = document.createElement("span");
      text.textContent = option.text;

      label.appendChild(input);
      label.appendChild(text);
      container.appendChild(label);
    });

    const selectedOption = calculatedOptions.find((option) => option.key === selectedKey) || calculatedOptions[0];
    updateConclusion(selectedOption.text);
    setSelectedPair(selectedOption.key);
    updateExcludedPairs(calculatedOptions, selectedOption.key);
    updateBlockColor(selectedOption.level);
  }

  function toggleHistoryPanel() {
    const panel = document.getElementById("kdigoHistoryPanel");
    const button = document.getElementById("kdigoHistoryToggleButton");
    if (!panel || !button) return;
    const willShow = panel.classList.contains("d-none");
    panel.classList.toggle("d-none", !willShow);
    button.textContent = willShow
      ? "Скрыть историю прогнозов по KDIGO"
      : "Посмотреть историю прогнозов по KDIGO";
  }

  function scheduleRender() {
    window.setTimeout(() => renderCurrentVisitOptions(), 0);
  }

  function init() {
    if (!document.getElementById("kdigoRiskPreview")) return;

    const refreshButton = document.getElementById("kdigoRefreshButton");
    if (refreshButton) {
      refreshButton.addEventListener("click", () => renderCurrentVisitOptions());
    }

    const historyButton = document.getElementById("kdigoHistoryToggleButton");
    if (historyButton) {
      historyButton.addEventListener("click", toggleHistoryPanel);
    }

    document.addEventListener("input", scheduleRender, true);
    document.addEventListener("change", scheduleRender, true);
    document.addEventListener("click", function (event) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (
        target.matches('[data-add-lab="biochemistryContainer"]') ||
        target.matches('[data-add-lab="albuminuriaContainer"]') ||
        target.closest('[data-add-lab="biochemistryContainer"]') ||
        target.closest('[data-add-lab="albuminuriaContainer"]') ||
        target.matches(".remove-lab-card") ||
        target.closest(".remove-lab-card")
      ) {
        scheduleRender();
      }
    }, true);

    renderCurrentVisitOptions();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
