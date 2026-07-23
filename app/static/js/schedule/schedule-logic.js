/*
  Общие функции расписания.

  Файл не обращается к DOM и серверу: здесь находятся вычисления времени,
  проверка пересечений и безопасные вспомогательные функции. Благодаря этому
  бизнес-логику можно позже покрыть отдельными unit-тестами.

  Используется обычный глобальный объект window.ScheduleLogic, а не ES-модули.
  Это сделано для совместимости с текущей серверной раздачей статических файлов
  и исключает ошибки MIME/type="module" в локальном окружении.
*/
(function exposeScheduleLogic(global) {
  'use strict';

  const DEFAULT_DURATIONS = Object.freeze({ primary: 40, repeated: 15 });

  function toMinutes(time) {
    const parts = String(time || '').split(':').map(Number);
    if (parts.length !== 2 || parts.some(Number.isNaN)) return 0;
    return parts[0] * 60 + parts[1];
  }

  function minutesToTime(total) {
    const normalized = Math.max(0, Math.min(23 * 60 + 59, Number(total) || 0));
    const hours = Math.floor(normalized / 60).toString().padStart(2, '0');
    const minutes = (normalized % 60).toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  }

  function slotEndMinutes(slot) {
    return toMinutes(slot.start) + Number(slot.durationMinutes || 0);
  }

  function hasOverlap(candidate, slots, ignoredId) {
    const start = toMinutes(candidate.start);
    const end = start + Number(candidate.durationMinutes || 0);

    return slots.some((slot) => {
      if (String(slot.id) === String(ignoredId)) return false;
      if (slot.date !== candidate.date || Number(slot.doctorId) !== Number(candidate.doctorId)) return false;

      const otherStart = toMinutes(slot.start);
      const otherEnd = otherStart + Number(slot.durationMinutes || 0);
      return start < otherEnd && end > otherStart;
    });
  }

  function durationForType(slot, type) {
    if (type === 'primary') {
      return Number(slot.primaryDurationMinutes || DEFAULT_DURATIONS.primary);
    }
    return Number(slot.repeatedDurationMinutes || DEFAULT_DURATIONS.repeated);
  }

  function formatSlotRange(slot) {
    return `${slot.start} - ${minutesToTime(slotEndMinutes(slot))}`;
  }

  // Формируем дату в локальном часовом поясе, чтобы UTC не сдвигал день назад/вперёд.
  function dateKey(date) {
    const value = date instanceof Date ? date : new Date(date);
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function startOfWeek(date) {
    const result = new Date(date);
    const day = result.getDay() || 7;
    result.setDate(result.getDate() - day + 1);
    result.setHours(12, 0, 0, 0);
    return result;
  }

  function createId() {
    if (global.crypto && typeof global.crypto.randomUUID === 'function') {
      return global.crypto.randomUUID();
    }
    return `slot-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function deepClone(value) {
    if (typeof global.structuredClone === 'function') return global.structuredClone(value);
    return JSON.parse(JSON.stringify(value));
  }

  // Экранируем пользовательский текст перед вставкой через innerHTML.
  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  global.ScheduleLogic = Object.freeze({
    DEFAULT_DURATIONS,
    toMinutes,
    minutesToTime,
    slotEndMinutes,
    hasOverlap,
    durationForType,
    formatSlotRange,
    dateKey,
    startOfWeek,
    createId,
    deepClone,
    escapeHtml,
  });
}(window));
