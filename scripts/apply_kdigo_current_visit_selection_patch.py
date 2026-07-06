"""
Одноразовый скрипт применения патча KDIGO current visit selection.

Что делает:
- заменяет live-блок KDIGO в форме приёма;
- заменяет JS-логику: текущий приём = список вариантов с выбором одного;
- добавляет скрытую историческую матрицу прошлых прогнозов;
- передаёт историю KDIGO в context формы повторного приёма;
- не трогает миграции и инструкции по базе данных.

После успешной проверки этот файл можно удалить.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    print(f"OK: записан {path}")


KDIGO_TEMPLATE = r'''{#
Назначение файла: live-блок KDIGO внутри заключения формы приёма.

Что выполняет файл:
- показывает прогноз только для текущего заполняемого приёма;
- если врач внёс несколько СКФ, показывает несколько вариантов прогноза;
- даёт выбрать один вариант, который будет сохранён как клинически значимый;
- передаёт JavaScript прошлые СКФ/альбуминурию для fallback-логики;
- показывает историю прошлых прогнозов по кнопке, отдельно от текущего приёма.

Что редактировать здесь:
- подписи в блоке заключения;
- расположение кнопки истории;
- набор JSON-данных, передаваемых в JavaScript.

Что не редактировать здесь:
- матрицу риска KDIGO;
- SQL-сохранение;
- расчёт СКФ и ACR.
#}

<div id="kdigoRiskPreview" class="kdigo-risk-preview kdigo-risk-empty mt-3 mb-3">
  <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
    <div>
      <strong>Оценка риска по KDIGO</strong>
      <div class="small text-muted">Выберите вариант прогноза, который попадёт в заключение.</div>
    </div>
    <button type="button" id="kdigoRefreshButton" class="btn btn-outline-secondary btn-sm">
      Обновить прогноз
    </button>
  </div>

  <div id="kdigoCurrentRiskOptions" class="kdigo-current-risk-options mb-3">
    <div class="text-muted small">
      Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии и СКФ не предоставлены.
    </div>
  </div>

  <input type="hidden" id="kdigoSelectedPair" name="kdigo_selected_pair" value="">
  <div id="kdigoExcludedPairs"></div>

  <label for="kdigoSelectedRiskText" class="form-label mb-1">Формулировка для заключения</label>
  <textarea
    id="kdigoSelectedRiskText"
    name="kdigo_selected_risk_text"
    class="form-control kdigo-risk-conclusion-text"
    rows="3"
    readonly
  >Невозможно оценить риск прогрессирования ХБП и развития ХПН, данные по альбуминурии и СКФ не предоставлены.</textarea>

  <div class="mt-3">
    <button type="button" id="kdigoHistoryToggleButton" class="btn btn-outline-secondary btn-sm">
      Посмотреть историю прогнозов по KDIGO
    </button>
  </div>

  <div id="kdigoHistoryPanel" class="kdigo-history-panel mt-3 d-none">
    <div class="small text-muted mb-2">
      История прошлых сохранённых прогнозов. Данные текущего заполняемого приёма сюда не входят.
    </div>
    <div id="kdigoHistoryMatrix"></div>
  </div>
</div>

<script type="application/json" id="kdigoPreviousGfrData">
[
{% for item in metrics_history or [] %}
  {
    "date": "{{ item.investigation_date.isoformat() if item.investigation_date else '' }}",
    "category": "{{ item.ckd_stage or '' }}"
  }{% if not loop.last %},{% endif %}
{% endfor %}
]
</script>

<script type="application/json" id="kdigoPreviousAlbuminuriaData">
[
{% for item in albuminuria_history or [] %}
  {
    "date": "{{ item.investigation_date.isoformat() if item.investigation_date else '' }}",
    "category": "{{ item.albuminuria_category or '' }}"
  }{% if not loop.last %},{% endif %}
{% endfor %}
]
</script>

<script type="application/json" id="kdigoSavedRiskHistoryData">
[
{% for item in ckd_prognosis_history or [] %}
  {
    "appointment_date": "{{ item.appointment_date.date().isoformat() if item.appointment_date and item.appointment_date.date is defined else (item.appointment_date.isoformat() if item.appointment_date else '') }}",
    "gfr_date": "{{ item.gfr_investigation_date.isoformat() if item.gfr_investigation_date else '' }}",
    "gfr_category": "{{ item.gfr_category or '' }}",
    "albuminuria_date": "{{ item.albuminuria_investigation_date.isoformat() if item.albuminuria_investigation_date else '' }}",
    "albuminuria_category": "{{ item.albuminuria_category or '' }}",
    "combined_category": "{{ item.combined_category or '' }}",
    "risk_level": "{{ item.prognosis_level or '' }}",
    "risk_text": "{{ item.prognosis_text or '' }}"
  }{% if not loop.last %},{% endif %}
{% endfor %}
]
</script>
'''


KDIGO_JS = r'''/*
Назначение файла: live-предпросмотр KDIGO в форме приёма.

Что выполняет файл:
- строит прогноз только для текущего заполняемого приёма;
- для каждой новой СКФ подбирает одну альбуминурию: текущую ближайшую по дате,
  либо последнюю подходящую из прошлых приёмов;
- если вариантов несколько, показывает radio-выбор одного варианта для заключения;
- создаёт скрытые kdigo_excluded_pair для всех невыбранных пар, чтобы backend
  сохранил только клинически выбранный вариант;
- по кнопке показывает read-only историю прошлых прогнозов в виде матрицы.

Что редактировать здесь:
- правила выбора ближайшей альбуминурии;
- тексты для врача;
- внешний вид создаваемых элементов.

Что не редактировать здесь:
- SQL и миграции;
- серверный расчёт СКФ/ACR;
- медицинскую матрицу риска без отдельной проверки.
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
  let selectedPairKey = "";

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
    return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : "";
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
      if (date && category) result.push({ date, category, source: "current_appointment", index });
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
      if (date && category) result.push({ date, category, source: "current_appointment", index });
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

  function closestByDate(sources, targetDate) {
    const target = parseIsoDate(targetDate);
    if (!target || !sources.length) return null;
    return sources
      .filter((item) => normalizeDate(item.date))
      .sort((a, b) => {
        const distanceA = Math.abs(parseIsoDate(a.date) - target);
        const distanceB = Math.abs(parseIsoDate(b.date) - target);
        if (distanceA !== distanceB) return distanceA - distanceB;
        return parseIsoDate(b.date) - parseIsoDate(a.date);
      })[0] || null;
  }

  function latestPreviousBeforeOrOn(sources, targetDate) {
    const target = parseIsoDate(targetDate);
    if (!target) return null;
    return sources
      .filter((item) => normalizeDate(item.date) && parseIsoDate(item.date) <= target)
      .sort((a, b) => parseIsoDate(b.date) - parseIsoDate(a.date))[0] || null;
  }

  function assessmentFromPair(gfrSource, albuminuriaSource, staleSourceWhenOld) {
    const risk = calculateRisk(gfrSource.category, albuminuriaSource.category);
    if (!risk) return null;
    const intervalDays = daysBetween(gfrSource.date, albuminuriaSource.date);
    const maxDays = maxIntervalByRisk[risk.level] || 90;
    const key = pairKey(gfrSource.date, risk.gfrCategory, albuminuriaSource.date, risk.albuminuriaCategory);
    if (intervalDays === null || intervalDays > maxDays) {
      return { status: "stale", key, text: stalePhrase(staleSourceWhenOld, intervalDays), level: null };
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
      riskText: risk.text,
    };
  }

  function buildCurrentVisitAssessments() {
    const currentGfr = readCurrentGfrSources();
    const currentAlbuminuria = readCurrentAlbuminuriaSources();
    const previousGfr = loadPreviousGfrSources();
    const previousAlbuminuria = loadPreviousAlbuminuriaSources();
    const assessments = [];

    if (currentGfr.length) {
      currentGfr.forEach((gfr) => {
        const selectedAlbuminuria = currentAlbuminuria.length
          ? closestByDate(currentAlbuminuria, gfr.date)
          : latestPreviousBeforeOrOn(previousAlbuminuria, gfr.date);
        if (!selectedAlbuminuria) {
          assessments.push({ status: "missing", text: missingPhrase("albuminuria"), level: null });
          return;
        }
        const staleSource = selectedAlbuminuria.source === "previous_appointment" ? "albuminuria" : "albuminuria";
        const assessment = assessmentFromPair(gfr, selectedAlbuminuria, staleSource);
        if (assessment) assessments.push(assessment);
      });
    } else if (currentAlbuminuria.length) {
      currentAlbuminuria.forEach((albuminuria) => {
        const selectedGfr = latestPreviousBeforeOrOn(previousGfr, albuminuria.date);
        if (!selectedGfr) {
          assessments.push({ status: "missing", text: missingPhrase("gfr"), level: null });
          return;
        }
        const assessment = assessmentFromPair(selectedGfr, albuminuria, "gfr");
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

  function allBackendPotentialCalculatedKeys() {
    const keys = new Set();
    const currentGfr = readCurrentGfrSources();
    const currentAlbuminuria = readCurrentAlbuminuriaSources();
    const previousGfr = loadPreviousGfrSources();
    const previousAlbuminuria = loadPreviousAlbuminuriaSources();

    if (currentGfr.length && currentAlbuminuria.length) {
      currentGfr.forEach((gfr) => {
        currentAlbuminuria.forEach((albuminuria) => {
          const assessment = assessmentFromPair(gfr, albuminuria, "albuminuria");
          if (assessment && assessment.status === "calculated") keys.add(assessment.key);
        });
      });
    } else if (currentGfr.length) {
      currentGfr.forEach((gfr) => {
        const albuminuria = latestPreviousBeforeOrOn(previousAlbuminuria, gfr.date);
        if (!albuminuria) return;
        const assessment = assessmentFromPair(gfr, albuminuria, "albuminuria");
        if (assessment && assessment.status === "calculated") keys.add(assessment.key);
      });
    } else if (currentAlbuminuria.length) {
      currentAlbuminuria.forEach((albuminuria) => {
        const gfr = latestPreviousBeforeOrOn(previousGfr, albuminuria.date);
        if (!gfr) return;
        const assessment = assessmentFromPair(gfr, albuminuria, "gfr");
        if (assessment && assessment.status === "calculated") keys.add(assessment.key);
      });
    }
    return keys;
  }

  function chooseDefaultSelected(calculatedAssessments) {
    if (!calculatedAssessments.length) return "";
    if (selectedPairKey && calculatedAssessments.some((item) => item.key === selectedPairKey)) return selectedPairKey;
    return calculatedAssessments
      .slice()
      .sort((a, b) => (riskOrder[b.level] || 0) - (riskOrder[a.level] || 0))[0].key;
  }

  function setBlockRiskClass(block, selectedAssessment) {
    block.classList.remove("kdigo-risk-empty", "kdigo-risk-low", "kdigo-risk-moderate", "kdigo-risk-high", "kdigo-risk-very_high");
    if (selectedAssessment && selectedAssessment.level) {
      block.classList.add(`kdigo-risk-${selectedAssessment.level}`);
    } else {
      block.classList.add("kdigo-risk-empty");
    }
  }

  function syncHiddenExcludedPairs(selectedKey) {
    const container = document.getElementById("kdigoExcludedPairs");
    const selectedInput = document.getElementById("kdigoSelectedPair");
    if (!container) return;
    container.innerHTML = "";
    if (selectedInput) selectedInput.value = selectedKey || "";
    allBackendPotentialCalculatedKeys().forEach((key) => {
      if (key === selectedKey) return;
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "kdigo_excluded_pair";
      input.value = key;
      container.appendChild(input);
    });
  }

  function renderCurrentVisitOptions() {
    const block = document.getElementById("kdigoRiskPreview");
    const options = document.getElementById("kdigoCurrentRiskOptions");
    const textarea = document.getElementById("kdigoSelectedRiskText");
    if (!block || !options || !textarea) return;

    const assessments = buildCurrentVisitAssessments();
    const calculated = assessments.filter((item) => item.status === "calculated");
    selectedPairKey = chooseDefaultSelected(calculated);
    const selectedAssessment = calculated.find((item) => item.key === selectedPairKey) || null;

    options.innerHTML = "";

    if (calculated.length) {
      calculated.forEach((assessment, index) => {
        const row = document.createElement("label");
        row.className = `kdigo-current-option kdigo-current-option-${assessment.level}`;
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "kdigo_current_selected_option";
        radio.value = assessment.key;
        radio.checked = assessment.key === selectedPairKey;
        radio.addEventListener("change", () => {
          selectedPairKey = assessment.key;
          renderCurrentVisitOptions();
        });
        const text = document.createElement("span");
        text.textContent = assessment.text;
        row.appendChild(radio);
        row.appendChild(text);
        options.appendChild(row);
      });
      textarea.value = selectedAssessment ? selectedAssessment.text : calculated[0].text;
      syncHiddenExcludedPairs(selectedPairKey);
      setBlockRiskClass(block, selectedAssessment || calculated[0]);
    } else {
      const messages = [];
      const seen = new Set();
      assessments.forEach((assessment) => {
        if (seen.has(assessment.text)) return;
        seen.add(assessment.text);
        messages.push(assessment.text);
        const line = document.createElement("div");
        line.className = "kdigo-current-message text-muted small";
        line.textContent = assessment.text;
        options.appendChild(line);
      });
      textarea.value = messages.join("\n");
      syncHiddenExcludedPairs("");
      setBlockRiskClass(block, null);
    }
  }

  function loadSavedRiskHistory() {
    return readJsonScript("kdigoSavedRiskHistoryData")
      .map((item) => ({
        gfrDate: normalizeDate(item.gfr_date),
        gfrCategory: normalizeGfrCategory(item.gfr_category),
        albuminuriaDate: normalizeDate(item.albuminuria_date),
        albuminuriaCategory: normalizeAlbuminuriaCategory(item.albuminuria_category),
        riskLevel: String(item.risk_level || ""),
        riskText: String(item.risk_text || ""),
      }))
      .filter((item) => item.gfrDate && item.gfrCategory && item.albuminuriaDate && item.albuminuriaCategory && item.riskText);
  }

  function renderHistoryMatrix() {
    const container = document.getElementById("kdigoHistoryMatrix");
    if (!container) return;
    const history = loadSavedRiskHistory();
    container.innerHTML = "";
    if (!history.length) {
      container.innerHTML = '<div class="text-muted small">Нет сохранённых прогнозов по прошлым приёмам.</div>';
      return;
    }

    const rows = [];
    const cols = [];
    const rowSeen = new Set();
    const colSeen = new Set();
    history.forEach((item) => {
      const rowKey = `${item.gfrDate}|${item.gfrCategory}`;
      const colKey = `${item.albuminuriaDate}|${item.albuminuriaCategory}`;
      if (!rowSeen.has(rowKey)) {
        rowSeen.add(rowKey);
        rows.push({ key: rowKey, date: item.gfrDate, category: item.gfrCategory });
      }
      if (!colSeen.has(colKey)) {
        colSeen.add(colKey);
        cols.push({ key: colKey, date: item.albuminuriaDate, category: item.albuminuriaCategory });
      }
    });
    rows.sort((a, b) => parseIsoDate(a.date) - parseIsoDate(b.date));
    cols.sort((a, b) => parseIsoDate(a.date) - parseIsoDate(b.date));

    const table = document.createElement("table");
    table.className = "table table-sm table-bordered kdigo-history-matrix-table";
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    const corner = document.createElement("th");
    corner.textContent = "СКФ / альбуминурия";
    headRow.appendChild(corner);
    cols.forEach((col) => {
      const th = document.createElement("th");
      th.innerHTML = `<div>${formatRuDate(col.date)}</div><div class="small text-muted">${col.category}</div>`;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.innerHTML = `<div>${formatRuDate(row.date)}</div><div class="small text-muted">${row.category}</div>`;
      tr.appendChild(th);
      cols.forEach((col) => {
        const td = document.createElement("td");
        const matches = history.filter((item) => `${item.gfrDate}|${item.gfrCategory}` === row.key && `${item.albuminuriaDate}|${item.albuminuriaCategory}` === col.key);
        matches.forEach((item) => {
          const div = document.createElement("div");
          div.className = `kdigo-history-cell kdigo-history-cell-${item.riskLevel}`;
          div.textContent = item.riskText;
          td.appendChild(div);
        });
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
  }

  function scheduleRender() {
    window.setTimeout(renderCurrentVisitOptions, 0);
  }

  function init() {
    if (!document.getElementById("kdigoRiskPreview")) return;

    const refreshButton = document.getElementById("kdigoRefreshButton");
    if (refreshButton) refreshButton.addEventListener("click", renderCurrentVisitOptions);

    const historyButton = document.getElementById("kdigoHistoryToggleButton");
    const historyPanel = document.getElementById("kdigoHistoryPanel");
    if (historyButton && historyPanel) {
      historyButton.addEventListener("click", () => {
        historyPanel.classList.toggle("d-none");
        renderHistoryMatrix();
      });
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
'''


KDIGO_CSS = r'''/*
Назначение файла: стили блока KDIGO.

Что выполняет файл:
- подсвечивает весь блок текущего прогноза по выбранному уровню риска;
- оформляет radio-варианты текущего приёма;
- оформляет раскрываемую историческую матрицу;
- не меняет общий дизайн формы и карточки пациента.
*/

.kdigo-risk-preview {
  border: 1px solid #dee2e6;
  border-radius: 0.5rem;
  padding: 1rem;
  background: #f8f9fa;
}

.kdigo-risk-low {
  background: #eef8ef;
  border-color: #b9e2c0;
}

.kdigo-risk-moderate {
  background: #fff8d6;
  border-color: #f0df8a;
}

.kdigo-risk-high {
  background: #fff0df;
  border-color: #efbe85;
}

.kdigo-risk-very_high {
  background: #fde8e8;
  border-color: #e6a1a1;
}

.kdigo-current-option {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.5rem 0.65rem;
  border: 1px solid #dee2e6;
  border-radius: 0.375rem;
  background: #ffffff;
  margin-bottom: 0.5rem;
  cursor: pointer;
}

.kdigo-current-option input {
  margin-top: 0.25rem;
}

.kdigo-current-option-low {
  border-left: 0.35rem solid #7abf7a;
}

.kdigo-current-option-moderate {
  border-left: 0.35rem solid #e0c64d;
}

.kdigo-current-option-high {
  border-left: 0.35rem solid #df9235;
}

.kdigo-current-option-very_high {
  border-left: 0.35rem solid #c94a4a;
}

.kdigo-risk-conclusion-text {
  background: #fff8d6;
}

.kdigo-history-panel {
  border-top: 1px solid #dee2e6;
  padding-top: 0.75rem;
}

.kdigo-history-matrix-table th,
.kdigo-history-matrix-table td {
  vertical-align: middle;
  min-width: 9rem;
}

.kdigo-history-cell {
  border-radius: 0.25rem;
  padding: 0.25rem 0.4rem;
  text-align: center;
  font-size: 0.875rem;
}

.kdigo-history-cell-low {
  background: #eef8ef;
}

.kdigo-history-cell-moderate {
  background: #fff8d6;
}

.kdigo-history-cell-high {
  background: #fff0df;
}

.kdigo-history-cell-very_high {
  background: #fde8e8;
}
'''


TEST = r'''from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_kdigo_form_has_current_visit_selection_and_history_button():
    html = read("app/templates/appointment_form/_kdigo_risk_preview.html")

    assert "Выберите вариант прогноза" in html
    assert "kdigoCurrentRiskOptions" in html
    assert "kdigoSelectedPair" in html
    assert "kdigoSelectedRiskText" in html
    assert "Посмотреть историю прогнозов по KDIGO" in html
    assert "kdigoHistoryPanel" in html
    assert "kdigoSavedRiskHistoryData" in html
    assert "✖" not in html


def test_kdigo_js_builds_one_current_option_per_gfr_and_radio_selection():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert "buildCurrentVisitAssessments" in js
    assert "chooseDefaultSelected" in js
    assert "radio.type = \"radio\"" in js
    assert "kdigo_current_selected_option" in js
    assert "closestByDate(currentAlbuminuria, gfr.date)" in js
    assert "syncHiddenExcludedPairs" in js
    assert "allBackendPotentialCalculatedKeys" in js
    assert "renderHistoryMatrix" in js
    assert "kdigoHistoryToggleButton" in js
    assert "kdigo-risk-remove" not in js


def test_appointment_form_context_exposes_kdigo_history_for_repeat_visit():
    service = read("app/services/appointment_form_context_service.py")

    assert "_fetch_patient_ckd_prognosis_history" in service
    assert "ckd_prognosis_history" in service


def test_kdigo_css_has_current_options_and_history_matrix_styles():
    css = read("app/static/css/04_kdigo_risk.css")

    assert ".kdigo-current-option" in css
    assert ".kdigo-history-matrix-table" in css
    assert ".kdigo-history-cell-high" in css
'''


def patch_context_service() -> None:
    path = ROOT / "app/services/appointment_form_context_service.py"
    if not path.exists():
        print("WARN: app/services/appointment_form_context_service.py не найден")
        return
    content = path.read_text(encoding="utf-8")
    original = content

    if "_fetch_patient_ckd_prognosis_history" not in content:
        marker = "from app.repositories.lab_history import"
        if marker in content:
            content = content.replace(
                marker,
                "from app.repositories.ckd_prognosis import _fetch_patient_ckd_prognosis_history\n" + marker,
                1,
            )
        else:
            content = content.replace(
                "from app.db.connection import get_db_connection",
                "from app.db.connection import get_db_connection\nfrom app.repositories.ckd_prognosis import _fetch_patient_ckd_prognosis_history",
                1,
            )

    if '"ckd_prognosis_history"' not in content:
        candidates = [
            '"metrics_history": _fetch_patient_metrics_history(cur, patient_id),',
            '"metrics_history": _fetch_patient_metrics_history(cur, patient_id), ',
        ]
        inserted = False
        for candidate in candidates:
            if candidate in content:
                content = content.replace(
                    candidate,
                    candidate + ' "ckd_prognosis_history": _fetch_patient_ckd_prognosis_history(cur, patient_id, None),',
                    1,
                )
                inserted = True
                break
        if not inserted:
            # Более мягкая вставка перед словарями справочников в return context.
            marker = '"icd10_diagnoses": _fetch_icd10_diagnoses(cur),'
            if marker in content:
                content = content.replace(
                    marker,
                    '"ckd_prognosis_history": _fetch_patient_ckd_prognosis_history(cur, patient_id, None), ' + marker,
                    1,
                )

    if content != original:
        path.write_text(content, encoding="utf-8", newline="\n")
        print("OK: обновлён app/services/appointment_form_context_service.py")
    else:
        print("OK: appointment_form_context_service.py уже содержит KDIGO history")


def main() -> None:
    write("app/templates/appointment_form/_kdigo_risk_preview.html", KDIGO_TEMPLATE)
    write("app/static/js/kdigo_risk_preview.js", KDIGO_JS)
    write("app/static/css/04_kdigo_risk.css", KDIGO_CSS)
    write("tests/layer/test_kdigo_current_visit_selection_contract.py", TEST)
    patch_context_service()
    print("\nOK: KDIGO current-visit selection patch применён.")
    print("Теперь запусти: pytest tests/layer/test_kdigo_current_visit_selection_contract.py")
    print("Потом общий слой: pytest tests/layer")


if __name__ == "__main__":
    main()
