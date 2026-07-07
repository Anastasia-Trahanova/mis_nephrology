"""
Патч для live-обновления таблицы СКФ в форме повторного приёма.
Запускать из корня проекта mis_nephrology / mis_for_registrations:
    python apply_gfr_live_table_patch.py
"""
from pathlib import Path
import re
import sys

ROOT = Path.cwd()
metrics_path = ROOT / "app" / "templates" / "appointment_form" / "_metrics.html"
scripts_path = ROOT / "app" / "templates" / "appointment_form" / "_scripts.html"

for path in (metrics_path, scripts_path):
    if not path.exists():
        print(f"Не найден файл: {path}", file=sys.stderr)
        sys.exit(1)

metrics = metrics_path.read_text(encoding="utf-8")
old_metrics_block = '''            <div class="d-flex justify-content-between align-items-center mb-2">
                <h5 class="mb-0">Расчётные показатели</h5>
                <button type="button" class="btn btn-outline-primary btn-sm" id="updateMetricsTableBtn">
                    🔄 Обновить
                </button>
            </div>'''
new_metrics_block = '''            <div class="d-flex justify-content-between align-items-center mb-2">
                <h5 class="mb-0">Расчётные показатели</h5>
                <div class="text-muted small">Обновляется автоматически при вводе креатинина</div>
            </div>'''
if old_metrics_block not in metrics:
    metrics = re.sub(
        r'''            <div class="d-flex justify-content-between align-items-center mb-2">\s*\n\s*<h5 class="mb-0">Расчётные показатели</h5>\s*\n\s*<button type="button" class="btn btn-outline-primary btn-sm" id="updateMetricsTableBtn">\s*\n\s*🔄 Обновить\s*\n\s*</button>\s*\n\s*</div>''',
        new_metrics_block,
        metrics,
        count=1,
    )
else:
    metrics = metrics.replace(old_metrics_block, new_metrics_block)

if 'id="updateMetricsTableBtn"' in metrics:
    print("Не удалось удалить кнопку updateMetricsTableBtn из _metrics.html", file=sys.stderr)
    sys.exit(1)
metrics_path.write_text(metrics, encoding="utf-8")

scripts = scripts_path.read_text(encoding="utf-8")

# 1. Убираем alert из live-функции: на вводе пустого креатинина врач не должен получать всплывающее окно.
scripts = scripts.replace("""    let addedAnyColumn = false;

""", "")
scripts = scripts.replace("""
        addedAnyColumn = true;
""", "")
scripts = scripts.replace("""
    if (!addedAnyColumn) {
        alert('Добавьте биохимический анализ и заполните креатинин.');
    }
""", "")

