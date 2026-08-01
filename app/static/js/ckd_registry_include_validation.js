(() => {
  "use strict";

  if (window.__ckdRegistryIncludeValidationBound) return;
  window.__ckdRegistryIncludeValidationBound = true;

  const FORM_SELECTOR = "[data-ckd-include-form]";
  const REQUIRED_SELECTOR = "[data-ckd-required]";

  const formForTarget = (target) => {
    if (!(target instanceof Element)) return null;
    const form = target.closest(FORM_SELECTOR);
    return form instanceof HTMLFormElement ? form : null;
  };

  const fieldLabel = (form, control) => {
    const ariaLabel = control.getAttribute("aria-label")?.trim();
    if (ariaLabel) return ariaLabel;

    if (control.id) {
      const label = form.querySelector(`label[for="${CSS.escape(control.id)}"]`);
      const text = label?.textContent?.replace("(необязательно)", "")?.trim();
      if (text) return text;
    }

    return control.name || "обязательное поле";
  };

  const removeForeignValidation = (form) => {
    form.querySelectorAll(".mis-field-error-message, .mis-form-error-summary").forEach((node) => {
      const nodeId = node.id;
      if (nodeId) {
        form.querySelectorAll(`[aria-describedby="${CSS.escape(nodeId)}"]`).forEach((control) => {
          control.removeAttribute("aria-describedby");
        });
      }
      node.remove();
    });

    form.querySelectorAll(".mis-field-invalid").forEach((control) => {
      control.classList.remove("mis-field-invalid");
      if (!control.classList.contains("is-invalid")) {
        control.removeAttribute("aria-invalid");
      }
    });
  };

  const feedbackFor = (form, control) => {
    const savedId = control.dataset.ckdFeedbackId;
    if (savedId) {
      const saved = document.getElementById(savedId);
      if (saved?.classList.contains("ckd-registry-invalid-feedback")) return saved;
    }

    const existing = control.nextElementSibling;
    if (existing?.classList.contains("ckd-registry-invalid-feedback")) {
      control.dataset.ckdFeedbackId = existing.id;
      control.setAttribute("aria-describedby", existing.id);
      return existing;
    }

    const baseName = (control.id || control.name || "field").replace(/[^a-zA-Z0-9_-]/g, "_");
    let feedbackId = `ckdRegistryInvalid_${baseName}`;
    let suffix = 1;
    while (document.getElementById(feedbackId)) {
      feedbackId = `ckdRegistryInvalid_${baseName}_${suffix}`;
      suffix += 1;
    }

    const feedback = document.createElement("div");
    feedback.id = feedbackId;
    feedback.className = "ckd-registry-invalid-feedback";
    feedback.setAttribute("role", "status");
    feedback.hidden = true;
    control.insertAdjacentElement("afterend", feedback);
    control.dataset.ckdFeedbackId = feedback.id;
    control.setAttribute("aria-describedby", feedback.id);
    return feedback;
  };

  const validateControl = (form, control) => {
    control.setCustomValidity("");
    const rawValue = typeof control.value === "string" ? control.value.trim() : "";
    let message = "";

    if (!rawValue) {
      message = `Заполните поле «${fieldLabel(form, control)}»`;
    } else if (control.matches("[data-ckd-egfr]")) {
      const parsed = Number(rawValue.replace(",", "."));
      if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1000) {
        message = "Укажите СКФ числом от 0 до 1000";
      }
    } else if (!control.validity.valid) {
      message = `Проверьте поле «${fieldLabel(form, control)}»`;
    }

    control.setCustomValidity(message);
    const invalid = Boolean(message);
    control.classList.toggle("is-invalid", invalid);
    control.setAttribute("aria-invalid", invalid ? "true" : "false");

    const feedback = feedbackFor(form, control);
    feedback.textContent = message;
    feedback.hidden = !invalid;
    return !invalid;
  };

  const requiredControls = (form) => Array.from(form.querySelectorAll(REQUIRED_SELECTOR));

  const updateSummary = (form, invalidControls) => {
    const summary = form.querySelector("[data-ckd-validation-summary]");
    if (!summary) return;

    if (!invalidControls.length) {
      summary.classList.add("d-none");
      summary.textContent = "";
      return;
    }

    const labels = invalidControls.map((control) => fieldLabel(form, control));
    summary.textContent = `Заполните обязательные поля: ${labels.join(", ")}.`;
    summary.classList.remove("d-none");
  };

  const focusFirstInvalid = (control) => {
    control.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => {
      try {
        control.focus({ preventScroll: true });
      } catch (_error) {
        control.focus();
      }
    }, 250);
  };

  const validateForm = (form) => {
    removeForeignValidation(form);

    form.querySelectorAll("input, textarea").forEach((control) => {
      if (control.type !== "date" && typeof control.value === "string") {
        control.value = control.value.trim();
      }
    });

    const invalidControls = requiredControls(form).filter(
      (control) => !validateControl(form, control),
    );
    updateSummary(form, invalidControls);
    return invalidControls;
  };

  const initializeForm = (form) => {
    if (form.dataset.ckdValidationInitialized === "true") return;
    form.dataset.ckdValidationInitialized = "true";
    removeForeignValidation(form);

    requiredControls(form).forEach((control) => {
      control.setAttribute("aria-required", "true");
      const eventName = control instanceof HTMLSelectElement ? "change" : "input";

      control.addEventListener(eventName, () => {
        removeForeignValidation(form);
        if (control.classList.contains("is-invalid")) {
          validateControl(form, control);
          const invalidControls = requiredControls(form).filter((item) =>
            item.classList.contains("is-invalid"),
          );
          updateSummary(form, invalidControls);
        }
      });

      control.addEventListener("blur", () => {
        removeForeignValidation(form);
        if (control.classList.contains("is-invalid")) validateControl(form, control);
      });
    });
  };

  document.querySelectorAll(FORM_SELECTOR).forEach((form) => {
    if (form instanceof HTMLFormElement) initializeForm(form);
  });

  // Перехватываем отправку раньше общего simple_form_guard.js, чтобы форма регистра
  // проверялась только одним валидатором и сообщения не дублировались.
  window.addEventListener(
    "submit",
    (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement) || !form.matches(FORM_SELECTOR)) return;

      const invalidControls = validateForm(form);
      if (!invalidControls.length) return;

      event.preventDefault();
      event.stopImmediatePropagation();
      focusFirstInvalid(invalidControls[0]);
    },
    true,
  );

  const clearForeignAfterGlobalHandler = (event) => {
    const form = formForTarget(event.target);
    if (form) removeForeignValidation(form);
  };

  // Общий валидатор подключён глобально в base.html. После его обработчиков
  // удаляем только созданные им сообщения внутри формы регистра.
  document.addEventListener("input", clearForeignAfterGlobalHandler);
  document.addEventListener("change", clearForeignAfterGlobalHandler);
  document.addEventListener("blur", clearForeignAfterGlobalHandler, true);
})();
