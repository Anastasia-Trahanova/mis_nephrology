(() => {
  "use strict";

  const form = document.getElementById("ckdRegistryFilterForm");
  if (!form) return;

  const submitButton = document.getElementById("ckdRegistrySubmitButton");
  const resetButton = document.getElementById("ckdRegistryResetButton");
  const exportButton = document.getElementById("ckdRegistryExportButton");
  const previousPage = document.getElementById("ckdRegistryPreviousPage");
  const nextPage = document.getElementById("ckdRegistryNextPage");
  const egfrOperator = document.getElementById("ckdRegistryEgfrOperator");
  const egfrValueControl = document.getElementById("ckdRegistryEgfrValueControl");
  const egfrFromPrefix = document.getElementById("ckdRegistryEgfrFromPrefix");
  const egfrFrom = document.getElementById("ckdRegistryEgfrFrom");
  const egfrToGroup = document.getElementById("ckdRegistryEgfrToGroup");
  const egfrTo = document.getElementById("ckdRegistryEgfrTo");

  const syncEgfrFilter = () => {
    if (!egfrOperator || !egfrValueControl || !egfrFrom || !egfrTo) return;

    const active = Boolean(egfrOperator.value);
    const isRange = egfrOperator.value === "between";

    egfrValueControl.hidden = !active;
    egfrFrom.disabled = !active;
    egfrFromPrefix.hidden = !isRange;
    egfrToGroup.hidden = !isRange;
    egfrTo.disabled = !isRange;
  };

  egfrOperator?.addEventListener("change", syncEgfrFilter);
  syncEgfrFilter();

  const isInput = (target) => target instanceof HTMLInputElement
    || target instanceof HTMLSelectElement
    || target instanceof HTMLTextAreaElement;

  document.addEventListener("keydown", (event) => {
    const code = event.code;

    if (code === "Enter" && isInput(event.target) && !event.shiftKey && !event.ctrlKey && !event.altKey) {
      event.preventDefault();
      form.requestSubmit(submitButton || undefined);
      return;
    }

    if (event.altKey && code === "KeyS") {
      event.preventDefault();
      form.requestSubmit(submitButton || undefined);
      return;
    }

    if (event.altKey && code === "KeyR" && resetButton) {
      event.preventDefault();
      resetButton.click();
      return;
    }

    if (event.altKey && code === "KeyC" && exportButton) {
      event.preventDefault();
      exportButton.click();
      return;
    }

    if (event.ctrlKey && code === "ArrowLeft" && previousPage && !previousPage.classList.contains("disabled")) {
      event.preventDefault();
      previousPage.click();
      return;
    }

    if (event.ctrlKey && code === "ArrowRight" && nextPage && !nextPage.classList.contains("disabled")) {
      event.preventDefault();
      nextPage.click();
    }
  });
  document.querySelectorAll("[data-ckd-remove-form]").forEach((removeForm) => {
    removeForm.addEventListener("submit", (event) => {
      const patientName = removeForm.dataset.patientFio || "этого пациента";
      const confirmed = window.confirm(
        `Удалить ${patientName} из активного регистра ХБП? ЭМК и приёмы останутся без изменений.`
      );
      if (!confirmed) event.preventDefault();
    });
  });

})();
