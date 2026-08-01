(() => {
  "use strict";

  const form = document.getElementById("analyticsFilterForm");
  const locationSelect = document.getElementById("analyticsLocation");
  const doctorSelect = document.getElementById("analyticsDoctor");
  const dateFrom = document.getElementById("analyticsDateFrom");
  const dateTo = document.getElementById("analyticsDateTo");
  const errorBox = document.getElementById("analyticsFilterError");

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
    if (!form || !locationSelect) return;
    locationSelect.value = String(locationId || "");
    filterDoctors();
    form.submit();
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

  locationSelect?.addEventListener("change", filterDoctors);
  form?.addEventListener("submit", validateDates);
  dateFrom?.addEventListener("change", () => validateDates());
  dateTo?.addEventListener("change", () => validateDates());
  filterDoctors();
  setupLocationLinks();
  setupSorting(document.getElementById("analyticsDoctorsTable"));
})();
