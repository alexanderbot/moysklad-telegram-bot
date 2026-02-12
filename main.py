#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)
from telegram import Update
from telegram.constants import ParseMode

from config import config
from database import init_database
from handlers import AuthHandlers, MenuHandlers, NotificationHandlers, REGISTRATION, API_TOKEN
from keyboards import get_main_menu
from scheduler import StatisticsScheduler
from moysklad_api import MoyskladAPI

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    logger.info(f"👋 Пользователь {user.id} ({user.first_name}) начал работу с ботом")

    try:
        # Инициализируем БД
        db = init_database(config.DB_PATH)

        # Проверяем регистрацию пользователя
        user_data = db.get_user(user.id)
        is_registered = user_data and user_data.get('api_token_encrypted')

        # Формируем приветственное сообщение
        if is_registered:
            # Пользователь зарегистрирован
            welcome_text = (
                f"С возвращением, {user.first_name}! 👋\n\n"
                "Я бот для работы со статистикой МойСклад.\n\n"
                "*Доступные функции:*\n"
                "• 📊 Быстрый отчет - сводка за сегодня, неделю и месяц\n"
                "• 📊 Детальные отчеты - розничные продажи, заказы, отгрузки, объединенный отчет\n"
                "• 📈 Аналитика - сравнение периодов\n"
                "• ⚙️ Настройки - управление API-токеном\n\n"
                "Используйте меню для навигации."
            )
            logger.info(f"✅ Зарегистрированный пользователь {user.id}")
        else:
            # Пользователь не зарегистрирован
            welcome_text = (
                f"Привет, {user.first_name}! 👋\n\n"
                "Я бот для работы со статистикой МойСклад.\n\n"
                "*Для начала работы необходимо:*\n"
                "1. Зарегистрироваться по номеру телефона\n"
                "2. Указать ваш API-токен МойСклад\n\n"
                "API-токен можно получить:\n"
                "1. Зайдите в МойСклад → Настройки → Безопасность\n"
                "2. Создайте новый токен или скопируйте существующий\n\n"
                "Используйте меню для навигации."
            )
            logger.info(f"⚠️ Незарегистрированный пользователь {user.id}")

        # Отправляем приветствие с правильной клавиатурой
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_menu(is_registered),
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке регистрации пользователя {user.id}: {e}", exc_info=True)

        # В случае ошибки показываем стандартное приветствие
        error_text = (
            f"Привет, {user.first_name}! 👋\n\n"
            "Я бот для работы со статистикой МойСклад.\n\n"
            "⚠️ *Временные технические проблемы*\n"
            "Не удалось проверить вашу регистрацию.\n\n"
            "Попробуйте использовать кнопки меню."
        )

        await update.message.reply_text(
            error_text,
            reply_markup=get_main_menu(False),
            parse_mode=ParseMode.MARKDOWN
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
📊 *Telegram Bot для МойСклад*

*Доступные команды:*
/start - Начать работу
/settings - Настройки API-токена
/notifications - Управление уведомлениями
/help - Эта справка

*Главное меню:*
📊 *Быстрый отчет* - сводка за сегодня, неделю и месяц
📊 *Детальные отчеты* - розничные продажи, заказы, отгрузки, объединенный отчет
📈 *Аналитика* - сравнение периодов
⚙️ *Настройки* - управление API-токеном
ℹ️ *Помощь* - справка по использованию

*Регистрация:*
1. Нажмите кнопку "Регистрация"
2. Поделитесь номером телефона
3. Введите API-токен из МойСклад

*Автоматические отчеты:*
• Ежедневно в 9:00 - статистика за вчера
• Понедельник в 9:05 - статистика за неделю
• 1 число месяца в 9:00 - отчет за месяц

Управление: /notifications

*Поддержка:*
По вопросам работы бота обращайтесь к администратору @ustinalex
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


def setup_handlers(application, db):
    """Настройка всех обработчиков"""
    auth = AuthHandlers(db)
    menu = MenuHandlers(db)
    notifications = NotificationHandlers(db)

    # ===== 1. СОЗДАЕМ ВСЕ ConversationHandler =====

    # ConversationHandler для регистрации
    registration_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(📱 Регистрация)$'), auth.start_auth)
        ],
        states={
            REGISTRATION: [
                MessageHandler(filters.CONTACT, auth.get_phone_number)
            ],
            API_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, auth.get_api_token)
            ]
        },
        fallbacks=[CommandHandler('cancel', auth.cancel_registration)]
    )

    # ConversationHandler для обновления токена
    token_update_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(🔄 Обновить токен|🔑 Установить API-токен)$'),
                           auth.update_token)
        ],
        states={
            'WAITING_TOKEN': [
                MessageHandler(filters.TEXT & ~filters.COMMAND, auth.process_token_update)
            ]
        },
        fallbacks=[CommandHandler('cancel', auth.cancel_registration)]
    )

    # 1. Сначала ConversationHandler
    application.add_handler(registration_handler)
    application.add_handler(token_update_handler)

    # 2. Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", auth.show_settings))
    application.add_handler(CommandHandler("notifications", notifications.notifications_command))

    # 3. Детальные отчеты
    application.add_handler(MessageHandler(
        filters.Regex('^(📊 Детальные отчеты)$'), menu.show_detailed_reports_menu
    ))

    # Выбор типа детального отчета
    application.add_handler(MessageHandler(
        filters.Regex('^(🛍 Розничные продажи)$'), menu.handle_retail_sales_report_menu
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^(📦 Заказы покупателей)$'), menu.handle_customer_orders_menu
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^(🚚 Отгрузки)$'), menu.handle_demand_menu
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^(📊 Объединенный отчет)$'), menu.handle_combined_report_menu
    ))

    # 4. ✅ ВАЖНО: Обработчик ввода дат (должен быть перед периодом)
    application.add_handler(MessageHandler(
        filters.Regex(r'^(\d{1,2}\.\d{1,2}\.\d{4} - \d{1,2}\.\d{1,2}\.\d{4}|\d{1,2}\.\d{1,2}\.\d{4})$') &
        filters.ChatType.PRIVATE,
        menu._handle_date_input  # ✅ Используем новый метод
    ))

    # 5. Обработчик кнопок периода для детальных отчетов
    application.add_handler(MessageHandler(
        filters.Regex('^(📅 Сегодня|📆 Неделя|📈 Месяц|🗓 Произвольный период)$') &
        filters.ChatType.PRIVATE,
        menu.handle_detailed_period_selection
    ))

    # 6. Возврат из детальных отчетов
    application.add_handler(MessageHandler(
        filters.Regex('^(🔙 Назад к отчетам)$'), menu.show_detailed_reports_menu
    ))

    # 7. Кнопка Назад
    application.add_handler(MessageHandler(
        filters.Regex('^(🔙 Назад)$'), menu.handle_back
    ))

    # 8. Быстрый отчет
    application.add_handler(MessageHandler(
        filters.Regex('^(📊 Быстрый отчет)$'), menu.handle_quick_report
    ))

    # 9. Аналитика
    application.add_handler(MessageHandler(
        filters.Regex('^(📈 Аналитика)$'), menu.show_analytics_menu
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^(📈 Сегодня vs Вчера)$'), menu.compare_today_yesterday
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^(📅 Год назад)$'), menu.compare_year_ago
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^(📆 Неделя vs Прошлая)$'), menu.compare_week
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^(📊 Месяц vs Прошлый)$'), menu.compare_month
    ))

    # 11. Топ-20 товаров за месяц
    application.add_handler(MessageHandler(
        filters.Regex('^(🧾 Топ-20 товаров)$'), menu.handle_top_products_month
    ))

    # 10. Настройки и помощь
    application.add_handler(MessageHandler(
        filters.Regex('^(⚙️ Настройки)$'), auth.show_settings
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^(ℹ️ Помощь)$'), help_command
    ))

    # 11. Управление уведомлениями (обработчики кнопок)
    application.add_handler(MessageHandler(
        filters.Regex('^(🔔 Включить уведомления|🔕 Выключить уведомления|◀️ Назад в меню)$'),
        notifications.toggle_notifications
    ))

    # 12. Эхо-обработчик (последним)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, menu.show_main_menu
    ))

def main():
    """Основная функция запуска бота"""
    # Проверка конфигурации
    try:
        config.validate()
        config.setup_dirs()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return

    # Инициализация базы данных
    db = init_database(config.DB_PATH)
    logger.info(f"Database initialized at {config.DB_PATH}")

    # Создание приложения бота
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Настройка обработчиков
    setup_handlers(application, db)

    # Инициализация и запуск планировщика
    logger.info("Initializing statistics scheduler...")
    scheduler = StatisticsScheduler(
        application=application,
        db=db,
        api_factory=lambda token: MoyskladAPI(token)
    )
    scheduler.start()
    logger.info("Statistics scheduler started successfully")

    # Запуск бота
    logger.info("Bot starting...")
    try:
        application.run_polling(allowed_updates=None)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    finally:
        # Останавливаем планировщик при завершении
        scheduler.stop()
        logger.info("Bot stopped")


if __name__ == '__main__':
    main()