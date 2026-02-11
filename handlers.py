import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
from telegram.constants import ParseMode

from moysklad_api import MoyskladAPI, get_period_dates, AnalyticsCalculator
from datetime import datetime
from database import Database
from security import security
from keyboards import (
    get_main_menu,
    get_phone_keyboard,
    get_report_keyboard,
    get_settings_keyboard,
    get_back_keyboard,
    get_analytics_keyboard,
    get_detailed_reports_keyboard,
    get_detailed_period_keyboard,
    get_notifications_keyboard
)

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
REGISTRATION, API_TOKEN = range(2)


class AuthHandlers:
    """Обработчики аутентификации"""

    def __init__(self, db: Database):
        self.db = db

    async def start_auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса регистрации"""
        user = update.effective_user
        logger.info(f"Начало регистрации для пользователя: {user.id}")

        # Проверяем, зарегистрирован ли уже пользователь
        user_data = self.db.get_user(user.id)

        # Проверяем полную регистрацию (телефон + токен)
        is_fully_registered = user_data and user_data.get('phone_number') and user_data.get('api_token_encrypted')

        if is_fully_registered:
            logger.info(f"Пользователь {user.id} уже зарегистрирован")

            # Формируем информацию о пользователе
            phone = user_data.get('phone_number', 'Не указан')
            registered_date = user_data.get('created_at', 'Неизвестно')

            await update.message.reply_text(
                f"✅ *Вы уже зарегистрированы!*\n\n"
                f"📱 Телефон: `{phone}`\n"
                f"📅 Дата регистрации: `{registered_date}`\n\n"
                "Используйте меню для работы с ботом.",
                reply_markup=get_main_menu(True),  # ✅ Исправлено: передаем True для зарегистрированных
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END

        # Проверяем, есть ли частичная регистрация (только телефон)
        has_phone = user_data and user_data.get('phone_number')

        if has_phone and not user_data.get('api_token_encrypted'):
            # Есть телефон, но нет токена - запрашиваем токен
            logger.info(f"У пользователя {user.id} есть телефон, но нет токена")

            phone = user_data.get('phone_number', 'Не указан')

            await update.message.reply_text(
                f"📱 *Продолжение регистрации*\n\n"
                f"У вас уже указан номер: `{phone}`\n\n"
                "📋 Теперь введите ваш *API-токен МойСклад*:\n\n"
                "1. Зайдите в МойСклад → Настройки → Токен \n"
                "2. Создайте новый токен \n"
                "3. Вставьте его в чат\n\n"
                "⚠️ *Токен будет зашифрован и безопасно сохранен*",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode=ParseMode.MARKDOWN
            )

            # Сохраняем user_id в контексте
            context.user_data['user_id'] = user_data['id']
            context.user_data['phone'] = phone

            return API_TOKEN

        # Полная регистрация - запрашиваем номер телефона
        logger.info(f"Начало полной регистрации для пользователя {user.id}")

        await update.message.reply_text(
            "🔐 *Регистрация в боте МойСклад*\n\n"
            "*Для доступа к статистике необходимо:*\n\n"
            "1. 📱 *Предоставить номер телефона*\n"
            "   - Нажмите кнопку 'Поделиться номером' ниже\n"
            "   - Или отправьте номер вручную\n\n"
            "2. 🔑 *Указать API-токен МойСклад*\n"
            "   - Зайдите в МойСклад → Настройки → Безопасность\n"
            "   - Создайте токен с правами на чтение\n"
            "   - Скопируйте и вставьте в бот\n\n"
            "*Ваши данные будут защищены:*\n"
            "• Номер телефона хранится в зашифрованном виде\n"
            "• API-токен шифруется перед сохранением\n"
            "• Данные не передаются третьим лицам\n\n"
            "Нажмите кнопку ниже, чтобы поделиться номером:",
            reply_markup=get_phone_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

        return REGISTRATION

    async def get_phone_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение номера телефона"""
        user = update.effective_user

        if update.message.contact:
            phone_number = update.message.contact.phone_number
            logger.info(f"Номер телефона получен для пользователя {user.id}: {phone_number}")

            # Сохраняем/обновляем пользователя
            user_id = self.db.add_user(user.id, phone_number)
            context.user_data['user_id'] = user_id
            context.user_data['phone'] = phone_number

            await update.message.reply_text(
                f"✅ *Номер телефона получен:* `{phone_number}`\n\n"
                "📋 Теперь введите ваш *API-токен МойСклад*:\n\n"
                "1. Зайдите в МойСклад → Настройки → Токены\n"
                "2. Создайте новый токен или скопируйте существующий\n"
                "3. Вставьте его в чат\n\n"
                "⚠️ *Токен будет зашифрован и безопасно сохранен*",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode=ParseMode.MARKDOWN
            )

            return API_TOKEN
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, используйте кнопку '📱 Поделиться номером'",
                reply_markup=get_phone_keyboard()
            )
            return REGISTRATION

    async def get_api_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение и сохранение API-токена"""
        user = update.effective_user
        api_token = update.message.text.strip()

        # Базовая валидация токена
        if len(api_token) < 20:
            await update.message.reply_text(
                "❌ Токен слишком короткий. Пожалуйста, проверьте правильность токена и введите его снова:"
            )
            return API_TOKEN

        try:
            # Шифруем токен
            encrypted_token = security.encrypt(api_token)

            # Сохраняем в базе данных
            success = self.db.update_user_token(user.id, encrypted_token)

            if success:
                logger.info(f"API-токен сохранен для пользователя {user.id}")

                # Обновляем время активности
                self.db.update_last_active(user.id)

                phone = context.user_data.get('phone', 'не указан')

                await update.message.reply_text(
                    "🎉 *Регистрация успешно завершена!*\n\n"
                    f"📱 *Телефон:* `{phone}`\n"
                    "🔐 *Токен:* ✅ Сохранен в зашифрованном виде\n\n"
                    "✅ Теперь вы можете получать статистику из МойСклад\n"
                    "Используйте меню для работы с отчетами:",
                    reply_markup=get_main_menu(True),  # ✅ Исправлено
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка сохранения токена. Попробуйте снова:",
                    reply_markup=ReplyKeyboardRemove()
                )
                return API_TOKEN

        except Exception as e:
            logger.error(f"Ошибка сохранения токена для пользователя {user.id}: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при сохранении токена. Попробуйте снова:",
                reply_markup=ReplyKeyboardRemove()
            )
            return API_TOKEN

        # Очищаем временные данные
        context.user_data.pop('user_id', None)
        context.user_data.pop('phone', None)

        return ConversationHandler.END

    async def cancel_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена регистрации"""
        user = update.effective_user

        # Проверяем статус пользователя
        user_data = self.db.get_user(user.id)
        is_registered = user_data and user_data.get('api_token_encrypted')

        await update.message.reply_text(
            "❌ Регистрация отменена.",
            reply_markup=get_main_menu(is_registered)  # ✅ Исправлено
        )

        # Очищаем временные данные
        context.user_data.clear()

        return ConversationHandler.END

    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать настройки"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)

        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Вы еще не зарегистрированы. Используйте /start для регистрации.",
                reply_markup=get_main_menu()
            )
            return

        phone_number = user_data.get('phone_number', 'Не указан')
        created_at = user_data.get('created_at', 'Неизвестно')

        text = (
            f"⚙️ *Ваши настройки*\n\n"
            f"📱 Телефон: `{phone_number}`\n"
            f"📅 Зарегистрирован: `{created_at}`\n"
            f"🔐 API-токен: {'✅ Сохранен' if user_data.get('api_token_encrypted') else '❌ Отсутствует'}\n\n"
            f"Используйте кнопки ниже для управления:"
        )

        await update.message.reply_text(
            text,
            reply_markup=get_settings_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

    async def update_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновление API-токена"""
        user = update.effective_user

        await update.message.reply_text(
            "🔑 *Обновление API-токена*\n\n"
            "Введите новый API-токен МойСклад:\n\n"
            "1. Зайдите в МойСклад → Настройки → Безопасность\n"
            "2. Создайте новый токен\n"
            "3. Вставьте его в чат\n\n"
            "Для отмены нажмите /cancel",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.MARKDOWN
        )

        context.user_data['waiting_for_token'] = True
        return 'WAITING_TOKEN'

    async def process_token_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нового токена"""
        user = update.effective_user
        api_token = update.message.text.strip()

        if len(api_token) < 20:
            await update.message.reply_text(
                "❌ Токен слишком короткий. Пожалуйста, введите валидный API-токен:"
            )
            return 'WAITING_TOKEN'

        try:
            encrypted_token = security.encrypt(api_token)
            success = self.db.update_user_token(user.id, encrypted_token)

            if success:
                await update.message.reply_text(
                    "✅ API-токен успешно обновлен!",
                    reply_markup=get_main_menu()
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка обновления токена. Попробуйте позже.",
                    reply_markup=get_main_menu()
                )

        except Exception as e:
            logger.error(f"Ошибка обновления токена: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже.",
                reply_markup=get_main_menu()
            )

        context.user_data.pop('waiting_for_token', None)
        return ConversationHandler.END


class MenuHandlers:
    """Обработчики меню"""

    def __init__(self, db: Database):
        self.db = db

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать главное меню"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        is_registered = user_data and user_data.get('api_token_encrypted')

        await update.message.reply_text(
            "📱 *Главное меню*\n\n"
            "Выберите нужный раздел:",
            reply_markup=get_main_menu(is_registered),  # ✅ ПРАВИЛЬНО
            parse_mode=ParseMode.MARKDOWN
        )

    async def show_reports_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать меню отчетов"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        is_registered = user_data and user_data.get('api_token_encrypted')

        if not is_registered:
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться и указать API-токен.\n"
                "Используйте /start для регистрации.",
                reply_markup=get_main_menu(False)  # ✅ ПРАВИЛЬНО
            )
            return

        await update.message.reply_text(
            "📊 *Отчеты*\n\n"
            "Выберите период для получения статистики:",
            reply_markup=get_report_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

    async def show_analytics_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать меню аналитики"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        is_registered = user_data and user_data.get('api_token_encrypted')

        if not is_registered:
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться и указать API-токен.\n"
                "Используйте /start для регистрации.",
                reply_markup=get_main_menu(False)  # ✅ ПРАВИЛЬНО
            )
            return

        await update.message.reply_text(
            "📈 *Аналитика*\n\n"
            "Сравнение периодов и детальная аналитика:",
            reply_markup=get_analytics_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопки Назад"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        is_registered = user_data and user_data.get('api_token_encrypted')

        await update.message.reply_text(
            "📱 *Главное меню*\n\n"
            "Выберите нужный раздел:",
            reply_markup=get_main_menu(is_registered),  # ✅ ПРАВИЛЬНО
            parse_mode=ParseMode.MARKDOWN
        )

    async def compare_today_yesterday(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сравнение сегодня vs вчера"""
        await self._compare_periods(update, context, 'today', 'yesterday')

    async def compare_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сравнение этой недели с прошлой"""
        await self._compare_periods(update, context, 'week', 'last_week')

    async def compare_month(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сравнение этого месяца с прошлым"""
        await self._compare_periods(update, context, 'month', 'last_month')

    async def compare_year_ago(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сравнение сегодняшнего дня с таким же днем год назад"""
        await self._compare_periods(update, context, 'today', 'year_ago')

    async def _compare_periods(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               current_period: str, previous_period: str):
        """Общий метод для сравнения периодов"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)

        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться и указать API-токен.",
                reply_markup=get_main_menu()
            )
            return

        # Получаем и расшифровываем токен
        encrypted_token = user_data['api_token_encrypted']
        api_token = security.decrypt(encrypted_token)

        if not api_token:
            await update.message.reply_text(
                "❌ Ошибка расшифровки токена. Обновите API-токен.",
                reply_markup=get_settings_keyboard()
            )
            return

        loading_msg = await update.message.reply_text("⏳ Сравниваем периоды...")

        try:
            api = MoyskladAPI(api_token)

            # Получаем отчеты за оба периода
            curr_from, curr_to = get_period_dates(current_period)
            prev_from, prev_to = get_period_dates(previous_period)

            current_report = api.get_sales_report(curr_from, curr_to)
            previous_report = api.get_sales_report(prev_from, prev_to)

            if current_report and previous_report:
                # Сравниваем отчеты
                comparison = AnalyticsCalculator.compare_reports(current_report, previous_report)

                await update.message.reply_text(
                    comparison,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_analytics_keyboard()
                )

                # Логируем запрос
                self.db.log_request(
                    user_data['id'],
                    f'compare_{current_period}_{previous_period}',
                    f"current: {curr_from}-{curr_to}, previous: {prev_from}-{prev_to}"
                )
            else:
                error_msg = "❌ Не удалось получить данные для сравнения.\n"
                if not current_report:
                    error_msg += f"- Нет данных за текущий период ({curr_from} - {curr_to})\n"
                if not previous_report:
                    error_msg += f"- Нет данных за предыдущий период ({prev_from} - {prev_to})\n"

                await update.message.reply_text(
                    error_msg,
                    reply_markup=get_analytics_keyboard()
                )

        except Exception as e:
            logger.error(f"Ошибка при сравнении периодов: {e}")
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)[:100]}",
                reply_markup=get_analytics_keyboard()
            )

        finally:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=loading_msg.message_id
                )
            except:
                pass

    async def ask_custom_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрос произвольного периода"""
        await update.message.reply_text(
            "🗓 *Произвольный период*\n\n"
            "Введите период в формате:\n"
            "`ДД.ММ.ГГГГ - ДД.ММ.ГГГГ`\n\n"
            "Пример: `01.01.2026 - 31.01.2026`\n\n"
            "Или введите одну дату для отчета за день: `01.01.2026`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_keyboard()
        )

        return 'WAITING_CUSTOM_PERIOD'

    async def process_custom_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка произвольного периода"""
        user_input = update.message.text.strip()

        try:
            if ' - ' in user_input:
                # Диапазон дат
                date1_str, date2_str = user_input.split(' - ')
                date1 = datetime.strptime(date1_str.strip(), '%d.%m.%Y')
                date2 = datetime.strptime(date2_str.strip(), '%d.%m.%Y')

                # Убедимся, что первая дата раньше второй
                if date1 > date2:
                    date1, date2 = date2, date1

                date_from = date1.strftime('%Y-%m-%d')
                date_to = date2.strftime('%Y-%m-%d')
                period_name = f"{date1_str} - {date2_str}"

            else:
                # Одна дата
                date = datetime.strptime(user_input.strip(), '%d.%m.%Y')
                date_from = date_to = date.strftime('%Y-%m-%d')
                period_name = user_input

            # Сохраняем период в context
            context.user_data['custom_period'] = {
                'date_from': date_from,
                'date_to': date_to,
                'period_name': period_name
            }

            # Запрашиваем отчет
            await self._get_custom_report(update, context)

            return ConversationHandler.END

        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты.\n"
                "Используйте формат: `ДД.ММ.ГГГГ - ДД.ММ.ГГГГ`\n"
                "Пример: `01.01.2024 - 31.01.2024`",
                parse_mode=ParseMode.MARKDOWN
            )
            return 'WAITING_CUSTOM_PERIOD'

    async def _get_custom_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение отчета за произвольный период"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)

        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться.",
                reply_markup=get_main_menu()
            )
            return

        period_data = context.user_data.get('custom_period', {})
        if not period_data:
            await update.message.reply_text(
                "❌ Ошибка: период не указан.",
                reply_markup=get_report_keyboard()
            )
            return

        encrypted_token = user_data['api_token_encrypted']
        api_token = security.decrypt(encrypted_token)

        if not api_token:
            await update.message.reply_text(
                "❌ Ошибка расшифровки токена.",
                reply_markup=get_settings_keyboard()
            )
            return

        loading_msg = await update.message.reply_text("⏳ Загружаем данные...")

        try:
            api = MoyskladAPI(api_token)
            report = api.get_sales_report(
                period_data['date_from'],
                period_data['date_to']
            )

            if report:
                # Переопределяем период для отображения
                report.period = period_data['period_name']
                report_text = report.format_report()

                await update.message.reply_text(
                    report_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_report_keyboard()
                )

                # Логируем запрос
                self.db.log_request(
                    user_data['id'],
                    'custom_period',
                    f"{period_data['date_from']} - {period_data['date_to']}"
                )
            else:
                await update.message.reply_text(
                    "❌ Нет данных за выбранный период.",
                    reply_markup=get_report_keyboard()
                )

        except Exception as e:
            logger.error(f"Ошибка при получении кастомного отчета: {e}")
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)[:100]}",
                reply_markup=get_report_keyboard()
            )

        finally:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=loading_msg.message_id
                )
            except:
                pass

    async def show_detailed_reports_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать меню детализированных отчетов"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)

        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться и указать API-токен.",
                reply_markup=get_main_menu()
            )
            return

        await update.message.reply_text(
            "📊 *Детализированные отчеты*\n\n"
            "Выберите тип отчета:",
            reply_markup=get_detailed_reports_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_retail_sales_report_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню выбора периода для розничных продаж"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)

        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться.",
                reply_markup=get_main_menu(False)
            )
            return

        # ✅ Сохраняем тип отчета в контексте
        context.user_data['current_report_type'] = 'retail_sales'
        logger.info(f"✅ Установлен тип отчета: retail_sales для пользователя {user.id}")

        await update.message.reply_text(
            "🛍 *Розничные продажи*\n\n"
            "Выберите период для отчета:",
            reply_markup=get_detailed_period_keyboard('retail_sales'),
            parse_mode=ParseMode.MARKDOWN
        )



    # ===== ЗАКАЗЫ ПОКУПАТЕЛЕЙ =====
    async def handle_customer_orders_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню выбора периода для заказов покупателей"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)

        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться.",
                reply_markup=get_main_menu(False)
            )
            return

        # ✅ Сохраняем тип отчета в контексте
        context.user_data['current_report_type'] = 'customer_orders'
        logger.info(f"✅ Установлен тип отчета: customer_orders для пользователя {user.id}")

        await update.message.reply_text(
            "📦 *Заказы покупателей*\n\n"
            "Выберите период для отчета:",
            reply_markup=get_detailed_period_keyboard('customer_orders'),
            parse_mode=ParseMode.MARKDOWN
        )

    # ===== ОБЪЕДИНЕННЫЙ ОТЧЕТ =====
    async def handle_combined_report_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню выбора периода для объединенного отчета"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)

        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться.",
                reply_markup=get_main_menu(False)
            )
            return

        # ✅ Сохраняем тип отчета в контексте
        context.user_data['current_report_type'] = 'combined_report'
        logger.info(f"✅ Установлен тип отчета: combined_report для пользователя {user.id}")

        await update.message.reply_text(
            "📊 *Объединенный отчет*\n\n"
            "Выберите период для отчета:",
            reply_markup=get_detailed_period_keyboard('combined_report'),
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_top_products_month(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отчет по товарам: топ-20 за текущий месяц"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)

        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться.",
                reply_markup=get_main_menu(False)
            )
            return

        encrypted_token = user_data['api_token_encrypted']
        api_token = security.decrypt(encrypted_token)

        if not api_token:
            await update.message.reply_text(
                "❌ Ошибка расшифровки токена. Обновите API-токен.",
                reply_markup=get_settings_keyboard()
            )
            return

        # Период – текущий месяц
        date_from, date_to = get_period_dates('month')

        loading_msg = await update.message.reply_text("⏳ Формируем отчет по товарам за месяц...")

        try:
            api = MoyskladAPI(api_token)
            top_items = api.get_top_products(date_from, date_to, limit=20)

            if not top_items:
                await update.message.reply_text(
                    "📭 Нет данных по продажам товаров за текущий месяц.",
                    reply_markup=get_detailed_reports_keyboard()
                )
                return

            # Формируем текст отчета
            from datetime import datetime
            month_title = datetime.now().strftime('%m.%Y')

            lines = [
                f"📊 *Топ-20 товаров за месяц ({month_title})*",
                "",
            ]

            for idx, item in enumerate(top_items, start=1):
                lines.append(
                    f"{idx}. *{item['name']}*\n"
                    f"   Кол-во: {item['quantity']:.2f}\n"
                    f"   Сумма: {item['amount']:,.2f} ₽"
                )

            text = "\n".join(lines)

            await update.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_detailed_reports_keyboard()
            )

            # Логируем запрос
            self.db.log_request(
                user_data['id'],
                'top_products_month',
                f"{date_from} - {date_to}"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка при формировании отчета по товарам: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка при формировании отчета: {str(e)[:120]}",
                reply_markup=get_detailed_reports_keyboard()
            )

        finally:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=loading_msg.message_id
                )
            except Exception:
                pass

    async def handle_detailed_custom_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Универсальный обработчик произвольного периода для детальных отчетов"""
        user_input = update.message.text.strip()

        # Проверяем, находимся ли мы в потоке детальных отчетов
        if not self._is_in_detailed_report_flow(context):
            # Если нет - это обычный ввод дат, показываем главное меню
            await self.show_main_menu(update, context)
            return

        # Получаем тип отчета из контекста
        report_type = context.user_data.get('detailed_report_type', 'customer_orders')

        # Если это кнопка "🗓 Произвольный период"
        if user_input == "🗓 Произвольный период":
            report_names = {
                'retail_sales': 'розничных продаж',
                'customer_orders': 'заказов покупателей',
                'combined_report': 'объединенного отчета'
            }

            report_name = report_names.get(report_type, 'отчета')

            await update.message.reply_text(
                f"🗓 *Произвольный период для {report_name}*\n\n"
                "Введите период в формате:\n"
                "`ДД.ММ.ГГГГ - ДД.ММ.ГГГГ`\n\n"
                "Пример: `01.01.2026 - 31.01.2026`\n\n"
                "Или введите одну дату для отчета за день: `01.01.2026`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_back_keyboard()
            )

            # Устанавливаем флаг ожидания ввода даты
            context.user_data['waiting_for_detailed_period'] = True
            return

        # Если это ввод даты (ожидаем после нажатия кнопки)
        elif context.user_data.get('waiting_for_detailed_period'):
            try:
                if ' - ' in user_input:
                    # Диапазон дат
                    date1_str, date2_str = user_input.split(' - ')
                    date1 = datetime.strptime(date1_str.strip(), '%d.%m.%Y')
                    date2 = datetime.strptime(date2_str.strip(), '%d.%m.%Y')

                    if date1 > date2:
                        date1, date2 = date2, date1

                    date_from = date1.strftime('%Y-%m-%d')
                    date_to = date2.strftime('%Y-%m-%d')
                    period_name = f"{date1_str} - {date2_str}"
                else:
                    # Одна дата
                    date = datetime.strptime(user_input.strip(), '%d.%m.%Y')
                    date_from = date_to = date.strftime('%Y-%m-%d')
                    period_name = user_input

                # Сохраняем период
                context.user_data['detailed_custom_period'] = {
                    'date_from': date_from,
                    'date_to': date_to,
                    'period_name': period_name
                }

                # Сбрасываем флаг
                context.user_data.pop('waiting_for_detailed_period', None)

                # ✅ ВАЖНО: Логируем какой отчет будет получен
                logger.info(f"Получение отчета типа '{report_type}' за период {date_from} - {date_to}")

                # Получаем отчет
                await self._get_detailed_report_by_type(update, context, report_type, 'custom')

            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат даты.\n"
                    "Используйте формат: `ДД.ММ.ГГГГ - ДД.ММ.ГГГГ`\n"
                    "Пример: `01.01.2026 - 31.01.2026`",
                    parse_mode=ParseMode.MARKDOWN
                )

        # Если это не дата и не кнопка - показываем меню детальных отчетов
        else:
            await self.show_detailed_reports_menu(update, context)

    async def _handle_date_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода дат для произвольного периода"""
        user_input = update.message.text.strip()

        # ✅ Проверяем, ожидаем ли мы ввод дат
        report_type = context.user_data.get('expecting_custom_period_for')

        if not report_type:
            # Если не ожидаем - это обычный ввод, показываем главное меню
            logger.info(f"📅 Ввод дат без ожидания: '{user_input}'")
            user = update.effective_user
            user_data = self.db.get_user(user.id)
            is_registered = user_data and user_data.get('api_token_encrypted')
            await update.message.reply_text(
                "📱 *Главное меню*\n\nВыберите нужный раздел:",
                reply_markup=get_main_menu(is_registered),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        logger.info(f"📅 Обработка дат '{user_input}' для отчета типа '{report_type}'")

        try:
            if ' - ' in user_input:
                # Диапазон дат
                date1_str, date2_str = user_input.split(' - ')
                date1 = datetime.strptime(date1_str.strip(), '%d.%m.%Y')
                date2 = datetime.strptime(date2_str.strip(), '%d.%m.%Y')

                if date1 > date2:
                    date1, date2 = date2, date1

                date_from = date1.strftime('%Y-%m-%d')
                date_to = date2.strftime('%Y-%m-%d')
                period_name = f"{date1_str} - {date2_str}"
            else:
                # Одна дата
                date = datetime.strptime(user_input.strip(), '%d.%m.%Y')
                date_from = date_to = date.strftime('%Y-%m-%d')
                period_name = user_input

            # ✅ Сохраняем период
            context.user_data['detailed_custom_period'] = {
                'date_from': date_from,
                'date_to': date_to,
                'period_name': period_name
            }

            logger.info(f"📊 Получение отчета типа '{report_type}' за период {date_from} - {date_to}")

            # ✅ Очищаем флаг ожидания
            context.user_data.pop('expecting_custom_period_for', None)

            # Получаем отчет
            await self._get_detailed_report_by_type(update, context, report_type, 'custom')

        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты.\n"
                "Используйте формат: `ДД.ММ.ГГГГ - ДД.ММ.ГГГГ`\n\n"
                "Попробуйте снова:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_back_keyboard()
            )


    # ===== ОБРАБОТКА ВЫБОРА ПЕРИОДА =====
    async def handle_detailed_period_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора периода для детальных отчетов"""
        user_input = update.message.text

        # ✅ Берем тип отчета из контекста
        report_type = context.user_data.get('current_report_type', 'customer_orders')
        logger.info(f"📝 Выбор периода '{user_input}' для отчета типа '{report_type}'")

        # Маппинг текста кнопок на типы периодов
        period_mapping = {
            '📅 Сегодня': 'today',
            '📆 Неделя': 'week',
            '📈 Месяц': 'month',
            '🗓 Произвольный период': 'custom'
        }

        period_type = period_mapping.get(user_input)

        if not period_type:
            await update.message.reply_text(
                "❌ Неизвестный период. Попробуйте снова.",
                reply_markup=get_detailed_period_keyboard(report_type)
            )
            return

        if period_type == 'custom':
            # ✅ Запрашиваем произвольный период для текущего типа отчета
            await self._ask_custom_period_for_report(update, context, report_type)
            return

        # Получаем отчет за выбранный период
        await self._get_detailed_report_by_type(update, context, report_type, period_type)

    async def _ask_custom_period_for_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE, report_type: str):
        """Запрос произвольного периода для указанного типа отчета"""
        report_names = {
            'retail_sales': 'розничных продаж',
            'customer_orders': 'заказов покупателей',
            'combined_report': 'объединенного отчета'
        }

        report_name = report_names.get(report_type, 'отчета')

        logger.info(f"🗓 Запрос произвольного периода для отчета '{report_type}'")

        await update.message.reply_text(
            f"🗓 *Произвольный период для {report_name}*\n\n"
            "Введите период в формате:\n"
            "`ДД.ММ.ГГГГ - ДД.ММ.ГГГГ`\n\n"
            "Пример: `01.01.2026 - 31.01.2026`\n\n"
            "Или введите одну дату для отчета за день: `01.01.2026`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_keyboard()
        )

        # ✅ Сохраняем тип отчета для обработки ввода дат
        context.user_data['expecting_custom_period_for'] = report_type
        logger.info(f"💾 Ожидаем ввод дат для отчета типа '{report_type}'")





    # async def ask_custom_period_for_detailed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     """Запрос произвольного периода для детальных отчетов"""
    #     report_type = context.user_data.get('report_type', 'customer_orders')
    #     report_names = {
    #         'retail_sales': 'розничных продаж',
    #         'customer_orders': 'заказов покупателей',
    #         'combined_report': 'объединенного отчета'
    #     }
    #
    #     report_name = report_names.get(report_type, 'отчета')
    #
    #     await update.message.reply_text(
    #         f"🗓 *Произвольный период для {report_name}*\n\n"
    #         "Введите период в формате:\n"
    #         "`ДД.ММ.ГГГГ - ДД.ММ.ГГГГ`\n\n"
    #         "Пример: `01.01.2024 - 31.01.2024`\n\n"
    #         "Или введите одну дату для отчета за день: `01.01.2024`",
    #         parse_mode=ParseMode.MARKDOWN,
    #         reply_markup=get_back_keyboard()
    #     )

    # def _is_in_detailed_report_flow(context: ContextTypes.DEFAULT_TYPE) -> bool:
    #     """Проверяем, находится ли пользователь в потоке детальных отчетов"""
    #     return (
    #             context.user_data.get('waiting_for_detailed_period') or
    #             context.user_data.get('detailed_report_type') is not None
    #     )

    async def process_detailed_custom_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка произвольного периода для детальных отчетов"""
        user_input = update.message.text.strip()

        # ✅ ВАЖНО: Берем тип отчета из нескольких мест
        report_type = (
                context.user_data.get('current_report_type') or
                context.user_data.get('waiting_custom_period_type') or
                context.user_data.get('detailed_report_type', 'customer_orders')
        )

        logger.info(f"📅 Обработка дат для отчета типа '{report_type}': '{user_input}'")

        try:
            if ' - ' in user_input:
                # Диапазон дат
                date1_str, date2_str = user_input.split(' - ')
                date1 = datetime.strptime(date1_str.strip(), '%d.%m.%Y')
                date2 = datetime.strptime(date2_str.strip(), '%d.%m.%Y')

                if date1 > date2:
                    date1, date2 = date2, date1

                date_from = date1.strftime('%Y-%m-%d')
                date_to = date2.strftime('%Y-%m-%d')
                period_name = f"{date1_str} - {date2_str}"
            else:
                # Одна дата
                date = datetime.strptime(user_input.strip(), '%d.%m.%Y')
                date_from = date_to = date.strftime('%Y-%m-%d')
                period_name = user_input

            # ✅ ВАЖНО: Сохраняем период с правильным ключом
            context.user_data['detailed_custom_period'] = {
                'date_from': date_from,
                'date_to': date_to,
                'period_name': period_name
            }

            logger.info(f"📊 Получение отчета типа '{report_type}' за период {date_from} - {date_to}")

            # Получаем отчет
            await self._get_detailed_report_by_type(update, context, report_type, 'custom')

            # Очищаем временные данные
            context.user_data.pop('current_report_type', None)
            context.user_data.pop('waiting_custom_period_type', None)

            return ConversationHandler.END

        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты.\n"
                "Используйте формат: `ДД.ММ.ГГГГ - ДД.ММ.ГГГГ`",
                parse_mode=ParseMode.MARKDOWN
            )
            return 'WAITING_DETAILED_CUSTOM_PERIOD'

    async def _get_detailed_report_by_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                           report_type: str, period_type: str):
        """Получение детального отчета по типу"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)

        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться.",
                reply_markup=get_main_menu(False)
            )
            return

        encrypted_token = user_data['api_token_encrypted']
        api_token = security.decrypt(encrypted_token)

        if not api_token:
            await update.message.reply_text(
                "❌ Ошибка расшифровки токена.",
                reply_markup=get_settings_keyboard()
            )
            return

        # Определяем даты периода
        if period_type == 'custom':
            period_data = context.user_data.get('detailed_custom_period', {})

            if not period_data:
                logger.error(f"❌ Нет данных периода для отчета типа '{report_type}'")
                await update.message.reply_text(
                    "❌ Ошибка: период не указан.",
                    reply_markup=get_detailed_period_keyboard(report_type)
                )
                return

            date_from = period_data['date_from']
            date_to = period_data['date_to']
            period_display = period_data['period_name']

            # ✅ Очищаем период после использования
            context.user_data.pop('detailed_custom_period', None)
        else:
            date_from, date_to = get_period_dates(period_type)
            period_display = period_type

        logger.info(f"📊 ЗАПРОС: report_type='{report_type}', period='{date_from} - {date_to}'")

        loading_msg = await update.message.reply_text("⏳ Загружаем данные...")

        try:
            api = MoyskladAPI(api_token)

            if report_type == 'retail_sales':
                # ✅ ВАЖНО: Используем правильный метод для розничных продаж
                logger.info(f"🛍 Вызов get_retail_sales_report()")
                report = api.get_retail_sales_report(date_from, date_to)

                if report:
                    report.period = period_display
                    report_text = report.format_retail_report()
                    logger.info(
                        f"✅ Получен отчет по розничным продажам: {report.total_orders} чеков, {report.total_sales:.2f} руб")
                else:
                    report_text = f"📭 Нет розничных продаж за период: {period_display}"
                    logger.info(f"📭 Нет данных по розничным продажам")

            elif report_type == 'customer_orders':
                logger.info(f"📦 Вызов get_sales_report()")
                report = api.get_sales_report(date_from, date_to)

                if report:
                    report.period = period_display
                    report_text = report.format_report()
                    logger.info(
                        f"✅ Получен отчет по заказам: {report.total_orders} заказов, {report.total_sales:.2f} руб")
                else:
                    report_text = f"📭 Нет заказов покупателей за период: {period_display}"
                    logger.info(f"📭 Нет данных по заказам")

            elif report_type == 'combined_report':
                logger.info(f"📊 Вызов get_combined_sales_report()")
                report = api.get_combined_sales_report(date_from, date_to)

                if report:
                    report.period = period_display
                    report_text = report.format_combined_report()
                    logger.info(f"✅ Получен объединенный отчет")
                else:
                    report_text = f"📭 Нет данных для объединенного отчета за период: {period_display}"
                    logger.info(f"📭 Нет данных для объединенного отчета")

            else:
                report_text = "❌ Неизвестный тип отчета"
                logger.error(f"❌ Неизвестный тип отчета: {report_type}")

            # Отправляем отчет
            await update.message.reply_text(
                report_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_detailed_period_keyboard(report_type)
            )

            # Логируем запрос
            self.db.log_request(
                user_data['id'],
                f'{report_type}_{period_type}',
                f"{date_from} - {date_to}"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка при получении отчета {report_type}: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка при получении отчета: {str(e)[:100]}",
                reply_markup=get_detailed_period_keyboard(report_type)
            )

        finally:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=loading_msg.message_id
                )
            except:
                pass

    async def back_to_detailed_reports(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат к меню детальных отчетов"""
        await self.show_detailed_reports_menu(update, context)


    def _generate_sales_diagram(self, retail_share: float, orders_share: float) -> str:
        """Генерация текстовой диаграммы распределения продаж"""
        bar_length = 20
        retail_bars = int((retail_share / 100) * bar_length)
        orders_bars = bar_length - retail_bars

        diagram = (
            f"🛍 Розничные: {'█' * retail_bars}{'░' * orders_bars} {retail_share:.1f}%\n"
            f"📦 Заказы:    {'░' * retail_bars}{'█' * orders_bars} {orders_share:.1f}%\n"
            f"              {'1' + ' ' * (bar_length - 2) + str(bar_length)}"
        )

        return diagram

    # добавляем метод для быстрого отчета
    async def handle_quick_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик быстрого отчета"""
        user = update.effective_user
        logger.info(f"📊 Запрос быстрого отчета от пользователя {user.id}")

        # Проверяем регистрацию
        user_data = self.db.get_user(user.id)
        is_registered = user_data and user_data.get('api_token_encrypted')

        if not is_registered:
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться.\n"
                "Используйте /start для регистрации.",
                reply_markup=get_main_menu(False)  # ✅ ПРАВИЛЬНО
            )
            return

        # Показываем сообщение о загрузке
        loading_msg = await update.message.reply_text("⏳ Формируем быстрый отчет...")

        try:
            # Получаем и расшифровываем токен
            encrypted_token = user_data['api_token_encrypted']
            api_token = security.decrypt(encrypted_token)

            if not api_token:
                await update.message.reply_text(
                    "❌ Ошибка расшифровки токена. Обновите API-токен в настройках.",
                    reply_markup=get_settings_keyboard()
                )
                return

            # Создаем API клиент и получаем отчет
            api = MoyskladAPI(api_token)
            quick_report = api.get_quick_report()

            if quick_report:
                # Форматируем и отправляем отчет
                report_text = quick_report.format_quick_report()

                await update.message.reply_text(
                    report_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_main_menu(True)
                )

                # Логируем успешный запрос
                self.db.log_request(user_data['id'], 'quick_report', 'today+week+month')
                logger.info(f"✅ Быстрый отчет отправлен пользователю {user.id}")

            else:
                await update.message.reply_text(
                    "❌ Не удалось получить данные для отчета.\n"
                    "Возможные причины:\n"
                    "• Нет данных в МойСклад за указанные периоды\n"
                    "• Проблемы с подключением к API\n"
                    "• Ошибка в настройках токена",
                    reply_markup=get_main_menu(False)
                )

        except Exception as e:
            logger.error(f"❌ Ошибка при получении быстрого отчета: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Произошла ошибка при формировании отчета:\n\n"
                f"```{str(e)[:150]}```",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_menu(False)
            )

        finally:
            # Удаляем сообщение о загрузке
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=loading_msg.message_id
                )
            except:
                pass


