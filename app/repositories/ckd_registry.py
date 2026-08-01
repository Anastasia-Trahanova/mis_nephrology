"""Repository локального регистра пациентов с ХБП."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any, Mapping
from urllib.parse import urlencode
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from app.db.connection import get_db_connection

STAGES = ("С1", "С2", "С3а", "С3б", "С4", "С5")
DEFAULT_OUTCOME_LABEL = "Наблюдается"

OUTCOME_LABELS = {
    "rrt_hemodialysis": "ЗПТ, гемодиализ",
    "rrt_peritoneal_dialysis": "ЗПТ, перитонеальный диализ",
    "rrt_kidney_transplant": "ЗПТ, трансплантация почки",
    "death": "Летальный исход",
}


class RegistryValidationError(ValueError):
    """Ошибка данных формы регистра."""


class RegistryConflictError(ValueError):
    """Пациент уже включён в регистр."""


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _positive_int(value: Any, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, 1), maximum)


def _filter_decimal(value: Any) -> Decimal | None:
    """Безопасно разбирает неотрицательное число из GET-параметра."""
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return parsed


@dataclass(frozen=True)
class CkdRegistryFilters:
    search: str = ""
    stage: str = ""
    egfr_operator: str = ""
    egfr_from: Decimal | None = None
    egfr_to: Decimal | None = None
    outcome: str = ""
    included_from: date | None = None
    included_to: date | None = None
    page: int = 1
    page_size: int = 25

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "CkdRegistryFilters":
        search = str(values.get("search") or "").strip()[:200]
        stage = str(values.get("stage") or "").strip()
        if stage not in STAGES:
            stage = ""
        egfr_operator = str(values.get("egfr_operator") or "").strip()
        if egfr_operator not in {"lt", "gt", "between"}:
            egfr_operator = ""
        egfr_from = _filter_decimal(values.get("egfr_from"))
        egfr_to = _filter_decimal(values.get("egfr_to"))
        if not egfr_operator or egfr_from is None:
            egfr_operator = ""
            egfr_from = None
            egfr_to = None
        elif egfr_operator == "between":
            if egfr_to is None:
                egfr_operator = ""
                egfr_from = None
            elif egfr_from > egfr_to:
                egfr_from, egfr_to = egfr_to, egfr_from
        else:
            egfr_to = None
        outcome = str(values.get("outcome") or "").strip()
        if outcome not in {*OUTCOME_LABELS, "none"}:
            outcome = ""
        included_from = _parse_date(values.get("included_from"))
        included_to = _parse_date(values.get("included_to"))
        if included_from and included_to and included_from > included_to:
            included_from, included_to = included_to, included_from
        return cls(
            search=search,
            stage=stage,
            egfr_operator=egfr_operator,
            egfr_from=egfr_from,
            egfr_to=egfr_to,
            outcome=outcome,
            included_from=included_from,
            included_to=included_to,
            page=_positive_int(values.get("page"), 1, 100000),
            page_size=_positive_int(values.get("page_size"), 25, 100),
        )

    def without_page_query(self) -> str:
        values: dict[str, Any] = {"page_size": self.page_size}
        if self.search:
            values["search"] = self.search
        if self.stage:
            values["stage"] = self.stage
        if self.egfr_operator and self.egfr_from is not None:
            values["egfr_operator"] = self.egfr_operator
            values["egfr_from"] = str(self.egfr_from)
            if self.egfr_operator == "between" and self.egfr_to is not None:
                values["egfr_to"] = str(self.egfr_to)
        if self.outcome:
            values["outcome"] = self.outcome
        if self.included_from:
            values["included_from"] = self.included_from.isoformat()
        if self.included_to:
            values["included_to"] = self.included_to.isoformat()
        return urlencode(values)


def _snapshot_select_sql() -> str:
    return """
        SELECT
            p.id AS patient_id,
            p.last_name,
            p.first_name,
            p.patronymic,
            TRIM(p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '')) AS patient_fio,
            p.birth_date,
            p.phone,
            latest_appointment.appointment_id,
            latest_appointment.appointment_date,
            NULLIF(TRIM(structured_diagnosis.icd10_diagnosis), '') AS main_diagnosis,
            latest_appointment.egfr_ckdepi AS egfr,
            latest_appointment.ckd_stage
        FROM patients p
        LEFT JOIN LATERAL (
            SELECT
                a.id AS appointment_id,
                a.appointment_date,
                latest_metrics.egfr_ckdepi,
                latest_metrics.ckd_stage
            FROM appointments a
            LEFT JOIN LATERAL (
                SELECT cm.egfr_ckdepi, cm.ckd_stage
                FROM calculated_metrics cm
                WHERE cm.appointment_id = a.id
                ORDER BY cm.investigation_date DESC NULLS LAST,
                         cm.calculation_date DESC,
                         cm.id DESC
                LIMIT 1
            ) latest_metrics ON TRUE
            WHERE a.patient_id = p.id
            ORDER BY a.appointment_date DESC, a.id DESC
            LIMIT 1
        ) latest_appointment ON TRUE
        LEFT JOIN LATERAL (
            SELECT v.icd10_diagnosis
            FROM appointment_icd10_diagnoses_view v
            WHERE v.appointment_id = latest_appointment.appointment_id
              AND v.diagnosis_type = 'main'
            ORDER BY v.sort_order, v.id
            LIMIT 1
        ) structured_diagnosis ON TRUE
        WHERE p.id = %s
    """


def _fetch_current_snapshot(cur: Any, patient_id: int) -> dict[str, Any] | None:
    cur.execute(_snapshot_select_sql(), (patient_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def _fetch_registry_entry(cur: Any, patient_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT
            e.*,
            latest_outcome.outcome_type,
            latest_outcome.outcome_date,
            latest_outcome.comment AS outcome_comment
        FROM ckd_registry_entries e
        LEFT JOIN LATERAL (
            SELECT o.outcome_type, o.outcome_date, o.comment
            FROM ckd_registry_outcomes o
            WHERE o.registry_entry_id = e.id
            ORDER BY o.outcome_date DESC, o.created_at DESC, o.id DESC
            LIMIT 1
        ) latest_outcome ON TRUE
        WHERE e.patient_id = %s AND e.is_active = TRUE
        LIMIT 1
        """,
        (patient_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    item = dict(row)
    item["outcome_label"] = OUTCOME_LABELS.get(item.get("outcome_type"), DEFAULT_OUTCOME_LABEL)
    if not item.get("outcome_type") and not item.get("outcome_date"):
        item["outcome_date"] = item.get("included_at")
    return item


def get_patient_registry_context(patient_id: int) -> dict[str, Any] | None:
    """Данные для блока регистра в ЭМК."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            snapshot = _fetch_current_snapshot(cur, patient_id)
            if not snapshot:
                return None
            return {
                "snapshot": snapshot,
                "entry": _fetch_registry_entry(cur, patient_id),
                "outcomes": OUTCOME_LABELS,
                "stages": STAGES,
            }


def _required_text(value: Any, label: str) -> str:
    """Возвращает непустое строковое значение обязательного поля."""
    normalized = str(value or "").strip()
    if not normalized:
        raise RegistryValidationError(f"Заполните поле «{label}»")
    return normalized


def _validate_identity(last_name: str, first_name: str, birth_date: date) -> tuple[str, str]:
    last_name = _required_text(last_name, "Фамилия")
    first_name = _required_text(first_name, "Имя")
    if birth_date > date.today() or birth_date < date(1900, 1, 1):
        raise RegistryValidationError("Проверьте дату рождения")
    return last_name, first_name


def _normalize_egfr(value: Any) -> Decimal:
    if value in (None, "") or not str(value).strip():
        raise RegistryValidationError("Заполните поле «СКФ»")
    try:
        parsed = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        raise RegistryValidationError("СКФ указана некорректно")
    if not parsed.is_finite() or parsed < 0 or parsed > 1000:
        raise RegistryValidationError("СКФ должна быть от 0 до 1000")
    return parsed.quantize(Decimal("0.01"))


def add_patient_to_registry(
    *,
    patient_id: int,
    user_id: int,
    last_name: str,
    first_name: str,
    patronymic: str | None,
    birth_date: date,
    phone: str | None,
    diagnosis: str,
    egfr: Any,
    stage: str | None,
    outcome: str | None,
    comment: str | None,
) -> int:
    """Обновляет проверенные данные пациента и включает его в регистр."""
    last_name, first_name = _validate_identity(last_name, first_name, birth_date)
    patronymic = _required_text(patronymic, "Отчество")
    phone = _required_text(phone, "Телефон")
    diagnosis = _required_text(diagnosis, "Основной диагноз")
    egfr_value = _normalize_egfr(egfr)
    stage = _required_text(stage, "Стадия ХБП")
    if stage not in STAGES:
        raise RegistryValidationError("Выберите корректную стадию ХБП")
    # «Наблюдается» — обязательный выбранный статус, но отдельная строка исхода для него не создаётся.
    outcome_value = str(outcome or "").strip()
    outcome = None if outcome_value in {"", "observed"} else outcome_value
    if outcome is not None and outcome not in OUTCOME_LABELS:
        raise RegistryValidationError("Выберите корректный исход")
    comment = _required_text(comment, "Комментарий")
    today = date.today()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM patients WHERE id = %s FOR UPDATE", (patient_id,))
            if not cur.fetchone():
                raise RegistryValidationError("Пациент не найден")
            cur.execute(
                """
                SELECT id, is_active
                FROM ckd_registry_entries
                WHERE patient_id = %s
                FOR UPDATE
                """,
                (patient_id,),
            )
            existing_entry = cur.fetchone()
            if existing_entry and existing_entry["is_active"]:
                raise RegistryConflictError("Пациент уже добавлен в регистр ХБП")

            cur.execute(
                """
                UPDATE patients
                SET last_name = %s,
                    first_name = %s,
                    patronymic = %s,
                    birth_date = %s,
                    phone = %s
                WHERE id = %s
                """,
                (last_name, first_name, patronymic, birth_date, phone, patient_id),
            )
            if existing_entry:
                registry_entry_id = int(existing_entry["id"])
                cur.execute(
                    """
                    UPDATE ckd_registry_entries
                    SET included_at = %s,
                        included_by_user_id = %s,
                        diagnosis_at_inclusion = %s,
                        egfr_at_inclusion = %s,
                        ckd_stage_at_inclusion = %s,
                        comment_at_inclusion = %s,
                        is_active = TRUE,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        today,
                        user_id,
                        diagnosis,
                        egfr_value,
                        stage,
                        comment,
                        registry_entry_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO ckd_registry_entries (
                        patient_id, included_at, included_by_user_id,
                        diagnosis_at_inclusion, egfr_at_inclusion,
                        ckd_stage_at_inclusion, comment_at_inclusion
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        patient_id,
                        today,
                        user_id,
                        diagnosis,
                        egfr_value,
                        stage,
                        comment,
                    ),
                )
                registry_entry_id = int(cur.fetchone()["id"])
            if outcome:
                cur.execute(
                    """
                    INSERT INTO ckd_registry_outcomes (
                        registry_entry_id, outcome_type, outcome_date,
                        comment, created_by_user_id
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (registry_entry_id, outcome, today, comment, user_id),
                )
            return registry_entry_id



def remove_patient_from_registry(*, patient_id: int, user_id: int) -> int:
    """Скрывает ошибочно включённого пациента, не удаляя его ЭМК."""
    if patient_id <= 0 or user_id <= 0:
        raise RegistryValidationError("Не удалось определить пациента или пользователя")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ckd_registry_entries
                SET is_active = FALSE,
                    updated_at = now()
                WHERE patient_id = %s AND is_active = TRUE
                RETURNING id
                """,
                (patient_id,),
            )
            row = cur.fetchone()
            if not row:
                raise RegistryValidationError("Пациент не состоит в активном регистре ХБП")
            return int(row["id"])


