"""
Одноразовый скрипт для исправления KDIGO-блока в форме повторного приёма.

Что делает:
- перезаписывает appointment_form/_kdigo_risk_preview.html полноценным блоком;
- перезаписывает static/js/kdigo_risk_preview.js логикой заключения + матрицы;
- перезаписывает/дополняет static/css/04_kdigo_risk.css;
- гарантирует include KDIGO перед диагнозами в _conclusion.html;
- гарантирует подключение CSS/JS в base.html;
- убирает старую строку "Прогноз ХБП по KDIGO:" и ошибочный <strong>{% include ... %}</strong>.

Скрипт нужен только для применения патча. После зелёных тестов его можно удалить.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

KDIGO_TEMPLATE = r'''{#
Назначение файла: live-блок KDIGO внутри формы приёма.

Что выполняет файл:
- показывает врачу полную фразу заключения "По KDIGO: ..." до сохранения приёма;
- показывает матрицу СКФ × альбуминурия в форме повторного приёма;
- передаёт JavaScript историю СКФ и альбуминурии пациента для fallback-логики;
- хранит скрытые поля kdigo_excluded_pair, если врач нажал ✖ у лишней комбинации.

Что редактировать здесь:
- внешний текст заголовка;
- расположение кнопки обновления матрицы;
- какие исторические поля передаются JavaScript.

Что не редактировать здесь:
- медицинскую матрицу риска — она в app/medical_algorithms/kdigo_risk.py и JS-зеркале;
- SQL и сохранение ckd_prognosis_results;
- расчёт eGFR и ACR.
#}

{% set kdigo_gfr_history = [] %}
{% for item in metrics_history or [] %}
  {% if item.investigation_date and item.ckd_stage %}
    {% set _ = kdigo_gfr_history.append({
      "date": item.investigation_date.strftime('%Y-%m-%d'),
      "category": item.ckd_stage|string,
      "source": "previous_appointment"
    }) %}
  {% endif %}
{% endfor %}

{% set kdigo_albuminuria_history = [] %}
{% for item in albuminuria_history or [] %}
  {% if item.investigation_date and item.albuminuria_category %}
    {% set _ = kdigo_albuminuria_history.append({
      "date": item.investigation_date.strftime('%Y-%m-%d'),
      "category": item.albuminuria_category|string,
      "source": "previous_appointment"
    }) %}
  {% endif %}
{% endfor %}

<div id="kdigoRiskPreview" class="kdigo-risk-preview kdigo-risk-empty mt-3 mb-3">
  <div class="d-flex justify-content-between align-items-center gap-2 mb-2">
    <strong>Оценка риска по KDIGO</strong>
    <button type="button" class="btn btn-sm btn-outline-secondary" id="kdigoRiskRefreshMatrix">
      Обновить матрицу
    </button>
  </div>

  <div class="kdigo-risk-conclusion" id="kdigoRiskConclusionBox">
    <div id="kdigoRiskLines" class="kdigo-risk-lines">
      Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии и СКФ не предоставлены.
    </div>
  </div>

  <div id="kdigoRiskHiddenFields"></div>
  <div id="kdigoExcludedPairs"></div>

  <div class="kdigo-risk-matrix-wrapper mt-3">
    <div class="small text-muted mb-1">Матрица СКФ × альбуминурия</div>
    <div id="kdigoRiskMatrix" class="kdigo-risk-matrix"></div>
  </div>
</div>

<script type="application/json" id="kdigoPreviousGfrData">{{ kdigo_gfr_history | tojson }}</script>
<script type="application/json" id="kdigoPreviousAlbuminuriaData">{{ kdigo_albuminuria_history | tojson }}</script>
'''

KDIGO_JS = r'''/*
Назначение файла: live-предпросмотр риска по KDIGO в форме приёма.

Что выполняет файл:
- следит за СКФ, категорией СКФ, ACR и категорией альбуминурии;
- строит фразы "По KDIGO: ..." до сохранения приёма;
- строит матрицу СКФ × альбуминурия прямо в форме;
- если одного текущего показателя нет, использует последний подходящий показатель из истории пациента;
- если показатель устарел, показывает сообщение без цветовой подсветки;
- не дублирует одинаковые фразы;
- позволяет врачу нажать ✖ у лишней рассчитанной комбинации, чтобы она не сохранялась.

Что редактировать здесь:
- правила чтения полей формы;
- внешний вид/тексты live-блока;
- правила построения матрицы.

Что не редактировать здесь:
- серверное сохранение ckd_prognosis_results;
- SQL;
- расчёт eGFR/ACR, который уже делает существующий код формы.
*/
(function () {
  "use strict";

  const riskMatrix = {
    "С1": { A1: ["low", "низкий риск"], A2: ["moderate", "умеренно повышенный риск"], A3: ["high", "высокий риск"] },
    "С2": { A1: ["low", "низкий риск"], A2: ["moderate", "умеренно повышенный риск"], A3: ["high", "высокий риск"] },
    "С3а": { A1: ["moderate", "умеренно повышенный риск"], A2: ["high", "высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С3б": { A1: ["high", "высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С4": { A1: ["very_high", "очень высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] },
    "С5": { A1: ["very_high", "очень высокий риск"], A2: ["very_high", "очень высокий риск"], A3: ["very_high", "очень высокий риск"] },
  };

  const maxIntervalByRisk = { low: 365, moderate: 180, high: 90, very_high: 90 };
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
    const risk = riskMatrix[gfr] && riskMatrix[gfr][albuminuria];
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

  function sourceKey(source) {
    return [normalizeDate(source.date), source.category, source.source || ""].join("|");
  }

  function pairKey(gfrSource, albuminuriaSource) {
    return [
      normalizeDate(gfrSource.date),
      normalizeGfrCategory(gfrSource.category),
      normalizeDate(albuminuriaSource.date),
      normalizeAlbuminuriaCategory(albuminuriaSource.category),
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

  function uniqueByKey(items, keyFn) {
    const seen = new Set();
    const result = [];
    items.forEach((item) => {
      const key = keyFn(item);
      if (!key || seen.has(key)) return;
      seen.add(key);
      result.push(item);
    });
    return result;
  }

  function readCurrentGfrSources() {
    const cards = Array.from(document.querySelectorAll("#biochemistryContainer .lab-analysis-card"));
    return cards
      .map((card) => {
        const date = normalizeDate(card.querySelector('[name="biochemistry_investigation_date"]')?.value);
        const category = normalizeGfrCategory(card.querySelector(".biochemistry-stage")?.value) ||
          gfrCategoryFromEgfr(card.querySelector(".biochemistry-egfr")?.value);
        return date && category ? { date, category, source: "current_appointment" } : null;
      })
      .filter(Boolean);
  }

  function readCurrentAlbuminuriaSources() {
    const cards = Array.from(document.querySelectorAll("#albuminuriaContainer .albuminuria-block"));
    return cards
      .map((card) => {
        const date = normalizeDate(card.querySelector('[name="albuminuria_investigation_date"]')?.value);
        const category = normalizeAlbuminuriaCategory(card.querySelector(".albuminuria-category")?.value) ||
          albuminuriaCategoryFromAcr(card.querySelector(".albuminuria-acr")?.value);
        return date && category ? { date, category, source: "current_appointment" } : null;
      })
      .filter(Boolean);
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

  function latestPreviousBeforeOrOn(sources, targetDate) {
    const target = parseIsoDate(targetDate);
    if (!target) return null;
    return sources
      .filter((item) => normalizeDate(item.date) && parseIsoDate(item.date) <= target)
      .sort((a, b) => parseIsoDate(b.date) - parseIsoDate(a.date))[0] || null;
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
    const key = pairKey(gfrSource, albuminuriaSource);
    if (intervalDays === null || intervalDays > maxDays) {
      return {
        status: "stale",
        key,
        level: null,
        text: stalePhrase(staleSourceWhenOld, intervalDays),
        gfr: gfrSource,
        albuminuria: albuminuriaSource,
        risk,
      };
    }
    return {
      status: "calculated",
      key,
      level: risk.level,
      text: riskPhrase(risk, gfrSource.date, albuminuriaSource.date),
      gfr: gfrSource,
      albuminuria: albuminuriaSource,
      risk,
    };
  }

  function buildConclusionAssessments() {
    const currentGfr = uniqueByKey(readCurrentGfrSources(), sourceKey);
    const currentAlbuminuria = uniqueByKey(readCurrentAlbuminuriaSources(), sourceKey);
    const previousGfr = uniqueByKey(loadPreviousGfrSources(), sourceKey);
    const previousAlbuminuria = uniqueByKey(loadPreviousAlbuminuriaSources(), sourceKey);
    const assessments = [];

    if (currentGfr.length && currentAlbuminuria.length) {
      currentGfr.forEach((gfr) => {
        currentAlbuminuria.forEach((albuminuria) => {
          const assessment = assessmentFromPair(gfr, albuminuria, "albuminuria");
          if (assessment) assessments.push(assessment);
        });
      });
    } else if (currentGfr.length && !currentAlbuminuria.length) {
      let hasAnyPrevious = false;
      currentGfr.forEach((gfr) => {
        const previous = latestPreviousBeforeOrOn(previousAlbuminuria, gfr.date);
        if (!previous) return;
        hasAnyPrevious = true;
        const assessment = assessmentFromPair(gfr, previous, "albuminuria");
        if (assessment) assessments.push(assessment);
      });
      if (!hasAnyPrevious) {
        assessments.push({ status: "missing", text: missingPhrase("albuminuria"), level: null });
      }
    } else if (!currentGfr.length && currentAlbuminuria.length) {
      let hasAnyPrevious = false;
      currentAlbuminuria.forEach((albuminuria) => {
        const previous = latestPreviousBeforeOrOn(previousGfr, albuminuria.date);
        if (!previous) return;
        hasAnyPrevious = true;
        const assessment = assessmentFromPair(previous, albuminuria, "gfr");
        if (assessment) assessments.push(assessment);
      });
      if (!hasAnyPrevious) {
        assessments.push({ status: "missing", text: missingPhrase("gfr"), level: null });
      }
    } else {
      assessments.push({ status: "missing", text: missingPhrase("both"), level: null });
    }

    return uniqueByKey(assessments, (item) => item.key || item.text);
  }

  function buildMatrixSources() {
    const gfrSources = uniqueByKey([...loadPreviousGfrSources(), ...readCurrentGfrSources()], sourceKey)
      .sort((a, b) => parseIsoDate(a.date) - parseIsoDate(b.date));
    const albuminuriaSources = uniqueByKey([...loadPreviousAlbuminuriaSources(), ...readCurrentAlbuminuriaSources()], sourceKey)
      .sort((a, b) => parseIsoDate(a.date) - parseIsoDate(b.date));
    return { gfrSources, albuminuriaSources };
  }

  function highestRiskLevel(assessments) {
    let best = null;
    assessments.forEach((item) => {
      if (item.status !== "calculated" || !item.level) return;
      if (!best || (riskOrder[item.level] || 0) > (riskOrder[best] || 0)) best = item.level;
    });
    return best;
  }

  function clearHiddenFields() {
    const container = document.getElementById("kdigoRiskHiddenFields");
    if (container) container.innerHTML = "";
  }

  function addHiddenField(name, value) {
    const container = document.getElementById("kdigoRiskHiddenFields");
    if (!container || value === null || value === undefined || value === "") return;
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = String(value);
    container.appendChild(input);
  }

  function renderConclusion() {
    const block = document.getElementById("kdigoRiskPreview");
    const lines = document.getElementById("kdigoRiskLines");
    if (!block || !lines) return;

    const excluded = currentExcludedPairs();
    const assessments = buildConclusionAssessments().filter((item) => !item.key || !excluded.has(item.key));
    const riskLevel = highestRiskLevel(assessments);

    block.classList.remove("kdigo-risk-empty", "kdigo-risk-low", "kdigo-risk-moderate", "kdigo-risk-high", "kdigo-risk-very_high");
    block.classList.add(riskLevel ? `kdigo-risk-${riskLevel}` : "kdigo-risk-empty");

    lines.innerHTML = "";
    clearHiddenFields();

    uniqueByKey(assessments, (item) => item.key || item.text).forEach((assessment) => {
      const row = document.createElement("div");
      row.className = "kdigo-risk-line";
      if (assessment.status === "calculated") row.classList.add(`kdigo-risk-line-${assessment.level}`);

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
          renderAll();
        });
        row.appendChild(button);

        addHiddenField("kdigo_assessment_key", assessment.key);
        addHiddenField("kdigo_assessment_phrase", assessment.text);
      }

      lines.appendChild(row);
    });
  }

  function renderMatrix() {
    const container = document.getElementById("kdigoRiskMatrix");
    if (!container) return;

    const { gfrSources, albuminuriaSources } = buildMatrixSources();
    if (!gfrSources.length || !albuminuriaSources.length) {
      container.innerHTML = '<div class="text-muted small">Матрица появится после добавления СКФ и альбуминурии.</div>';
      return;
    }

    const table = document.createElement("table");
    table.className = "table table-bordered table-sm kdigo-risk-matrix-table mb-0";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    const corner = document.createElement("th");
    corner.textContent = "СКФ / Альбуминурия";
    headerRow.appendChild(corner);

    albuminuriaSources.forEach((albuminuria) => {
      const th = document.createElement("th");
      th.innerHTML = `<div>${formatRuDate(albuminuria.date)}</div><div class="small">${albuminuria.category}</div>`;
      headerRow.appendChild(th);
    });

    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    gfrSources.forEach((gfr) => {
      const row = document.createElement("tr");
      const th = document.createElement("th");
      th.innerHTML = `<div>${formatRuDate(gfr.date)}</div><div class="small">${gfr.category}</div>`;
      row.appendChild(th);

      albuminuriaSources.forEach((albuminuria) => {
        const td = document.createElement("td");
        const assessment = assessmentFromPair(gfr, albuminuria, "albuminuria");
        if (assessment && assessment.status === "calculated") {
          td.className = `kdigo-matrix-cell kdigo-matrix-${assessment.level}`;
          td.textContent = assessment.risk.text;
        } else {
          td.className = "kdigo-matrix-cell kdigo-matrix-empty";
          td.textContent = "—";
        }
        row.appendChild(td);
      });
      tbody.appendChild(row);
    });

    table.appendChild(tbody);
    container.innerHTML = "";
    container.appendChild(table);
  }

  function renderAll() {
    renderConclusion();
    renderMatrix();
  }

  function scheduleRender() {
    window.setTimeout(renderAll, 0);
  }

  function init() {
    if (!document.getElementById("kdigoRiskPreview")) return;

    document.addEventListener("input", scheduleRender, true);
    document.addEventListener("change", scheduleRender, true);
    document.addEventListener("click", function (event) {
      const target = event.target;
      if (!(target instanceof Element)) return;

      if (target.id === "kdigoRiskRefreshMatrix" || target.closest("#kdigoRiskRefreshMatrix")) {
        renderAll();
        return;
      }

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

    renderAll();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
'''

KDIGO_CSS = r'''/*
Назначение файла: внешний вид live-блока KDIGO и матрицы СКФ × альбуминурия.

Что редактировать здесь:
- мягкость подсветки риска;
- отступы матрицы;
- вид кнопки удаления строки.
*/

.kdigo-risk-preview {
  border: 1px solid #dee2e6;
  border-radius: 0.375rem;
  padding: 0.75rem;
  background: #f8f9fa;
}

.kdigo-risk-conclusion {
  border-radius: 0.375rem;
  background: rgba(255, 255, 255, 0.65);
  padding: 0.5rem 0.75rem;
}

.kdigo-risk-line {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.25rem 0;
}

.kdigo-risk-remove-btn {
  border: 0;
  background: transparent;
  color: #6c757d;
  line-height: 1;
  padding: 0.15rem 0.25rem;
}

.kdigo-risk-remove-btn:hover {
  color: #dc3545;
}

.kdigo-risk-low {
  background: #eaf6ec;
  border-color: #badbcc;
}

.kdigo-risk-moderate {
  background: #fff8e1;
  border-color: #ffe69c;
}

.kdigo-risk-high {
  background: #fff1df;
  border-color: #ffdaaa;
}

.kdigo-risk-very_high {
  background: #fdecec;
  border-color: #f5c2c7;
}

.kdigo-risk-empty {
  background: #f8f9fa;
  border-color: #dee2e6;
}

.kdigo-risk-matrix {
  overflow-x: auto;
}

.kdigo-risk-matrix-table th,
.kdigo-risk-matrix-table td {
  text-align: center;
  vertical-align: middle;
  min-width: 120px;
}

.kdigo-risk-matrix-table th:first-child {
  min-width: 150px;
  text-align: left;
}

.kdigo-matrix-cell {
  font-weight: 500;
}

.kdigo-matrix-low {
  background: #eaf6ec;
}

.kdigo-matrix-moderate {
  background: #fff8e1;
}

.kdigo-matrix-high {
  background: #fff1df;
}

.kdigo-matrix-very_high {
  background: #fdecec;
}

.kdigo-matrix-empty {
  background: #f8f9fa;
  color: #adb5bd;
  font-weight: 400;
}
'''

TEST_FILE = r'''from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_kdigo_preview_template_contains_conclusion_and_matrix():
    html = read("app/templates/appointment_form/_kdigo_risk_preview.html")

    assert 'id="kdigoRiskPreview"' in html
    assert 'id="kdigoRiskLines"' in html
    assert 'id="kdigoRiskMatrix"' in html
    assert 'id="kdigoRiskRefreshMatrix"' in html
    assert 'kdigoPreviousGfrData' in html
    assert 'kdigoPreviousAlbuminuriaData' in html


def test_kdigo_preview_is_included_before_diagnosis_block():
    html = read("app/templates/appointment_form/_conclusion.html")

    include_pos = html.find('appointment_form/_kdigo_risk_preview.html')
    diagnosis_pos = html.find('icd10_diagnosis_block.html')

    assert include_pos != -1
    assert diagnosis_pos != -1
    assert include_pos < diagnosis_pos
    assert '<strong>{% include "appointment_form/_kdigo_risk_preview.html" %}</strong>' not in html
    assert 'ckdPrognosisBlock' not in html


def test_kdigo_javascript_builds_matrix_and_deduplicates_phrases():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert 'function renderMatrix()' in js
    assert 'function renderConclusion()' in js
    assert 'uniqueByKey' in js
    assert 'kdigoRiskRefreshMatrix' in js
    assert 'kdigoRiskMatrix' in js
    assert 'kdigo_assessment_phrase' in js


def test_kdigo_css_has_matrix_risk_classes():
    css = read("app/static/css/04_kdigo_risk.css")

    assert '.kdigo-risk-preview' in css
    assert '.kdigo-matrix-low' in css
    assert '.kdigo-matrix-moderate' in css
    assert '.kdigo-matrix-high' in css
    assert '.kdigo-matrix-very_high' in css
'''


def write_text(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def patch_conclusion() -> bool:
    path = ROOT / "app/templates/appointment_form/_conclusion.html"
    content = path.read_text(encoding="utf-8")
    original = content
    include = '{% include "appointment_form/_kdigo_risk_preview.html" %}'

    content = content.replace('<strong>{% include "appointment_form/_kdigo_risk_preview.html" %}</strong>', include)
    content = content.replace('<strong> {% include "appointment_form/_kdigo_risk_preview.html" %} </strong>', include)
    content = content.replace('Прогноз ХБП по KDIGO:', '')
    content = re.sub(r'\n\s*<div[^>]+id=["\']ckdPrognosisBlock["\'][\s\S]*?</div>\s*\n', '\n', content)

    if include in content:
        # Оставляем только первое подключение, чтобы фразы не дублировались.
        first = content.find(include)
        before = content[: first + len(include)]
        after = content[first + len(include):].replace(include, "")
        content = before + after
    else:
        match = re.search(r'(#####\s+Заключение\s*)', content)
        if match:
            content = content[: match.end()] + "\n\n" + include + "\n" + content[match.end():]
        else:
            content = include + "\n" + content

    # Гарантируем, что KDIGO стоит перед диагнозами.
    diagnosis = '{% include "icd10_diagnosis_block.html" %}'
    if diagnosis in content and content.find(include) > content.find(diagnosis):
        content = content.replace(include, "")
        content = content.replace(diagnosis, include + "\n\n" + diagnosis)

    if content != original:
        path.write_text(content, encoding="utf-8", newline="\n")
        return True
    return False


def patch_base() -> tuple[bool, bool]:
    path = ROOT / "app/templates/base.html"
    content = path.read_text(encoding="utf-8")
    original = content
    css_changed = False
    js_changed = False

    if "css/04_kdigo_risk.css" not in content:
        link = '<link rel="stylesheet" href="{{ url_for(\'static\', path=\'css/04_kdigo_risk.css\') }}">'
        if "</head>" in content:
            content = content.replace("</head>", f"    {link}\n</head>", 1)
        else:
            content = link + "\n" + content
        css_changed = True

    if "js/kdigo_risk_preview.js" not in content:
        script = '<script src="{{ url_for(\'static\', path=\'js/kdigo_risk_preview.js\') }}" defer></script>'
        if "</body>" in content:
            content = content.replace("</body>", f"    {script}\n</body>", 1)
        else:
            content += "\n" + script + "\n"
        js_changed = True

    if content != original:
        path.write_text(content, encoding="utf-8", newline="\n")
    return css_changed, js_changed


def main() -> None:
    write_text("app/templates/appointment_form/_kdigo_risk_preview.html", KDIGO_TEMPLATE)
    write_text("app/static/js/kdigo_risk_preview.js", KDIGO_JS)
    write_text("app/static/css/04_kdigo_risk.css", KDIGO_CSS)
    write_text("tests/layer/test_kdigo_form_matrix_dedupe_contract.py", TEST_FILE)

    conclusion_changed = patch_conclusion()
    css_changed, js_changed = patch_base()

    print("OK: KDIGO-блок формы заменён на версию с матрицей и без дублей.")
    print(f"_conclusion.html изменён: {'да' if conclusion_changed else 'нет, уже было'}")
    print(f"base.html CSS изменён: {'да' if css_changed else 'нет, уже было'}")
    print(f"base.html JS изменён: {'да' if js_changed else 'нет, уже было'}")
    print("Теперь запусти: pytest tests/layer/test_kdigo_form_matrix_dedupe_contract.py && pytest tests/layer")


if __name__ == "__main__":
    main()
