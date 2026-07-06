# Runtime fix для матрицы KDIGO

Этот одноразовый скрипт исправляет падение карточки пациента:

```text
TypeError: 'builtin_function_or_method' object is not iterable
```

Причина: в Jinja `cell.items` читается как метод словаря `dict.items`, а не как поле `"items"`.
Правильное обращение: `cell["items"]`.

## Применение

```cmd
python scripts\fix_kdigo_matrix_template_runtime_error.py
pytest tests/layer
```

Потом открыть карточку пациента:

```text
/patient/1?appointment_id=3
```

Если всё работает, удалить временный скрипт:

```cmd
del scripts\fix_kdigo_matrix_template_runtime_error.py
```
