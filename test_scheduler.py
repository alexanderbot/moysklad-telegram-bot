#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Тестовый скрипт для проверки функционала планировщика и уведомлений
"""

import sys
import os

# Добавляем текущую директорию в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database
from config import config

def print_header(text):
    """Печать заголовка секции"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def test_database_methods():
    """Тестирование методов базы данных"""
    print_header("ТЕСТ: Методы базы данных")
    
    # Инициализация БД
    db = Database(config.DB_PATH)
    print(f"✅ База данных инициализирована: {config.DB_PATH}")
    
    # Тест 1: Проверка наличия метода get_users_with_notifications
    print("\n1. Проверка метода get_users_with_notifications()...")
    try:
        users = db.get_users_with_notifications()
        print(f"   ✅ Метод работает")
        print(f"   📊 Найдено пользователей с уведомлениями: {len(users)}")
        
        if users:
            print("\n   Пользователи:")
            for i, (telegram_id, encrypted_token) in enumerate(users, 1):
                print(f"   {i}. Telegram ID: {telegram_id}")
                print(f"      Токен: {'✅ Есть' if encrypted_token else '❌ Нет'}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Тест 2: Проверка метода get_notification_status
    print("\n2. Проверка метода get_notification_status()...")
    try:
        # Получаем первого пользователя для теста
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM users LIMIT 1")
            result = cursor.fetchone()
            
            if result:
                test_user_id = result['telegram_id']
                status = db.get_notification_status(test_user_id)
                print(f"   ✅ Метод работает")
                print(f"   📊 Статус для пользователя {test_user_id}: {status}")
            else:
                print("   ℹ️  Нет пользователей в базе для теста")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Тест 3: Проверка метода update_notification_setting
    print("\n3. Проверка метода update_notification_setting()...")
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM users LIMIT 1")
            result = cursor.fetchone()
            
            if result:
                test_user_id = result['telegram_id']
                
                # Получаем текущий статус
                current_status = db.get_notification_status(test_user_id)
                print(f"   📊 Текущий статус: {current_status}")
                
                # Переключаем
                new_status = not current_status if current_status is not None else True
                success = db.update_notification_setting(test_user_id, new_status)
                
                if success:
                    # Проверяем изменение
                    updated_status = db.get_notification_status(test_user_id)
                    print(f"   ✅ Статус обновлен: {current_status} → {updated_status}")
                    
                    # Возвращаем обратно
                    db.update_notification_setting(test_user_id, current_status if current_status is not None else False)
                    print(f"   ✅ Статус возвращен к исходному значению")
                else:
                    print(f"   ❌ Не удалось обновить статус")
            else:
                print("   ℹ️  Нет пользователей в базе для теста")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

def test_scheduler_config():
    """Тестирование конфигурации планировщика"""
    print_header("ТЕСТ: Конфигурация планировщика")
    
    print("\n1. Проверка констант...")
    try:
        print(f"   ✅ SCHEDULER_TIMEZONE: {config.SCHEDULER_TIMEZONE}")
        print(f"   ✅ DAILY_REPORT_TIME: {config.DAILY_REPORT_TIME}")
        print(f"   ✅ WEEKLY_REPORT_TIME: {config.WEEKLY_REPORT_TIME}")
        print(f"   ✅ MONTHLY_REPORT_TIME: {config.MONTHLY_REPORT_TIME}")
    except AttributeError as e:
        print(f"   ❌ Отсутствует константа: {e}")
    
    print("\n2. Проверка модуля scheduler...")
    try:
        from scheduler import StatisticsScheduler
        print("   ✅ Модуль scheduler импортирован")
        print(f"   ✅ Класс StatisticsScheduler доступен")
    except ImportError as e:
        print(f"   ❌ Ошибка импорта: {e}")

def test_handlers():
    """Тестирование обработчиков уведомлений"""
    print_header("ТЕСТ: Обработчики уведомлений")
    
    print("\n1. Проверка импорта NotificationHandlers...")
    try:
        from handlers import NotificationHandlers
        print("   ✅ Класс NotificationHandlers импортирован")
        
        # Проверяем наличие методов
        methods = ['notifications_command', 'toggle_notifications']
        for method in methods:
            if hasattr(NotificationHandlers, method):
                print(f"   ✅ Метод {method} существует")
            else:
                print(f"   ❌ Метод {method} отсутствует")
    except ImportError as e:
        print(f"   ❌ Ошибка импорта: {e}")

def test_keyboards():
    """Тестирование клавиатур"""
    print_header("ТЕСТ: Клавиатуры")
    
    print("\n1. Проверка функции get_notifications_keyboard...")
    try:
        from keyboards import get_notifications_keyboard
        print("   ✅ Функция импортирована")
        
        # Тест для включенных уведомлений
        keyboard_enabled = get_notifications_keyboard(True)
        print("   ✅ Клавиатура для enabled=True создана")
        
        # Тест для выключенных уведомлений
        keyboard_disabled = get_notifications_keyboard(False)
        print("   ✅ Клавиатура для enabled=False создана")
        
    except ImportError as e:
        print(f"   ❌ Ошибка импорта: {e}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

def show_statistics():
    """Показать статистику по уведомлениям"""
    print_header("СТАТИСТИКА")
    
    db = Database(config.DB_PATH)
    
    # Общее количество пользователей
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_users = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as enabled 
            FROM users u
            JOIN user_settings s ON u.id = s.user_id
            WHERE s.notification_enabled = 1
        """)
        enabled_users = cursor.fetchone()['enabled']
        
        cursor.execute("""
            SELECT COUNT(*) as with_token 
            FROM users 
            WHERE api_token_encrypted IS NOT NULL
        """)
        users_with_token = cursor.fetchone()['with_token']
    
    print(f"\n👥 Всего пользователей: {total_users}")
    print(f"🔑 С API-токеном: {users_with_token}")
    print(f"🔔 С включенными уведомлениями: {enabled_users}")
    
    if enabled_users > 0:
        percentage = (enabled_users / total_users * 100) if total_users > 0 else 0
        print(f"📊 Процент подписанных: {percentage:.1f}%")

def main():
    """Основная функция тестирования"""
    print("\n" + "🧪 " * 30)
    print("  ТЕСТИРОВАНИЕ ФУНКЦИОНАЛА ПЛАНИРОВЩИКА")
    print("🧪 " * 30)
    
    try:
        # Запускаем тесты
        test_database_methods()
        test_scheduler_config()
        test_handlers()
        test_keyboards()
        show_statistics()
        
        print_header("ИТОГ")
        print("\n✅ Все тесты завершены!")
        print("\n📝 Следующие шаги:")
        print("   1. Запустите бота: python main.py")
        print("   2. Отправьте команду /notifications в чат с ботом")
        print("   3. Проверьте включение/выключение уведомлений")
        print("   4. Для теста рассылки измените время в scheduler.py")
        print("   5. Проверьте логи на наличие ошибок")
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
