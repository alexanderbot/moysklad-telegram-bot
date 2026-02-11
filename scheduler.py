import logging
import asyncio
from datetime import datetime
from typing import Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from telegram.ext import Application
from telegram.constants import ParseMode

from database import Database
from moysklad_api import MoyskladAPI, get_period_dates
from security import security

logger = logging.getLogger(__name__)


class StatisticsScheduler:
    """Планировщик для автоматической отправки статистики пользователям"""

    def __init__(self, application: Application, db: Database, api_factory: Callable):
        """
        Инициализация планировщика
        
        Args:
            application: Telegram Application
            db: Экземпляр Database
            api_factory: Функция для создания MoyskladAPI (lambda token: MoyskladAPI(token))
        """
        self.application = application
        self.db = db
        self.api_factory = api_factory
        self.scheduler = AsyncIOScheduler(timezone='Europe/Moscow')
        
        logger.info("📅 Инициализация планировщика статистики")

    def start(self):
        """Запуск планировщика с настройкой всех задач"""
        logger.info("🚀 Запуск планировщика статистики...")
        
        # Ежедневная статистика за вчера в 9:00
        self.scheduler.add_job(
            self._send_daily_report,
            CronTrigger(hour=9, minute=0, timezone='Europe/Moscow'),
            id='daily_stats',
            name='Ежедневная статистика',
            replace_existing=True
        )
        logger.info("✅ Настроена ежедневная статистика (9:00)")
        
        # Недельная статистика по понедельникам в 9:05
        self.scheduler.add_job(
            self._send_weekly_report,
            CronTrigger(day_of_week='mon', hour=9, minute=5, timezone='Europe/Moscow'),
            id='weekly_stats',
            name='Недельная статистика',
            replace_existing=True
        )
        logger.info("✅ Настроена недельная статистика (понедельник 9:05)")
        
        # Месячная статистика 1 числа в 9:00
        self.scheduler.add_job(
            self._send_monthly_report,
            CronTrigger(day=1, hour=9, minute=1, timezone='Europe/Moscow'),
            id='monthly_stats',
            name='Месячная статистика',
            replace_existing=True
        )
        logger.info("✅ Настроена месячная статистика (1 число 9:00)")
        
        # Запускаем планировщик
        self.scheduler.start()
        logger.info("✅ Планировщик статистики запущен успешно")

    def stop(self):
        """Остановка планировщика"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("⏹ Планировщик остановлен")

    async def _send_daily_report(self):
        """Отправка ежедневного отчета за вчера"""
        logger.info("📊 Начало отправки ежедневных отчетов...")
        
        # Получаем даты за вчера
        date_from, date_to = get_period_dates('yesterday')
        period_name = f"вчера ({date_from})"
        
        await self._send_reports_to_users(
            period_type='yesterday',
            period_name=period_name,
            report_title=f"📊 Статистика за {period_name}"
        )

    async def _send_weekly_report(self):
        """Отправка недельного отчета за прошлую неделю"""
        logger.info("📊 Начало отправки недельных отчетов...")
        
        # Получаем даты за прошлую неделю
        date_from, date_to = get_period_dates('last_week')
        period_name = f"прошлую неделю ({date_from} - {date_to})"
        
        await self._send_reports_to_users(
            period_type='last_week',
            period_name=period_name,
            report_title=f"📊 Статистика за {period_name}"
        )

    async def _send_monthly_report(self):
        """Отправка месячного отчета за прошлый месяц"""
        logger.info("📊 Начало отправки месячных отчетов...")
        
        # Получаем даты за прошлый месяц
        date_from, date_to = get_period_dates('last_month')
        
        # Форматируем название месяца
        from datetime import datetime
        month_date = datetime.strptime(date_from, '%Y-%m-%d')
        month_name = month_date.strftime('%B %Y')
        period_name = f"{month_name}"
        
        await self._send_reports_to_users(
            period_type='last_month',
            period_name=period_name,
            report_title=f"📊 Отчет о продажах за {period_name}"
        )

    async def _send_reports_to_users(self, period_type: str, period_name: str, report_title: str):
        """
        Общий метод для отправки отчетов всем пользователям с включенными уведомлениями
        
        Args:
            period_type: Тип периода для get_period_dates()
            period_name: Название периода для отображения
            report_title: Заголовок отчета
        """
        try:
            # Получаем пользователей с включенными уведомлениями
            users = self.db.get_users_with_notifications()
            
            if not users:
                logger.info("ℹ️ Нет пользователей с включенными уведомлениями")
                return
            
            logger.info(f"📤 Отправка отчетов {len(users)} пользователям...")
            
            success_count = 0
            error_count = 0
            
            # Получаем даты периода
            date_from, date_to = get_period_dates(period_type)
            
            for user_id, encrypted_token in users:
                try:
                    # Расшифровываем токен
                    api_token = security.decrypt(encrypted_token)
                    
                    if not api_token:
                        logger.error(f"❌ Не удалось расшифровать токен для пользователя {user_id}")
                        error_count += 1
                        continue
                    
                    # Создаем API клиент
                    api = self.api_factory(api_token)
                    
                    # Получаем объединенный отчет
                    report = api.get_combined_sales_report(date_from, date_to)
                    
                    if not report:
                        logger.warning(f"⚠️ Нет данных для пользователя {user_id} за период {period_name}")
                        # Отправляем уведомление об отсутствии данных
                        message = (
                            f"{report_title}\n\n"
                            f"📭 Нет данных за этот период.\n"
                            f"Возможно, не было продаж или заказов."
                        )
                        await self.application.bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        success_count += 1
                        continue
                    
                    # Форматируем отчет
                    report_text = self._format_scheduled_report(report, period_name, report_title)
                    
                    # Отправляем отчет
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=report_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Логируем в базу
                    # Получаем user_id из БД по telegram_id
                    user_data = self.db.get_user(user_id)
                    if user_data:
                        self.db.log_request(
                            user_data['id'],
                            f'scheduled_{period_type}',
                            f"{date_from} - {date_to}"
                        )
                    
                    success_count += 1
                    logger.info(f"✅ Отчет отправлен пользователю {user_id}")
                    
                    # Небольшая задержка между отправками
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки отчета пользователю {user_id}: {e}", exc_info=True)
                    error_count += 1
            
            logger.info(f"📊 Отправка завершена: успешно={success_count}, ошибок={error_count}")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при отправке отчетов: {e}", exc_info=True)

    def _format_scheduled_report(self, report, period_name: str, report_title: str) -> str:
        """
        Форматирование отчета для автоматической рассылки
        
        Args:
            report: CombinedSalesReport
            period_name: Название периода
            report_title: Заголовок отчета
            
        Returns:
            Отформатированный текст отчета
        """
        return (
            f"{report_title}\n\n"
            f"💰 *ОБЩАЯ СУММА:* {report.combined_total:,.2f} ₽\n\n"
            
            f"🛍 *Розничные продажи:*\n"
            f"   Сумма: {report.retail.total_sales:,.2f} ₽ ({report.retail_share:.1f}%)\n"
            f"   Чеки: {report.retail.total_orders} шт\n"
            f"   Средний чек: {report.retail.average_order:,.2f} ₽\n"
            f"   Товаров: {report.retail.products_count} шт\n\n"
            
            f"📦 *Заказы покупателей:*\n"
            f"   Сумма: {report.orders.total_sales:,.2f} ₽ ({report.orders_share:.1f}%)\n"
            f"   Заказы: {report.orders.total_orders} шт\n"
            f"   Средний заказ: {report.orders.average_order:,.2f} ₽\n"
            f"   Товаров: {report.orders.products_count} шт\n\n"
            
            f"_Автоматическая рассылка. Управление: /notifications_"
        )
