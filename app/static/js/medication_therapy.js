(function () {
    'use strict';

    function clearMedicationRow(row) {
        row.querySelectorAll('input[type="text"]').forEach(function (input) {
            input.value = '';
            input.classList.remove('prefilled-field');
        });
        row.querySelector('input[name="medication"]')?.focus();
    }

    function initializeMedicationTherapy(root) {
        if (!root || root.dataset.medicationTherapyInitialized === 'true') {
            return;
        }
        root.dataset.medicationTherapyInitialized = 'true';

        // Значения, подставленные из прошлого приёма, выделяются целиком
        // при переходе в поле. Это работает и для строк, добавленных динамически.
        root.addEventListener('focusin', function (event) {
            const field = event.target.closest(
                'input[name="medication"], input[name="dosage"], input[name="schedule"]'
            );

            if (!field || !field.value.trim()) {
                return;
            }

            field.select();
        });

        root.addEventListener('click', function (event) {
            const addButton = event.target.closest('.add-medication-row-btn');
            if (addButton) {
                const group = addButton.closest('.medication-therapy-group');
                const rowsContainer = group?.querySelector('.medication-rows');
                const template = group?.querySelector('.medication-row-template');
                if (!rowsContainer || !template) {
                    return;
                }

                rowsContainer.appendChild(template.content.cloneNode(true));
                rowsContainer.lastElementChild
                    ?.querySelector('input[name="medication"]')
                    ?.focus();
                return;
            }

            const removeButton = event.target.closest('.remove-medication-row-btn');
            if (!removeButton) {
                return;
            }

            const row = removeButton.closest('.medication-row');
            const rowsContainer = row?.closest('.medication-rows');
            if (!row || !rowsContainer) {
                return;
            }

            const rows = rowsContainer.querySelectorAll('.medication-row');
            if (rows.length === 1) {
                clearMedicationRow(row);
            } else {
                row.remove();
            }
        });
    }

    function initializeAll() {
        document.querySelectorAll('[data-medication-therapy]').forEach(initializeMedicationTherapy);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeAll, { once: true });
    } else {
        initializeAll();
    }
})();