# 2. Добавляем debounce/scheduler сразу после updateMetricsTable(), если его ещё нет.
if "function scheduleMetricsTableUpdate()" not in scripts:
    marker = """function updateMetricsTable() {
    clearNewMetricsColumns();

    const birthDate = document.querySelector('[name=\"birth_date\"]')?.value;
    const gender = document.querySelector('[name=\"gender\"]')?.value;
    const weight = parseNumber(document.querySelector('[name=\"weight\"]')?.value);
    const appointmentDate = document.querySelector('[name=\"appointment_date\"]')?.value;

    const creatinineInputs = Array.from(document.querySelectorAll('[name=\"creatinine\"]'));
    const biochemistryDateInputs = Array.from(document.querySelectorAll('[name=\"biochemistry_investigation_date\"]'));

    creatinineInputs.forEach((input, index) => {
        const creatinine = parseNumber(input.value);

        if (creatinine === null) {
            return;
        }

        const dateValue = biochemistryDateInputs[index]?.value || appointmentDate;
        const age = calculateAge(birthDate, dateValue);

        const egfr = calculateCkdEpi2021(creatinine, age, gender);
        const cockcroft = calculateCockcroftGault(creatinine, age, weight, gender);
        const stage = getCkdStage(egfr);

        appendMetricColumn(dateValue, egfr, cockcroft, stage);
    });

    sortMetricsTableChronologically();
}
"""
    replacement = marker + """
let metricsTableUpdateFrame = null;

function scheduleMetricsTableUpdate() {
    if (metricsTableUpdateFrame !== null) {
        window.cancelAnimationFrame(metricsTableUpdateFrame);
    }

    metricsTableUpdateFrame = window.requestAnimationFrame(function () {
        metricsTableUpdateFrame = null;
        updateMetricsTable();
    });
}
"""
    if marker in scripts:
        scripts = scripts.replace(marker, replacement, 1)
    else:
        pattern = r"function updateMetricsTable\(\) \{.*?\n\}\n\ndocument\.addEventListener\('DOMContentLoaded', function \(\) \{"
        match = re.search(pattern, scripts, flags=re.S)
        if not match:
            print("Не удалось найти функцию updateMetricsTable() для вставки scheduler", file=sys.stderr)
            sys.exit(1)
        block = match.group(0).replace("\n\ndocument.addEventListener", "\n\nlet metricsTableUpdateFrame = null;\n\nfunction scheduleMetricsTableUpdate() {\n    if (metricsTableUpdateFrame !== null) {\n        window.cancelAnimationFrame(metricsTableUpdateFrame);\n    }\n\n    metricsTableUpdateFrame = window.requestAnimationFrame(function () {\n        metricsTableUpdateFrame = null;\n        updateMetricsTable();\n    });\n}\n\ndocument.addEventListener")
        scripts = scripts[:match.start()] + block + scripts[match.end():]

# 3. Убираем привязку к кнопке и добавляем live-события.
scripts = scripts.replace("""    const updateMetricsButton = document.getElementById('updateMetricsTableBtn');
""", "")
scripts = scripts.replace("""
    if (updateMetricsButton) {
        updateMetricsButton.addEventListener('click', updateMetricsTable);
    }
""", "")

if "const metricsLiveSelector" not in scripts:
    insert_after = """    if (addUltrasoundButton) {
        addUltrasoundButton.addEventListener('click', function () {
            addDynamicColumn({
                headerRowId: 'ultrasoundHeaderRow',
                title: 'Новое УЗИ',
                dateFieldName: 'ultrasound_investigation_date',
                minWidth: '170px',
                fields: [
                    { rowId: 'us_left_kidney_size_row', name: 'left_kidney_size' },
                    { rowId: 'us_right_kidney_size_row', name: 'right_kidney_size' },
                    { rowId: 'us_left_parenchyma_row', name: 'left_parenchyma' },
                    { rowId: 'us_right_parenchyma_row', name: 'right_parenchyma' },
                    { rowId: 'us_description_row', name: 'ultrasound_desc', type: 'textarea' }
                ]
            });
        });
    }
"""
    live_block = insert_after + """

    const metricsLiveSelector = [
        '[name="creatinine"]',
        '[name="biochemistry_investigation_date"]',
        '[name="weight"]',
        '[name="birth_date"]',
        '[name="gender"]',
        '[name="appointment_date"]'
    ].join(', ');

    document.addEventListener('input', function (event) {
        if (event.target.matches(metricsLiveSelector)) {
            scheduleMetricsTableUpdate();
        }
    });

    document.addEventListener('change', function (event) {
        if (event.target.matches(metricsLiveSelector)) {
            scheduleMetricsTableUpdate();
        }
    });

    updateMetricsTable();
"""
    if insert_after in scripts:
        scripts = scripts.replace(insert_after, live_block, 1)
    else:
        # Более грубый fallback: вставить перед концом DOMContentLoaded-блока, где раньше была кнопка.
        old_tail = """});
</script>


<script>
document.addEventListener('DOMContentLoaded', function () {
    const addAlbuminuriaButton = document.getElementById('addAlbuminuriaColumnBtn');
"""
        new_tail = """    const metricsLiveSelector = [
        '[name="creatinine"]',
        '[name="biochemistry_investigation_date"]',
        '[name="weight"]',
        '[name="birth_date"]',
        '[name="gender"]',
        '[name="appointment_date"]'
    ].join(', ');

    document.addEventListener('input', function (event) {
        if (event.target.matches(metricsLiveSelector)) {
            scheduleMetricsTableUpdate();
        }
    });

    document.addEventListener('change', function (event) {
        if (event.target.matches(metricsLiveSelector)) {
            scheduleMetricsTableUpdate();
        }
    });

    updateMetricsTable();
});
</script>


<script>
document.addEventListener('DOMContentLoaded', function () {
    const addAlbuminuriaButton = document.getElementById('addAlbuminuriaColumnBtn');
"""
        if old_tail not in scripts:
            print("Не удалось вставить live-события для таблицы СКФ", file=sys.stderr)
            sys.exit(1)
        scripts = scripts.replace(old_tail, new_tail, 1)

