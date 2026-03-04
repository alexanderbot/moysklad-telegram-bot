import os
from dataclasses import dataclass, field
from datetime import datetime, date
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from typing import List

# Часовой пояс для регистрации, подписки и отчётов (время в БД и сравнения)
APP_TIMEZONE = "Europe/Moscow"


def now_moscow() -> datetime:
    """Текущее время по Москве (naive datetime для записи в БД)."""
    return datetime.now(ZoneInfo(APP_TIMEZONE)).replace(tzinfo=None)


def today_moscow() -> date:
    """Текущая дата по Москве (для сравнения дней подписки и т.п.)."""
    return datetime.now(ZoneInfo(APP_TIMEZONE)).date()

# Базовая директория проекта (там, где лежит этот файл config.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Загружаем переменные окружения из .env в корне проекта (независимо от текущей директории)
load_dotenv(os.path.join(BASE_DIR, ".env"))


@dataclass
class Config:
    """Конфигурация приложения"""
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Папки для данных и логов - всегда внутри проекта
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    LOGS_DIR: str = os.path.join(BASE_DIR, "logs")

    # Путь к БД: если в .env указан абсолютный путь - используем его как есть,
    # если относительный или не указан - создаём/используем БД в папке проекта /data
    DB_PATH: str = os.path.join(
        BASE_DIR,
        os.getenv("DB_PATH", os.path.join("data", "bot_database.db"))
    ) if not os.path.isabs(os.getenv("DB_PATH", "")) else os.getenv("DB_PATH")

    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

    # Настройки API МойСклад
    MOYSKLAD_API_BASE_URL: str = "https://api.moysklad.ru/api/remap/1.2"
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))

    # Настройки бота - используем field с default_factory для списка
    ADMIN_IDS: List[int] = field(default_factory=lambda:
    list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
                                 )

    # Подписка
    SUBSCRIPTION_PAYMENT_URL: str = os.getenv("SUBSCRIPTION_PAYMENT_URL", "")
    SUBSCRIPTION_PRICE_RUB: int = int(os.getenv("SUBSCRIPTION_PRICE_RUB", "199"))
    TELEGRAM_PROVIDER_TOKEN: str = os.getenv("TELEGRAM_PROVIDER_TOKEN", "")

    # Настройки планировщика и времени в приложении (регистрация, подписка)
    SCHEDULER_TIMEZONE: str = APP_TIMEZONE
    DAILY_REPORT_TIME: tuple = (9, 0)  # час, минута
    WEEKLY_REPORT_TIME: tuple = (9, 5)  # понедельник в 9:05
    MONTHLY_REPORT_TIME: tuple = (9, 0)  # 1 число месяца в 9:00

    def validate(self) -> bool:
        """Проверка обязательных настроек"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен в .env файле")

        # Проверка ключа шифрования
        if not self.ENCRYPTION_KEY:
            print("⚠️  Внимание: ENCRYPTION_KEY не установлен. Создаю временный ключ...")
            self.ENCRYPTION_KEY = self._generate_temp_key()
        elif len(self.ENCRYPTION_KEY) != 44:  # Fernet ключ всегда 44 символа
            print(f"⚠️  Внимание: ENCRYPTION_KEY имеет неверную длину ({len(self.ENCRYPTION_KEY)} вместо 44)")
            print("Создаю временный ключ...")
            self.ENCRYPTION_KEY = self._generate_temp_key()

        return True

    def _generate_temp_key(self) -> str:
        """Генерация временного ключа шифрования"""
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        print(f"📋 Временный ключ (добавьте в .env):")
        print(f"ENCRYPTION_KEY={key}")
        return key

    def setup_dirs(self):
        """Создание необходимых директорий"""
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.LOGS_DIR, exist_ok=True)

        # Создаем папку для базы данных, если нужно
        db_dir = os.path.dirname(self.DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)


# Создаем экземпляр конфигурации
config = Config()