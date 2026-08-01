(() => {
  "use strict";
  const form = document.getElementById("patientRegistryForm");
  if (!form || window.__patientListsInitialized) return;
  window.__patientListsInitialized = true;
  const indicator = document.getElementById("registryIndicator");
  const mode = document.getElementById("registryMode");
  const operator = document.getElementById("registryOperator");
  const category = document.getElementById("registryCategory");
  const valueFrom = document.getElementById("registryValueFrom");
  const valueTo = document.getElementById("registryValueTo");
  const valueLabel = document.getElementById("registryValueLabel");
  const fromPrefix = document.getElementById("registryFromPrefix");
  const valueToGroup = document.getElementById("registryValueToGroup");
  const modeField = document.getElementById("registryModeField");
  const categoryField = document.getElementById("registryCategoryField");
  const operatorField = document.getElementById("registryOperatorField");
  const valueField = document.getElementById("registryValueField");
  const units = document.querySelectorAll(".registry-unit");
  const submitButton = document.getElementById("registrySubmitButton");
  const resetButton = document.getElementById("registryResetButton");
  const exportButton = document.getElementById("registryExportButton");
  const previousPage = document.getElementById("registryPreviousPage");
  const nextPage = document.getElementById("registryNextPage");
  const dynamicsModalElement = document.getElementById("registryDynamicsModal");
  const dynamicsTitle = document.getElementById("registryDynamicsTitle");
  const dynamicsPatient = document.getElementById("registryDynamicsPatient");
  const dynamicsBirthDate = document.getElementById("registryDynamicsBirthDate");
  const dynamicsLoading = document.getElementById("registryDynamicsLoading");
  const dynamicsError = document.getElementById("registryDynamicsError");
  const dynamicsEmpty = document.getElementById("registryDynamicsEmpty");
  const dynamicsChart = document.getElementById("registryDynamicsChart");
  const dynamicsSvg = document.getElementById("registryDynamicsSvg");
  const dynamicsModal = dynamicsModalElement && window.bootstrap?.Modal
    ? window.bootstrap.Modal.getOrCreateInstance(dynamicsModalElement)
    : null;
  const presets = {
    hemoglobin: { operator: "lt", value: "120" },
    potassium: { operator: "gt", value: "5.5" },
    ptg: { operator: "gt", value: "300" },
    egfr: { operator: "lt", value: "30", category: "С4" },
  };
  let dynamicsRequestId = 0;
  function setHidden(element, hidden) {
    element.hidden = hidden;
    element.querySelectorAll("input, select").forEach((control) => {
      control.disabled = hidden;
    });
  }
  function updateValueTo() {
    const showRangeEnd = !operatorField.hidden && operator.value === "between";
    valueToGroup.hidden = !showRangeEnd;
    fromPrefix.hidden = !showRangeEnd;
    valueTo.disabled = !showRangeEnd;
    valueLabel.textContent = showRangeEnd ? "Диапазон" : "Значение";
  }
  function updateLayout(usePreset) {
    const key = indicator.value;
    const isEgfr = key === "egfr";
    const unit = indicator.selectedOptions[0]?.dataset.unit || "";
    units.forEach((node) => {
      node.textContent = unit;
    });
    if (usePreset) {
      const preset = presets[key];
      operator.value = preset.operator;
      valueFrom.value = preset.value;
      valueTo.value = "";
      if (isEgfr) {
        mode.value = "category";
        category.value = preset.category;
      } else {
        mode.value = "manual";
      }
    }
    setHidden(modeField, !isEgfr);
    const categoryMode = isEgfr && mode.value === "category";
    setHidden(categoryField, !categoryMode);
    setHidden(operatorField, categoryMode);
    setHidden(valueField, categoryMode);
    updateValueTo();
  }
  function isAvailableLink(element) {
    return Boolean(
      element
      && !element.classList.contains("disabled")
      && element.getAttribute("aria-disabled") !== "true"
    );
  }
  function patientRows() {
    return Array.from(document.querySelectorAll("[data-registry-patient-row]"));
  }
  function selectRow(row, focusRow = true) {
    if (!row) return false;
    patientRows().forEach((item) => {
      const selected = item === row;
      item.classList.toggle("registry-row--selected", selected);
      item.setAttribute("aria-selected", selected ? "true" : "false");
      item.tabIndex = selected ? 0 : -1;
    });
    if (focusRow) {
      row.focus({ preventScroll: true });
      row.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    return true;
  }
  function selectedRow() {
    return document.querySelector("[data-registry-patient-row].registry-row--selected")
      || document.activeElement?.closest?.("[data-registry-patient-row]")
      || null;
  }
  function moveRow(direction) {
    const rows = patientRows();
    if (!rows.length) return false;
    const current = selectedRow();
    let index = rows.indexOf(current);
    if (index < 0) index = direction > 0 ? -1 : rows.length;
    index = Math.max(0, Math.min(rows.length - 1, index + direction));
    return selectRow(rows[index]);
  }
  function openSelectedPatient() {
    const row = selectedRow() || patientRows()[0] || null;
    const link = row?.querySelector("[data-registry-open-patient]");
    if (!link) return false;
    link.click();
    return true;
  }
  function isEditableTarget(target) {
    return Boolean(target instanceof HTMLElement && target.closest("input, select, textarea, [contenteditable='true']"));
  }

  function helpIsOpen() {
    return Boolean(document.querySelector(".modal.show"));
  }
  function stop(event) {
    event.preventDefault();
    event.stopPropagation();
  }
  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("ru-RU");
  }

  function formatValue(value) {
    return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(value);
  }
  function svgNode(name, attributes = {}, text = "") {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text) node.textContent = text;
    return node;
  }

  function buildAxisTitle(indicatorKey, indicatorLabel, unit) {
    if (indicatorKey === "egfr") {
      return `СКФ по CKD-EPI 2021, ${unit}`;
    }
    return unit ? `${indicatorLabel}, ${unit}` : indicatorLabel;
  }
  function renderDynamicsChart(rawPoints, unit, indicatorLabel, indicatorKey) {
    const points = rawPoints
      .map((point) => ({
        date: point.date,
        time: new Date(`${point.date}T00:00:00`).getTime(),
        value: Number(point.value),
      }))
      .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.value))
      .sort((left, right) => left.time - right.time);
    dynamicsSvg.replaceChildren();
    const chartTitle = svgNode(
      "title",
      { id: "registryDynamicsChartTitle" },
      `${indicatorLabel}: ${points.length} значений за весь срок наблюдения`
    );
    dynamicsSvg.append(chartTitle);
    if (!points.length) return false;
    const width = 760;
    const height = 360;
    const margin = { top: 24, right: 24, bottom: 88, left: 96 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const values = points.map((point) => point.value);
    let minValue = Math.min(...values);
    let maxValue = Math.max(...values);
    const padding = minValue === maxValue
      ? Math.max(Math.abs(minValue) * 0.1, 1)
      : (maxValue - minValue) * 0.1;
    minValue -= padding;
    maxValue += padding;
    const xStep = points.length > 1 ? plotWidth / (points.length - 1) : 0;
    const xPosition = (_, index) => {
      if (points.length === 1) return margin.left + plotWidth / 2;
      return margin.left + (index * xStep);
    };
    const yPosition = (value) => (
      margin.top + ((maxValue - value) / (maxValue - minValue)) * plotHeight
    );
    const yTicks = 5;
    for (let index = 0; index < yTicks; index += 1) {
      const ratio = index / (yTicks - 1);
      const y = margin.top + ratio * plotHeight;
      const value = maxValue - ratio * (maxValue - minValue);
      dynamicsSvg.append(
        svgNode("line", {
          x1: margin.left,
          y1: y,
          x2: width - margin.right,
          y2: y,
          class: "registry-chart-grid",
        }),
        svgNode("text", {
          x: margin.left - 10,
          y: y + 4,
          class: "registry-chart-label registry-chart-label--y",
          "text-anchor": "end",
        }, formatValue(value))
      );
    }
    dynamicsSvg.append(
      svgNode("line", {
        x1: margin.left,
        y1: margin.top,
        x2: margin.left,
        y2: margin.top + plotHeight,
        class: "registry-chart-axis",
      }),
      svgNode("line", {
        x1: margin.left,
        y1: margin.top + plotHeight,
        x2: width - margin.right,
        y2: margin.top + plotHeight,
        class: "registry-chart-axis",
      }),
      svgNode("text", {
        x: 20,
        y: margin.top + plotHeight / 2,
        class: "registry-chart-axis-title",
        transform: `rotate(-90 20 ${margin.top + plotHeight / 2})`,
        "text-anchor": "middle",
      }, buildAxisTitle(indicatorKey, indicatorLabel, unit)),
      svgNode("text", {
        x: margin.left + plotWidth / 2,
        y: height - 10,
        class: "registry-chart-axis-title",
        "text-anchor": "middle",
      }, "Дата")
    );
    points.forEach((point, index) => {
      const x = xPosition(point.time, index);
      dynamicsSvg.append(
        svgNode("line", {
          x1: x,
          y1: margin.top + plotHeight,
          x2: x,
          y2: margin.top + plotHeight + 6,
          class: "registry-chart-axis",
        })
      );
      const label = svgNode("text", {
        x,
        y: margin.top + plotHeight + 20,
        class: "registry-chart-label registry-chart-label--x",
        transform: `rotate(-35 ${x} ${margin.top + plotHeight + 20})`,
        "text-anchor": "end",
      }, formatDate(point.date));
      dynamicsSvg.append(label);
    });
    if (points.length > 1) {
      const pathData = points
        .map((point, index) => `${index === 0 ? "M" : "L"} ${xPosition(point.time, index)} ${yPosition(point.value)}`)
        .join(" ");
      dynamicsSvg.append(svgNode("path", { d: pathData, class: "registry-chart-line" }));
    }
    points.forEach((point, index) => {
      const circle = svgNode("circle", {
        cx: xPosition(point.time, index),
        cy: yPosition(point.value),
        r: 4.5,
        class: "registry-chart-point",
        tabindex: 0,
      });
      circle.append(svgNode("title", {}, `${formatDate(point.date)} — ${formatValue(point.value)} ${unit}`));
      dynamicsSvg.append(circle);
    });
    return true;
  }
  function setDynamicsState(state, message = "") {
    dynamicsLoading.hidden = state !== "loading";
    dynamicsError.hidden = state !== "error";
    dynamicsEmpty.hidden = state !== "empty";
    dynamicsChart.hidden = state !== "chart";
    dynamicsError.textContent = message;
  }
  async function showDynamics(button) {
    const patientId = button.dataset.patientId;
    const indicatorKey = button.dataset.indicator;
    const requestId = ++dynamicsRequestId;
    dynamicsTitle.textContent = `Динамика: ${button.dataset.indicatorLabel || "показатель"}`;
    dynamicsPatient.textContent = button.dataset.patientName || "";
    dynamicsBirthDate.textContent = button.dataset.birthDate
      ? `Дата рождения: ${formatDate(button.dataset.birthDate)}`
      : "Дата рождения: —";
    setDynamicsState("loading");
    dynamicsModal?.show();
    try {
      const response = await fetch(
        `/patient-lists/patient/${encodeURIComponent(patientId)}/dynamics?indicator=${encodeURIComponent(indicatorKey)}`,
        { headers: { Accept: "application/json" }, credentials: "same-origin", cache: "no-store" }
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Не удалось загрузить данные");
      if (requestId !== dynamicsRequestId) return;
      dynamicsTitle.textContent = `Динамика: ${data.indicator_label}`;
      dynamicsPatient.textContent = data.patient_fio;
      dynamicsBirthDate.textContent = `Дата рождения: ${formatDate(data.birth_date)}`;
      const rendered = renderDynamicsChart(
        data.points || [],
        data.unit || "",
        data.indicator_label || "Показатель",
        indicatorKey
      );
      setDynamicsState(rendered ? "chart" : "empty");
    } catch (error) {
      if (requestId !== dynamicsRequestId) return;
      setDynamicsState("error", error.message || "Не удалось загрузить данные");
    }
  }
  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.isComposing || helpIsOpen()) return;
    const code = event.code;
    if (!event.ctrlKey && !event.altKey && !event.metaKey && !event.shiftKey && code === "Enter") {
      const target = event.target;
      if (form.contains(target) && !target.closest("button, a")) {
        stop(event);
        form.requestSubmit(submitButton || undefined);
      }
      return;
    }
    if (event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
      if (code === "KeyS") {
        stop(event);
        form.requestSubmit(submitButton || undefined);
        return;
      }
      if (code === "KeyR" && resetButton) {
        stop(event);
        resetButton.click();
        return;
      }
      if (code === "KeyC" && exportButton) {
        stop(event);
        exportButton.click();
        return;
      }
      if (code === "KeyO") {
        if (openSelectedPatient()) stop(event);
        return;
      }
    }
    if (event.ctrlKey && !event.altKey && !event.metaKey && !event.shiftKey) {
      if (code === "ArrowLeft" && isAvailableLink(previousPage)) {
        stop(event);
        previousPage.click();
        return;
      }
      if (code === "ArrowRight" && isAvailableLink(nextPage)) {
        stop(event);
        nextPage.click();
        return;
      }
    }
    if (
      !event.ctrlKey
      && !event.altKey
      && !event.metaKey
      && !event.shiftKey
      && !isEditableTarget(event.target)
      && (code === "ArrowUp" || code === "ArrowDown")
    ) {
      if (moveRow(code === "ArrowDown" ? 1 : -1)) stop(event);
    }
  }, true);
  patientRows().forEach((row) => {
    row.addEventListener("click", () => selectRow(row, false));
    row.addEventListener("focusin", () => selectRow(row, false));
  });
  document.querySelectorAll("[data-registry-dynamics]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      selectRow(button.closest("[data-registry-patient-row]"), false);
      showDynamics(button);
    });
  });
  indicator.addEventListener("change", () => updateLayout(true));
  mode.addEventListener("change", () => updateLayout(false));
  operator.addEventListener("change", updateValueTo);
  updateLayout(false);
})();
