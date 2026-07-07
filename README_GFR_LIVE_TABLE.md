# Live-обновление таблицы СКФ

Патч убирает кнопку «Обновить» из блока «Расчётные показатели» в форме повторного приёма и переводит таблицу СКФ на автоматическое обновление.

## Что меняется

- `app/templates/appointment_form/_metrics.html`
  - удаляется кнопка `updateMetricsTableBtn`;
  - добавляется короткая подпись «Обновляется автоматически при вводе креатинина».

- `app/templates/appointment_form/_scripts.html`
  - `updateMetricsTable()` больше не показывает `alert` при пустом креатинине;
  - появляется `scheduleMetricsTableUpdate()` через `requestAnimationFrame`;
  - таблица СКФ обновляется на `input/change` для креатинина, даты биохимии, веса, даты рождения, пола и даты приёма;
  - после добавления новой биохимии таблица готова добавить новый столбец сразу после ввода креатинина.

- `tests/layer/test_gfr_live_metrics_table_contract.py`
  - фиксирует новый контракт: кнопки нет, live-события есть, alert нет, столбцы строятся по всем заполненным `name="creatinine"`.

## Применение

Из корня проекта:

```cmd
python apply_gfr_live_table_patch.py
```

Потом скопировать тест, если он не скопирован автоматически из архива:

```cmd
copy tests\layer\test_gfr_live_metrics_table_contract.py tests\layer\test_gfr_live_metrics_table_contract.py
```

## Проверка

```cmd
pytest tests/layer/test_gfr_live_metrics_table_contract.py -v
pytest tests/layer -v
```

Если есть Node.js:

```cmd
node --check app/templates/appointment_form/_scripts.html
```

`node --check` для Jinja/HTML может быть неприменим, если файл содержит несколько `<script>` и шаблонный текст. Основная проверка здесь — pytest-contract.
