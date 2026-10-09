"""Валидация форм. ORM-модели не используются."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation


def validate_patient(d: dict) -> str | None:
    if not str(d.get("full_name", "")).strip():
        return "Введите ФИО пациента"
    if len(str(d.get("full_name"))) > 150:
        return "ФИО слишком длинное"
    bd = d.get("birth_date")
    if bd:
        try:
            b = date.fromisoformat(str(bd))
            if b > date.today() or b.year < 1900:
                return "Некорректная дата рождения"
        except ValueError:
            return "Дата рождения должна быть в формате ГГГГ-ММ-ДД"
    return None


def validate_doctor(d: dict) -> str | None:
    if not str(d.get("full_name", "")).strip():
        return "Введите ФИО врача"
    if not str(d.get("specialty", "")).strip():
        return "Введите специализацию"
    return None


def validate_service(d: dict) -> str | None:
    if not str(d.get("name", "")).strip():
        return "Введите название услуги"
    if not str(d.get("category", "")).strip():
        return "Введите категорию"
    try:
        price = Decimal(str(d.get("price", "")).replace(",", "."))
    except InvalidOperation:
        return "Цена должна быть числом"
    if price <= 0:
        return "Цена должна быть больше 0"
    try:
        dur = int(d.get("duration", 0))
    except (TypeError, ValueError):
        return "Длительность должна быть целым числом"
    if dur <= 0:
        return "Длительность должна быть больше 0"
    return None


def validate_appointment(d: dict) -> str | None:
    if not d.get("patient_id"):
        return "Выберите пациента"
    if not d.get("doctor_id"):
        return "Выберите врача"
    if not d.get("cabinet_id"):
        return "Выберите кабинет"
    try:
        date.fromisoformat(str(d.get("visit_date")))
    except (ValueError, TypeError):
        return "Дата приёма должна быть в формате ГГГГ-ММ-ДД"
    vt = str(d.get("visit_time", ""))
    if not re.fullmatch(r"\d{2}:\d{2}", vt):
        return "Время приёма должно быть в формате ЧЧ:ММ"
    if d.get("status") not in ("planned", "done", "cancelled", "no_show"):
        return "Недопустимый статус приёма"
    return None


def validate_payment(d: dict) -> str | None:
    if not d.get("appointment_id"):
        return "Выберите приём"
    try:
        amount = Decimal(str(d.get("amount", "")).replace(",", "."))
    except InvalidOperation:
        return "Сумма должна быть числом"
    if amount <= 0:
        return "Сумма должна быть больше 0"
    if d.get("method") not in ("cash", "card", "transfer"):
        return "Недопустимый способ оплаты"
    try:
        date.fromisoformat(str(d.get("pay_date", "")))
    except (ValueError, TypeError):
        return "Дата платежа должна быть в формате ГГГГ-ММ-ДД"
    return None