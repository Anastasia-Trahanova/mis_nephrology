/*
Назначение файла: live-предпросмотр риска по KDIGO в форме приёма.

Что выполняет файл:
- следит за СКФ, категорией СКФ, ACR и категорией альбуминурии;
- показывает фразы "По KDIGO: ..." перед блоком диагнозов до сохранения;
- если одного текущего показателя нет, использует последний подходящий показатель
  из истории пациента;
- если показатель устарел, показывает серое сообщение без цветовой подсветки;
- позволяет врачу нажать ✖ у лишней рассчитанной комбинации: такая пара не будет
  отправлена на backend для сохранения.

Что редактировать здесь:
- правила чтения полей формы;
- визуальное поведение live-блока;
- точные короткие фразы для врача.

Что не редактировать здесь:
- серверное сохранение ckd_prognosis_results;
- медицинскую матрицу KDIGO на backend;
- расчёт ACR/eGFR, который уже делает существующий код формы.
*/
(function () {
  "use strict";

  const riskMatrix = {
    "С1": { A1: ["low", "низкий риск"], A2: ["moderate", "умеренно повышенный риск"], A3: ["high", "высокий риск"] },
    "С2": { A1: ["low", "низкий риск"], A2: ["moderate", "умеренно повышенный риск"], A3: ["high", "высокий риск"] },
    "С3а": { A1: ["moderate", "умеренно повышенный риск"], A2: ["high", "высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С3б": { A1: ["high", "высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С4": { A1: ["very_high", "очень высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С5": { A1: ["very_high", "очень высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] }
  };

  const maxIntervalByRisk = {
    low: 365,
    moderate: 180,
    high: 90,
    very_high: 90
  };

  const riskOrder = { low: 1, moderate: 2, high: 3, very_high: 4 };

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
    if (["С1", "С2", "С3а", "С3б", "С4", "С5"].includes(text)) return text;
    return "";
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
    const risk = riskMatrix[gfr] && riskMatrix[gfr][albuminuria];
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

  function pairKey(gfrDate, gfrCategory, albuminuriaDate, albuminuriaCategory) {
    return [
      normalizeDate(gfrDate),
      normalizeGfrCategory(gfrCategory),
      normalizeDate(albuminuriaDate),
      normalizeAlbuminuriaCategory(albuminuriaCategory)
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

  function findClosestLabCard(input, selector) {
    if (!input) return null;
    return input.closest(selector) || input.closest(".lab-analysis-card");
  }

  function readCurrentGfrSources() {
    const result = [];
    const cards = Array.from(document.querySelectorAll("#biochemistryContainer .lab-analysis-card"));
    cards.forEach((card) => {
      const date = normalizeDate(card.querySelector('[name="biochemistry_investigation_date"]')?.value);
      const stageInput = card.querySelector(".biochemistry-stage");
      const egfrInput = card.querySelector(".biochemistry-egfr");
      const category = normalizeGfrCategory(stageInput?.value) || gfrCategoryFromEgfr(egfrInput?.value);
      if (date && category) {
        result.push({ date, category, source: "current_appointment" });
      }
    });
    return result;
  }

  function readCurrentAlbuminuriaSources() {
    const result = [];
    const cards = Array.from(document.querySelectorAll("#albuminuriaContainer .albuminuria-block"));
    cards.forEach((card) => {
      const date = normalizeDate(card.querySelector('[name="albuminuria_investigation_date"]')?.value);
      const categoryInput = card.querySelector(".albuminuria-category");
      const acrInput = card.querySelector(".albuminuria-acr");
      const category = normalizeAlbuminuriaCategory(categoryInput?.value) || albuminuriaCategoryFromAcr(acrInput?.value);
      if (date && category) {
        result.push({ date, category, source: "current_appointment" });
      }
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

  function currentExcludedPairs() {
    return new Set(Array.from(document.querySelectorAll('input[name="kdigo_excluded_pair"]')).map((input) => input.value));
  }

  function addExcludedPair(key) {
    const container = document.getElementById("kdigoExcludedPairs");
    if (!container || !key || currentExcludedPairs().has(key)) return;
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "kdigo_excluded_pair";
    input.value = key;
    container.appendChild(input);
  }

  function assessmentFromPair(gfrSource, albuminuriaSource, staleSourceWhenOld) {
    const risk = calculateRisk(gfrSource.category, albuminuriaSource.category);
    if (!risk) return null;
    const intervalDays = daysBetween(gfrSource.date, albuminuriaSource.date);
    const maxDays = maxIntervalByRisk[risk.level] || 90;
    const key = pairKey(gfrSource.date, risk.gfrCategory, albuminuriaSource.date, risk.albuminuriaCategory);
    if (intervalDays === null || intervalDays > maxDays) {
      return {
        status: "stale",
        key,
        text: stalePhrase(staleSourceWhenOld, intervalDays),
        level: null
      };
    }
    return {
      status: "calculated",
      key,
      level: risk.level,
      text: riskPhrase(risk, gfrSource.date, albuminuriaSource.date)
    };
  }

  function buildAssessments() {
    const currentGfr = readCurrentGfrSources();
    const currentAlbuminuria = readCurrentAlbuminuriaSources();
    const previousGfr = loadPreviousGfrSources();
    const previousAlbuminuria = loadPreviousAlbuminuriaSources();
    const assessments = [];

    if (currentGfr.length && currentAlbuminuria.length) {
      currentGfr.forEach((gfr) => {
        currentAlbuminuria.forEach((albuminuria) => {
          const assessment = assessmentFromPair(gfr, albuminuria, "albuminuria");
          if (assessment) assessments.push(assessment);
        });
      });
    } else if (currentGfr.length && !currentAlbuminuria.length) {
      currentGfr.forEach((gfr) => {
        const previous = latestPreviousBeforeOrOn(previousAlbuminuria, gfr.date);
        if (!previous) {
          assessments.push({ status: "missing", text: missingPhrase("albuminuria"), level: null });
          return;
        }
        const assessment = assessmentFromPair(gfr, previous, "albuminuria");
        if (assessment) assessments.push(assessment);
      });
    } else if (!currentGfr.length && currentAlbuminuria.length) {
      currentAlbuminuria.forEach((albuminuria) => {
        const previous = latestPreviousBeforeOrOn(previousGfr, albuminuria.date);
        if (!previous) {
          assessments.push({ status: "missing", text: missingPhrase("gfr"), level: null });
          return;
        }
        const assessment = assessmentFromPair(previous, albuminuria, "gfr");
        if (assessment) assessments.push(assessment);
      });
    } else {
      assessments.push({ status: "missing", text: missingPhrase("both"), level: null });
    }

    const deduplicated = [];
    const seen = new Set();
    assessments.forEach((assessment) => {
      const key = assessment.key || assessment.text;
      if (seen.has(key)) return;
      seen.add(key);
      deduplicated.push(assessment);
    });
    return deduplicated;
  }

  function highestRiskLevel(assessments) {
    let best = null;
    assessments.forEach((item) => {
      if (item.status !== "calculated" || !item.level) return;
      if (!best || (riskOrder[item.level] || 0) > (riskOrder[best] || 0)) {
        best = item.level;
      }
    });
    return best;
  }

  function renderAssessments() {
    const block = document.getElementById("kdigoRiskPreview");
    const lines = document.getElementById("kdigoRiskLines");
    if (!block || !lines) return;

    const excluded = currentExcludedPairs();
    const assessments = buildAssessments().filter((item) => !item.key || !excluded.has(item.key));
    const riskLevel = highestRiskLevel(assessments);

    block.classList.remove("kdigo-risk-empty", "kdigo-risk-low", "kdigo-risk-moderate", "kdigo-risk-high", "kdigo-risk-very_high");
    block.classList.add(riskLevel ? `kdigo-risk-${riskLevel}` : "kdigo-risk-empty");

    lines.innerHTML = "";
    assessments.forEach((assessment) => {
      const row = document.createElement("div");
      row.className = "kdigo-risk-line";
      if (assessment.status === "calculated") {
        row.classList.add(`kdigo-risk-line-${assessment.level}`);
      }

      const text = document.createElement("span");
      text.textContent = assessment.text;
      row.appendChild(text);

      if (assessment.status === "calculated" && assessment.key) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "kdigo-risk-remove-btn";
        button.title = "Не сохранять эту строку";
        button.textContent = "✖";
        button.addEventListener("click", () => {
          addExcludedPair(assessment.key);
          renderAssessments();
        });
        row.appendChild(button);
      }

      lines.appendChild(row);
    });
  }

  function scheduleRender() {
    window.setTimeout(renderAssessments, 0);
  }

  function init() {
    if (!document.getElementById("kdigoRiskPreview")) return;
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
    renderAssessments();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
