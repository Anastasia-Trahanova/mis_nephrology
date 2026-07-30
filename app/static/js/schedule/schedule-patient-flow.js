/* Выбор действия при нажатии на ФИО пациента в расписании. */
(() => {
  const config = window.ScheduleConfig || {};
  if (!config.canStartAppointment) return;

  const style = document.createElement("style");
  style.textContent = `
    .schedule-patient-dialog {
      width: min(640px, calc(100vw - 2rem));
      padding: 0;
      border: 0;
      border-radius: .85rem;
      box-shadow: 0 1rem 3rem rgba(0, 0, 0, .25);
    }
    .schedule-patient-dialog::backdrop { background: rgba(33, 37, 41, .55); }
    .schedule-patient-dialog__header,
    .schedule-patient-dialog__body,
    .schedule-patient-dialog__footer { padding: 1rem 1.25rem; }
    .schedule-patient-dialog__header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      border-bottom: 1px solid #dee2e6;
    }
    .schedule-patient-dialog__header h3 { margin: 0; font-size: 1.2rem; }
    .schedule-patient-dialog__close {
      width: 2rem;
      height: 2rem;
      padding: 0;
      border: 0;
      background: transparent;
      color: #6c757d;
      font-size: 1.55rem;
      line-height: 1;
    }
    .schedule-patient-dialog__actions {
      display: grid;
      gap: .7rem;
      margin-top: 1rem;
    }
    .schedule-patient-dialog__actions .btn {
      min-height: 2.75rem;
      white-space: normal;
    }
    .schedule-patient-dialog__footer {
      border-top: 1px solid #dee2e6;
      text-align: center;
    }
  `;
  document.head.appendChild(style);

  const dialog = document.createElement("dialog");
  dialog.className = "schedule-patient-dialog";
  dialog.innerHTML = `
    <div class="schedule-patient-dialog__header">
      <h3 id="schedulePatientDialogTitle">Действия с пациентом</h3>
      <button type="button" class="schedule-patient-dialog__close" aria-label="Закрыть">×</button>
    </div>
    <div class="schedule-patient-dialog__body">
      <div data-role="message" aria-live="polite"></div>
      <div class="schedule-patient-dialog__actions" data-role="actions"></div>
      <div class="alert alert-danger d-none mt-3" data-role="error" role="alert"></div>
    </div>
    <div class="schedule-patient-dialog__footer">
      <button type="button" class="btn btn-outline-secondary" data-action="cancel">Отмена</button>
    </div>
  `;
  document.body.appendChild(dialog);

  const title = dialog.querySelector("h3");
  const message = dialog.querySelector('[data-role="message"]');
  const actions = dialog.querySelector('[data-role="actions"]');
  const errorBox = dialog.querySelector('[data-role="error"]');
  const closeButton = dialog.querySelector(".schedule-patient-dialog__close");
  const cancelButton = dialog.querySelector('[data-action="cancel"]');
  let busy = false;
  let currentEntry = null;
  let originalHref = "";

  const formatEntryDate = (value) => {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value || "");
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    }).format(parsed);
  };

  const responseError = (payload) => {
    if (payload && typeof payload.detail === "string") return payload.detail;
    return "Не удалось выполнить действие. Обновите страницу и повторите попытку.";
  };

  const clearError = () => {
    errorBox.textContent = "";
    errorBox.classList.add("d-none");
  };

  const showError = (text) => {
    errorBox.textContent = text;
    errorBox.classList.remove("d-none");
  };

  const setBusy = (value) => {
    busy = value;
    closeButton.disabled = value;
    cancelButton.disabled = value;
    actions.querySelectorAll("button").forEach((button) => {
      button.disabled = value;
    });
  };

  const addButton = (label, className, handler) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `btn ${className}`;
    button.textContent = label;
    button.addEventListener("click", handler);
    actions.appendChild(button);
  };

  const goToEmk = () => {
    window.location.assign(`/patient/${currentEntry.patient_id}`);
  };

  const createWalkIn = async (action) => {
    clearError();
    setBusy(true);
    message.textContent = "Создаём внеплановую запись на сегодня…";
    try {
      const response = await fetch(
        `/schedule/api/patients/${currentEntry.patient_id}/walk-in`,
        {
          method: "POST",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/json"
          },
          credentials: "same-origin",
          body: JSON.stringify({
            action,
            scheduled_entry_id: currentEntry.id
          })
        }
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(responseError(payload));
      window.location.assign(payload.redirect_url);
    } catch (error) {
      renderFutureChoice();
      showError(error.message);
      setBusy(false);
    }
  };

  const renderFutureChoice = () => {
    clearError();
    actions.replaceChildren();
    title.textContent = "Приём запланирован на будущее";
    message.textContent = `Запись стоит на ${formatEntryDate(currentEntry.starts_at)}. Выберите, как принять пациента сегодня.`;
    addButton(
      "Перезаписать пациента на сегодня",
      "btn-outline-danger",
      () => createWalkIn("cancel_and_create")
    );
    addButton(
      "Добавить ещё один приём сегодня и оставить будущую запись",
      "btn-primary",
      () => createWalkIn("keep_and_create")
    );
    addButton("Назад", "btn-outline-secondary", renderInitialChoice);
  };

  const startAppointment = () => {
    const scheduledStart = new Date(currentEntry.starts_at);
    if (!Number.isNaN(scheduledStart.getTime()) && scheduledStart > new Date()) {
      renderFutureChoice();
      return;
    }
    window.location.assign(originalHref);
  };

  const renderInitialChoice = () => {
    clearError();
    actions.replaceChildren();
    title.textContent = "Действия с пациентом";
    message.textContent = currentEntry.patient_fio || "Выберите действие";
    addButton("Посмотреть ЭМК пациента", "btn-outline-primary", goToEmk);
    addButton("Перейти к заполнению данных приёма", "btn-primary", startAppointment);
  };

  const openEntry = async (entryId, href) => {
    originalHref = href;
    currentEntry = null;
    clearError();
    actions.replaceChildren();
    title.textContent = "Действия с пациентом";
    message.textContent = "Загружаем данные записи…";
    if (typeof dialog.showModal === "function") dialog.showModal();
    setBusy(true);
    try {
      const response = await fetch(`/schedule/api/entries/${entryId}`, {
        headers: { "Accept": "application/json" },
        credentials: "same-origin"
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(responseError(payload));
      currentEntry = payload.item;
      if (currentEntry.appointment_id) {
        window.location.assign(href);
        return;
      }
      renderInitialChoice();
    } catch (error) {
      message.textContent = "Не удалось загрузить данные записи.";
      showError(error.message);
    } finally {
      setBusy(false);
    }
  };

  const closeDialog = () => {
    if (!busy && dialog.open) dialog.close();
  };
  closeButton.addEventListener("click", closeDialog);
  cancelButton.addEventListener("click", closeDialog);
  dialog.addEventListener("cancel", (event) => {
    if (busy) event.preventDefault();
  });

  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const link = event.target.closest(".schedule-entry__patient");
    if (!link) return;
    const card = link.closest(".schedule-entry[data-entry-id]");
    const entryId = Number(card && card.dataset.entryId);
    if (!Number.isInteger(entryId) || entryId <= 0) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    openEntry(entryId, link.href);
  }, true);
})();
