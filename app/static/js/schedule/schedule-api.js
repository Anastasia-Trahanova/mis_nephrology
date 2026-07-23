/*
  Асинхронный mock API расписания.

  Сейчас данные живут только в памяти вкладки браузера. Каждая функция содержит
  комментарий SERVER INTEGRATION: это место, где mock затем заменяется реальным
  fetch-запросом, не меняя код интерфейса в schedule-page.js.
*/
(function exposeScheduleApi(global) {
  'use strict';

  const logic = global.ScheduleLogic;
  if (!logic) throw new Error('ScheduleLogic должен быть подключён до ScheduleApi');

  const { createId, dateKey, deepClone, startOfWeek } = logic;
  const wait = (value, ms = 120) => new Promise((resolve) => {
    global.setTimeout(() => resolve(deepClone(value)), ms);
  });

  const doctors = [
    { id: 1, fio: 'Иванова Анна Сергеевна' },
    { id: 2, fio: 'Петров Михаил Андреевич' },
    { id: 3, fio: 'Соколова Елена Викторовна' },
  ];

  const patients = [
    { id: 101, fullName: 'Смирнова Ольга Петровна', birthDate: '1982-05-16' },
    { id: 102, fullName: 'Иванов Сергей Николаевич', birthDate: '1976-11-02' },
    { id: 103, fullName: 'Иванова Анна Игоревна', birthDate: '1990-03-10' },
  ];

  function buildDemoSlots() {
    const result = [];
    const week = startOfWeek(new Date());
    const times = ['08:00', '08:40', '09:20', '10:00', '10:40', '11:20', '12:00', '13:00', '13:40', '14:20'];

    doctors.forEach((doctor, doctorIndex) => {
      for (let dayOffset = 0; dayOffset < 5; dayOffset += 1) {
        const date = new Date(week);
        date.setDate(date.getDate() + dayOffset);

        times.forEach((start, index) => {
          let status = 'free';
          let durationMinutes = index % 2 === 0 ? 40 : 15;
          let appointmentType = durationMinutes === 15 ? 'repeated' : 'primary';
          let patient = null;

          if (index === doctorIndex + 1) {
            status = 'busy';
            appointmentType = 'repeated';
            durationMinutes = 15;
            patient = patients[doctorIndex];
          } else if (index === 4 && dayOffset === 1) {
            status = 'pending';
          } else if (index === 6) {
            status = 'break';
            durationMinutes = 60;
          }

          result.push({
            id: createId(),
            doctorId: doctor.id,
            date: dateKey(date),
            start,
            durationMinutes,
            status,
            appointmentType,
            patientId: patient ? patient.id : null,
            patientName: patient ? patient.fullName : null,
            primaryDurationMinutes: 40,
            repeatedDurationMinutes: 15,
            durationOverridden: false,
          });
        });
      }
    });

    return result;
  }

  let slots = buildDemoSlots();

  const doctorsApi = {
    // SERVER INTEGRATION: заменить на GET /api/doctors
    async list() {
      return wait(doctors);
    },
  };

  const patientsApi = {
    // SERVER INTEGRATION: заменить на GET /api/patients/search?full_name=...&birth_date=...
    async search({ fullName, birthDate }) {
      const query = String(fullName || '').trim().toLowerCase();
      const found = patients.filter((patient) => {
        const sameName = patient.fullName.toLowerCase().includes(query);
        const sameBirthDate = !birthDate || patient.birthDate === birthDate;
        return sameName && sameBirthDate;
      });
      return wait(found);
    },

    // SERVER INTEGRATION: заменить на POST /api/patients.
    // doctorId сохраняется вместе с пациентом/приёмом для будущего разграничения доступа.
    async create(payload) {
      const patient = {
        id: Date.now(),
        fullName: String(payload.fullName || '').trim(),
        birthDate: payload.birthDate || null,
        attendingDoctorId: Number(payload.doctorId),
      };
      patients.push(patient);
      return wait(patient);
    },
  };

  const slotsApi = {
    // SERVER INTEGRATION: заменить на GET /api/schedule/slots
    async list() {
      return wait(slots);
    },

    // SERVER INTEGRATION: заменить на POST/PATCH /api/schedule/slots
    async save(slot) {
      const index = slots.findIndex((item) => String(item.id) === String(slot.id));
      if (index >= 0) slots[index] = deepClone(slot);
      else slots.push(deepClone(slot));
      return wait(slot);
    },

    // SERVER INTEGRATION: заменить на DELETE /api/schedule/slots/{id}
    async remove(id) {
      slots = slots.filter((slot) => String(slot.id) !== String(id));
      return wait({ ok: true });
    },

    // SERVER INTEGRATION: заменить пакетным endpoint генерации/копирования слотов.
    async replaceAll(nextSlots) {
      slots = deepClone(nextSlots);
      return wait(slots);
    },
  };

  const templatesApi = {
    // SERVER INTEGRATION: заменить на POST /api/schedule/templates
    async save(template) {
      global.localStorage.setItem('misScheduleTemplate', JSON.stringify(template));
      return wait(template);
    },

    // SERVER INTEGRATION: заменить на GET /api/schedule/templates/current
    async load() {
      const raw = global.localStorage.getItem('misScheduleTemplate');
      return wait(raw ? JSON.parse(raw) : {
        primaryDurationMinutes: 40,
        repeatedDurationMinutes: 15,
      });
    },
  };

  global.ScheduleApi = Object.freeze({ doctorsApi, patientsApi, slotsApi, templatesApi });
}(window));
