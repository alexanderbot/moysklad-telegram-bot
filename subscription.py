from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, Optional

from config import config, now_moscow, today_moscow


FULL_ACCESS_STATUSES = {"trial", "active"}


def is_superadmin(telegram_id: int) -> bool:
    """
    Проверка, является ли пользователь суперадмином.

    Суперадмины берутся из config.ADMIN_IDS (список ID из .env/ADMIN_IDS).
    """
    return telegram_id in config.ADMIN_IDS


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Безопасно парсим значение даты/времени из БД."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # SQLite по умолчанию возвращает строку в ISO-формате
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def check_subscription(db, telegram_id: int, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Универсальная проверка подписки пользователя.

    Возвращает словарь:
        {
            "ok": bool,               # есть ли доступ хотя бы к чему-то
            "mode": "full"|"limited"|None,
            "status": str,            # none|trial|active|expired|no_registration|superadmin
            "days_left": int|None,    # дни до окончания (может быть отрицательным)
            "is_superadmin": bool
        }
    """
    if now is None:
        now = now_moscow()

    if is_superadmin(telegram_id):
        return {
            "ok": True,
            "mode": "full",
            "status": "superadmin",
            "days_left": None,
            "is_superadmin": True,
        }

    user = db.get_user(telegram_id)
    if not user or not user.get("api_token_encrypted"):
        return {
            "ok": False,
            "mode": None,
            "status": "no_registration",
            "days_left": None,
            "is_superadmin": False,
        }

    status = (user.get("subscription_status") or "none").lower()
    expires_at_raw = user.get("subscription_expires_at")
    expires_at = _parse_datetime(expires_at_raw)

    # Если дат нет, считаем, что ограничений нет (на всякий случай)
    if not expires_at or status == "none":
        return {
            "ok": True,
            "mode": "full",
            "status": status,
            "days_left": None,
            "is_superadmin": False,
        }

    days_left = (expires_at.date() - now.date()).days

    # Полный доступ в рамках триала/оплаченного периода
    if status in FULL_ACCESS_STATUSES and days_left >= 0:
        return {
            "ok": True,
            "mode": "full",
            "status": status,
            "days_left": days_left,
            "is_superadmin": False,
        }

    # Льготный период: -2 и -1 день после окончания основной подписки
    if status in FULL_ACCESS_STATUSES and -2 <= days_left < 0:
        return {
            "ok": True,
            "mode": "limited",
            "status": status,
            "days_left": days_left,
            "is_superadmin": False,
        }

    # Больше чем 2 дня после окончания — подписка считается полностью истекшей
    if status in FULL_ACCESS_STATUSES and days_left < -2:
        # Пытаемся обновить статус в БД на expired
        try:
            db.set_subscription_status(telegram_id, "expired")
        except Exception:
            # Не критично, просто логика выше будет считать статусом старое значение
            pass

        return {
            "ok": False,
            "mode": None,
            "status": "expired",
            "days_left": days_left,
            "is_superadmin": False,
        }

    # Явно просроченный или неизвестный статус
    return {
        "ok": False,
        "mode": None,
        "status": status or "expired",
        "days_left": days_left,
        "is_superadmin": False,
    }


def compute_days_left(expires_at_value: Any, today: Optional[date] = None) -> Optional[int]:
    """
    Вспомогательная функция для расчета дней до окончания по произвольному значению даты.
    Используется в планировщике напоминаний. Даты считаются по Москве.
    """
    if today is None:
        today = today_moscow()
    dt = _parse_datetime(expires_at_value)
    if not dt:
        return None
    return (dt.date() - today).days

