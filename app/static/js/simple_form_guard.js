/*
Назначение файла: живая проверка форм пациента и приёма.

Этот модуль нужен, чтобы врач видел проблему сразу в том поле,
где она возникла, а не после 20 минут ввода и не на белой странице
с техническим JSON.

Что делает файл:
- проверяет обязательные поля;
- проверяет клинические числовые поля по широким техническим пределам;
- проверяет даты: дата рождения, дата приёма, дата следующего визита,
  даты исследований;
- показывает короткие сообщения рядом с полем;
- подсвечивает проблемное поле красной рамкой;
- при попытке сохранить форму с ошибкой прокручивает к первому проблемному полю.

Что файл намеренно НЕ делает:
- не показывает врачу технические пределы проверки;
- не объясняет формулы и автоматическую нормализацию;
- не ругается на частично заполненные таблицы расчётов СКФ и ACR;
- не меняет введённые врачом значения без отдельной серверной логики.
*/

(function () {
  "use strict";

  const MESSAGE_REQUIRED = "Не все обязательные поля заполнены";
  const MESSAGE_INVALID_VALUE = "Неверное значение";

  const DATE_MESSAGES = {
    birthInFuture: "Дата рождения не может быть в будущем",
    appointmentBeforeBirth: "Дата приёма не может быть раньше даты рождения",
    nextBeforeAppointment: "Дата следующего визита не может быть раньше даты приёма",
    nextBeforeToday: "Дата следующего визита не может быть раньше текущей даты",
    investigationAfterAppointment: "Дата исследования не может быть позже даты приёма",
  };

  /*
  Широкие технические пределы для live-проверки.
  Это не нормы и не подсказки для врача. Наружу всегда показывается
  только короткое сообщение «Неверное значение».
  */
  const NUMERIC_RULES = {
    // Осмотр
    height: { min: 50, max: 250 },
    weight: { min: 30, max: 300 },
    systolic_pressure: { min: 50, max: 300 },
    diastolic_pressure: { min: 30, max: 200 },
    heart_rate: { min: 20, max: 250 },

    // ОАК
    hemoglobin: { min: 20, max: 250 },
    erythrocytes: { min: 0.5, max: 10 },
    leukocytes: { min: 0.1, max: 300 },
    platelets: { min: 5, max: 1500 },
    esr: { min: 0, max: 150 },
    mcv: { min: 40, max: 140 },
    hematocrit: { min: 5, max: 70, allowFractionPercent: true },

    // Биохимия
    creatinine: { min: 15, max: 3000 },
    urea: { min: 0.5, max: 80 },
    uric_acid: { min: 50, max: 1500 },
    glucose: { min: 0.5, max: 40 },
    total_protein: { min: 20, max: 120 },
    albumin: { min: 10, max: 70 },
    potassium: { min: 1, max: 10 },
    calcium: { min: 1, max: 4 },
    phosphorus: { min: 0.2, max: 5 },
    ferritin: { min: 0, max: 10000 },
    ptg: { min: 0, max: 10000 },

    // ОАМ
    specific_gravity: { min: 1.0, max: 1.05, specificGravity: true },
    urine_protein: { min: 0, max: 20 },
    urine_leukocytes: { min: 0, max: 10000 },
    urine_erythrocytes: { min: 0, max: 10000 },
    bacteria: { min: 0, max: 100 },

    // Альбуминурия: частично заполненные расчёты не блокируем,
    // но если поле заполнено, оно должно быть числом без абсурдных значений.
    urine_albumin: { min: 0, max: 100000 },
    urine_creatinine: { min: 0.000001, max: 1000000 },

    // УЗИ
    left_parenchyma: { min: 1, max: 50 },
    right_parenchyma: { min: 1, max: 50 },
  };

  const INVESTIGATION_DATE_FIELDS = [
    "cbc_investigation_date",
    "biochemistry_investigation_date",
    "urinalysis_investigation_date",
    "albuminuria_investigation_date",
    "ultrasound_investigation_date",
  ];

  const REQUIRED_FIELD_NAMES = [
    "last_name",
    "first_name",
    "birth_date",
    "gender",
    "doctor_id",
    "location_id",
    "appointment_date",
    "appointment_time",
  ];

  function todayIso() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function isVisibleControl(control) {
    if (!control || control.disabled) return false;
    if (control.type === "hidden") return false;
    if (control.closest("[hidden]")) return false;
    return true;
  }

  function controlsByName(form, name) {
    return Array.from(form.querySelectorAll(`[name="${CSS.escape(name)}"]`)).filter(isVisibleControl);
  }

  function firstControlByName(form, name) {
    return controlsByName(form, name)[0] || null;
  }

  function fieldValue(control) {
    if (!control) return "";
    return String(control.value || "").trim();
  }

  function selectedRadioValue(form, name) {
    const selected = form.querySelector(`input[type="radio"][name="${CSS.escape(name)}"]:checked`);
    return selected ? selected.value : "";
  }

  function parseClinicalNumber(rawValue, rule) {
    const text = String(rawValue || "").trim();
    if (!text) return null;

    const normalizedText = text.replace(/\s+/g, "").replace(",", ".");
    if (!/^[+-]?(\d+(\.\d*)?|\.\d+)$/.test(normalizedText)) {
      return Number.NaN;
    }

    let number = Number(normalizedText);
    if (!Number.isFinite(number)) return Number.NaN;

    // Удельный вес мочи: 1015 считаем допустимой формой ввода для 1.015.
    if (rule && rule.specificGravity && Number.isInteger(number) && number >= 1000 && number <= 1050) {
      number = number / 1000;
    }

    // Гематокрит: 0.39 допустим как 39%.
    if (rule && rule.allowFractionPercent && number > 0 && number < 1) {
      number = number * 100;
    }

    return number;
  }

  function parseIsoDate(value) {
        const text = String(value || "").trim();

        if (!text) return null;

        const match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);

        if (!match) return "invalid";

        const year = Number(match[1]);
        const month = Number(match[2]);
        const day = Number(match[3]);

        if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
            return "invalid";
        }

        const date = new Date(year, month - 1, day);

        if (Number.isNaN(date.getTime())) return "invalid";

        if (
            date.getFullYear() !== year ||
            date.getMonth() !== month - 1 ||
            date.getDate() !== day
        ) {
            return "invalid";
        }

        return text;
    }

  function ensureFieldMessage(control) {
    if (!control) return null;

    const existingId = control.getAttribute("aria-describedby");
    if (existingId) {
      const existing = document.getElementById(existingId);
      if (existing && existing.classList.contains("mis-field-error-message")) {
        return existing;
      }
    }

    const message = document.createElement("div");
    message.className = "mis-field-error-message";
    message.setAttribute("role", "alert");
    message.setAttribute("aria-live", "polite");
    message.hidden = true;

    const id = `mis-error-${control.name || "field"}-${Math.random().toString(36).slice(2)}`;
    message.id = id;
    control.setAttribute("aria-describedby", id);

    control.insertAdjacentElement("afterend", message);
    return message;
  }

  function setFieldError(control, messageText) {
    if (!control) return;
    control.classList.add("is-invalid", "mis-field-invalid");
    control.setAttribute("aria-invalid", "true");

    const message = ensureFieldMessage(control);
    if (message) {
      message.textContent = messageText;
      message.hidden = false;
    }
  }

  function clearFieldError(control) {
    if (!control) return;
    control.classList.remove("is-invalid", "mis-field-invalid");
    control.removeAttribute("aria-invalid");

    const describedBy = control.getAttribute("aria-describedby");
    if (!describedBy) return;

    const message = document.getElementById(describedBy);
    if (message && message.classList.contains("mis-field-error-message")) {
      message.textContent = "";
      message.hidden = true;
    }
  }

  function clearFieldGroup(form, name) {
    controlsByName(form, name).forEach(clearFieldError);
  }

  function firstInvalidControl(form) {
    return form.querySelector(".mis-field-invalid, .is-invalid");
  }

  function showFormSummary(form, text) {
    let summary = form.querySelector(".mis-form-error-summary[data-live-validation-summary='true']");
    if (!summary) {
      summary = document.createElement("div");
      summary.className = "alert alert-danger mis-form-error-summary";
      summary.dataset.liveValidationSummary = "true";
      summary.setAttribute("role", "alert");
      summary.setAttribute("aria-live", "assertive");
      form.insertAdjacentElement("afterbegin", summary);
    }
    summary.textContent = text;
    summary.hidden = false;
  }

  function hideFormSummary(form) {
    const summary = form.querySelector(".mis-form-error-summary[data-live-validation-summary='true']");
    if (summary) {
      summary.textContent = "";
      summary.hidden = true;
    }
  }

  function validateRequiredName(form, name, showError) {
    const controls = controlsByName(form, name);
    if (!controls.length) return true;

    const first = controls[0];
    let valid = true;

    if (first.type === "radio") {
      valid = Boolean(selectedRadioValue(form, name));
      if (!valid && showError) setFieldError(first, MESSAGE_REQUIRED);
      if (valid) clearFieldGroup(form, name);
      return valid;
    }

    valid = controls.some((control) => fieldValue(control) !== "");
    if (!valid && showError) setFieldError(first, MESSAGE_REQUIRED);
    if (valid) clearFieldGroup(form, name);
    return valid;
  }

  function validateNumericControl(control, showError) {
    if (!isVisibleControl(control)) return true;
    const rule = NUMERIC_RULES[control.name];
    if (!rule) return true;

    const value = fieldValue(control);
    if (!value) {
      clearFieldError(control);
      return true;
    }

    const number = parseClinicalNumber(value, rule);
    const valid = Number.isFinite(number) && number >= rule.min && number <= rule.max;

    if (valid) {
      clearFieldError(control);
      return true;
    }

    if (showError) setFieldError(control, MESSAGE_INVALID_VALUE);
    return false;
  }

  function validateBloodPressure(form, showError) {
    const systolic = firstControlByName(form, "systolic_pressure");
    const diastolic = firstControlByName(form, "diastolic_pressure");
    if (!systolic || !diastolic) return true;

    const systolicValue = parseClinicalNumber(fieldValue(systolic), NUMERIC_RULES.systolic_pressure);
    const diastolicValue = parseClinicalNumber(fieldValue(diastolic), NUMERIC_RULES.diastolic_pressure);

    if (!Number.isFinite(systolicValue) || !Number.isFinite(diastolicValue)) return true;
    if (!fieldValue(systolic) || !fieldValue(diastolic)) return true;

    if (systolicValue <= diastolicValue) {
      if (showError) {
        setFieldError(systolic, MESSAGE_INVALID_VALUE);
        setFieldError(diastolic, MESSAGE_INVALID_VALUE);
      }
      return false;
    }

    return true;
  }

  function validateSingleDateControl(control, showError) {
    if (!isVisibleControl(control)) return true;
    if (!control.name || !control.name.endsWith("_date")) return true;

    const value = fieldValue(control);
    if (!value) {
      clearFieldError(control);
      return true;
    }

    const parsed = parseIsoDate(value);
    if (parsed === "invalid") {
      if (showError) setFieldError(control, "Некорректная дата");
      return false;
    }

    return true;
  }

  function validateDateRelations(form, showError) {
    let valid = true;

    const birth = firstControlByName(form, "birth_date");
    const appointment = firstControlByName(form, "appointment_date");
    const next = firstControlByName(form, "next_control_date");

    const today = todayIso();
    const birthValue = birth ? parseIsoDate(fieldValue(birth)) : null;
    const appointmentValue = appointment ? parseIsoDate(fieldValue(appointment)) : null;
    const nextValue = next ? parseIsoDate(fieldValue(next)) : null;

    if (birth && birthValue && birthValue !== "invalid" && birthValue > today) {
      if (showError) setFieldError(birth, DATE_MESSAGES.birthInFuture);
      valid = false;
    }

    if (
      birth && appointment &&
      birthValue && birthValue !== "invalid" &&
      appointmentValue && appointmentValue !== "invalid" &&
      appointmentValue < birthValue
    ) {
      if (showError) setFieldError(appointment, DATE_MESSAGES.appointmentBeforeBirth);
      valid = false;
    }

    if (
      next && appointment &&
      nextValue && nextValue !== "invalid" &&
      appointmentValue && appointmentValue !== "invalid" &&
      nextValue < appointmentValue
    ) {
      if (showError) setFieldError(next, DATE_MESSAGES.nextBeforeAppointment);
      valid = false;
    }

    if (next && nextValue && nextValue !== "invalid" && nextValue < today) {
      if (showError) setFieldError(next, DATE_MESSAGES.nextBeforeToday);
      valid = false;
    }

    if (appointmentValue && appointmentValue !== "invalid") {
      INVESTIGATION_DATE_FIELDS.forEach((name) => {
        controlsByName(form, name).forEach((control) => {
          const investigationValue = parseIsoDate(fieldValue(control));
          if (investigationValue && investigationValue !== "invalid" && investigationValue > appointmentValue) {
            if (showError) setFieldError(control, DATE_MESSAGES.investigationAfterAppointment);
            valid = false;
          }
        });
      });
    }

    return valid;
  }

  function validateControl(control, showError) {
    if (!control || !control.form) return true;
    let valid = true;

    if (control.required || REQUIRED_FIELD_NAMES.includes(control.name)) {
      valid = validateRequiredName(control.form, control.name, showError) && valid;
    }

    valid = validateNumericControl(control, showError) && valid;
    valid = validateSingleDateControl(control, showError) && valid;

    // Проверки связей дат и АД выполняем после одиночного поля,
    // чтобы сообщение появлялось сразу при изменении любого связанного поля.
    valid = validateBloodPressure(control.form, showError) && valid;
    valid = validateDateRelations(control.form, showError) && valid;

    return valid;
  }

  function validateForm(form, showError) {
    let valid = true;

    REQUIRED_FIELD_NAMES.forEach((name) => {
      valid = validateRequiredName(form, name, showError) && valid;
    });

    Object.keys(NUMERIC_RULES).forEach((name) => {
      controlsByName(form, name).forEach((control) => {
        valid = validateNumericControl(control, showError) && valid;
      });
    });

    Array.from(form.querySelectorAll("input[name$='_date'], input[type='date']")).forEach((control) => {
      valid = validateSingleDateControl(control, showError) && valid;
    });

    valid = validateBloodPressure(form, showError) && valid;
    valid = validateDateRelations(form, showError) && valid;

    if (valid) hideFormSummary(form);
    return valid;
  }

  function focusFirstProblem(form) {
    const first = firstInvalidControl(form);
    if (!first) return;

    first.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => {
      try {
        first.focus({ preventScroll: true });
      } catch (error) {
        first.focus();
      }
    }, 250);
  }

  function messageForForm(form) {
    const requiredInvalid = REQUIRED_FIELD_NAMES.some((name) => {
      const controls = controlsByName(form, name);
      if (!controls.length) return false;
      const first = controls[0];
      if (first.type === "radio") return !selectedRadioValue(form, name);
      return controls.every((control) => fieldValue(control) === "");
    });

    if (requiredInvalid) return MESSAGE_REQUIRED;

    const invalid = firstInvalidControl(form);
    const describedBy = invalid ? invalid.getAttribute("aria-describedby") : null;
    const message = describedBy ? document.getElementById(describedBy) : null;
    return message && message.textContent ? message.textContent : MESSAGE_INVALID_VALUE;
  }

  document.addEventListener("input", function (event) {
    const control = event.target;
    if (!(control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement || control instanceof HTMLSelectElement)) return;
    validateControl(control, true);
  });

  document.addEventListener("change", function (event) {
    const control = event.target;
    if (!(control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement || control instanceof HTMLSelectElement)) return;
    validateControl(control, true);
  });

  document.addEventListener("blur", function (event) {
    const control = event.target;
    if (!(control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement || control instanceof HTMLSelectElement)) return;
    validateControl(control, true);
  }, true);

  document.addEventListener("submit", function (event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;

    const valid = validateForm(form, true);
    if (!valid) {
      event.preventDefault();
      event.stopPropagation();
      showFormSummary(form, messageForForm(form));
      focusFirstProblem(form);
    }
  }, true);

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form").forEach((form) => {
      hideFormSummary(form);
      validateForm(form, false);
    });
  });
})();