# 4. После добавления новой биохимии сразу запускаем обновление таблицы: пустой столбец не добавится,
# но как только врач введёт креатинин, делегированные input/change события добавят новый столбец СКФ.
scripts = scripts.replace("""            addDynamicColumn({
                headerRowId: 'biochemistryHeaderRow',
                title: 'Новый анализ',
                dateFieldName: 'biochemistry_investigation_date',
                fields: [
                    { rowId: 'bio_creatinine_row', name: 'creatinine' },
                    { rowId: 'bio_urea_row', name: 'urea' },
                    { rowId: 'bio_uric_acid_row', name: 'uric_acid' },
                    { rowId: 'bio_glucose_row', name: 'glucose' },
                    { rowId: 'bio_total_protein_row', name: 'total_protein' },
                    { rowId: 'bio_albumin_row', name: 'albumin' },
                    { rowId: 'bio_potassium_row', name: 'potassium' },
                    { rowId: 'bio_calcium_row', name: 'calcium' },
                    { rowId: 'bio_phosphorus_row', name: 'phosphorus' },
                    { rowId: 'bio_ferritin_row', name: 'ferritin' },
                    { rowId: 'bio_ptg_row', name: 'ptg' }
                ]
            });
""", """            addDynamicColumn({
                headerRowId: 'biochemistryHeaderRow',
                title: 'Новый анализ',
                dateFieldName: 'biochemistry_investigation_date',
                fields: [
                    { rowId: 'bio_creatinine_row', name: 'creatinine' },
                    { rowId: 'bio_urea_row', name: 'urea' },
                    { rowId: 'bio_uric_acid_row', name: 'uric_acid' },
                    { rowId: 'bio_glucose_row', name: 'glucose' },
                    { rowId: 'bio_total_protein_row', name: 'total_protein' },
                    { rowId: 'bio_albumin_row', name: 'albumin' },
                    { rowId: 'bio_potassium_row', name: 'potassium' },
                    { rowId: 'bio_calcium_row', name: 'calcium' },
                    { rowId: 'bio_phosphorus_row', name: 'phosphorus' },
                    { rowId: 'bio_ferritin_row', name: 'ferritin' },
                    { rowId: 'bio_ptg_row', name: 'ptg' }
                ]
            });
            scheduleMetricsTableUpdate();
""", 1)

checks = [
    "function updateMetricsTable()",
    "function scheduleMetricsTableUpdate()",
    "requestAnimationFrame",
    "metricsLiveSelector",
    "[name=\"creatinine\"]",
]
missing = [item for item in checks if item not in scripts]
if missing:
    print("После патча в _scripts.html не найдены ожидаемые фрагменты: " + ", ".join(missing), file=sys.stderr)
    sys.exit(1)
if "getElementById('updateMetricsTableBtn')" in scripts or "alert('Добавьте биохимический анализ" in scripts:
    print("В _scripts.html осталась старая кнопка/alert", file=sys.stderr)
    sys.exit(1)

scripts_path.write_text(scripts, encoding="utf-8")
print("OK: таблица СКФ переведена на live-обновление, кнопка удаления не нужна.")
