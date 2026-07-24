/*
Глобальные горячие клавиши МИС нефролога.

Основные принципы:
- глобальные команды подключаются через base.html;
- навигация по полям действует только в форме создания приёма;
- обычные стрелки в таблицах анализов перемещают фокус по строкам;
- сохранение выполняется штатной отправкой формы, поэтому сохраняются
  существующая браузерная и проектная валидация;
- после Ctrl + Shift + Enter Word скачивается уже с карточки сохранённого приёма.
*/

(function () {
    'use strict';

    const EXPORT_AFTER_SAVE_KEY = 'mis_nephrology_export_after_save';
    const EXPORT_REQUEST_TTL_MS = 2 * 60 * 1000;
    const FOCUSABLE_SELECTOR = [
        'input:not([type="hidden"])',
        'select',
        'textarea',
        'button',
        '[contenteditable="true"]'
    ].join(',');
    const ENTRY_FIELD_SELECTOR = [
        'input:not([type="hidden"])',
        'select',
        'textarea',
        '[contenteditable="true"]'
    ].join(',');

    let noticeTimer = null;
    let appointmentFormDirty = false;
    let formSubmissionLocked = false;

    function isVisible(element) {
        if (!(element instanceof HTMLElement)) {
            return false;
        }

        const style = window.getComputedStyle(element);
        return style.display !== 'none'
            && style.visibility !== 'hidden'
            && element.getClientRects().length > 0;
    }

    function isUsableControl(element) {
        if (!(element instanceof HTMLElement)) {
            return false;
        }

        if (!isVisible(element)) {
            return false;
        }

        if (element.matches(':disabled, [aria-disabled="true"], [data-hotkeys-skip]')) {
            return false;
        }

        if (element instanceof HTMLInputElement && element.type === 'hidden') {
            return false;
        }

        return true;
    }

    function isEntryField(element) {
        if (!(element instanceof HTMLElement) || !element.matches(ENTRY_FIELD_SELECTOR)) {
            return false;
        }

        if (!isUsableControl(element)) {
            return false;
        }

        if (element instanceof HTMLInputElement && element.readOnly) {
            return false;
        }

        if (element instanceof HTMLTextAreaElement && element.readOnly) {
            return false;
        }

        return true;
    }

    function isEditableTarget(element) {
        return element instanceof HTMLElement && Boolean(
            element.closest('input, textarea, select, [contenteditable="true"]')
        );
    }

    function isInsideTable(element) {
        return element instanceof HTMLElement && Boolean(element.closest('table'));
    }

    function focusControl(element, options) {
        if (!(element instanceof HTMLElement) || !isUsableControl(element)) {
            return false;
        }

        const config = Object.assign({ scroll: true, selectText: true }, options || {});

        if (config.scroll) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
        }

        window.setTimeout(function () {
            element.focus({ preventScroll: true });

            if (
                config.selectText
                && element instanceof HTMLInputElement
                && ['text', 'search', 'tel', 'email', 'url', 'number'].includes(element.type)
            ) {
                try {
                    element.select();
                } catch (error) {
                    // Для некоторых типов input браузер не поддерживает select().
                }
            }

            element.classList.remove('hotkeys-focus-flash');
            void element.offsetWidth;
            element.classList.add('hotkeys-focus-flash');
            window.setTimeout(function () {
                element.classList.remove('hotkeys-focus-flash');
            }, 750);
        }, config.scroll ? 180 : 0);

        return true;
    }

    function showNotice(message, type) {
        const notice = document.getElementById('hotkeysNotice');
        if (!notice) {
            return;
        }

        const alertType = type || 'secondary';
        notice.className = `hotkeys-notice alert alert-${alertType}`;
        notice.textContent = message;
        notice.hidden = false;

        if (noticeTimer !== null) {
            window.clearTimeout(noticeTimer);
        }

        noticeTimer = window.setTimeout(function () {
            notice.hidden = true;
        }, 3200);
    }

    function findAppointmentForm() {
        const candidates = Array.from(document.querySelectorAll('form')).filter(function (form) {
            const action = form.getAttribute('action') || '';
            const method = (form.getAttribute('method') || 'get').toLowerCase();

            if (method !== 'post') {
                return false;
            }

            return action.includes('/appointments/new')
                || action === '/api/patients/new'
                || action.endsWith('/api/patients/new');
        });

        return candidates[0] || null;
    }

    function getPatientIdFromPathOrForm() {
        const patientPathMatch = window.location.pathname.match(/^\/patient\/(\d+)(?:\/)?$/);
        if (patientPathMatch) {
            return patientPathMatch[1];
        }

        const newAppointmentPathMatch = window.location.pathname.match(/^\/new-appointment\/(\d+)(?:\/)?$/);
        if (newAppointmentPathMatch) {
            return newAppointmentPathMatch[1];
        }

        const form = findAppointmentForm();
        if (form) {
            const action = form.getAttribute('action') || '';
            const actionMatch = action.match(/\/api\/patients\/(\d+)\/appointments\/new/);
            if (actionMatch) {
                return actionMatch[1];
            }
        }

        const patientLink = document.querySelector('a[href^="/patient/"]');
        if (patientLink) {
            const linkMatch = patientLink.getAttribute('href').match(/^\/patient\/(\d+)/);
            if (linkMatch) {
                return linkMatch[1];
            }
        }

        return null;
    }

    function getFormEntryFields(form) {
        return Array.from(form.querySelectorAll(ENTRY_FIELD_SELECTOR)).filter(function (field) {
            return isEntryField(field) && !isInsideTable(field);
        });
    }

    function moveBetweenOrdinaryFields(direction) {
        const form = findAppointmentForm();
        if (!form) {
            return false;
        }

        const active = document.activeElement;
        if (active instanceof HTMLElement && isInsideTable(active)) {
            return false;
        }

        const fields = getFormEntryFields(form);
        if (fields.length === 0) {
            showNotice('В форме нет доступных полей.', 'warning');
            return true;
        }

        const activeIndex = fields.indexOf(active);
        let targetIndex;

        if (activeIndex === -1) {
            targetIndex = direction > 0 ? 0 : fields.length - 1;
        } else {
            targetIndex = activeIndex + direction;
        }

        if (targetIndex < 0 || targetIndex >= fields.length) {
            showNotice(direction > 0 ? 'Это последнее поле формы.' : 'Это первое поле формы.');
            return true;
        }

        return focusControl(fields[targetIndex]);
    }

    function getFormSections(form) {
        const headings = Array.from(form.querySelectorAll('h2, h3, h4, h5, h6')).filter(isVisible);
        const allControls = Array.from(form.querySelectorAll(FOCUSABLE_SELECTOR)).filter(isUsableControl);
        const sections = [];

        headings.forEach(function (heading, index) {
            const nextHeading = headings[index + 1] || null;
            const controls = allControls.filter(function (control) {
                const headingRelation = heading.compareDocumentPosition(control);
                const isAfterHeading = Boolean(headingRelation & Node.DOCUMENT_POSITION_FOLLOWING);
                if (!isAfterHeading) {
                    return false;
                }

                if (!nextHeading) {
                    return true;
                }

                const nextHeadingRelation = nextHeading.compareDocumentPosition(control);
                return Boolean(nextHeadingRelation & Node.DOCUMENT_POSITION_PRECEDING);
            });

            if (controls.length === 0) {
                return;
            }

            const preferredEntry = controls.find(isEntryField);
            const preferredButton = controls.find(function (control) {
                return control instanceof HTMLButtonElement;
            });

            sections.push({
                heading: heading,
                controls: controls,
                preferredControl: preferredEntry || preferredButton || controls[0]
            });
        });

        return sections;
    }

    function findCurrentSectionIndex(sections, active) {
        if (!(active instanceof HTMLElement)) {
            return -1;
        }

        const directControlIndex = sections.findIndex(function (section) {
            return section.controls.includes(active) || section.controls.some(function (control) {
                return control.contains(active);
            });
        });

        if (directControlIndex !== -1) {
            return directControlIndex;
        }

        let currentIndex = -1;
        sections.forEach(function (section, index) {
            const relation = section.heading.compareDocumentPosition(active);
            if (relation & Node.DOCUMENT_POSITION_FOLLOWING) {
                currentIndex = index;
            }
        });

        return currentIndex;
    }

    function moveToSection(direction) {
        const form = findAppointmentForm();
        if (!form) {
            return false;
        }

        const sections = getFormSections(form);
        if (sections.length === 0) {
            showNotice('Разделы формы не найдены.', 'warning');
            return true;
        }

        const active = document.activeElement;
        const currentIndex = findCurrentSectionIndex(sections, active);
        let targetIndex;

        if (currentIndex === -1) {
            targetIndex = direction > 0 ? 0 : sections.length - 1;
        } else {
            targetIndex = currentIndex + direction;
        }

        if (targetIndex < 0 || targetIndex >= sections.length) {
            showNotice(direction > 0 ? 'Это последний раздел формы.' : 'Это первый раздел формы.');
            return true;
        }

        const section = sections[targetIndex];
        section.heading.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return focusControl(section.preferredControl, { scroll: false });
    }

    function getControlsInCell(cell) {
        if (!(cell instanceof HTMLTableCellElement)) {
            return [];
        }

        return Array.from(cell.querySelectorAll(FOCUSABLE_SELECTOR)).filter(isUsableControl);
    }

    function moveVerticallyInTable(active, direction) {
        if (!(active instanceof HTMLElement)) {
            return false;
        }

        const cell = active.closest('td, th');
        const table = active.closest('table');
        if (!(cell instanceof HTMLTableCellElement) || !(table instanceof HTMLTableElement)) {
            return false;
        }

        const row = cell.parentElement;
        if (!(row instanceof HTMLTableRowElement)) {
            return false;
        }

        const rows = Array.from(table.rows);
        const rowIndex = rows.indexOf(row);
        const columnIndex = Array.from(row.cells).indexOf(cell);
        const currentCellControls = getControlsInCell(cell);
        const currentControlIndex = Math.max(0, currentCellControls.indexOf(active));

        for (
            let candidateRowIndex = rowIndex + direction;
            candidateRowIndex >= 0 && candidateRowIndex < rows.length;
            candidateRowIndex += direction
        ) {
            const targetCell = rows[candidateRowIndex].cells[columnIndex];
            if (!targetCell) {
                continue;
            }

            const targetControls = getControlsInCell(targetCell);
            if (targetControls.length === 0) {
                continue;
            }

            const targetControl = targetControls[Math.min(currentControlIndex, targetControls.length - 1)];
            return focusControl(targetControl);
        }

        showNotice(direction > 0 ? 'Ниже в этом столбце полей нет.' : 'Выше в этом столбце полей нет.');
        return true;
    }

    function scrollPage(direction) {
        // Небольшой шаг позволяет плавно читать длинную страницу,
        // не перескакивая сразу почти на целый экран. При удержании клавиш
        // повторяющиеся события keydown продолжают движение в выбранную сторону.
        const distance = Math.min(Math.max(Math.round(window.innerHeight * 0.18), 120), 220);
        window.scrollBy({ top: distance * direction, left: 0, behavior: 'smooth' });
    }

    function lockFormAfterSubmit(form) {
        formSubmissionLocked = true;
        form.dataset.hotkeysSubmitting = 'true';

        Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"]')).forEach(function (button) {
            button.disabled = true;
        });
    }

    function saveAppointment(downloadWordAfterSave) {
        const form = findAppointmentForm();
        if (!form) {
            showNotice('На этой странице нет формы приёма.', 'warning');
            return;
        }

        if (formSubmissionLocked || form.dataset.hotkeysSubmitting === 'true') {
            showNotice('Приём уже сохраняется.');
            return;
        }

        const onSubmit = function (event) {
            if (event.defaultPrevented) {
                return;
            }

            if (downloadWordAfterSave) {
                const patientId = getPatientIdFromPathOrForm();
                sessionStorage.setItem(EXPORT_AFTER_SAVE_KEY, JSON.stringify({
                    createdAt: Date.now(),
                    patientId: patientId
                }));
            } else {
                sessionStorage.removeItem(EXPORT_AFTER_SAVE_KEY);
            }

            lockFormAfterSubmit(form);
        };

        form.addEventListener('submit', onSubmit, { once: true });
        form.requestSubmit();
    }

    function getPendingExportRequest() {
        const rawValue = sessionStorage.getItem(EXPORT_AFTER_SAVE_KEY);
        if (!rawValue) {
            return null;
        }

        try {
            const value = JSON.parse(rawValue);
            if (!value || typeof value.createdAt !== 'number') {
                sessionStorage.removeItem(EXPORT_AFTER_SAVE_KEY);
                return null;
            }

            if (Date.now() - value.createdAt > EXPORT_REQUEST_TTL_MS) {
                sessionStorage.removeItem(EXPORT_AFTER_SAVE_KEY);
                return null;
            }

            return value;
        } catch (error) {
            sessionStorage.removeItem(EXPORT_AFTER_SAVE_KEY);
            return null;
        }
    }

    function findWordExportLink() {
        return document.querySelector('a[href^="/export/"][href$="/docx"]');
    }

    function downloadWord() {
        const exportLink = findWordExportLink();
        if (!exportLink) {
            showNotice('Сначала откройте карточку и выберите приём.', 'warning');
            return;
        }

        exportLink.click();
    }

    function runPendingExportAfterSave() {
        const pendingRequest = getPendingExportRequest();
        if (!pendingRequest) {
            return;
        }

        const appointmentForm = findAppointmentForm();
        if (appointmentForm) {
            // Если сервер вернул форму повторно из-за ошибки, автоматический экспорт не запускаем.
            sessionStorage.removeItem(EXPORT_AFTER_SAVE_KEY);
            return;
        }

        const exportLink = findWordExportLink();
        if (!exportLink) {
            return;
        }

        const currentPatientId = getPatientIdFromPathOrForm();
        if (
            pendingRequest.patientId
            && currentPatientId
            && String(pendingRequest.patientId) !== String(currentPatientId)
        ) {
            return;
        }

        sessionStorage.removeItem(EXPORT_AFTER_SAVE_KEY);
        window.setTimeout(function () {
            exportLink.click();
        }, 450);
    }

    function confirmLeavingDirtyAppointment() {
        if (!appointmentFormDirty) {
            return true;
        }

        return window.confirm(
            'В приёме есть несохранённые изменения. Перейти на другую страницу без сохранения?'
        );
    }

    function openMainAppointments() {
        if (!confirmLeavingDirtyAppointment()) {
            return;
        }

        window.location.href = '/';
    }

    function openNewAppointment() {
        const currentPath = window.location.pathname;
        if (/^\/new-appointment\/\d+\/?$/.test(currentPath)) {
            showNotice('Вы уже заполняете новый приём.');
            return;
        }

        const directLink = document.querySelector('a[href^="/new-appointment/"]');
        if (directLink) {
            if (!confirmLeavingDirtyAppointment()) {
                return;
            }
            directLink.click();
            return;
        }

        const patientId = getPatientIdFromPathOrForm();
        if (!patientId) {
            showNotice('Текущий пациент не определён.', 'warning');
            return;
        }

        if (!confirmLeavingDirtyAppointment()) {
            return;
        }

        window.location.href = `/new-appointment/${patientId}`;
    }

    function openCurrentPatientCard() {
        const patientId = getPatientIdFromPathOrForm();
        if (!patientId) {
            showNotice('Текущий пациент не определён.', 'warning');
            return;
        }

        if (window.location.pathname === `/patient/${patientId}`) {
            window.scrollTo({ top: 0, behavior: 'smooth' });
            return;
        }

        if (!confirmLeavingDirtyAppointment()) {
            return;
        }

        window.location.href = `/patient/${patientId}`;
    }

    function focusPatientSearch() {
        const searchInput = document.getElementById('searchInput');
        if (!searchInput || !isUsableControl(searchInput)) {
            showNotice('Поиск пациента доступен на главной странице.', 'warning');
            return;
        }

        focusControl(searchInput, { scroll: true, selectText: true });
    }

    function isHelpModalOpen() {
        const modal = document.getElementById('hotkeysHelpModal');
        return Boolean(modal && modal.classList.contains('show'));
    }

    function handleKeydown(event) {
        if (event.defaultPrevented || event.isComposing) {
            return;
        }

        if (isHelpModalOpen()) {
            return;
        }

        const active = document.activeElement;
        const code = event.code;

        // Ctrl + Shift + Enter: сохранить и скачать Word.
        if (event.ctrlKey && event.shiftKey && code === 'Enter') {
            event.preventDefault();
            saveAppointment(true);
            return;
        }

        // Ctrl + Enter: сохранить приём.
        if (event.ctrlKey && !event.shiftKey && code === 'Enter') {
            event.preventDefault();
            saveAppointment(false);
            return;
        }

        // Ctrl + ↑ / Ctrl + ↓: плавная пошаговая прокрутка на всех страницах.
        if (event.ctrlKey && !event.altKey && !event.shiftKey && code === 'ArrowUp') {
            event.preventDefault();
            scrollPage(-1);
            return;
        }

        if (event.ctrlKey && !event.altKey && !event.shiftKey && code === 'ArrowDown') {
            event.preventDefault();
            scrollPage(1);
            return;
        }

        // Глобальные переходы определяются по физическим клавишам,
        // поэтому работают и при русской раскладке.
        if (event.altKey && !event.ctrlKey && !event.shiftKey && code === 'KeyW') {
            event.preventDefault();
            downloadWord();
            return;
        }

        if (event.altKey && !event.ctrlKey && !event.shiftKey && code === 'KeyN') {
            event.preventDefault();
            openNewAppointment();
            return;
        }

        if (event.altKey && !event.ctrlKey && !event.shiftKey && code === 'KeyP') {
            event.preventDefault();
            openCurrentPatientCard();
            return;
        }

        if (event.altKey && !event.ctrlKey && !event.shiftKey && code === 'KeyM') {
            event.preventDefault();
            openMainAppointments();
            return;
        }

        // Символ / не перехватывается внутри полей ввода.
        if (
            !event.ctrlKey
            && !event.altKey
            && !event.metaKey
            && !event.shiftKey
            && (code === 'Slash' || event.key === '/')
            && !isEditableTarget(event.target)
        ) {
            event.preventDefault();
            focusPatientSearch();
            return;
        }

        const appointmentForm = findAppointmentForm();
        if (!appointmentForm || !(active instanceof HTMLElement) || !appointmentForm.contains(active)) {
            return;
        }

        const inTable = isInsideTable(active);

        // В таблицах обычные стрелки двигаются по строкам того же столбца.
        if (inTable && !event.ctrlKey && !event.altKey && !event.metaKey && !event.shiftKey) {
            if (code === 'ArrowUp') {
                event.preventDefault();
                moveVerticallyInTable(active, -1);
                return;
            }

            if (code === 'ArrowDown') {
                event.preventDefault();
                moveVerticallyInTable(active, 1);
                return;
            }
        }

        // Enter и Shift + Enter в таблице переходят между типами анализа.
        if (inTable && !event.ctrlKey && !event.altKey && !event.metaKey && code === 'Enter') {
            event.preventDefault();
            moveToSection(event.shiftKey ? -1 : 1);
            return;
        }

        // Навигация Ctrl + стрелки действует только вне таблиц.
        if (inTable || !event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) {
            return;
        }

        if (code === 'ArrowLeft') {
            event.preventDefault();
            moveBetweenOrdinaryFields(-1);
            return;
        }

        if (code === 'ArrowRight') {
            event.preventDefault();
            moveBetweenOrdinaryFields(1);
            return;
        }

    }

    function initializeDirtyTracking() {
        const form = findAppointmentForm();
        if (!form) {
            return;
        }

        const markDirty = function () {
            appointmentFormDirty = true;
        };

        form.addEventListener('input', markDirty);
        form.addEventListener('change', markDirty);
        form.addEventListener('submit', function (event) {
            if (!event.defaultPrevented) {
                appointmentFormDirty = false;
            }
        });
    }

    document.addEventListener('keydown', handleKeydown, true);

    document.addEventListener('DOMContentLoaded', function () {
        initializeDirtyTracking();
        runPendingExportAfterSave();
    });
}());
