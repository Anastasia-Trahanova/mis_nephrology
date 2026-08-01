(() => {
  document.querySelectorAll('[data-registry-dialog-open]').forEach((button) => {
    button.addEventListener('click', () => {
      const dialog = document.getElementById(button.dataset.registryDialogOpen);
      if (!dialog) return;
      if (typeof dialog.showModal === 'function') dialog.showModal();
      else dialog.setAttribute('open', '');
    });
  });

  document.querySelectorAll('.ckd-registry-dialog').forEach((dialog) => {
    dialog.querySelectorAll('[data-registry-dialog-close]').forEach((button) => {
      button.addEventListener('click', () => dialog.close());
    });
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
    });
  });
})();
