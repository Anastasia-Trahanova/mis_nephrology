# Frontend style controls patch

Назначение архива: добавить единый слой CSS-настроек для проекта без изменения текущего визуального стиля.

## Файлы

```text
app/static/css/01_layout_controls.css
app/static/css/02_clinical_messages.css
app/static/css/03_select_popups.css
```

### `01_layout_controls.css`

Настройки общего оформления:

- шрифт всего приложения;
- размер основного текста;
- выравнивание;
- кнопки;
- кнопка экспорта Word;
- таблицы;
- отступы и базовые карточки.

### `02_clinical_messages.css`

Настройки сообщений:

- ошибки сохранения формы;
- предупреждения;
- подсказки под полями;
- подсветка некорректных полей;
- будущие сообщения о нормализации значений.

### `03_select_popups.css`

Настройки выпадающих списков:

- select;
- dropdown;
- будущий autocomplete;
- выбор врача, лекарств, диагнозов;
- стили пунктов выбора и пустого состояния.

## Нужно ли заменять файлы?

Если папки `app/static/css/` ещё нет, просто распакуй архив в корень проекта.

Если файлы уже есть, лучше сравнить содержимое и заменить только эти 3 CSS-файла.

## Точечные правки, которые нужно сделать

### 1. Проверить `app/main.py`

Если статика ещё не подключена, добавь импорт:

```python
from fastapi.staticfiles import StaticFiles
```

И после создания `app = FastAPI(...)` добавь:

```python
app.mount("/static", StaticFiles(directory="app/static"), name="static")
```

Если `app.mount("/static", ...)` уже есть, второй раз добавлять не нужно.

### 2. Подключить CSS в `app/templates/base.html`

Внутри `<head>` после Bootstrap CSS, но до `{% block head %}` / `{% block extra_css %}`, добавь:

```html
<link rel="stylesheet" href="{{ url_for('static', path='css/01_layout_controls.css') }}">
<link rel="stylesheet" href="{{ url_for('static', path='css/02_clinical_messages.css') }}">
<link rel="stylesheet" href="{{ url_for('static', path='css/03_select_popups.css') }}">
```

Порядок важен:

1. Bootstrap;
2. наши CSS-настройки;
3. индивидуальные стили страниц, если они есть.

## Что должно измениться визуально сейчас

Почти ничего.

Файлы содержат консервативные значения, близкие к Bootstrap. Главная цель — создать единое место, где потом можно менять дизайн.

## Где менять что

### Поменять шрифт во всём проекте

`01_layout_controls.css`:

```css
--mis-font-family-base: Arial, sans-serif;
```

### Сделать таблицы компактнее

`01_layout_controls.css`:

```css
--mis-table-cell-padding-y: 0.25rem;
--mis-table-cell-padding-x: 0.35rem;
--mis-table-font-size: 0.875rem;
```

### Изменить кнопку экспорта Word

`01_layout_controls.css`:

```css
--mis-word-export-font-size: 0.95rem;
--mis-word-export-padding-y: 0.5rem;
--mis-word-export-padding-x: 1rem;
```

Для более точного управления добавь класс `mis-word-export-btn` к ссылке экспорта.

### Настроить ошибки формы

`02_clinical_messages.css`:

```css
--mis-error-color: #842029;
--mis-error-bg: #f8d7da;
--mis-error-border-color: #f5c2c7;
```

### Настроить предупреждения врача

`02_clinical_messages.css`:

```css
--mis-warning-color: #664d03;
--mis-warning-bg: #fff3cd;
```

### Настроить выпадающие списки лекарств/диагнозов

`03_select_popups.css`:

```css
--mis-popup-max-height: 20rem;
--mis-popup-font-size: 0.95rem;
--mis-popup-item-hover-bg: #f8f9fa;
```

## Проверка после подключения

1. Запусти приложение.
2. Открой главную страницу.
3. Открой форму нового пациента.
4. Открой форму нового приёма.
5. Открой карточку пациента.
6. Проверь в DevTools → Network, что CSS-файлы отдаются без 404:
   - `/static/css/01_layout_controls.css`
   - `/static/css/02_clinical_messages.css`
   - `/static/css/03_select_popups.css`

## Коммит

```cmd
git add app/static/css/01_layout_controls.css app/static/css/02_clinical_messages.css app/static/css/03_select_popups.css app/main.py app/templates/base.html
git commit -m "add frontend style control layer"
git push
```
