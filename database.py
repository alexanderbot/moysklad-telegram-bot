import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager

from config import now_moscow

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных SQLite"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для соединения с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def init_db(self):
        """Инициализация базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    phone_number TEXT,
                    api_token_encrypted TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    subscription_status TEXT DEFAULT 'none',
                    trial_started_at TIMESTAMP,
                    subscription_expires_at TIMESTAMP,
                    last_subscription_notified_at DATE
                )
            ''')

            # На случай уже существующей таблицы — добавляем недостающие колонки безопасно
            alter_statements = [
                "ALTER TABLE users ADD COLUMN subscription_status TEXT DEFAULT 'none'",
                "ALTER TABLE users ADD COLUMN trial_started_at TIMESTAMP",
                "ALTER TABLE users ADD COLUMN subscription_expires_at TIMESTAMP",
                "ALTER TABLE users ADD COLUMN last_subscription_notified_at DATE",
            ]
            for stmt in alter_statements:
                try:
                    cursor.execute(stmt)
                except Exception:
                    # Колонка уже есть или другая не критичная ошибка миграции — игнорируем
                    pass

            # Таблица настроек пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER NOT NULL,
                    default_report_type TEXT DEFAULT 'today',
                    notification_enabled BOOLEAN DEFAULT 0,
                    timezone TEXT DEFAULT 'Europe/Moscow',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')

            # Таблица логов запросов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    request_type TEXT,
                    period TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

            logger.info("Database initialized successfully")

    def add_user(self, telegram_id: int, phone_number: str = None) -> int:
        """Добавление нового пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Проверяем, существует ли пользователь
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
            existing = cursor.fetchone()

            if existing:
                return existing['id']

            # Добавляем нового пользователя (время по Москве)
            now = now_moscow()
            cursor.execute('''
                INSERT INTO users (telegram_id, phone_number, created_at, last_active)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, phone_number, now, now))

            user_id = cursor.lastrowid

            # Добавляем настройки по умолчанию
            cursor.execute('''
                INSERT INTO user_settings (user_id)
                VALUES (?)
            ''', (user_id,))

            logger.info(f"New user added: {telegram_id}")
            return user_id

    def update_user_token(self, telegram_id: int, encrypted_token: str) -> bool:
        """Обновление API-токена пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET api_token_encrypted = ?, last_active = ?
                WHERE telegram_id = ?
            ''', (encrypted_token, now_moscow(), telegram_id))

            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Token updated for user: {telegram_id}")
            return updated

    def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение данных пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.*, us.* 
                FROM users u
                LEFT JOIN user_settings us ON u.id = us.user_id
                WHERE u.telegram_id = ?
            ''', (telegram_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def log_request(self, user_id: int, request_type: str, period: str):
        """Логирование запроса пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO request_logs (user_id, request_type, period)
                VALUES (?, ?, ?)
            ''', (user_id, request_type, period))

    # ===== Методы подписки =====

    def update_subscription(self,
                            telegram_id: int,
                            status: str,
                            expires_at: datetime | None = None,
                            trial_started_at: datetime | None = None) -> bool:
        """
        Обновление информации о подписке пользователя.

        Args:
            telegram_id: Telegram ID пользователя
            status: Статус подписки (none|trial|active|expired)
            expires_at: Дата окончания подписки/триала
            trial_started_at: Дата начала триала
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            fields = ["subscription_status = ?"]
            values: list[Any] = [status]

            if expires_at is not None:
                fields.append("subscription_expires_at = ?")
                values.append(expires_at)
            if trial_started_at is not None:
                fields.append("trial_started_at = ?")
                values.append(trial_started_at)

            # всегда обновляем last_active при изменении подписки (по Москве)
            fields.append("last_active = ?")
            values.append(now_moscow())

            values.append(telegram_id)

            query = f'''
                UPDATE users
                SET {", ".join(fields)}
                WHERE telegram_id = ?
            '''
            cursor.execute(query, tuple(values))
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Subscription updated for user {telegram_id}: status={status}")
            else:
                logger.warning(f"Attempt to update subscription for non-existing user {telegram_id}")
            return updated

    def set_subscription_status(self, telegram_id: int, status: str) -> bool:
        """Обновление только статуса подписки (без изменения дат)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                UPDATE users
                SET subscription_status = ?, last_active = ?
                WHERE telegram_id = ?
                ''',
                (status, now_moscow(), telegram_id)
            )
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Subscription status set to {status} for user {telegram_id}")
            return updated

    def get_all_users_for_subscription_check(self) -> list[Dict[str, Any]]:
        """
        Получить список пользователей для проверки подписки.

        Возвращает минимальный набор полей, необходимых для напоминаний.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT telegram_id,
                       subscription_status,
                       trial_started_at,
                       subscription_expires_at,
                       last_subscription_notified_at
                FROM users
                WHERE is_active = 1
                '''
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_subscription_notification_date(self, telegram_id: int, notify_date: datetime.date) -> bool:
        """
        Обновить дату последнего уведомления по подписке.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                UPDATE users
                SET last_subscription_notified_at = ?
                WHERE telegram_id = ?
                ''',
                (notify_date, telegram_id)
            )
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Updated last_subscription_notified_at for user {telegram_id} to {notify_date}")
            return updated

    def update_last_active(self, telegram_id: int):
        """Обновление времени последней активности"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET last_active = ?
                WHERE telegram_id = ?
            ''', (now_moscow(), telegram_id))

    def get_users_with_notifications(self) -> list:
        """
        Получить список пользователей с включенными уведомлениями
        
        Returns:
            List[tuple]: Список кортежей (telegram_id, encrypted_api_token)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.telegram_id, u.api_token_encrypted
                FROM users u
                JOIN user_settings s ON u.id = s.user_id
                WHERE s.notification_enabled = 1 
                  AND u.api_token_encrypted IS NOT NULL
                  AND u.is_active = 1
            ''')
            
            results = cursor.fetchall()
            # Преобразуем Row объекты в кортежи
            return [(row['telegram_id'], row['api_token_encrypted']) for row in results]

    def update_notification_setting(self, telegram_id: int, enabled: bool) -> bool:
        """
        Обновить настройку уведомлений для пользователя
        
        Args:
            telegram_id: Telegram ID пользователя
            enabled: True для включения, False для выключения
            
        Returns:
            bool: True если обновление успешно
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем ID пользователя
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
            user = cursor.fetchone()
            
            if not user:
                logger.warning(f"Пользователь {telegram_id} не найден")
                return False
            
            user_id = user['id']
            
            # Обновляем настройку
            cursor.execute('''
                UPDATE user_settings 
                SET notification_enabled = ?, updated_at = ?
                WHERE user_id = ?
            ''', (1 if enabled else 0, now_moscow(), user_id))
            
            updated = cursor.rowcount > 0
            
            if updated:
                logger.info(f"Уведомления {'включены' if enabled else 'выключены'} для пользователя {telegram_id}")
            
            return updated

    def get_notification_status(self, telegram_id: int) -> Optional[bool]:
        """
        Получить статус уведомлений для пользователя
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            bool: True если уведомления включены, False если выключены, None если пользователь не найден
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.notification_enabled
                FROM users u
                JOIN user_settings s ON u.id = s.user_id
                WHERE u.telegram_id = ?
            ''', (telegram_id,))
            
            result = cursor.fetchone()
            if result:
                return bool(result['notification_enabled'])
            return None

    def delete_user(self, telegram_id: int) -> bool:
        """
        Полное удаление пользователя и связанных данных из БД.
        Удаляются:
        - запись в users
        - связанные настройки и логи запросов.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Получаем внутренний id пользователя
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
            user = cursor.fetchone()

            if not user:
                logger.info(f"Попытка удаления несуществующего пользователя {telegram_id}")
                return False

            user_id = user["id"]

            # Сначала удаляем логи запросов и настройки (на случай отсутствия каскадов)
            cursor.execute("DELETE FROM request_logs WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Пользователь {telegram_id} (id={user_id}) успешно удалён из БД")

            return deleted


# Создаем синглтон экземпляр БД
def init_database(db_path: str) -> Database:
    """Инициализация базы данных"""
    return Database(db_path)