(() => {
  const form = document.getElementById('ckdRegistryFilterForm');
  if (!form) return;

  const rows = Array.from(document.querySelectorAll('[data-ckd-registry-row]'));
  const submitButton = document.getElementById('ckdRegistrySubmitButton');
  const resetButton = document.getElementById('ckdRegistryResetButton');
  const exportButton = document.getElementById('ckdRegistryExportButton');
  const previousPage = document.getElementById('ckdRegistryPreviousPage');
  const nextPage = document.getElementById('ckdRegistryNextPage');
  let selectedIndex = rows.length ? 0 : -1;

  const isInput = (target) => target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement;
  const selectRow = (index) => {
    if (!rows.length) return;
    selectedIndex = Math.max(0, Math.min(index, rows.length - 1));
    rows.forEach((row, rowIndex) => {
      const selected = rowIndex === selectedIndex;
      row.classList.toggle('is-selected', selected);
      row.setAttribute('aria-selected', selected ? 'true' : 'false');
    });
    rows[selectedIndex].focus({ preventScroll: true });
    rows[selectedIndex].scrollIntoView({ block: 'nearest' });
  };

  rows.forEach((row, index) => row.addEventListener('click', () => selectRow(index)));
  if (rows.length) selectRow(0);

  document.addEventListener('keydown', (event) => {
    const code = event.code;
    if (code === 'Enter' && isInput(event.target) && !event.shiftKey && !event.ctrlKey && !event.altKey) {
      event.preventDefault();
      form.requestSubmit(submitButton || undefined);
      return;
    }
    if (event.altKey && code === 'KeyS') {
      event.preventDefault();
      form.requestSubmit(submitButton || undefined);
      return;
    }
    if (event.altKey && code === 'KeyR' && resetButton) {
      event.preventDefault();
      resetButton.click();
      return;
    }
    if (event.altKey && code === 'KeyC' && exportButton) {
      event.preventDefault();
      exportButton.click();
      return;
    }
    if (event.altKey && code === 'KeyO' && selectedIndex >= 0) {
      event.preventDefault();
      rows[selectedIndex].querySelector('[data-ckd-open-patient]')?.click();
      return;
    }
    if (!isInput(event.target) && (code === 'ArrowUp' || code === 'ArrowDown')) {
      event.preventDefault();
      selectRow(selectedIndex + (code === 'ArrowDown' ? 1 : -1));
      return;
    }
    if (event.ctrlKey && code === 'ArrowLeft' && previousPage && !previousPage.classList.contains('disabled')) {
      event.preventDefault();
      previousPage.click();
      return;
    }
    if (event.ctrlKey && code === 'ArrowRight' && nextPage && !nextPage.classList.contains('disabled')) {
      event.preventDefault();
      nextPage.click();
    }
  });
})();
