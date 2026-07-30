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

  const presets = {
    hemoglobin: { operator: "lt", value: "120" },
    potassium: { operator: "gt", value: "5.5" },
    ptg: { operator: "gt", value: "300" },
    egfr: { operator: "lt", value: "30", category: "С4" },
  };

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
    return document.getElementById("hotkeysHelpModal")?.classList.contains("show");
  }

  function stop(event) {
    event.preventDefault();
    event.stopPropagation();
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

  indicator.addEventListener("change", () => updateLayout(true));
  mode.addEventListener("change", () => updateLayout(false));
  operator.addEventListener("change", updateValueTo);
  updateLayout(false);
})();
