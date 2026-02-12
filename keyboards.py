from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)



def get_main_menu(is_registered: bool = False):
    """Главное меню бота"""
    if is_registered:
        keyboard = [
            [KeyboardButton("📊 Быстрый отчет"), KeyboardButton("📊 Детальные отчеты")],
            [KeyboardButton("📈 Аналитика"), KeyboardButton("⚙️ Настройки")]
        ]
    else:
        keyboard = [
            [KeyboardButton("📱 Регистрация")],
            [KeyboardButton("ℹ️ Помощь")]
        ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_phone_keyboard():
    """Клавиатура для запроса номера телефона"""
    keyboard = [
        [KeyboardButton("📱 Поделиться номером", request_contact=True)],
        [KeyboardButton("❌ Отмена регистрации")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_report_keyboard():
    """Клавиатура для выбора отчетов"""
    keyboard = [
        [KeyboardButton("📅 Сегодня"), KeyboardButton("📆 Неделя")],
        [KeyboardButton("📈 Месяц"), KeyboardButton("🗓 Произвольный период")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_settings_keyboard():
    """Клавиатура настроек"""
    keyboard = [
        [KeyboardButton("🔑 Установить API-токен")],
        [KeyboardButton("🔄 Обновить токен")],
        [KeyboardButton("❌ Удалить аккаунт")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_back_keyboard():
    """Простая кнопка назад"""
    keyboard = [[KeyboardButton("🔙 Назад")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_analytics_keyboard():
    """Клавиатура для аналитики"""
    keyboard = [
        [KeyboardButton("📈 Сегодня vs Вчера"), KeyboardButton("📅 Год назад")],
        [KeyboardButton("📆 Неделя vs Прошлая"), KeyboardButton("📊 Месяц vs Прошлый")],
        [KeyboardButton("🧾 Топ-20 товаров")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Обновим функцию детализированных отчетов
def get_detailed_reports_keyboard():
    """Клавиатура детализированных отчетов"""
    keyboard = [
        [KeyboardButton("🛍 Розничные продажи")],
        [KeyboardButton("📦 Заказы покупателей")],
        [KeyboardButton("🚚 Отгрузки")],
        [KeyboardButton("📊 Объединенный отчет")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)



def get_detailed_period_keyboard(report_type: str = None):
    """Клавиатура выбора периода для детальных отчетов"""
    keyboard = [
        [KeyboardButton("📅 Сегодня"), KeyboardButton("📆 Неделя")],
        [KeyboardButton("📈 Месяц"), KeyboardButton("🗓 Произвольный период")],
        [KeyboardButton("🔙 Назад к отчетам")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_notifications_keyboard(enabled: bool) -> ReplyKeyboardMarkup:
    """
    Клавиатура управления уведомлениями
    
    Args:
        enabled: True если уведомления включены, False если выключены
        
    Returns:
        ReplyKeyboardMarkup с кнопками управления
    """
    if enabled:
        keyboard = [
            [KeyboardButton("🔕 Выключить уведомления")],
            [KeyboardButton("◀️ Назад в меню")]
        ]
    else:
        keyboard = [
            [KeyboardButton("🔔 Включить уведомления")],
            [KeyboardButton("◀️ Назад в меню")]
        ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)