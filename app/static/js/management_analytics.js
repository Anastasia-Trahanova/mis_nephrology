(() => {
  "use strict";

  const form = document.getElementById("analyticsFilterForm");
  if (!form || window.__managementAnalyticsInitialized) return;
  window.__managementAnalyticsInitialized = true;

  const locationSelect = document.getElementById("analyticsLocation");
  const doctorSelect = document.getElementById("analyticsDoctor");
  const dateFrom = document.getElementById("analyticsDateFrom");
  const dateTo = document.getElementById("analyticsDateTo");
  const errorBox = document.getElementById("analyticsFilterError");
  const resetLink = form.querySelector('a[href="/analytics"]');
  const exportButton = form.querySelector('.analytics-export-dropdown [data-bs-toggle="dropdown"]');
  const fullExportLink = form.querySelector('.analytics-export-dropdown a[href*="report=all"]');

  function filterDoctors() {
    if (!locationSelect || !doctorSelect) return;
    const locationId = locationSelect.value;
    let selectedIsAvailable = !doctorSelect.value;
    [...doctorSelect.options].forEach((option, index) => {
      if (index === 0) return;
      const locations = (option.dataset.locationIds || "").split(",").filter(Boolean);
      const visible = !locationId || locations.includes(locationId);
      option.hidden = !visible;
      option.disabled = !visible;
      if (visible && option.selected) selectedIsAvailable = true;
    });
    if (!selectedIsAvailable) doctorSelect.value = "";
  }

  function validateDates(event) {
    if (!dateFrom || !dateTo || !errorBox) return true;
    if (dateFrom.value && dateTo.value && dateFrom.value > dateTo.value) {
      if (event) event.preventDefault();
      dateFrom.classList.add("is-invalid");
      dateTo.classList.add("is-invalid");
      errorBox.textContent = "Дата начала периода не может быть позже даты окончания.";
      errorBox.hidden = false;
      dateFrom.focus();
      return false;
    }
    dateFrom.classList.remove("is-invalid");
    dateTo.classList.remove("is-invalid");
    errorBox.hidden = true;
    return true;
  }

  function applyLocation(locationId) {
    if (!locationSelect) return;
    locationSelect.value = String(locationId || "");
    filterDoctors();
    form.requestSubmit();
  }

  function setupLocationLinks() {
    document.querySelectorAll("[data-location-id]").forEach((element) => {
      element.addEventListener("click", () => applyLocation(element.dataset.locationId));
    });
  }

  function setupSorting(table) {
    if (!table) return;
    let lastColumn = -1;
    let direction = 1;
    table.querySelectorAll("thead button[data-sort-column]").forEach((button) => {
      button.addEventListener("click", () => {
        const column = Number(button.dataset.sortColumn);
        const type = button.dataset.sortType || "text";
        direction = lastColumn === column ? -direction : 1;
        lastColumn = column;
        const body = table.tBodies[0];
        const rows = [...body.rows].filter((row) => row.cells.length > 1);
        rows.sort((left, right) => {
          const leftRaw = left.cells[column]?.dataset.sortValue ?? left.cells[column]?.textContent ?? "";
          const rightRaw = right.cells[column]?.dataset.sortValue ?? right.cells[column]?.textContent ?? "";
          if (type === "number") {
            const leftValue = Number(String(leftRaw).replace(",", ".")) || 0;
            const rightValue = Number(String(rightRaw).replace(",", ".")) || 0;
            return (leftValue - rightValue) * direction;
          }
          return String(leftRaw).localeCompare(String(rightRaw), "ru", { sensitivity: "base" }) * direction;
        });
        rows.forEach((row) => body.appendChild(row));
      });
    });
  }

  function isHelpModalOpen() {
    return document.getElementById("hotkeysHelpModal")?.classList.contains("show") === true;
  }

  function stopEvent(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }

  function focusFilter(control) {
    if (!control || control.disabled) return;
    control.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => control.focus({ preventScroll: true }), 150);
  }

  function toggleExportMenu() {
    if (!exportButton) return;
    if (window.bootstrap?.Dropdown) {
      window.bootstrap.Dropdown.getOrCreateInstance(exportButton).toggle();
      return;
    }
    exportButton.click();
  }

  function installHotkeysHelp() {
    const title = document.getElementById("pageHotkeysTitle");
    const list = title?.parentElement?.querySelector(".hotkeys-list");
    if (!list) return;
    list.innerHTML = `
      <div class="hotkey-row"><span class="hotkey-keys"><kbd>Alt</kbd><span>+</span><kbd>S</kbd></span><span class="hotkey-action">Применить фильтры</span></div>
      <div class="hotkey-row"><span class="hotkey-keys"><kbd>Alt</kbd><span>+</span><kbd>R</kbd></span><span class="hotkey-action">Сбросить фильтры</span></div>
      <div class="hotkey-row"><span class="hotkey-keys"><kbd>Alt</kbd><span>+</span><kbd>O</kbd></span><span class="hotkey-action">Перейти к выбору отделения</span></div>
      <div class="hotkey-row"><span class="hotkey-keys"><kbd>Alt</kbd><span>+</span><kbd>V</kbd></span><span class="hotkey-action">Перейти к выбору врача</span></div>
      <div class="hotkey-row"><span class="hotkey-keys"><kbd>Alt</kbd><span>+</span><kbd>E</kbd></span><span class="hotkey-action">Открыть меню выгрузок</span></div>
      <div class="hotkey-row"><span class="hotkey-keys"><kbd>Alt</kbd><span>+</span><kbd>C</kbd></span><span class="hotkey-action">Скачать общий аналитический отчёт</span></div>
    `;
  }

  function handleHotkeys(event) {
    if (event.defaultPrevented || event.isComposing || isHelpModalOpen()) return;
    const code = event.code;
    if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;

    if (code === "KeyS") {
      stopEvent(event);
      form.requestSubmit();
    } else if (code === "KeyR") {
      stopEvent(event);
      resetLink?.click();
    } else if (code === "KeyO") {
      stopEvent(event);
      focusFilter(locationSelect);
    } else if (code === "KeyV") {
      stopEvent(event);
      focusFilter(doctorSelect);
    } else if (code === "KeyE") {
      stopEvent(event);
      toggleExportMenu();
    } else if (code === "KeyC") {
      stopEvent(event);
      fullExportLink?.click();
    }
  }

  locationSelect?.addEventListener("change", filterDoctors);
  form.addEventListener("submit", validateDates);
  dateFrom?.addEventListener("change", () => validateDates());
  dateTo?.addEventListener("change", () => validateDates());
  window.addEventListener("keydown", handleHotkeys, true);

  filterDoctors();
  setupLocationLinks();
  setupSorting(document.getElementById("analyticsDoctorsTable"));
  installHotkeysHelp();
})();