def add_registry_outcome(
    *,
    patient_id: int,
    user_id: int,
    outcome: str,
    comment: str | None,
) -> int:
    """Добавляет новый исход, сохраняя историю предыдущих исходов."""
    outcome = str(outcome or "").strip()
    if outcome not in OUTCOME_LABELS:
        raise RegistryValidationError("Выберите исход")
    comment = str(comment or "").strip() or None
    today = date.today()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM ckd_registry_entries
                WHERE patient_id = %s AND is_active = TRUE
                FOR UPDATE
                """,
                (patient_id,),
            )
            row = cur.fetchone()
            if not row:
                raise RegistryValidationError("Пациент не состоит в регистре ХБП")
            registry_entry_id = int(row["id"])
            cur.execute(
                """
                INSERT INTO ckd_registry_outcomes (
                    registry_entry_id, outcome_type, outcome_date,
                    comment, created_by_user_id
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (registry_entry_id, outcome, today, comment, user_id),
            )
            outcome_id = int(cur.fetchone()["id"])
            cur.execute(
                "UPDATE ckd_registry_entries SET updated_at = now() WHERE id = %s",
                (registry_entry_id,),
            )
            return outcome_id


def _registry_sql(filters: CkdRegistryFilters) -> tuple[str, dict[str, Any]]:
    conditions = ["e.is_active = TRUE"]
    params: dict[str, Any] = {
        "limit": filters.page_size,
        "offset": (filters.page - 1) * filters.page_size,
    }
    if filters.search:
        conditions.append(
            "(TRIM(p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '')) ILIKE %(search)s "
            "OR COALESCE(p.phone, '') ILIKE %(search)s)"
        )
        params["search"] = f"%{filters.search}%"
    if filters.stage:
        conditions.append(
            "COALESCE(metrics.ckd_stage, e.ckd_stage_at_inclusion) = %(stage)s"
        )
        params["stage"] = filters.stage
    egfr_expression = "COALESCE(metrics.egfr_ckdepi, e.egfr_at_inclusion)"
    if filters.egfr_operator == "lt" and filters.egfr_from is not None:
        conditions.append(f"{egfr_expression} < %(egfr_from)s")
        params["egfr_from"] = filters.egfr_from
    elif filters.egfr_operator == "gt" and filters.egfr_from is not None:
        conditions.append(f"{egfr_expression} > %(egfr_from)s")
        params["egfr_from"] = filters.egfr_from
    elif (
        filters.egfr_operator == "between"
        and filters.egfr_from is not None
        and filters.egfr_to is not None
    ):
        conditions.append(
            f"{egfr_expression} BETWEEN %(egfr_from)s AND %(egfr_to)s"
        )
        params["egfr_from"] = filters.egfr_from
        params["egfr_to"] = filters.egfr_to
    if filters.outcome == "none":
        conditions.append("latest_outcome.outcome_type IS NULL")
    elif filters.outcome:
        conditions.append("latest_outcome.outcome_type = %(outcome)s")
        params["outcome"] = filters.outcome
    if filters.included_from:
        conditions.append("e.included_at >= %(included_from)s")
        params["included_from"] = filters.included_from
    if filters.included_to:
        conditions.append("e.included_at <= %(included_to)s")
        params["included_to"] = filters.included_to

    sql = f"""
        SELECT
            COUNT(*) OVER() AS total_count,
            e.id AS registry_entry_id,
            e.patient_id,
            e.included_at,
            TRIM(p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '')) AS patient_fio,
            p.birth_date,
            p.phone,
            COALESCE(
                NULLIF(TRIM(structured_diagnosis.icd10_diagnosis), ''),
                e.diagnosis_at_inclusion
            ) AS main_diagnosis,
            COALESCE(metrics.egfr_ckdepi, e.egfr_at_inclusion) AS egfr,
            COALESCE(metrics.ckd_stage, e.ckd_stage_at_inclusion) AS ckd_stage,
            latest_outcome.outcome_type,
            latest_outcome.outcome_date,
            latest_outcome.comment AS outcome_comment,
            latest_appointment.appointment_date AS last_appointment_date
        FROM ckd_registry_entries e
        JOIN patients p ON p.id = e.patient_id
        LEFT JOIN LATERAL (
            SELECT a.id AS appointment_id, a.appointment_date
            FROM appointments a
            WHERE a.patient_id = e.patient_id
            ORDER BY a.appointment_date DESC, a.id DESC
            LIMIT 1
        ) latest_appointment ON TRUE
        LEFT JOIN LATERAL (
            SELECT v.icd10_diagnosis
            FROM appointment_icd10_diagnoses_view v
            WHERE v.appointment_id = latest_appointment.appointment_id
              AND v.diagnosis_type = 'main'
            ORDER BY v.sort_order, v.id
            LIMIT 1
        ) structured_diagnosis ON TRUE
        LEFT JOIN LATERAL (
            SELECT cm.egfr_ckdepi, cm.ckd_stage
            FROM calculated_metrics cm
            WHERE cm.appointment_id = latest_appointment.appointment_id
            ORDER BY cm.investigation_date DESC NULLS LAST,
                     cm.calculation_date DESC,
                     cm.id DESC
            LIMIT 1
        ) metrics ON TRUE
        LEFT JOIN LATERAL (
            SELECT o.outcome_type, o.outcome_date, o.comment
            FROM ckd_registry_outcomes o
            WHERE o.registry_entry_id = e.id
            ORDER BY o.outcome_date DESC, o.created_at DESC, o.id DESC
            LIMIT 1
        ) latest_outcome ON TRUE
        WHERE {' AND '.join(conditions)}
        ORDER BY e.included_at DESC, p.last_name, p.first_name, e.id DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """
    return sql, params


