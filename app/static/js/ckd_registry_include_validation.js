(() => {
  "use strict";

  const form = document.querySelector("[data-ckd-include-form]");
  if (!(form instanceof HTMLFormElement)) return;

  const summary = form.querySelector("[data-ckd-validation-summary]");
  const controls = Array.from(
    form.querySelectorAll("input[required], select[required], textarea[required]")
  );

  const fieldLabel = (control) => {
    const ariaLabel = control.getAttribute("aria-label")?.trim();
    if (ariaLabel) return ariaLabel;

    if (control.id) {
      const label = form.querySelector(`label[for="${CSS.escape(control.id)}"]`);
      const text = label?.textContent?.trim();
      if (text) return text;
    }

    return control.name || "обязательное поле";
  };

  const feedbackFor = (control) => {
    const existingId = control.getAttribute("aria-describedby");
    if (existingId) {
      const existing = document.getElementById(existingId);
      if (existing?.classList.contains("ckd-registry-invalid-feedback")) return existing;
    }

    const feedback = document.createElement("div");
    feedback.id = `ckdRegistryInvalid_${control.name}_${Math.random().toString(36).slice(2, 8)}`;
    feedback.className = "ckd-registry-invalid-feedback";
    feedback.setAttribute("role", "status");
    control.insertAdjacentElement("afterend", feedback);
    control.setAttribute("aria-describedby", feedback.id);
    return feedback;
  };

  const validateControl = (control) => {
    control.setCustomValidity("");
    let message = "";
    const value = typeof control.value === "string" ? control.value.trim() : "";

    if (!value) {
      message = `Заполните поле «${fieldLabel(control)}»`;
    } else if (control.matches("[data-ckd-egfr]")) {
      const parsed = Number(value.replace(",", "."));
      if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1000) {
        message = "Укажите СКФ числом от 0 до 1000";
      }
    } else if (!control.validity.valid) {
      message = `Проверьте поле «${fieldLabel(control)}»`;
    }

    control.setCustomValidity(message);
    const invalid = Boolean(message);
    control.classList.toggle("is-invalid", invalid);
    control.setAttribute("aria-invalid", invalid ? "true" : "false");

    const feedback = feedbackFor(control);
    feedback.textContent = message;
    feedback.hidden = !invalid;
    return !invalid;
  };

  const hideSummaryWhenValid = () => {
    if (!summary) return;
    const hasInvalid = controls.some((control) => control.classList.contains("is-invalid"));
    if (!hasInvalid) {
      summary.classList.add("d-none");
      summary.textContent = "";
    }
  };

  controls.forEach((control) => {
    control.setAttribute("aria-required", "true");
    const eventName = control instanceof HTMLSelectElement ? "change" : "input";
    control.addEventListener(eventName, () => {
      if (control.classList.contains("is-invalid")) {
        validateControl(control);
        hideSummaryWhenValid();
      }
    });
    control.addEventListener("blur", () => {
      if (control.classList.contains("is-invalid")) validateControl(control);
    });
  });

  form.addEventListener("submit", (event) => {
    controls.forEach((control) => {
      if ((control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement)
          && control.type !== "date") {
        control.value = control.value.trim();
      }
    });

    const invalidControls = controls.filter((control) => !validateControl(control));
    if (!invalidControls.length) {
      if (summary) {
        summary.classList.add("d-none");
        summary.textContent = "";
      }
      return;
    }

    event.preventDefault();
    const labels = invalidControls.map(fieldLabel);
    if (summary) {
      summary.textContent = `Заполните обязательные поля: ${labels.join(", ")}.`;
      summary.classList.remove("d-none");
    }

    const firstInvalid = invalidControls[0];
    firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => firstInvalid.focus({ preventScroll: true }), 250);
  });
})();