class NotificationHandlers:
    """Обработчики управления уведомлениями"""

    def __init__(self, db: Database):
        self.db = db

    async def notifications_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статус уведомлений и кнопки управления"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)

        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться и указать API-токен.\n"
                "Используйте /start для регистрации.",
                reply_markup=get_main_menu(False)
            )
            return

        # Получаем текущий статус уведомлений
        notification_enabled = user_data.get('notification_enabled', 0)
        is_enabled = bool(notification_enabled)

        # Формируем текст сообщения
        status_emoji = "✅" if is_enabled else "❌"
        status_text = "включены" if is_enabled else "выключены"
        
        message_text = (
            f"🔔 *Управление уведомлениями*\n\n"
            f"Статус: Уведомления {status_text} {status_emoji}\n\n"
        )
        
        if is_enabled:
            message_text += (
                "*Вы получаете автоматические отчеты:*\n"
                "• Ежедневно в 9:00 - статистика за вчера\n"
                "• Понедельник в 9:05 - статистика за неделю\n"
                "• 1 число месяца в 9:00 - отчет за месяц\n\n"
                "Используйте кнопку ниже для управления."
            )
        else:
            message_text += (
                "*При включении вы будете получать:*\n"
                "• Ежедневно в 9:00 - статистика за вчера\n"
                "• Понедельник в 9:05 - статистика за неделю\n"
                "• 1 число месяца в 9:00 - отчет за месяц\n\n"
                "Нажмите кнопку ниже, чтобы включить уведомления."
            )

        await update.message.reply_text(
            message_text,
            reply_markup=get_notifications_keyboard(is_enabled),
            parse_mode=ParseMode.MARKDOWN
        )

    async def toggle_notifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопок включения/выключения уведомлений"""
        user = update.effective_user
        button_text = update.message.text

        # Проверяем регистрацию
        user_data = self.db.get_user(user.id)
        if not user_data or not user_data.get('api_token_encrypted'):
            await update.message.reply_text(
                "❌ Сначала необходимо зарегистрироваться.",
                reply_markup=get_main_menu(False)
            )
            return

        # Определяем действие по тексту кнопки
        if button_text == "🔔 Включить уведомления":
            # Включаем уведомления
            success = self.db.update_notification_setting(user.id, True)
            
            if success:
                logger.info(f"✅ Уведомления включены для пользователя {user.id}")
                await update.message.reply_text(
                    "✅ *Уведомления включены!*\n\n"
                    "Вы будете получать автоматические отчеты:\n"
                    "• Ежедневно в 9:00 - статистика за вчера\n"
                    "• Понедельник в 9:05 - статистика за неделю\n"
                    "• 1 число месяца в 9:00 - отчет за месяц\n\n"
                    "_Время указано по московскому часовому поясу_",
                    reply_markup=get_notifications_keyboard(True),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка при включении уведомлений. Попробуйте позже.",
                    reply_markup=get_notifications_keyboard(False)
                )

        elif button_text == "🔕 Выключить уведомления":
            # Выключаем уведомления
            success = self.db.update_notification_setting(user.id, False)
            
            if success:
                logger.info(f"🔕 Уведомления выключены для пользователя {user.id}")
                await update.message.reply_text(
                    "🔕 *Уведомления выключены*\n\n"
                    "Вы больше не будете получать автоматические отчеты.\n"
                    "Вы всегда можете включить их снова через /notifications",
                    reply_markup=get_notifications_keyboard(False),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка при выключении уведомлений. Попробуйте позже.",
                    reply_markup=get_notifications_keyboard(True)
                )

        elif button_text == "◀️ Назад в меню":
            # Возврат в главное меню
            is_registered = user_data and user_data.get('api_token_encrypted')
            await update.message.reply_text(
                "📱 *Главное меню*\n\nВыберите нужный раздел:",
                reply_markup=get_main_menu(is_registered),
                parse_mode=ParseMode.MARKDOWN
            )