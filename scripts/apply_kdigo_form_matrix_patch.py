"""
Одноразовый скрипт фикса формы KDIGO.

Что делает:
- заменяет старый скрытый блок "Прогноз ХБП по KDIGO" в заключении на новый live-блок;
- переписывает appointment_form/_kdigo_risk_preview.html так, чтобы в форме были:
  матрица, кнопка обновления, строки заключения и скрытые поля исключённых пар;
- переписывает app/static/js/kdigo_risk_preview.js, чтобы матрица считалась в браузере;
- добавляет/обновляет app/static/css/04_kdigo_risk.css.

БД и миграции не трогает.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONCLUSION = ROOT / "app" / "templates" / "appointment_form" / "_conclusion.html"
PREVIEW = ROOT / "app" / "templates" / "appointment_form" / "_kdigo_risk_preview.html"
JS = ROOT / "app" / "static" / "js" / "kdigo_risk_preview.js"
CSS = ROOT / "app" / "static" / "css" / "04_kdigo_risk.css"

PREVIEW_TEXT = r'''{#
Назначение файла: live-блок оценки риска по KDIGO внутри формы приёма.

Что выполняет файл:
- показывает врачу полную фразу "По KDIGO: ..." до сохранения приёма;
- показывает матрицу СКФ × альбуминурия прямо в форме;
- даёт кнопку "Обновить матрицу" для ручного пересчёта после заполнения анализов;
- даёт крестик у рассчитанной строки/ячейки, чтобы врач убрал шум до сохранения;
- передаёт JavaScript историю СКФ и альбуминурии пациента для fallback-логики;
- хранит скрытые поля kdigo_excluded_pair для строк, которые врач решил не сохранять.

Что редактировать здесь:
- внешний текст заголовка;
- расположение поля заключения, матрицы и кнопки;
- какие исторические данные передаются JavaScript.

Что не редактировать здесь:
- медицинскую матрицу риска — она дублируется в JS для live-предпросмотра и на backend для сохранения;
- SQL и сохранение ckd_prognosis_results;
- расчёт eGFR и ACR.
#}

<link rel="stylesheet" href="{{ url_for('static', path='css/04_kdigo_risk.css') }}">

<div id="kdigoRiskPreview"
     class="kdigo-risk-preview kdigo-risk-empty mt-3 mb-3"
     data-kdigo-preview="1">
  <div class="d-flex justify-content-between align-items-center gap-2 mb-2">
    <div class="fw-bold">Оценка риска по KDIGO</div>
    <button type="button" id="kdigoRiskRefreshBtn" class="btn btn-outline-secondary btn-sm">
      Обновить матрицу
    </button>
  </div>

  <div id="kdigoRiskLines" class="kdigo-risk-lines mb-2">
    Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии и СКФ не предоставлены.
  </div>

  <label for="kdigoConclusionText" class="form-label small mb-1">Формулировка для заключения</label>
  <textarea id="kdigoConclusionText"
            name="kdigo_conclusion_text"
            class="form-control form-control-sm kdigo-conclusion-text"
            rows="2"
            readonly>Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии и СКФ не предоставлены.</textarea>

  <div id="kdigoRiskMatrixWrap" class="table-responsive mt-3" hidden>
    <table id="kdigoRiskMatrix" class="table table-bordered table-sm align-middle kdigo-risk-matrix mb-0">
      <thead></thead>
      <tbody></tbody>
    </table>
  </div>

  <div id="kdigoExcludedPairs"></div>
</div>

<script type="application/json" id="kdigoPreviousGfrData">
[
{% for item in metrics_history|default([]) if item.ckd_stage %}
  {
    "date": "{{ item.investigation_date.isoformat() if item.investigation_date else '' }}",
    "category": "{{ item.ckd_stage|e }}",
    "source": "previous_appointment"
  }{% if not loop.last %},{% endif %}
{% endfor %}
]
</script>

<script type="application/json" id="kdigoPreviousAlbuminuriaData">
[
{% for item in albuminuria_history|default([]) if item.albuminuria_category %}
  {
    "date": "{{ item.investigation_date.isoformat() if item.investigation_date else '' }}",
    "category": "{{ item.albuminuria_category|e }}",
    "source": "previous_appointment"
  }{% if not loop.last %},{% endif %}
{% endfor %}
]
</script>

<script src="{{ url_for('static', path='js/kdigo_risk_preview.js') }}"></script>
'''

JS_TEXT = r'''/*
Назначение файла: live-матрица риска по KDIGO в форме приёма.

Что выполняет файл:
- читает текущие СКФ и категории СКФ из блока биохимии;
- читает текущие ACR/A-категории из блока альбуминурии;
- если одного текущего показателя нет, берёт последний подходящий показатель из истории пациента;
- строит все допустимые комбинации СКФ × альбуминурия для текущего приёма;
- показывает полные фразы для заключения;
- строит матрицу: строки = дата СКФ + категория, столбцы = дата альбуминурии + категория,
  ячейка = только уровень риска и цвет;
- даёт крестик для удаления шумной строки/ячейки до сохранения.

Что редактировать здесь:
- правила чтения полей формы;
- короткие фразы для врача;
- визуальное поведение матрицы.

Что не редактировать здесь:
- серверное сохранение ckd_prognosis_results;
- SQL;
- расчёт eGFR и ACR в основной форме.
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

  const maxIntervalByRisk = { low: 365, moderate: 180, high: 90, very_high: 90 };
  const riskOrder = { low: 1, moderate: 2, high: 3, very_high: 4 };

  function readJsonScript(id) {
    const node = document.getElementById(id);
    if (!node) return [];
    try {
      const parsed = JSON.parse(node.textContent || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
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
    if (missing === "both") return "Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии и СКФ не предоставлены.";
    if (missing === "gfr") return "Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по СКФ не предоставлены.";
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
    const cards = Array.from(document.querySelectorAll("#biochemistryContainer .lab-analysis-card"));
    cards.forEach((card, index) => {
      const date = normalizeDate(card.querySelector('[name="biochemistry_investigation_date"]')?.value);
      const stageInput = card.querySelector(".biochemistry-stage");
      const egfrInput = card.querySelector(".biochemistry-egfr");
      const category = normalizeGfrCategory(stageInput?.value) || gfrCategoryFromEgfr(egfrInput?.value);
      if (date && category) result.push({ date, category, source: "current_appointment", order: index });
    });
    return result;
  }

  function readCurrentAlbuminuriaSources() {
    const result = [];
    const cards = Array.from(document.querySelectorAll("#albuminuriaContainer .albuminuria-block"));
    cards.forEach((card, index) => {
      const date = normalizeDate(card.querySelector('[name="albuminuria_investigation_date"]')?.value);
      const categoryInput = card.querySelector(".albuminuria-category");
      const acrInput = card.querySelector(".albuminuria-acr");
      const category = normalizeAlbuminuriaCategory(categoryInput?.value) || albuminuriaCategoryFromAcr(acrInput?.value);
      if (date && category) result.push({ date, category, source: "current_appointment", order: index });
    });
    return result;
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
    const key = pairKey(gfrSource.date, risk.gfrCategory, albuminuriaSource.date, risk.albuminuriaCategory);
    const rowKey = `${normalizeDate(gfrSource.date)}|${risk.gfrCategory}`;
    const colKey = `${normalizeDate(albuminuriaSource.date)}|${risk.albuminuriaCategory}`;

    if (intervalDays === null || intervalDays > maxDays) {
      return { status: "stale", key, text: stalePhrase(staleSourceWhenOld, intervalDays), level: null };
    }

    return {
      status: "calculated",
      key,
      rowKey,
      colKey,
      level: risk.level,
      riskText: risk.text,
      text: riskPhrase(risk, gfrSource.date, albuminuriaSource.date),
      gfrDate: normalizeDate(gfrSource.date),
      gfrCategory: risk.gfrCategory,
      albuminuriaDate: normalizeDate(albuminuriaSource.date),
      albuminuriaCategory: risk.albuminuriaCategory
    };
  }

  function buildAssessments() {
    const currentGfr = readCurrentGfrSources();
    const currentAlbuminuria = readCurrentAlbuminuriaSources();
    const previousGfr = loadPreviousGfrSources();
    const previousAlbuminuria = loadPreviousAlbuminuriaSources();
    const assessments = [];

    if (currentGfr.length && currentAlbuminuria.length) {
      currentGfr.forEach((gfr) => currentAlbuminuria.forEach((albuminuria) => {
        const assessment = assessmentFromPair(gfr, albuminuria, "albuminuria");
        if (assessment) assessments.push(assessment);
      }));
    } else if (currentGfr.length && !currentAlbuminuria.length) {
      currentGfr.forEach((gfr) => {
        const previous = latestPreviousBeforeOrOn(previousAlbuminuria, gfr.date);
        if (!previous) assessments.push({ status: "missing", text: missingPhrase("albuminuria"), level: null });
        else {
          const assessment = assessmentFromPair(gfr, previous, "albuminuria");
          if (assessment) assessments.push(assessment);
        }
      });
    } else if (!currentGfr.length && currentAlbuminuria.length) {
      currentAlbuminuria.forEach((albuminuria) => {
        const previous = latestPreviousBeforeOrOn(previousGfr, albuminuria.date);
        if (!previous) assessments.push({ status: "missing", text: missingPhrase("gfr"), level: null });
        else {
          const assessment = assessmentFromPair(previous, albuminuria, "gfr");
          if (assessment) assessments.push(assessment);
        }
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
      if (!best || (riskOrder[item.level] || 0) > (riskOrder[best] || 0)) best = item.level;
    });
    return best;
  }

  function riskClass(level) {
    return level ? `kdigo-risk-${level}` : "kdigo-risk-empty";
  }

  function renderLines(assessments) {
    const lines = document.getElementById("kdigoRiskLines");
    const textField = document.getElementById("kdigoConclusionText");
    if (!lines) return;
    lines.innerHTML = "";

    assessments.forEach((assessment) => {
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
          renderAssessments();
        });
        row.appendChild(button);
      }
      lines.appendChild(row);
    });

    if (textField) textField.value = assessments.map((item) => item.text).join("\n");
  }

  function uniqueByKey(items, keyName) {
    const result = [];
    const seen = new Set();
    items.forEach((item) => {
      const key = item[keyName];
      if (!key || seen.has(key)) return;
      seen.add(key);
      result.push(item);
    });
    return result;
  }

  function renderMatrix(assessments) {
    const wrap = document.getElementById("kdigoRiskMatrixWrap");
    const table = document.getElementById("kdigoRiskMatrix");
    if (!wrap || !table) return;

    const calculated = assessments.filter((item) => item.status === "calculated");
    if (!calculated.length) {
      wrap.hidden = true;
      table.querySelector("thead").innerHTML = "";
      table.querySelector("tbody").innerHTML = "";
      return;
    }

    wrap.hidden = false;
    const rows = uniqueByKey(calculated, "rowKey").sort((a, b) => parseIsoDate(a.gfrDate) - parseIsoDate(b.gfrDate));
    const cols = uniqueByKey(calculated, "colKey").sort((a, b) => parseIsoDate(a.albuminuriaDate) - parseIsoDate(b.albuminuriaDate));

    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    thead.innerHTML = "";
    tbody.innerHTML = "";

    const headerRow = document.createElement("tr");
    const corner = document.createElement("th");
    corner.textContent = "СКФ \\ альбуминурия";
    headerRow.appendChild(corner);
    cols.forEach((col) => {
      const th = document.createElement("th");
      th.innerHTML = `<div>${formatRuDate(col.albuminuriaDate)}</div><div class="small">${col.albuminuriaCategory}</div>`;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    rows.forEach((rowItem) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.innerHTML = `<div>${formatRuDate(rowItem.gfrDate)}</div><div class="small">${rowItem.gfrCategory}</div>`;
      tr.appendChild(th);

      cols.forEach((colItem) => {
        const td = document.createElement("td");
        const cellItems = calculated.filter((item) => item.rowKey === rowItem.rowKey && item.colKey === colItem.colKey);
        if (!cellItems.length) {
          td.textContent = "—";
          tr.appendChild(td);
          return;
        }
        cellItems.forEach((item) => {
          const cell = document.createElement("div");
          cell.className = `kdigo-risk-cell ${riskClass(item.level)}`;
          const text = document.createElement("span");
          text.textContent = item.riskText;
          cell.appendChild(text);
          const button = document.createElement("button");
          button.type = "button";
          button.className = "kdigo-risk-remove-btn";
          button.title = "Не сохранять эту строку";
          button.textContent = "✖";
          button.addEventListener("click", () => {
            addExcludedPair(item.key);
            renderAssessments();
          });
          cell.appendChild(button);
          td.appendChild(cell);
        });
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  function renderAssessments() {
    const block = document.getElementById("kdigoRiskPreview");
    if (!block) return;
    const excluded = currentExcludedPairs();
    const assessments = buildAssessments().filter((item) => !item.key || !excluded.has(item.key));
    const riskLevel = highestRiskLevel(assessments);
    block.classList.remove("kdigo-risk-empty", "kdigo-risk-low", "kdigo-risk-moderate", "kdigo-risk-high", "kdigo-risk-very_high");
    block.classList.add(riskClass(riskLevel));
    renderLines(assessments);
    renderMatrix(assessments);
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
      if (target.id === "kdigoRiskRefreshBtn") {
        event.preventDefault();
        renderAssessments();
        return;
      }
      if (
        target.matches('[data-add-lab="biochemistryContainer"]') ||
        target.matches('[data-add-lab="albuminuriaContainer"]') ||
        target.closest('[data-add-lab="biochemistryContainer"]') ||
        target.closest('[data-add-lab="albuminuriaContainer"]') ||
        target.matches(".remove-lab-card") ||
        target.closest(".remove-lab-card") ||
        target.id === "addBiochemistryColumnBtn" ||
        target.id === "addAlbuminuriaColumnBtn"
      ) {
        scheduleRender();
      }
    }, true);
    renderAssessments();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
'''

CSS_TEXT = r'''/*
Назначение файла: внешний вид live-блока и матрицы KDIGO.

Редактировать здесь можно только визуальные параметры: отступы, рамки, цветовую подсветку.
Логику расчёта и фразы менять в JS/backend.
*/

.kdigo-risk-preview {
  border: 1px solid #ced4da;
  border-radius: 0.5rem;
  padding: 0.75rem;
  background: #f8f9fa;
}

.kdigo-risk-lines {
  display: grid;
  gap: 0.35rem;
}

.kdigo-risk-line {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.35rem 0.5rem;
  border-radius: 0.35rem;
  background: rgba(255, 255, 255, 0.75);
}

.kdigo-risk-remove-btn {
  border: 0;
  background: transparent;
  color: #6c757d;
  padding: 0 0.2rem;
  line-height: 1.2;
  cursor: pointer;
}

.kdigo-risk-remove-btn:hover {
  color: #dc3545;
}

.kdigo-risk-matrix th,
.kdigo-risk-matrix td {
  text-align: center;
  vertical-align: middle;
}

.kdigo-risk-cell {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.35rem;
  min-height: 2rem;
  padding: 0.25rem;
  border-radius: 0.35rem;
  font-weight: 600;
}

.kdigo-risk-low,
.kdigo-risk-line-low {
  background: #d1e7dd;
}

.kdigo-risk-moderate,
.kdigo-risk-line-moderate {
  background: #fff3cd;
}

.kdigo-risk-high,
.kdigo-risk-line-high {
  background: #ffe5d0;
}

.kdigo-risk-very_high,
.kdigo-risk-line-very_high {
  background: #f8d7da;
}

.kdigo-risk-empty {
  background: #f8f9fa;
}

.kdigo-conclusion-text {
  white-space: pre-wrap;
}
'''


def patch_conclusion() -> None:
    content = CONCLUSION.read_text(encoding="utf-8")
    include = '{% include "appointment_form/_kdigo_risk_preview.html" %}'

    # Удаляем старый скрытый блок, если он остался.
    content = re.sub(
        r"\n?\s*<div\s+id=[\"']ckdPrognosisBlock[\"'][\s\S]*?</div>\s*",
        "\n\n",
        content,
        count=1,
        flags=re.IGNORECASE,
    )

    # Удаляем кривой вариант include внутри strong.
    content = content.replace(f"<strong>{include}</strong>", include)

    # Если include уже есть, убираем дубликаты и вставляем в правильное место.
    content = content.replace(include, "")

    h5_patterns = [
        r"(<h5[^>]*>\s*Заключение\s*</h5>)",
        r"(#####\s*Заключение)",
    ]
    for pattern in h5_patterns:
        new_content, count = re.subn(pattern, r"\1\n\n " + include, content, count=1, flags=re.IGNORECASE)
        if count:
            CONCLUSION.write_text(new_content, encoding="utf-8")
            return

    raise RuntimeError("Не нашла заголовок 'Заключение' в _conclusion.html")


def main() -> None:
    if not CONCLUSION.exists():
        raise FileNotFoundError(CONCLUSION)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    JS.parent.mkdir(parents=True, exist_ok=True)
    CSS.parent.mkdir(parents=True, exist_ok=True)

    patch_conclusion()
    PREVIEW.write_text(PREVIEW_TEXT, encoding="utf-8")
    JS.write_text(JS_TEXT, encoding="utf-8")
    CSS.write_text(CSS_TEXT, encoding="utf-8")

    print("OK: форма KDIGO пересобрана.")
    print("- _conclusion.html: live-блок стоит перед диагнозами")
    print("- _kdigo_risk_preview.html: добавлены матрица, кнопка обновления и поле заключения")
    print("- kdigo_risk_preview.js: добавлен live-расчёт матрицы")
    print("- 04_kdigo_risk.css: добавлена подсветка")
    print("Теперь запусти: pytest tests/layer")


if __name__ == "__main__":
    main()