def get_ckd_registry(filters: CkdRegistryFilters) -> dict[str, Any]:
    """Возвращает страницу локального регистра."""
    sql, params = _registry_sql(filters)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["outcome_label"] = OUTCOME_LABELS.get(row.get("outcome_type"), DEFAULT_OUTCOME_LABEL)
        if not row.get("outcome_type") and not row.get("outcome_date"):
            row["outcome_date"] = row.get("included_at")
    total = int(rows[0]["total_count"]) if rows else 0
    pages = max((total + filters.page_size - 1) // filters.page_size, 1)
    return {
        "rows": rows,
        "total": total,
        "pages": pages,
        "page": filters.page,
        "page_size": filters.page_size,
        "query_without_page": filters.without_page_query(),
    }


def _excel_col(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell(ref: str, value: Any, style: int = 0) -> str:
    style_attr = f' s="{style}"' if style else ""
    if value is None:
        return f'<c r="{ref}"{style_attr} t="inlineStr"><is><t></t></is></c>'
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return f'<c r="{ref}"{style_attr}><v>{escape(str(value))}</v></c>'
    text = str(value)
    preserve = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f'<c r="{ref}"{style_attr} t="inlineStr"><is><t{preserve}>{escape(text)}</t></is></c>'


def _xlsx_bytes(rows: list[dict[str, Any]]) -> bytes:
    headers = [
        "ФИО",
        "Дата рождения",
        "Дата включения в регистр",
        "Номер телефона",
        "Основной диагноз",
        "СКФ",
        "Стадия ХБП",
        "Исход",
        "Дата исхода",
        "Ссылка на ЭМК",
    ]
    sheet_rows: list[str] = []
    sheet_rows.append(
        '<row r="1" ht="24" customHeight="1">'
        + _cell("A1", "Регистр пациентов с ХБП", 2)
        + "</row>"
    )
    sheet_rows.append(
        '<row r="2">'
        + _cell("A2", f"Сформировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}", 3)
        + "</row>"
    )
    header_cells = "".join(
        _cell(f"{_excel_col(index)}4", header, 1)
        for index, header in enumerate(headers, start=1)
    )
    sheet_rows.append(f'<row r="4" ht="30" customHeight="1">{header_cells}</row>')

    for row_index, item in enumerate(rows, start=5):
        values = [
            item.get("patient_fio") or "",
            item["birth_date"].strftime("%d.%m.%Y") if item.get("birth_date") else "",
            item["included_at"].strftime("%d.%m.%Y") if item.get("included_at") else "",
            item.get("phone") or "",
            item.get("main_diagnosis") or "",
            item.get("egfr"),
            item.get("ckd_stage") or "",
            item.get("outcome_label") or DEFAULT_OUTCOME_LABEL,
            item["outcome_date"].strftime("%d.%m.%Y") if item.get("outcome_date") else "",
            f"/patient/{item.get('patient_id')}",
        ]
        cells = "".join(
            _cell(f"{_excel_col(index)}{row_index}", value, 3)
            for index, value in enumerate(values, start=1)
        )
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')

    last_row = max(4, len(rows) + 4)
    worksheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:J{last_row}"/>
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="18"/>
  <cols>
    <col min="1" max="1" width="32" customWidth="1"/>
    <col min="2" max="3" width="19" customWidth="1"/>
    <col min="4" max="4" width="18" customWidth="1"/>
    <col min="5" max="5" width="52" customWidth="1"/>
    <col min="6" max="7" width="14" customWidth="1"/>
    <col min="8" max="8" width="31" customWidth="1"/>
    <col min="9" max="9" width="16" customWidth="1"/>
    <col min="10" max="10" width="20" customWidth="1"/>
  </cols>
  <sheetData>{''.join(sheet_rows)}</sheetData>
  <autoFilter ref="A4:J{last_row}"/>
  <mergeCells count="1"><mergeCell ref="A1:J1"/></mergeCells>
</worksheet>'''

    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="3">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="16"/><name val="Calibri"/></font>
  </fonts>
  <fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0D6EFD"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="2"><border/><border><left style="thin"><color rgb="FFD9E2F3"/></left><right style="thin"><color rgb="FFD9E2F3"/></right><top style="thin"><color rgb="FFD9E2F3"/></top><bottom style="thin"><color rgb="FFD9E2F3"/></bottom></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="4">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>''',
        )
        archive.writestr(
            "_rels/.rels",
            '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>''',
        )
        archive.writestr(
            "xl/workbook.xml",
            '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Регистр ХБП" sheetId="1" r:id="rId1"/></sheets>
</workbook>''',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>''',
        )
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
        archive.writestr("xl/styles.xml", styles)
        archive.writestr(
            "docProps/core.xml",
            f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Регистр пациентов с ХБП</dc:title><dc:creator>МИС Нефролога</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}</dcterms:created>
</cp:coreProperties>''',
        )
        archive.writestr(
            "docProps/app.xml",
            '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>МИС Нефролога</Application></Properties>''',
        )
    return output.getvalue()


def build_ckd_registry_xlsx(filters: CkdRegistryFilters) -> tuple[bytes, str]:
    export_filters = replace(filters, page=1, page_size=100000)
    result = get_ckd_registry(export_filters)
    return _xlsx_bytes(result["rows"]), f"ckd_registry_{date.today().isoformat()}.xlsx"
