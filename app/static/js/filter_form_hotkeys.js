/*
Единое поведение фильтров во всей МИС:
Enter в поле GET-формы применяет фильтры штатной отправкой формы.
POST-формы, textarea и редактируемые области не затрагиваются.
*/
(() => {
  "use strict";

  if (window.__filterFormHotkeysInitialized) return;
  window.__filterFormHotkeysInitialized = true;

  const CONTROL_SELECTOR = "input, select";
  const SUBMIT_SELECTOR = [
    'button[type="submit"]:not(:disabled)',
    'input[type="submit"]:not(:disabled)',
  ].join(",");

  function isHelpModalOpen() {
    return document.getElementById("hotkeysHelpModal")?.classList.contains("show") === true;
  }

  function isPlainEnter(event) {
    return event.code === "Enter"
      && !event.ctrlKey
      && !event.altKey
      && !event.metaKey
      && !event.shiftKey;
  }

  function isFilterForm(form) {
    if (!(form instanceof HTMLFormElement)) return false;
    if (form.dataset.enterSubmit === "false") return false;

    const method = (form.getAttribute("method") || "get").trim().toLowerCase();
    if (method !== "get") return false;

    return Boolean(form.querySelector(SUBMIT_SELECTOR));
  }

  function submitFilterForm(form) {
    const submitter = form.querySelector(SUBMIT_SELECTOR);
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit(submitter || undefined);
      return;
    }
    form.submit();
  }

  window.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.isComposing || !isPlainEnter(event)) return;
    if (isHelpModalOpen()) return;

    const control = event.target instanceof Element
      ? event.target.closest(CONTROL_SELECTOR)
      : null;
    if (!control || control.dataset.enterSubmit === "false") return;
    if (control instanceof HTMLInputElement
        && ["button", "submit", "reset", "checkbox", "radio", "file"].includes(control.type)) {
      return;
    }

    const form = control.closest("form");
    if (!isFilterForm(form)) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    submitFilterForm(form);
  }, true);
})();
