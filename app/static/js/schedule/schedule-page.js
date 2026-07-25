(() => {
  "use strict";

  const root = document.getElementById("scheduleApp");
  if (!root) return;

  const config = window.ScheduleConfig || {};
  const doctorFilter = document.getElementById("scheduleDoctorFilter");
  const weekFilter = document.getElementById("scheduleWeekFilter");
  const weekLabel = document.getElementById("scheduleWeekLabel");
  const weekWorkspace = document.getElementById("scheduleWeekWorkspace");
  const bookingWorkspace = document.getElementById("scheduleBookingWorkspace");
  const doctorHint = document.getElementById("scheduleDoctorHint");
  const alertBox = document.getElementById("scheduleAlert");
  const selectedDayWeekday = document.getElementById("selectedDayWeekday");
  const selectedDayDate = document.getElementById("selectedDayDate");
  const selectedDayEntries = document.getElementById("selectedDayEntries");
  const form = document.getElementById("scheduleBookingForm");
  const panelTitle = document.getElementById("bookingPanelTitle");
  const submitButton = document.getElementById("bookingSubmit");
  const entryIdInput = document.getElementById("bookingEntryId");
  const patientIdInput = document.getElementById("bookingPatientId");
  const patientModeInput = document.getElementById("bookingPatientMode");
  const bookingDate = document.getElementById("bookingDate");
  const bookingDoctor = document.getElementById("bookingDoctor");
  const bookingLocation = document.getElementById("bookingLocation");
  const startsAt = document.getElementById("bookingStartsAt");
  const endsAt = document.getElementById("bookingEndsAt");
  const durationBox = document.getElementById("bookingDuration");
  const lastName = document.getElementById("bookingLastName");
  const firstName = document.getElementById("bookingFirstName");
  const patronymic = document.getElementById("bookingPatronymic");
  const birthDate = document.getElementById("bookingBirthDate");
  const gender = document.getElementById("bookingGender");
  const phone = document.getElementById("bookingPhone");
  const searchResults = document.getElementById("patientSearchResults");
  const selectedPatientCard = document.getElementById("selectedPatientCard");

  const state = {
    doctorId: config.selectedDoctorId ? String(config.selectedDoctorId) : "",
    weekStart: String(config.selectedWeek || ""),
    selectedDate: "",
    panelOpen: false,
    entries: new Map(),
    patientResults: new Map(),
    selectedPatient: null,
    editingEntry: null,
    searchTimer: null,
  };

  const WEEKDAYS = ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"];
  const MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  class ApiError extends Error {
    constructor(message, detail = null) {
      super(message);
      this.name = "ApiError";
      this.detail = detail;
    }
  }

  function parseIso(value) {
    const [year, month, day] = String(value).split("-").map(Number);
    return new Date(year, month - 1, day, 12, 0, 0, 0);
  }

  function toIso(value) {
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  }

  function addDays(value, amount) {
    const result = parseIso(value);
    result.setDate(result.getDate() + amount);
    return toIso(result);
  }

  function mondayOf(value) {
    const result = parseIso(value);
    result.setDate(result.getDate() - ((result.getDay() + 6) % 7));
    return toIso(result);
  }

  function formatDay(value) {
    const current = parseIso(value);
    return {
      weekday: WEEKDAYS[current.getDay()],
      date: `${current.getDate()} ${MONTHS[current.getMonth()]} ${current.getFullYear()}`,
    };
  }

  function showError(message, scroll = true) {
    alertBox.textContent = String(message || "Произошла ошибка");
    alertBox.classList.remove("d-none");
    if (scroll) alertBox.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function clearError() {
    alertBox.textContent = "";
    alertBox.classList.add("d-none");
  }

  async function api(url, options = {}) {
    const response = await fetch(url, {
      headers: { Accept: "application/json", "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    let data = {};
    try { data = await response.json(); } catch (_) { data = {}; }
    if (!response.ok) {
      const detail = data.detail;
      const message = typeof detail === "string"
        ? detail
        : detail?.message || data.message || `Ошибка ${response.status}`;
      throw new ApiError(message, detail);
    }
    return data;
  }

  function buildScheduleUrl(weekStart) {
    const params = new URLSearchParams({ week: weekStart });
    if (state.doctorId) params.set("doctor_id", state.doctorId);
    return `/schedule?${params.toString()}`;
  }

  function entryHref(entry) {
    if (entry.appointment_id) return `/patient/${entry.patient_id}?appointment_id=${entry.appointment_id}`;
    if (config.canStartAppointment) {
      if (entry.appointment_type === "primary") return `/new-patient?schedule_entry_id=${entry.id}`;
      return `/new-appointment/${entry.patient_id}?schedule_entry_id=${entry.id}`;
    }
    return `/patient/${entry.patient_id}`;
  }

  function entryCard(entry) {
    const cancelled = entry.status === "cancelled";
    const editable = !cancelled && !entry.appointment_id;
    const statusBadge = ["no_show", "cancelled"].includes(entry.status)
      ? `<span class="schedule-status-badge status-${escapeHtml(entry.status)}">${escapeHtml(entry.status_label)}</span>`
      : "";
    const details = [
      entry.birth_date ? `Дата рождения: ${entry.birth_date.split("-").reverse().join(".")}` : "",
      entry.phone ? `Телефон: ${entry.phone}` : "",
      entry.appointment_type_label,
      entry.location_full_name,
    ].filter(Boolean).map((line) => `<div>${escapeHtml(line)}</div>`).join("");

    const menu = editable ? `
      <div class="dropdown schedule-entry-menu">
        <button type="button" class="btn btn-sm btn-light schedule-entry-menu__toggle"
                data-bs-toggle="dropdown" data-bs-boundary="viewport" aria-expanded="false" aria-label="Действия с записью">⋮</button>
        <ul class="dropdown-menu dropdown-menu-end">
          <li><button type="button" class="dropdown-item" data-action="edit-entry" data-entry-id="${entry.id}">Изменить запись</button></li>
          ${entry.status !== "no_show" ? `<li><button type="button" class="dropdown-item" data-action="set-status" data-entry-id="${entry.id}" data-status="no_show">Пациент не пришёл</button></li>` : ""}
          <li><hr class="dropdown-divider"></li>
          <li><button type="button" class="dropdown-item text-danger" data-action="set-status" data-entry-id="${entry.id}" data-status="cancelled">Отменить запись</button></li>
        </ul>
      </div>` : "";

    return `
      <article class="schedule-entry status-${escapeHtml(entry.status)} ${cancelled ? "is-cancelled" : ""} ${editable ? "is-editable" : ""}"
               data-entry-id="${entry.id}" data-editable="${editable ? "true" : "false"}"
               ${editable ? 'role="button" tabindex="0" title="Нажмите, чтобы изменить запись"' : ""}>
        <div class="schedule-entry__top">
          <strong>${escapeHtml(entry.time_label)}</strong>
          <div class="schedule-entry__top-actions">${statusBadge}${menu}</div>
        </div>
        <div class="schedule-patient-hover">
          <a class="schedule-entry__patient" href="${escapeHtml(entryHref(entry))}">${escapeHtml(entry.patient_fio)}</a>
          <div class="schedule-patient-popover">${details}</div>
        </div>
        <div class="schedule-entry__meta">
          <span>${escapeHtml(entry.appointment_type_label)}</span>
          ${entry.appointment_id ? "<span class=\"schedule-entry__saved\">✓ Приём сохранён</span>" : ""}
        </div>
      </article>`;
  }

  function groupEntries(items) {
    const grouped = new Map();
    for (const entry of items) {
      if (!grouped.has(entry.date_iso)) grouped.set(entry.date_iso, []);
      grouped.get(entry.date_iso).push(entry);
      state.entries.set(String(entry.id), entry);
    }
    return grouped;
  }

  function renderWeek(items) {
    state.entries.clear();
    const grouped = groupEntries(items);
    document.querySelectorAll("[data-day-entries]").forEach((container) => {
      const entries = grouped.get(container.dataset.dayEntries) || [];
      container.innerHTML = entries.length
        ? entries.map(entryCard).join("")
        : '<div class="schedule-empty-day">Нет записей</div>';
    });
  }

  async function loadWeekEntries() {
    if (!state.doctorId) {
      renderWeek([]);
      return;
    }
    const end = addDays(state.weekStart, 6);
    const data = await api(`/schedule/api/entries?doctor_id=${encodeURIComponent(state.doctorId)}&date_from=${state.weekStart}&date_to=${end}`);
    renderWeek(data.items || []);
  }

  async function loadSelectedDay() {
    const formatted = formatDay(state.selectedDate);
    selectedDayWeekday.textContent = formatted.weekday;
    selectedDayDate.textContent = formatted.date;
    bookingDate.value = state.selectedDate;
    selectedDayEntries.innerHTML = '<div class="schedule-empty-day">Загрузка…</div>';
    if (!state.doctorId) {
      selectedDayEntries.innerHTML = '<div class="schedule-empty-day">Выберите врача</div>';
      return;
    }
    const data = await api(`/schedule/api/entries?doctor_id=${encodeURIComponent(state.doctorId)}&date_from=${state.selectedDate}&date_to=${state.selectedDate}`);
    for (const entry of data.items || []) state.entries.set(String(entry.id), entry);
    selectedDayEntries.innerHTML = data.items?.length
      ? data.items.map(entryCard).join("")
      : '<div class="schedule-empty-day">Нет записей</div>';
  }

  function toggleBookingButtons() {
    const enabled = Boolean(state.doctorId);
    document.querySelectorAll("[data-action='open-booking']").forEach((button) => { button.disabled = !enabled; });
    doctorHint.classList.toggle("d-none", enabled);
  }

  function setDoctor(value) {
    state.doctorId = String(value || "");
    doctorFilter.value = state.doctorId;
    bookingDoctor.value = state.doctorId;
    toggleBookingButtons();
    const url = new URL(window.location.href);
    if (state.doctorId) url.searchParams.set("doctor_id", state.doctorId); else url.searchParams.delete("doctor_id");
    history.replaceState(null, "", url);
  }

  async function loadLocations(doctorId, selectedId = "") {
    bookingLocation.disabled = true;
    bookingLocation.replaceChildren(new Option("Загрузка…", ""));
    if (!doctorId) {
      bookingLocation.replaceChildren(new Option("Сначала выберите врача", ""));
      return;
    }
    const data = await api(`/schedule/api/doctors/${encodeURIComponent(doctorId)}/locations`);
    const options = [new Option("Выберите место приёма", "")];
    for (const item of data.items || []) options.push(new Option(item.full_name || item.name, item.id));
    if (options.length === 1) options[0].textContent = "У врача нет привязанных мест приёма";
    bookingLocation.replaceChildren(...options);
    bookingLocation.disabled = options.length === 1;
    bookingLocation.value = selectedId ? String(selectedId) : "";
  }

  function clearFieldError(field) {
    if (!field) return;
    field.classList.remove("is-invalid");
    field.removeAttribute("aria-invalid");
    const feedback = field.parentElement?.querySelector(`.schedule-field-error[data-for="${field.id}"]`);
    if (feedback) feedback.remove();
  }

  function clearFieldErrors() {
    form.querySelectorAll(".is-invalid").forEach(clearFieldError);
    form.querySelectorAll(".schedule-field-error").forEach((item) => item.remove());
  }

  function markInvalid(field, message) {
    if (!field) return;
    field.classList.add("is-invalid");
    field.setAttribute("aria-invalid", "true");
    let feedback = field.parentElement?.querySelector(`.schedule-field-error[data-for="${field.id}"]`);
    if (!feedback) {
      feedback = document.createElement("div");
      feedback.className = "invalid-feedback schedule-field-error";
      feedback.dataset.for = field.id;
      field.insertAdjacentElement("afterend", feedback);
    }
    feedback.textContent = message;
  }

  function focusFirstInvalid() {
    const field = form.querySelector(".is-invalid");
    if (!field) return;
    field.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => field.focus({ preventScroll: true }), 250);
  }

  function setPatientFieldsLocked(locked) {
    [lastName, firstName, patronymic, birthDate, phone].forEach((field) => { field.readOnly = locked; });
    gender.disabled = locked;
    birthDate.required = !locked;
    gender.required = !locked;
    phone.required = !locked;
  }

  function clearSearchResults() {
    state.patientResults.clear();
    searchResults.innerHTML = "";
    searchResults.classList.add("d-none");
  }

  function clearPatientSelection(preserveNames = false) {
    state.selectedPatient = null;
    patientIdInput.value = "";
    patientModeInput.value = "new";
    selectedPatientCard.innerHTML = "";
    selectedPatientCard.classList.add("d-none");
    setPatientFieldsLocked(false);
    if (!preserveNames) {
      lastName.value = "";
      firstName.value = "";
      patronymic.value = "";
    }
    birthDate.value = "";
    phone.value = "";
    gender.value = "";
    clearFieldErrors();
  }

  function selectedPatientActions(patient) {
    const editing = Boolean(entryIdInput.value);
    if (!editing) {
      return '<button type="button" class="btn btn-sm btn-link" data-action="different-patient">Это другой человек</button>';
    }
    const isOriginalPrimary = state.editingEntry
      && state.editingEntry.appointment_type === "primary"
      && String(state.editingEntry.patient_id) === String(patient.id);
    return `
      <div class="d-flex flex-wrap justify-content-end gap-2">
        ${isOriginalPrimary ? '<button type="button" class="btn btn-sm btn-outline-primary" data-action="edit-current-patient">Изменить данные</button>' : ""}
        <button type="button" class="btn btn-sm btn-link" data-action="different-patient">Выбрать другого пациента</button>
      </div>`;
  }

  function selectPatient(patient) {
    state.selectedPatient = patient;
    patientIdInput.value = patient.id;
    patientModeInput.value = "selected";
    lastName.value = patient.last_name || "";
    firstName.value = patient.first_name || "";
    patronymic.value = patient.patronymic || "";
    birthDate.value = patient.birth_date || "";
    phone.value = patient.phone || "";
    gender.value = patient.gender_value || "";
    setPatientFieldsLocked(true);
    clearSearchResults();
    selectedPatientCard.innerHTML = `
      <div><strong>${escapeHtml(patient.fio || patient.patient_fio)}</strong></div>
      <div class="small text-muted">${escapeHtml(patient.birth_date || "дата рождения не указана")} · ${escapeHtml(patient.phone || "телефон не указан")}</div>
      <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mt-2">
        <span class="badge text-bg-info">${escapeHtml(patient.appointment_type_label || "")}</span>
        ${selectedPatientActions(patient)}
      </div>`;
    selectedPatientCard.classList.remove("d-none");
    clearFieldErrors();
  }

  function editCurrentPatient() {
    if (!state.editingEntry || state.editingEntry.appointment_type !== "primary") return;
    patientModeInput.value = "edit_current";
    setPatientFieldsLocked(false);
    clearSearchResults();
    selectedPatientCard.innerHTML = `
      <div class="d-flex justify-content-between align-items-center gap-2">
        <strong>Редактирование данных пациента</strong>
        <button type="button" class="btn btn-sm btn-link" data-action="cancel-patient-edit">Отменить</button>
      </div>`;
    selectedPatientCard.classList.remove("d-none");
    lastName.focus();
  }

  function renderPatientResults(items) {
    state.patientResults.clear();
    for (const item of items) state.patientResults.set(String(item.id), item);
    if (!items.length) {
      searchResults.innerHTML = '<div class="text-muted small">Совпадений не найдено. Будет создан новый пациент.</div>';
    } else {
      searchResults.innerHTML = items.map((item) => `
        <button type="button" class="schedule-patient-result" data-action="select-patient" data-patient-id="${item.id}">
          <strong>${escapeHtml(item.fio)}</strong>
          <span>${escapeHtml(item.birth_date || "дата рождения не указана")} · ${escapeHtml(item.phone || "телефон не указан")}</span>
          <small>${escapeHtml(item.appointment_type_label)}</small>
        </button>`).join("");
    }
    searchResults.classList.remove("d-none");
  }

  async function searchPatients() {
    if (state.selectedPatient || patientModeInput.value === "edit_current") return;
    const surname = lastName.value.trim();
    if (surname.length < 2) {
      clearSearchResults();
      return;
    }
    const params = new URLSearchParams({ last_name: surname });
    try {
      const data = await api(`/schedule/api/patients/search?${params}`);
      renderPatientResults(data.items || []);
    } catch (error) {
      showError(error.message);
    }
  }

  function updateDuration() {
    if (!startsAt.value || !endsAt.value) {
      durationBox.textContent = "";
      return;
    }
    const [sh, sm] = startsAt.value.split(":").map(Number);
    const [eh, em] = endsAt.value.split(":").map(Number);
    const minutes = eh * 60 + em - sh * 60 - sm;
    durationBox.textContent = minutes > 0 ? `Продолжительность: ${minutes} мин.` : "Время окончания должно быть позже начала";
    durationBox.classList.toggle("text-danger", minutes <= 0);
  }

  function resetForm() {
    form.reset();
    entryIdInput.value = "";
    patientIdInput.value = "";
    patientModeInput.value = "new";
    state.selectedPatient = null;
    state.editingEntry = null;
    panelTitle.textContent = "Запись пациента";
    submitButton.textContent = "Подтвердить запись";
    clearSearchResults();
    selectedPatientCard.innerHTML = "";
    selectedPatientCard.classList.add("d-none");
    setPatientFieldsLocked(false);
    durationBox.textContent = "";
    clearFieldErrors();
  }

  function validateForm() {
    clearFieldErrors();
    const required = [
      [bookingDate, "Укажите дату приёма"],
      [bookingDoctor, "Выберите врача"],
      [bookingLocation, "Выберите место приёма"],
      [startsAt, "Укажите время начала"],
      [endsAt, "Укажите время окончания"],
      [lastName, "Укажите фамилию"],
      [firstName, "Укажите имя"],
    ];
    if (patientModeInput.value !== "selected") {
      required.push(
        [birthDate, "Укажите дату рождения"],
        [gender, "Укажите пол"],
        [phone, "Укажите номер телефона"],
      );
    }
    for (const [field, message] of required) {
      if (!String(field.value || "").trim()) markInvalid(field, message);
    }

    if (startsAt.value && endsAt.value) {
      const [sh, sm] = startsAt.value.split(":").map(Number);
      const [eh, em] = endsAt.value.split(":").map(Number);
      if (eh * 60 + em <= sh * 60 + sm) {
        markInvalid(startsAt, "Проверьте время начала");
        markInvalid(endsAt, "Окончание должно быть позже начала");
      }
    }

    if (form.querySelector(".is-invalid")) {
      showError("Проверьте выделенные поля", false);
      focusFirstInvalid();
      return false;
    }
    return true;
  }

  function mapServerError(error) {
    clearFieldErrors();
    const message = String(error?.message || "Не удалось сохранить запись");
    const text = message.toLowerCase();
    const fields = [];
    if (text.includes("время") || text.includes("у врача уже есть запись")) fields.push(startsAt, endsAt);
    if (text.includes("место") || text.includes("отделен")) fields.push(bookingLocation);
    if (text.includes("врач")) fields.push(bookingDoctor);
    if (text.includes("фио") || text.includes("пациент")) fields.push(lastName, firstName);
    if (text.includes("дату рождения") || text.includes("дата рождения")) fields.push(birthDate);
    if (text.includes("пол")) fields.push(gender);
    if (text.includes("телефон")) fields.push(phone);
    if (text.includes("прошедшую дату")) fields.push(bookingDate);
    for (const field of [...new Set(fields)]) markInvalid(field, message);
    showError(message, fields.length === 0);
    if (fields.length) focusFirstInvalid();
  }

  async function openBooking(dateValue) {
    clearError();
    resetForm();
    state.selectedDate = dateValue;
    state.panelOpen = true;
    setDoctor(state.doctorId);
    bookingDate.value = dateValue;
    weekWorkspace.classList.add("d-none");
    bookingWorkspace.classList.remove("d-none");
    await Promise.all([loadLocations(state.doctorId), loadSelectedDay()]);
    startsAt.focus();
  }

  async function openEdit(entry) {
    clearError();
    resetForm();
    state.selectedDate = entry.date_iso;
    state.panelOpen = true;
    state.editingEntry = entry;
    entryIdInput.value = entry.id;
    panelTitle.textContent = "Изменение записи";
    submitButton.textContent = "Сохранить изменения";
    setDoctor(entry.scheduled_doctor_id);
    weekWorkspace.classList.add("d-none");
    bookingWorkspace.classList.remove("d-none");
    await loadLocations(state.doctorId, entry.location_id);
    bookingDate.value = entry.date_iso;
    startsAt.value = entry.start_time;
    endsAt.value = entry.end_time;
    updateDuration();
    selectPatient({ ...entry, id: entry.patient_id, fio: entry.patient_fio });
    await loadSelectedDay();
  }

  async function closeBooking() {
    state.panelOpen = false;
    bookingWorkspace.classList.add("d-none");
    weekWorkspace.classList.remove("d-none");
    if (state.selectedDate && mondayOf(state.selectedDate) !== state.weekStart) {
      window.location.assign(buildScheduleUrl(mondayOf(state.selectedDate)));
      return;
    }
    await loadWeekEntries();
  }

  async function saveEntry(event) {
    event.preventDefault();
    clearError();
    if (!validateForm()) return;

    const editId = entryIdInput.value;
    const payload = {
      appointment_date: bookingDate.value,
      scheduled_doctor_id: Number(bookingDoctor.value),
      location_id: Number(bookingLocation.value),
      starts_at: startsAt.value,
      ends_at: endsAt.value,
      patient_id: patientIdInput.value ? Number(patientIdInput.value) : null,
      last_name: lastName.value.trim(),
      first_name: firstName.value.trim(),
      patronymic: patronymic.value.trim() || null,
      birth_date: birthDate.value || null,
      phone: phone.value.trim() || null,
      gender: gender.value === "male" ? true : gender.value === "female" ? false : null,
    };
    if (editId) payload.patient_mode = patientModeInput.value;

    submitButton.disabled = true;
    try {
      await api(editId ? `/schedule/api/entries/${editId}` : "/schedule/api/entries", {
        method: editId ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      await closeBooking();
    } catch (error) {
      mapServerError(error);
    } finally {
      submitButton.disabled = false;
    }
  }

  async function changeStatus(entryId, status) {
    let reason = null;
    if (status === "cancelled") {
      if (!window.confirm("Отменить запись пациента?")) return;
      reason = window.prompt("Причина отмены (необязательно):", "") || null;
    }
    clearError();
    try {
      await api(`/schedule/api/entries/${entryId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status, cancel_reason: reason }),
      });
      if (state.panelOpen) await loadSelectedDay(); else await loadWeekEntries();
    } catch (error) {
      showError(error.message);
    }
  }

  doctorFilter.addEventListener("change", async () => {
    clearError();
    setDoctor(doctorFilter.value);
    if (state.panelOpen) {
      await loadLocations(state.doctorId);
      await loadSelectedDay();
    } else {
      await loadWeekEntries();
    }
  });

  bookingDoctor.addEventListener("change", async () => {
    clearError();
    setDoctor(bookingDoctor.value);
    await loadLocations(state.doctorId);
    await loadSelectedDay();
  });

  weekFilter.addEventListener("change", () => window.location.assign(buildScheduleUrl(weekFilter.value)));
  form.addEventListener("submit", saveEntry);
  startsAt.addEventListener("input", updateDuration);
  endsAt.addEventListener("input", updateDuration);

  form.querySelectorAll("input, select").forEach((field) => {
    field.addEventListener("input", () => clearFieldError(field));
    field.addEventListener("change", () => clearFieldError(field));
  });

  lastName.addEventListener("input", () => {
    window.clearTimeout(state.searchTimer);
    state.searchTimer = window.setTimeout(searchPatients, 300);
  });

  root.addEventListener("click", async (event) => {
    const control = event.target.closest("[data-action]");
    if (control) {
      event.preventDefault();
      event.stopPropagation();
      const action = control.dataset.action;
      try {
        if (action === "open-booking") await openBooking(control.dataset.date);
        else if (action === "close-booking") await closeBooking();
        else if (action === "previous-day" || action === "next-day") {
          state.selectedDate = addDays(state.selectedDate, action === "previous-day" ? -1 : 1);
          bookingDate.value = state.selectedDate;
          await loadSelectedDay();
        } else if (action === "previous-week" || action === "next-week") {
          window.location.assign(buildScheduleUrl(addDays(state.weekStart, action === "previous-week" ? -7 : 7)));
        } else if (action === "select-patient") {
          const patient = state.patientResults.get(String(control.dataset.patientId));
          if (patient) selectPatient(patient);
        } else if (action === "different-patient") {
          clearPatientSelection(false);
          lastName.focus();
        } else if (action === "edit-current-patient") {
          editCurrentPatient();
        } else if (action === "cancel-patient-edit") {
          if (state.editingEntry) selectPatient({ ...state.editingEntry, id: state.editingEntry.patient_id, fio: state.editingEntry.patient_fio });
        } else if (action === "edit-entry") {
          const entry = state.entries.get(String(control.dataset.entryId));
          if (entry) await openEdit(entry);
        } else if (action === "set-status") {
          await changeStatus(control.dataset.entryId, control.dataset.status);
        }
      } catch (error) {
        showError(error.message);
      }
      return;
    }

    if (event.target.closest("a, button, input, select, textarea, .dropdown-menu")) return;
    const card = event.target.closest(".schedule-entry[data-editable='true']");
    if (card) {
      const entry = state.entries.get(String(card.dataset.entryId));
      if (entry) await openEdit(entry);
    }
  });

  root.addEventListener("keydown", async (event) => {
    if ((event.key === "Enter" || event.key === " ") && event.target.matches(".schedule-entry[data-editable='true']")) {
      event.preventDefault();
      const entry = state.entries.get(String(event.target.dataset.entryId));
      if (entry) await openEdit(entry);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.panelOpen) closeBooking();
  });

  setDoctor(state.doctorId);
  weekLabel.textContent = weekFilter.options[weekFilter.selectedIndex]?.textContent?.trim() || weekLabel.textContent;
  loadWeekEntries().catch((error) => showError(error.message));
})();
