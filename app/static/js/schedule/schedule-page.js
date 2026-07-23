/*
  Контроллер страницы расписания.

  Отвечает за состояние интерфейса, отрисовку дня/недели, модальные формы,
  запись пациента, проверку пересечений, drag & drop и горячие клавиши.

  Важное отличие исправленной версии: код не зависит от window.bootstrap и
  ES-модулей. Поэтому страница продолжает работать даже если Bootstrap JS с CDN
  не загрузился; для модального окна используется небольшой локальный fallback.
*/
(function schedulePageController(global) {
  'use strict';

  function start() {
    const root = document.getElementById('scheduleApp');
    if (!root) return;

    const logic = global.ScheduleLogic;
    const api = global.ScheduleApi;
    const alertNode = root.querySelector('#scheduleAlert');

    function showFatal(message, error) {
      console.error(message, error || '');
      alertNode.className = 'alert alert-danger';
      alertNode.innerHTML = `<strong>Расписание не запустилось.</strong> ${message}`;
    }

    if (!logic || !api) {
      showFatal('Не загружены файлы schedule-logic.js или schedule-api.js. Проверьте, что папка app/static/js/schedule скопирована целиком.');
      return;
    }

    const {
      createId,
      dateKey,
      durationForType,
      escapeHtml,
      formatSlotRange,
      hasOverlap,
      minutesToTime,
      startOfWeek,
      toMinutes,
    } = logic;
    const { doctorsApi, patientsApi, slotsApi, templatesApi } = api;

    const $ = (selector) => root.querySelector(selector);
    const $$ = (selector) => Array.from(root.querySelectorAll(selector));
    const initialDate = root.dataset.initialDate;
    const parsedInitialDate = initialDate ? new Date(`${initialDate}T12:00:00`) : new Date();

    const state = {
      doctors: [],
      slots: [],
      selectedDoctorId: null,
      selectedDate: Number.isNaN(parsedInitialDate.getTime()) ? new Date() : parsedInitialDate,
      view: 'week',
      busyOnly: false,
      selectedSlotId: null,
      bookingSlotId: null,
      selectedPatient: null,
      patientSearchPerformed: false,
      template: { primaryDurationMinutes: 40, repeatedDurationMinutes: 15 },
    };

    const modal = $('#scheduleModal');
    const modalBackdrop = $('#scheduleModalBackdrop');

    function showAlert(message, type = 'success', autoHide = true) {
      alertNode.className = `alert alert-${type}`;
      alertNode.textContent = message;
      if (autoHide) {
        global.setTimeout(() => alertNode.classList.add('d-none'), 3800);
      }
    }

    function formatDate(date) {
      return new Intl.DateTimeFormat('ru-RU', {
        day: 'numeric', month: 'long', year: 'numeric',
      }).format(date);
    }

    function statusLabel(status) {
      return ({
        free: 'Свободен',
        busy: 'Занят',
        pending: 'Бронь / ожидание',
        break: 'Перерыв',
        day_off: 'Выходной',
      })[status] || status;
    }

    function getDoctorSlots(date = state.selectedDate) {
      return state.slots.filter((slot) => (
        Number(slot.doctorId) === Number(state.selectedDoctorId)
        && slot.date === dateKey(date)
      ));
    }

    function renderDoctorSelect(query = '') {
      const select = $('#doctorSelect');
      const normalized = String(query).trim().toLowerCase();
      const filtered = state.doctors.filter((doctor) => doctor.fio.toLowerCase().includes(normalized));
      select.innerHTML = filtered.map((doctor) => (
        `<option value="${doctor.id}">${escapeHtml(doctor.fio)}</option>`
      )).join('');

      if (filtered.some((doctor) => Number(doctor.id) === Number(state.selectedDoctorId))) {
        select.value = String(state.selectedDoctorId);
      } else if (filtered.length) {
        state.selectedDoctorId = Number(filtered[0].id);
        select.value = String(filtered[0].id);
      }
    }

    function renderPeriodLabel() {
      if (state.view === 'day') {
        $('#periodLabel').textContent = formatDate(state.selectedDate);
        return;
      }
      const start = startOfWeek(state.selectedDate);
      const end = new Date(start);
      end.setDate(end.getDate() + 6);
      $('#periodLabel').textContent = `${formatDate(start)} — ${formatDate(end)}`;
    }

    function renderDay() {
      const scale = $('#timeScale');
      const area = $('#daySlots');
      scale.innerHTML = '';
      area.innerHTML = '';

      for (let hour = 7; hour <= 19; hour += 1) {
        const label = document.createElement('span');
        label.className = 'schedule-time-label';
        label.style.top = `${(hour - 7) * 64}px`;
        label.textContent = `${String(hour).padStart(2, '0')}:00`;
        scale.append(label);
      }

      const visibleSlots = getDoctorSlots()
        .filter((slot) => !state.busyOnly || ['busy', 'pending'].includes(slot.status));

      if (!visibleSlots.length) {
        area.innerHTML = '<div class="schedule-empty">На выбранную дату слотов нет. Нажмите «Создать расписание на день».</div>';
        return;
      }

      visibleSlots.forEach((slot) => {
        const startOffset = toMinutes(slot.start) - 7 * 60;
        const card = document.createElement('article');
        card.className = `schedule-slot schedule-slot--${slot.status}${String(slot.id) === String(state.selectedSlotId) ? ' is-selected' : ''}`;
        card.style.top = `${startOffset * (64 / 60)}px`;
        card.style.height = `${Math.max(40, Number(slot.durationMinutes) * (64 / 60))}px`;
        card.tabIndex = 0;
        card.draggable = true;
        card.dataset.slotId = slot.id;
        card.title = slot.patientName || statusLabel(slot.status);
        card.innerHTML = `
          <div class="schedule-slot__top">
            <span>${escapeHtml(formatSlotRange(slot))}</span>
            <span>${slot.appointmentType === 'primary' ? 'Первичный' : 'Повторный'}</span>
          </div>
          <div class="schedule-slot__meta">
            ${escapeHtml(slot.patientName || statusLabel(slot.status))} · ${Number(slot.durationMinutes)} мин
          </div>`;
        area.append(card);
      });
    }

    function renderWeek() {
      const start = startOfWeek(state.selectedDate);
      const days = Array.from({ length: 7 }, (_, index) => {
        const date = new Date(start);
        date.setDate(date.getDate() + index);
        return date;
      });

      $('#weekHead').innerHTML = `<tr><th>Врач</th>${days.map((day) => (
        `<th>${new Intl.DateTimeFormat('ru-RU', { weekday: 'short', day: '2-digit', month: '2-digit' }).format(day)}</th>`
      )).join('')}</tr>`;

      $('#weekBody').innerHTML = state.doctors.map((doctor) => {
        const cells = days.map((day) => {
          const items = state.slots.filter((slot) => (
            Number(slot.doctorId) === Number(doctor.id) && slot.date === dateKey(day)
          ));
          const free = items.filter((slot) => slot.status === 'free').length;
          const busy = items.filter((slot) => ['busy', 'pending'].includes(slot.status)).length;
          const displayed = state.busyOnly ? `${busy}/${items.length}` : `${free}/${items.length}`;
          const title = state.busyOnly
            ? `Занято или ожидает: ${busy}; всего: ${items.length}`
            : `Свободно: ${free}; всего: ${items.length}`;
          return `
            <td class="schedule-week-cell" data-doctor-id="${doctor.id}" data-date="${dateKey(day)}" title="${title}">
              <span class="schedule-week-cell__value ${free ? 'has-free' : 'no-free'}">${displayed}</span>
            </td>`;
        }).join('');
        return `<tr><th>${escapeHtml(doctor.fio)}</th>${cells}</tr>`;
      }).join('');
    }

    function render() {
      renderPeriodLabel();
      $('#dayView').classList.toggle('d-none', state.view !== 'day');
      $('#weekView').classList.toggle('d-none', state.view !== 'week');
      $$('[data-view]').forEach((button) => {
        const active = button.dataset.view === state.view;
        button.classList.toggle('btn-primary', active);
        button.classList.toggle('btn-outline-primary', !active);
      });
      if (state.view === 'day') renderDay();
      else renderWeek();
    }

    function showModal() {
      modal.style.display = 'block';
      modal.classList.add('show');
      modal.removeAttribute('aria-hidden');
      modal.setAttribute('aria-modal', 'true');
      modalBackdrop.classList.remove('d-none');
    }

    function hideModal() {
      modal.classList.remove('show');
      modal.style.display = 'none';
      modal.setAttribute('aria-hidden', 'true');
      modal.removeAttribute('aria-modal');
      modalBackdrop.classList.add('d-none');
    }

    function openForm(title, html, onSave) {
      $('#scheduleModalTitle').textContent = title;
      $('#scheduleModalBody').innerHTML = html;
      const oldSave = $('#scheduleModalSave');
      const save = oldSave.cloneNode(true);
      oldSave.replaceWith(save);
      save.addEventListener('click', async () => {
        try {
          await onSave();
        } catch (error) {
          console.error(error);
          showAlert(`Не удалось сохранить: ${error.message || 'неизвестная ошибка'}`, 'danger', false);
        }
      });
      showModal();
    }

    function openDrawer(slot) {
      state.bookingSlotId = slot.id;
      state.selectedPatient = null;
      state.patientSearchPerformed = false;
      $('#bookingSlotSummary').textContent = `${slot.date}, ${formatSlotRange(slot)}`;
      $('#appointmentType').value = slot.appointmentType;
      $('#appointmentDuration').value = slot.durationMinutes;
      $('#patientName').value = '';
      $('#patientBirthDate').value = '';
      $('#patientName').classList.remove('is-invalid');
      $('#patientSearchResults').classList.add('d-none');
      $('#bookingConflict').classList.add('d-none');
      $('#bookingDrawer').classList.add('is-open');
      $('#bookingDrawer').setAttribute('aria-hidden', 'false');
      $('#drawerBackdrop').classList.remove('d-none');
      global.setTimeout(() => $('#patientName').focus(), 100);
    }

    function closeDrawer() {
      $('#bookingDrawer').classList.remove('is-open');
      $('#bookingDrawer').setAttribute('aria-hidden', 'true');
      $('#drawerBackdrop').classList.add('d-none');
    }

    function validateBookingOverlap() {
      const slot = state.slots.find((item) => String(item.id) === String(state.bookingSlotId));
      if (!slot) return false;
      const candidate = {
        ...slot,
        appointmentType: $('#appointmentType').value,
        durationMinutes: Number($('#appointmentDuration').value),
      };
      const conflict = hasOverlap(candidate, state.slots, candidate.id);
      $('#bookingConflict').classList.toggle('d-none', !conflict);
      return conflict;
    }

    async function searchPatient() {
      const fullName = $('#patientName').value.trim();
      if (!fullName) {
        $('#patientName').classList.add('is-invalid');
        return;
      }
      $('#patientName').classList.remove('is-invalid');
      state.selectedPatient = null;
      state.patientSearchPerformed = true;

      const results = await patientsApi.search({
        fullName,
        birthDate: $('#patientBirthDate').value,
      });

      const body = $('#patientResultsBody');
      body.innerHTML = results.length
        ? results.map((patient) => `
          <tr>
            <td>${escapeHtml(patient.fullName)}</td>
            <td>${escapeHtml(patient.birthDate || '—')}</td>
            <td><button class="btn btn-sm btn-outline-primary" type="button" data-patient-id="${patient.id}">Выбрать</button></td>
          </tr>`).join('')
        : '<tr><td colspan="3">Совпадений нет. Можно создать нового пациента.</td></tr>';
      $('#patientSearchResults').classList.remove('d-none');
    }

    async function bookSelectedPatient() {
      const slot = state.slots.find((item) => String(item.id) === String(state.bookingSlotId));
      if (!slot) return;
      const fullName = $('#patientName').value.trim();
      if (!fullName) {
        $('#patientName').classList.add('is-invalid');
        return;
      }
      if (!state.patientSearchPerformed) {
        showAlert('Сначала выполните поиск пациента.', 'warning');
        return;
      }
      if (!state.selectedPatient) {
        showAlert('Выберите найденного пациента или нажмите «Создать нового пациента».', 'warning');
        return;
      }
      if (validateBookingOverlap()) return;

      const next = {
        ...slot,
        patientId: state.selectedPatient.id,
        patientName: state.selectedPatient.fullName,
        status: 'busy',
        appointmentType: $('#appointmentType').value,
        durationMinutes: Number($('#appointmentDuration').value),
        durationOverridden: true,
      };
      await slotsApi.save(next);
      state.slots = state.slots.map((item) => String(item.id) === String(next.id) ? next : item);
      closeDrawer();
      render();
      showAlert('Пациент записан. Врач прикреплён к текущему приёму.');
    }

    async function createAndBookPatient() {
      const slot = state.slots.find((item) => String(item.id) === String(state.bookingSlotId));
      if (!slot) return;
      const fullName = $('#patientName').value.trim();
      if (!fullName) {
        $('#patientName').classList.add('is-invalid');
        return;
      }
      if (!state.patientSearchPerformed) {
        showAlert('Сначала выполните поиск, чтобы исключить дубликат пациента.', 'warning');
        return;
      }

      $('#appointmentType').value = 'primary';
      if (!$('#appointmentDuration').dataset.userChanged) {
        $('#appointmentDuration').value = durationForType(slot, 'primary');
      }
      if (validateBookingOverlap()) return;

      const patient = await patientsApi.create({
        fullName,
        birthDate: $('#patientBirthDate').value,
        doctorId: slot.doctorId,
      });
      const next = {
        ...slot,
        patientId: patient.id,
        patientName: patient.fullName,
        status: 'busy',
        appointmentType: 'primary',
        durationMinutes: Number($('#appointmentDuration').value),
        durationOverridden: true,
      };
      await slotsApi.save(next);
      state.slots = state.slots.map((item) => String(item.id) === String(next.id) ? next : item);
      closeDrawer();
      render();
      showAlert('Новый пациент создан и записан. Врач прикреплён к текущему приёму.');
    }

    function openSlotForm(existing) {
      const slot = existing || {
        id: createId(),
        doctorId: state.selectedDoctorId,
        date: dateKey(state.selectedDate),
        start: '09:00',
        durationMinutes: state.template.primaryDurationMinutes,
        status: 'free',
        appointmentType: 'primary',
        patientId: null,
        patientName: null,
        primaryDurationMinutes: state.template.primaryDurationMinutes,
        repeatedDurationMinutes: state.template.repeatedDurationMinutes,
        durationOverridden: false,
      };

      openForm(existing ? 'Редактировать слот' : 'Новый слот', `
        <div class="row g-3">
          <div class="col-sm-6"><label class="form-label">Дата</label><input id="modalDate" class="form-control" type="date" value="${slot.date}"></div>
          <div class="col-sm-6"><label class="form-label">Время</label><input id="modalTime" class="form-control" type="time" value="${slot.start}"></div>
          <div class="col-sm-6"><label class="form-label">Тип</label><select id="modalType" class="form-select"><option value="primary">Первичный</option><option value="repeated">Повторный</option></select></div>
          <div class="col-sm-6"><label class="form-label">Длительность</label><input id="modalDuration" class="form-control" type="number" min="5" max="240" step="5" value="${slot.durationMinutes}"></div>
          <div class="col-12"><label class="form-label">Статус</label><select id="modalStatus" class="form-select"><option value="free">Свободен</option><option value="busy">Занят</option><option value="pending">Бронь</option><option value="break">Перерыв</option><option value="day_off">Выходной</option></select></div>
          <div id="modalConflict" class="alert alert-danger d-none">Время занято другим приемом</div>
        </div>`, async () => {
          const next = {
            ...slot,
            date: $('#modalDate').value,
            start: $('#modalTime').value,
            appointmentType: $('#modalType').value,
            durationMinutes: Number($('#modalDuration').value),
            status: $('#modalStatus').value,
            durationOverridden: true,
          };
          if (hasOverlap(next, state.slots, existing ? existing.id : null)) {
            $('#modalConflict').classList.remove('d-none');
            return;
          }
          await slotsApi.save(next);
          state.slots = existing
            ? state.slots.map((item) => String(item.id) === String(next.id) ? next : item)
            : [...state.slots, next];
          hideModal();
          render();
          showAlert(existing ? 'Слот обновлён.' : 'Слот создан.');
        });

      $('#modalType').value = slot.appointmentType;
      $('#modalStatus').value = slot.status;
      $('#modalType').addEventListener('change', (event) => {
        $('#modalDuration').value = durationForType(slot, event.target.value);
      });
    }

    function openTemplateForm() {
      openForm('Шаблон недели', `
        <div class="row g-3">
          <div class="col-sm-6"><label class="form-label">Длительность первичного приёма (мин)</label><input id="templatePrimary" class="form-control" type="number" min="5" max="240" step="5" value="${state.template.primaryDurationMinutes}"></div>
          <div class="col-sm-6"><label class="form-label">Длительность повторного приёма (мин)</label><input id="templateRepeated" class="form-control" type="number" min="5" max="240" step="5" value="${state.template.repeatedDurationMinutes}"></div>
        </div>
        <p class="text-muted mt-3 mb-0">Значения наследуются новыми слотами. Для конкретного слота длительность можно изменить вручную.</p>`, async () => {
          state.template = await templatesApi.save({
            primaryDurationMinutes: Number($('#templatePrimary').value),
            repeatedDurationMinutes: Number($('#templateRepeated').value),
          });
          hideModal();
          showAlert('Шаблон сохранён.');
        });
    }

    function createDaySchedule() {
      openForm('Создать расписание на день', `
        <div class="row g-3">
          <div class="col-sm-4"><label class="form-label">Дата</label><input id="dayDate" class="form-control" type="date" value="${dateKey(state.selectedDate)}"></div>
          <div class="col-sm-4"><label class="form-label">Начало</label><input id="dayStart" class="form-control" type="time" value="07:00"></div>
          <div class="col-sm-4"><label class="form-label">Окончание</label><input id="dayEnd" class="form-control" type="time" value="19:00"></div>
          <div class="col-sm-6"><label class="form-label">Базовая длительность приёма (мин)</label><input id="dayDuration" class="form-control" type="number" min="5" max="240" step="5" value="${state.template.primaryDurationMinutes}"></div>
          <div id="dayScheduleError" class="alert alert-danger d-none"></div>
        </div>`, async () => {
          const date = $('#dayDate').value;
          const duration = Number($('#dayDuration').value);
          let cursor = toMinutes($('#dayStart').value);
          const end = toMinutes($('#dayEnd').value);
          const error = $('#dayScheduleError');

          if (!date || duration < 5 || cursor >= end) {
            error.textContent = 'Проверьте дату, время начала/окончания и длительность.';
            error.classList.remove('d-none');
            return;
          }

          const additions = [];
          while (cursor + duration <= end) {
            const candidate = {
              id: createId(),
              doctorId: state.selectedDoctorId,
              date,
              start: minutesToTime(cursor),
              durationMinutes: duration,
              status: 'free',
              appointmentType: 'primary',
              patientId: null,
              patientName: null,
              primaryDurationMinutes: state.template.primaryDurationMinutes,
              repeatedDurationMinutes: state.template.repeatedDurationMinutes,
              durationOverridden: false,
            };
            if (!hasOverlap(candidate, [...state.slots, ...additions])) additions.push(candidate);
            cursor += duration;
          }

          state.slots = [...state.slots, ...additions];
          await slotsApi.replaceAll(state.slots);
          hideModal();
          state.selectedDate = new Date(`${date}T12:00:00`);
          state.view = 'day';
          render();
          showAlert(`Создано слотов: ${additions.length}. Конфликтующие интервалы пропущены.`);
        });
    }

    function openCopyWeekForm() {
      const source = getDoctorSlots();
      if (!source.length) {
        showAlert('На выбранный день нет слотов для копирования.', 'warning');
        return;
      }
      const start = startOfWeek(state.selectedDate);
      const labels = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница'];
      const checkboxes = labels.map((label, offset) => {
        const target = new Date(start);
        target.setDate(target.getDate() + offset);
        const disabled = dateKey(target) === dateKey(state.selectedDate);
        return `
          <div class="form-check">
            <input class="form-check-input copy-day-checkbox" type="checkbox" value="${dateKey(target)}" id="copyDay${offset}" ${disabled ? 'disabled' : 'checked'}>
            <label class="form-check-label" for="copyDay${offset}">${label}, ${new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit' }).format(target)}${disabled ? ' — исходный день' : ''}</label>
          </div>`;
      }).join('');

      openForm('Применить ко всей неделе', `
        <p>Выберите дни, на которые нужно скопировать сетку. Занятые пациентами интервалы не копируются, конфликты пропускаются.</p>
        <div class="d-grid gap-2">${checkboxes}</div>`, async () => {
          const targets = Array.from(root.querySelectorAll('.copy-day-checkbox:checked')).map((node) => node.value);
          const additions = [];
          targets.forEach((date) => {
            source.forEach((slot) => {
              const copy = {
                ...slot,
                id: createId(),
                date,
                patientId: null,
                patientName: null,
                status: slot.status === 'busy' ? 'free' : slot.status,
              };
              if (!hasOverlap(copy, [...state.slots, ...additions])) additions.push(copy);
            });
          });
          state.slots = [...state.slots, ...additions];
          await slotsApi.replaceAll(state.slots);
          hideModal();
          render();
          showAlert(`Скопировано слотов: ${additions.length}. Конфликты пропущены.`);
        });
    }

    async function removeSelectedSlot() {
      if (!state.selectedSlotId) return;
      if (!global.confirm('Удалить выбранный слот?')) return;
      await slotsApi.remove(state.selectedSlotId);
      state.slots = state.slots.filter((slot) => String(slot.id) !== String(state.selectedSlotId));
      state.selectedSlotId = null;
      render();
      showAlert('Слот удалён.');
    }

    function bindEvents() {
      $('#doctorSearch').addEventListener('input', (event) => {
        renderDoctorSelect(event.target.value);
        render();
      });
      $('#doctorSelect').addEventListener('change', (event) => {
        state.selectedDoctorId = Number(event.target.value);
        render();
      });
      $('#busyOnlyToggle').addEventListener('change', (event) => {
        state.busyOnly = event.target.checked;
        render();
      });
      $('#patientName').addEventListener('input', () => {
        state.selectedPatient = null;
        state.patientSearchPerformed = false;
        $('#patientSearchResults').classList.add('d-none');
      });
      $('#patientBirthDate').addEventListener('change', () => {
        state.selectedPatient = null;
        state.patientSearchPerformed = false;
        $('#patientSearchResults').classList.add('d-none');
      });
      $('#appointmentType').addEventListener('change', (event) => {
        const slot = state.slots.find((item) => String(item.id) === String(state.bookingSlotId));
        if (slot) {
          $('#appointmentDuration').value = durationForType(slot, event.target.value);
          delete $('#appointmentDuration').dataset.userChanged;
          validateBookingOverlap();
        }
      });
      $('#appointmentDuration').addEventListener('input', () => {
        $('#appointmentDuration').dataset.userChanged = 'true';
        validateBookingOverlap();
      });

      root.addEventListener('click', async (event) => {
        try {
          const actionNode = event.target.closest('[data-action]');
          const action = actionNode ? actionNode.dataset.action : null;

          if (action === 'previous-period' || action === 'next-period') {
            const direction = action === 'next-period' ? 1 : -1;
            state.selectedDate.setDate(state.selectedDate.getDate() + direction * (state.view === 'day' ? 1 : 7));
            render();
          } else if (action === 'today') {
            state.selectedDate = new Date();
            render();
          } else if (action === 'open-template') {
            openTemplateForm();
          } else if (action === 'create-day') {
            createDaySchedule();
          } else if (action === 'create-slot') {
            openSlotForm(null);
          } else if (action === 'copy-week') {
            openCopyWeekForm();
          } else if (action === 'print') {
            global.print();
          } else if (action === 'close-drawer') {
            closeDrawer();
          } else if (action === 'close-modal') {
            hideModal();
          } else if (action === 'search-patient') {
            await searchPatient();
          } else if (action === 'book-patient') {
            await bookSelectedPatient();
          } else if (action === 'create-new-patient') {
            await createAndBookPatient();
          }

          const viewButton = event.target.closest('[data-view]');
          if (viewButton) {
            state.view = viewButton.dataset.view;
            render();
          }

          const weekCell = event.target.closest('.schedule-week-cell');
          if (weekCell) {
            state.selectedDoctorId = Number(weekCell.dataset.doctorId);
            state.selectedDate = new Date(`${weekCell.dataset.date}T12:00:00`);
            state.view = 'day';
            renderDoctorSelect();
            render();
          }

          const patientButton = event.target.closest('[data-patient-id]');
          if (patientButton) {
            const results = await patientsApi.search({
              fullName: $('#patientName').value,
              birthDate: $('#patientBirthDate').value,
            });
            state.selectedPatient = results.find((patient) => Number(patient.id) === Number(patientButton.dataset.patientId)) || null;
            if (state.selectedPatient) {
              const slot = state.slots.find((item) => String(item.id) === String(state.bookingSlotId));
              $('#appointmentType').value = 'repeated';
              $('#appointmentDuration').value = durationForType(slot, 'repeated');
              delete $('#appointmentDuration').dataset.userChanged;
              patientButton.textContent = 'Выбрано';
              patientButton.classList.remove('btn-outline-primary');
              patientButton.classList.add('btn-success');
              validateBookingOverlap();
              showAlert('Пациент выбран. Тип автоматически установлен как повторный.', 'info');
            }
          }

          const card = event.target.closest('.schedule-slot');
          if (card && !event.target.closest('button')) {
            const slot = state.slots.find((item) => String(item.id) === String(card.dataset.slotId));
            if (!slot) return;
            state.selectedSlotId = slot.id;
            if (slot.status === 'free') openDrawer(slot);
            else openSlotForm(slot);
            renderDay();
          }
        } catch (error) {
          console.error(error);
          showAlert(`Ошибка действия: ${error.message || 'неизвестная ошибка'}`, 'danger', false);
        }
      });

      document.addEventListener('keydown', async (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'n') {
          event.preventDefault();
          openSlotForm(null);
        }
        if (event.key === 'Delete' && state.selectedSlotId && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
          await removeSelectedSlot();
        }
        if (event.key === 'Escape') {
          closeDrawer();
          hideModal();
        }
      });

      let dragged = null;
      $('#daySlots').addEventListener('dragstart', (event) => {
        const card = event.target.closest('.schedule-slot');
        dragged = card ? state.slots.find((slot) => String(slot.id) === String(card.dataset.slotId)) : null;
      });
      $('#daySlots').addEventListener('dragover', (event) => event.preventDefault());
      $('#daySlots').addEventListener('drop', async (event) => {
        event.preventDefault();
        if (!dragged) return;
        const rect = $('#daySlots').getBoundingClientRect();
        const rawMinutes = ((event.clientY - rect.top) / 64) * 60 + 7 * 60;
        const minutes = Math.max(7 * 60, Math.min(19 * 60 - Number(dragged.durationMinutes), Math.round(rawMinutes / 5) * 5));
        const next = { ...dragged, start: minutesToTime(minutes) };
        if (hasOverlap(next, state.slots, next.id)) {
          showAlert('Время занято другим приемом. Перенос отменён.', 'danger');
          return;
        }
        await slotsApi.save(next);
        state.slots = state.slots.map((slot) => String(slot.id) === String(next.id) ? next : slot);
        renderDay();
        showAlert('Время слота изменено.');
      });
    }

    async function init() {
      root.dataset.initialized = 'loading';
      [state.doctors, state.slots, state.template] = await Promise.all([
        doctorsApi.list(),
        slotsApi.list(),
        templatesApi.load(),
      ]);
      state.selectedDoctorId = state.doctors.length ? Number(state.doctors[0].id) : null;
      renderDoctorSelect();
      bindEvents();
      render();
      root.dataset.initialized = 'true';
      $('#scheduleLoading').classList.add('d-none');
    }

    init().catch((error) => {
      root.dataset.initialized = 'error';
      showFatal(`Ошибка инициализации: ${escapeHtml(error.message || 'неизвестная ошибка')}`, error);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
}(window));
