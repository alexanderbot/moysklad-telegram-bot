import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import json

logger = logging.getLogger(__name__)


@dataclass
class MoyskladReport:
    """Класс для хранения данных отчета МойСклад"""
    period: str
    total_sales: float  # Общая сумма продаж
    total_orders: int  # Количество заказов
    average_order: float  # Средний чек
    products_count: int  # Количество проданных товаров
    details: List[Dict]  # Детали по заказам/товарам

    def to_dict(self) -> Dict:
        """Преобразование в словарь"""
        return {
            'period': self.period,
            'total_sales': self.total_sales,
            'total_orders': self.total_orders,
            'average_order': self.average_order,
            'products_count': self.products_count,
            'details': self.details
        }

    def format_report(self) -> str:
        """Форматирование отчета для Telegram"""
        return (
            f"📊 *Отчет за {self.period}*\n\n"
            f"💰 *Общая сумма продаж:* {self.total_sales:,.2f} ₽\n"
            f"📦 *Количество заказов:* {self.total_orders}\n"
            f"🧮 *Средний чек:* {self.average_order:,.2f} ₽\n"
            f"📈 *Товаров продано:* {self.products_count}\n"
        )

    def format_demand_report(self) -> str:
        """Форматирование отчета по отгрузкам для Telegram"""
        return (
            f"🚚 *Отгрузки за {self.period}*\n\n"
            f"💰 *Общая сумма:* {self.total_sales:,.2f} ₽\n"
            f"📦 *Количество отгрузок:* {self.total_orders}\n"
            f"🧮 *Средняя отгрузка:* {self.average_order:,.2f} ₽\n"
            f"📈 *Товаров отгружено:* {self.products_count}\n"
        )

@dataclass
class RetailSalesReport(MoyskladReport):
    """Отчет по розничным продажам с детализацией"""
    retail_points: List[Dict] = field(default_factory=list)  # Торговые точки
    cashiers: List[Dict] = field(default_factory=list)  # Кассиры
    returns_count: int = 0  # Количество возвратов
    returns_sum: float = 0.0  # Сумма возвратов

    def format_retail_report(self) -> str:
        """Форматирование отчета по розничным продажам"""
        net_sales = self.total_sales - self.returns_sum

        report = (
            f"🛍 *Розничные продажи за {self.period}*\n\n"
            f"💰 *Общая сумма продаж:* {self.total_sales:,.2f} ₽\n"
            f"📦 *Количество чеков:* {self.total_orders}\n"
            f"🧮 *Средний чек:* {self.average_order:,.2f} ₽\n"
            f"📊 *Товаров продано:* {self.products_count}\n"
        )

        if self.returns_sum > 0:
            report += (
                f"\n🔄 *Возвраты:*\n"
                f"   Количество: {self.returns_count}\n"
                f"   Сумма: {self.returns_sum:,.2f} ₽\n"
                f"   *Чистые продажи:* {net_sales:,.2f} ₽\n"
            )

        if self.retail_points:
            report += f"\n🏪 *Торговых точек:* {len(self.retail_points)}"

        if self.cashiers:
            report += f"\n👤 *Кассиров:* {len(self.cashiers)}"

        return report


@dataclass
class CombinedSalesReport:
    """Объединенный отчет: розничные продажи + заказы покупателей"""
    period: str
    retail: RetailSalesReport
    orders: MoyskladReport
    combined_total: float
    combined_orders: int
    retail_share: float  # Доля розничных продаж в %
    orders_share: float  # Доля заказов в %

    def format_combined_report(self) -> str:
        """Форматирование объединенного отчета"""
        return (
            f"📊 *СВОДНЫЙ ОТЧЕТ за {self.period}*\n\n"
            f"💰 *ОБЩАЯ СУММА:* {self.combined_total:,.2f} ₽\n\n"

            f"🛍 *Розничные продажи:*\n"
            f"   Сумма: {self.retail.total_sales:,.2f} ₽ ({self.retail_share:.1f}%)\n"
            f"   Чеки: {self.retail.total_orders} шт\n"
            f"   Средний чек: {self.retail.average_order:,.2f} ₽\n\n"

            f"📦 *Заказы покупателей:*\n"
            f"   Сумма: {self.orders.total_sales:,.2f} ₽ ({self.orders_share:.1f}%)\n"
            f"   Заказы: {self.orders.total_orders} шт\n"
            f"   Средний заказ: {self.orders.average_order:,.2f} ₽\n\n"

            f"📈 *Сравнение:*\n"
            f"   Всего операций: {self.combined_orders}\n"
            f"   Средний чек (общий): {self.combined_total / self.combined_orders:,.2f} ₽\n"
        )


@dataclass
class QuickReport:
    """Структура для быстрого отчета по трем периодам с итогами"""
    today_date: str
    week_period: str
    month_name: str
    today_data: Dict
    week_data: Dict
    month_data: Dict

    def format_quick_report(self) -> str:
        """Форматирование быстрого отчета в Telegram-сообщение"""
        # Рассчитываем итоговые суммы
        today_total = self.today_data['retail_sales'] + self.today_data['order_sales']
        week_total = self.week_data['retail_sales'] + self.week_data['order_sales']
        month_total = self.month_data['retail_sales'] + self.month_data['order_sales']

        # Рассчитываем проценты для каждого канала
        today_retail_percent = (self.today_data['retail_sales'] / today_total * 100) if today_total > 0 else 0
        today_orders_percent = (self.today_data['order_sales'] / today_total * 100) if today_total > 0 else 0

        week_retail_percent = (self.week_data['retail_sales'] / week_total * 100) if week_total > 0 else 0
        week_orders_percent = (self.week_data['order_sales'] / week_total * 100) if week_total > 0 else 0

        month_retail_percent = (self.month_data['retail_sales'] / month_total * 100) if month_total > 0 else 0
        month_orders_percent = (self.month_data['order_sales'] / month_total * 100) if month_total > 0 else 0

        report = f"📊 *БЫСТРЫЙ ОТЧЕТ за {self.month_name}*\n"
        report += "=" * 30 + "\n\n"

        # Сегодня
        report += f"*СЕГОДНЯ  ({self.today_date}):*\n\n"
        report += f"🛍 Розничные продажи: ({self.today_data.get('retail_count', '—')})\n {self.today_data['retail_sales']:,.2f} ₽  ({today_retail_percent:.1f}%)\n\n"
        report += f"📦 Заказы покупателей: {self.today_data['order_sales']:,.2f} ₽ ({today_orders_percent:.1f}%)\n"
        report += f"   Количество заказов: {self.today_data.get('order_count', '—')}\n"
        report += f"💰 *Итого за день:* {today_total:,.2f} ₽\n\n"

        # Неделя
        report += f"*НЕДЕЛЯ \n ({self.week_period}):*\n\n"
        report += f"🛍 Розничные продажи: {self.week_data.get('retail_count', '—')} \n   {self.week_data['retail_sales']:,.2f} ₽ ({week_retail_percent:.1f}%)\n\n"

        report += f"📦 Заказы покупателей: {self.week_data['order_sales']:,.2f} ₽ ({week_orders_percent:.1f}%)\n"
        report += f"   Количество заказов: {self.week_data.get('order_count', '—')}\n\n"
        report += f"💰 *Итого за неделю:* {week_total:,.2f} ₽\n\n\n"


        # Месяц
        report += f"*МЕСЯЦ ({self.month_name}):*\n\n"
        report += f"🛍 Розничные продажи: ({self.month_data.get('retail_count', '—')})\n Итого:{self.month_data['retail_sales']:,.2f} ₽ ({month_retail_percent:.1f}%)\n\n"
        report += f"📦 Заказы покупателей: ({self.month_data.get('order_count', '—')})\n {self.month_data['order_sales']:,.2f} ₽ ({month_orders_percent:.1f}%)\n"
        report += f"💰 *ИТОГО за месяц:*\n **{month_total:,.2f}** ₽\n\n"

        report += "Отличные показатели, так держать!"

        return report

class MoyskladAPI:
    """Класс для работы с API МойСклад"""

    BASE_URL = "https://api.moysklad.ru/api/remap/1.2"

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json"
        }
        # Кэш для наименований ассортимента, чтобы не дергать API по одному и тому же href
        self._assortment_cache: Dict[str, str] = {}

    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Выполнение запроса к API"""
        url = f"{self.BASE_URL}/{endpoint}"

        logger.info(f"🌐 Запрос к API: {endpoint}")
        logger.info(f"📋 Параметры запроса: {params}")

        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )

            logger.info(f"📡 Статус ответа: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Успешный ответ. Всего записей: {data.get('meta', {}).get('size', 'unknown')}")
                logger.info(f"📊 Возвращено записей: {len(data.get('rows', []))}")
                return data
            elif response.status_code == 401:
                logger.error(f"❌ Ошибка 401: Неверный API-токен")
                return None
            elif response.status_code == 400:
                logger.error(f"❌ Ошибка 400: Неверные параметры запроса")
                logger.error(f"📄 Ответ: {response.text[:500]}")
                return None
            else:
                logger.error(f"❌ Ошибка API: {response.status_code}")
                logger.error(f"📄 Ответ: {response.text[:500]}")
                return None

        except requests.exceptions.Timeout:
            logger.error("⏰ Таймаут при подключении к API МойСклад")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("🔌 Ошибка подключения к API МойСклад")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка запроса: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка: {e}")
            return None

    def get_sales_report(self, date_from: str, date_to: str) -> Optional[MoyskladReport]:
        """
        Оптимизированная версия - загружаем позиции одним запросом
        """
        logger.info(f"📊 Запрос отчета продаж с {date_from} по {date_to} (оптимизированная версия)")

        # ✅ ИСПРАВЛЕНО: Добавляем expand=positions чтобы получить позиции сразу
        params = {
            "filter": f"created>={date_from} 00:00:00;created<={date_to} 23:59:59",
            "limit": 1000,  # Максимум на один запрос в API
            "order": "created,desc",
            "expand": "positions"  # ✅ ЗАГРУЖАЕМ ПОЗИЦИИ ВМЕСТЕ С ЗАКАЗАМИ
        }

        logger.info(f"📋 Оптимизированные параметры запроса: expand=positions")

        # Получаем заказы покупателей (с пагинацией)
        endpoint = "entity/customerorder"
        logger.info(f"🌐 Запрос к эндпоинту: {endpoint}")

        orders: list[dict] = []
        offset = 0
        while True:
            params["offset"] = offset
            page_data = self._make_request(endpoint, params)

            if not page_data or "rows" not in page_data:
                if offset == 0:
                    logger.error("❌ Нет данных от API")
                    return None
                break

            rows = page_data.get("rows", [])
            orders.extend(rows)
            logger.info(f"✅ Получено заказов с позициями (накопительно): {len(orders)}")

            # Если вернулось меньше лимита — это последняя страница
            if len(rows) < params["limit"]:
                break

            offset += params["limit"]

            # Защита от бесконечного цикла
            if offset > 100000:
                logger.warning("⚠️ Достигнут защитный лимит 100000 заказов покупателей")
                break

        # Дополнительная фильтрация на нашей стороне (на всякий случай)
        filtered_orders = []
        for order in orders:
            created_date = order.get('created')
            if created_date:
                # Преобразуем дату из формата "2024-01-15 10:30:00"
                order_date = created_date[:10]  # Берем только YYYY-MM-DD
                if date_from <= order_date <= date_to:
                    filtered_orders.append(order)
                else:
                    logger.debug(f"Заказ {order.get('name')} с датой {order_date} вне периода")
            else:
                # Если нет даты создания, включаем в отчет
                filtered_orders.append(order)

        orders = filtered_orders
        logger.info(f"📅 После фильтрации по дате: {len(orders)} заказов")

        if len(orders) == 0:
            logger.warning(f"⚠️ Нет заказов за период {date_from} - {date_to}")
            # Возвращаем пустой отчет
            return MoyskladReport(
                period=f"{date_from} - {date_to}" if date_from != date_to else date_from,
                total_sales=0,
                total_orders=0,
                average_order=0,
                products_count=0,
                details=[]
            )

        total_sales = 0
        products_count = 0
        details = []

        logger.info(f"🔍 Обработка {len(orders)} заказов...")

        for order in orders:
            order_sum = order.get('sum', 0) / 100  # Сумма в копейках, переводим в рубли
            total_sales += order_sum

            # Получаем позиции заказа (опционально)
            order_id = order.get('id')
            order_name = order.get('name', f"Заказ {order_id[:8]}" if order_id else "Без номера")
            order_date = order.get('created', '')[:10] if order.get('created') else 'Неизвестно'

            # Логируем информацию о заказе для отладки
            logger.debug(f"Заказ: {order_name}, дата: {order_date}, сумма: {order_sum:.2f} ₽")

            # Получаем позиции заказа
            if order_id:
                positions = order.get('positions', {}).get('rows', [])
                if positions:
                    for pos in positions:
                        quantity = pos.get('quantity', 0)
                        products_count += quantity
                        logger.debug(
                            f"  Позиция: {pos.get('assortment', {}).get('name', 'Без названия')}, количество: {quantity}")

            # Добавляем детали заказа
            order_state = order.get('state', {}).get('name', 'Новый')

            details.append({
                'id': order_id,
                'name': order_name,
                'sum': order_sum,
                'created': order_date,
                'state': order_state
            })

        total_orders = len(orders)
        average_order = total_sales / total_orders if total_orders > 0 else 0

        logger.info(f"📈 Итоги: заказов={total_orders}, сумма={total_sales:.2f} ₽, товаров={int(products_count)}")

        # Формируем период для отчета
        period = f"{date_from} - {date_to}" if date_from != date_to else date_from

        return MoyskladReport(
            period=period,
            total_sales=total_sales,
            total_orders=total_orders,
            average_order=average_order,
            products_count=int(products_count),
            details=details[:10]  # Ограничиваем детали
        )

    def get_demand_report(self, date_from: str, date_to: str) -> Optional[MoyskladReport]:
        """
        Получение отчета по отгрузкам (реализация товаров и услуг) за период.
        Эндпоинт: entity/demand
        """
        logger.info(f"📊 Запрос отчета по отгрузкам с {date_from} по {date_to}")

        params = {
            "filter": f"moment>={date_from} 00:00:00;moment<={date_to} 23:59:59",
            "limit": 1000,  # Максимум на один запрос в API
            "order": "moment,desc",
            "expand": "positions"
        }

        endpoint = "entity/demand"
        # Пагинация по отгрузкам
        demands: list[dict] = []
        offset = 0
        while True:
            params["offset"] = offset
            page_data = self._make_request(endpoint, params)

            if not page_data or "rows" not in page_data:
                if offset == 0:
                    logger.error("❌ Нет данных по отгрузкам")
                    return None
                break

            rows = page_data.get("rows", [])
            demands.extend(rows)
            logger.info(f"✅ Получено отгрузок (накопительно): {len(demands)}")

            if len(rows) < params["limit"]:
                break

            offset += params["limit"]

            if offset > 100000:
                logger.warning("⚠️ Достигнут защитный лимит 100000 отгрузок")
                break

        if len(demands) == 0:
            return MoyskladReport(
                period=f"{date_from} - {date_to}" if date_from != date_to else date_from,
                total_sales=0,
                total_orders=0,
                average_order=0,
                products_count=0,
                details=[]
            )

        total_sales = 0
        products_count = 0
        details = []

        for demand in demands:
            demand_sum = demand.get('sum', 0) / 100
            total_sales += demand_sum

            demand_id = demand.get('id')
            demand_name = demand.get('name', f"Отгрузка {demand_id[:8]}" if demand_id else "Без номера")
            demand_date = demand.get('moment', '')[:10] if demand.get('moment') else 'Неизвестно'

            positions = demand.get('positions', {}).get('rows', [])
            for pos in positions:
                quantity = pos.get('quantity', 0)
                products_count += quantity

            demand_state = demand.get('state', {}).get('name', 'Новый')
            agent = demand.get('agent', {})
            agent_name = agent.get('name', '—') if agent else '—'

            details.append({
                'id': demand_id,
                'name': demand_name,
                'sum': demand_sum,
                'created': demand_date,
                'state': demand_state,
                'agent': agent_name
            })

        total_orders = len(demands)
        average_order = total_sales / total_orders if total_orders > 0 else 0
        period = f"{date_from} - {date_to}" if date_from != date_to else date_from

        logger.info(f"📈 Итоги отгрузок: {total_orders} шт, сумма={total_sales:.2f} ₽, товаров={int(products_count)}")

        return MoyskladReport(
            period=period,
            total_sales=total_sales,
            total_orders=total_orders,
            average_order=average_order,
            products_count=int(products_count),
            details=details[:10]
        )

    def get_detailed_sales_report(self, date_from: str, date_to: str) -> Optional[Dict]:
        """Получение детального отчета о продажах"""
        params = {
            "momentFrom": f"{date_from} 00:00:00",
            "momentTo": f"{date_to} 23:59:59"
        }

        # Используем отчет по продажам
        endpoint = "report/profit/byvariant"
        data = self._make_request(endpoint, params)

        return data

    def get_stock_report(self) -> Optional[Dict]:
        """Получение отчета по остаткам"""
        endpoint = "report/stock/all"
        data = self._make_request(endpoint)
        return data

    def validate_token(self) -> bool:
        """Проверка валидности API-токена"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/entity/counterparty",
                headers=self.headers,
                params={"limit": 1},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False

    def get_retail_sales_report(self, date_from: str, date_to: str) -> Optional[RetailSalesReport]:
        """
        Получение отчета по розничным продажам за период
        """
        logger.info(f"📊 Запрос отчета по розничным продажам с {date_from} по {date_to}")

        # Основные параметры для розничных продаж
        params = {
            "filter": f"moment>={date_from} 00:00:00;moment<={date_to} 23:59:59",
            "limit": 1000,  # Максимум на один запрос в API
            "order": "moment,desc",
            "expand": "positions,retailStore,retailShift"
        }

        endpoint = "entity/retaildemand"
        logger.info(f"🌐 Оптимизированный запрос: expand=positions,retailStore,retailShift")

        # 🔁 ПАГИНАЦИЯ: загружаем все страницы по 1000 записей
        retail_demands: list[dict] = []
        offset = 0
        while True:
            params["offset"] = offset
            page_data = self._make_request(endpoint, params)

            if not page_data or "rows" not in page_data:
                if offset == 0:
                    logger.error("❌ Нет данных по розничным продажам")
                    return None
                break

            rows = page_data.get("rows", [])
            retail_demands.extend(rows)
            logger.info(f"✅ Получено розничных продаж (накопительно): {len(retail_demands)}")

            # Если вернулось меньше лимита — это последняя страница
            if len(rows) < params["limit"]:
                break

            offset += params["limit"]

            # Защита от бесконечного цикла на случай странного ответа API
            if offset > 100000:
                logger.warning("⚠️ Достигнут защитный лимит 100000 записей по розничным продажам")
                break

        # Получаем возвраты ОТДЕЛЬНЫМ запросом с пагинацией
        returns_params = {
            "filter": f"moment>={date_from} 00:00:00;moment<={date_to} 23:59:59",
            "limit": 1000,
            "expand": "positions,retailStore"
        }

        returns: list[dict] = []
        offset = 0
        while True:
            returns_params["offset"] = offset
            returns_data = self._make_request("entity/retailsalesreturn", returns_params)

            if not returns_data or "rows" not in returns_data:
                break

            rows = returns_data.get("rows", [])
            returns.extend(rows)

            if len(rows) < returns_params["limit"]:
                break

            offset += returns_params["limit"]

            if offset > 100000:
                logger.warning("⚠️ Достигнут защитный лимит 100000 записей по возвратам розничных продаж")
                break

        logger.info(f"🔄 Найдено возвратов: {len(returns)}")

        # ===== ИСПРАВЛЕНИЕ НАЧИНАЕТСЯ ЗДЕСЬ =====

        # Обработка данных
        total_sales = 0
        returns_sum = 0
        retail_points = {}
        cashiers = {}
        products_count = 0
        details = []

        # 1. СНАЧАЛА обрабатываем ВСЕ розничные продажи
        logger.info(f"🔍 Обработка {len(retail_demands)} розничных продаж...")
        for demand in retail_demands:
            demand_sum = demand.get('sum', 0) / 100  # Переводим из копеек в рубли
            total_sales += demand_sum

            # Подсчет товаров из позиций (если они загружены)
            positions = demand.get('positions', {}).get('rows', [])
            for pos in positions:
                quantity = pos.get('quantity', 0)
                products_count += quantity

            # Информация о торговой точке
            store = demand.get('retailStore', {})
            store_name = store.get('name', 'Не указана')
            retail_points[store_name] = retail_points.get(store_name, 0) + demand_sum

            # Информация о кассире/смене
            cashier_info = {
                'name': demand.get('name', 'Без номера'),
                'store': store_name,
                'sum': demand_sum
            }

            shift = demand.get('retailShift', {})
            if shift:
                cashier_info['shift'] = shift.get('name', 'Без смены')

            cashiers[demand.get('id')] = cashier_info

            # Добавляем детали продажи
            details.append({
                'id': demand.get('id'),
                'name': demand.get('name', 'Без номера'),
                'sum': demand_sum,
                'date': demand.get('moment', '')[:10],
                'store': store_name,
                'type': 'Розничная продажа',
                'positions_count': len(positions)
            })

        # 2. ПОТОМ отдельно обрабатываем ВСЕ возвраты
        logger.info(f"🔍 Обработка {len(returns)} возвратов...")
        for return_item in returns:
            # Сумма возврата обычно отрицательная, берем по модулю
            return_sum = abs(return_item.get('sum', 0) / 100)
            returns_sum += return_sum

            # Получаем информацию о магазине возврата
            return_store = return_item.get('retailStore', {})
            return_store_name = return_store.get('name', 'Не указана')

            # Подсчет возвращенных товаров
            return_positions = return_item.get('positions', {}).get('rows', [])
            return_products_count = 0
            for pos in return_positions:
                quantity = pos.get('quantity', 0)
                return_products_count += quantity

            # Вычитаем возвращенные товары из общего количества
            products_count -= return_products_count

            # Обновляем статистику по торговой точке (вычитаем возвраты)
            if return_store_name in retail_points:
                retail_points[return_store_name] -= return_sum
            else:
                retail_points[return_store_name] = -return_sum

            # Добавляем детали возврата
            details.append({
                'id': return_item.get('id'),
                'name': return_item.get('name', 'Без номера'),
                'sum': -return_sum,  # Отрицательная сумма
                'date': return_item.get('moment', '')[:10],
                'store': return_store_name,
                'type': 'Возврат',
                'positions_count': len(return_positions)
            })

        # ===== ИСПРАВЛЕНИЕ ЗАКОНЧЕНО =====

        # Рассчитываем итоговые показатели
        total_orders = len(retail_demands) + len(returns)  # Все операции: продажи + возвраты
        net_sales = total_sales - returns_sum  # Чистые продажи

        if len(retail_demands) > 0:
            average_order = total_sales / len(retail_demands)  # Средний чек только по продажам
        else:
            average_order = 0

        # Форматируем торговые точки
        retail_points_list = []
        for store_name, store_sales in retail_points.items():
            # Игнорируем точки с нулевыми или отрицательными продажами (после вычета возвратов)
            if store_sales > 0:
                retail_points_list.append({
                    'name': store_name,
                    'sales': store_sales,
                    'share': (store_sales / net_sales * 100) if net_sales > 0 else 0
                })

        retail_points_list.sort(key=lambda x: x['sales'], reverse=True)

        # Формируем период
        period = f"{date_from} - {date_to}" if date_from != date_to else date_from

        logger.info(f"📈 Итоги: Продаж={len(retail_demands)}, "
                    f"Возвратов={len(returns)}, "
                    f"Чистые продажи={net_sales:.2f} руб, "
                    f"Товаров={int(products_count)}")

        return RetailSalesReport(
            period=period,
            total_sales=total_sales,  # Общая сумма продаж (без учета возвратов)
            total_orders=len(retail_demands),  # Только количество продаж
            average_order=average_order,
            products_count=int(max(products_count, 0)),  # Не может быть отрицательным
            details=details[:20],  # Ограничиваем детали
            retail_points=retail_points_list[:10],
            cashiers=list(cashiers.values())[:10],
            returns_count=len(returns),
            returns_sum=returns_sum
        )


    def get_combined_sales_report(self, date_from: str, date_to: str) -> Optional[CombinedSalesReport]:
        """
        Объединенный отчет: розничные продажи + заказы покупателей
        """
        logger.info(f"📊 Запрос объединенного отчета с {date_from} по {date_to}")

        # Получаем оба отчета
        retail_report = self.get_retail_sales_report(date_from, date_to)
        orders_report = self.get_sales_report(date_from, date_to)  # Существующий метод

        if not retail_report or not orders_report:
            logger.error("❌ Не удалось получить один из отчетов")
            return None

        # Рассчитываем общие показатели
        combined_total = retail_report.total_sales + orders_report.total_sales
        combined_orders = retail_report.total_orders + orders_report.total_orders

        # Рассчитываем доли
        retail_share = (retail_report.total_sales / combined_total * 100) if combined_total > 0 else 0
        orders_share = (orders_report.total_sales / combined_total * 100) if combined_total > 0 else 0

        period = f"{date_from} - {date_to}" if date_from != date_to else date_from

        return CombinedSalesReport(
            period=period,
            retail=retail_report,
            orders=orders_report,
            combined_total=combined_total,
            combined_orders=combined_orders,
            retail_share=retail_share,
            orders_share=orders_share
        )

    def get_top_products(self, date_from: str, date_to: str, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """
        Топ товаров по количеству и сумме продаж за период
        (заказы покупателей + розничные продажи).
        """
        logger.info(f"📊 Запрос топ-{limit} товаров с {date_from} по {date_to}")

        products: Dict[str, Dict[str, float]] = {}

        # ===== 1. Заказы покупателей =====
        orders_params = {
            "filter": f"created>={date_from} 00:00:00;created<={date_to} 23:59:59",
            "limit": 1000,
            "order": "created,desc"
        }
        orders_data = self._make_request("entity/customerorder", orders_params)

        if orders_data and 'rows' in orders_data:
            orders = orders_data['rows']
            logger.info(f"📦 Заказы покупателей для топа: {len(orders)}")

            # Собираем ID заказов, для которых нужно загрузить позиции
            order_ids = [o.get("id") for o in orders if o.get("id")]
            logger.info(f"📦 Будет загружено позиций для {len(order_ids)} заказов (ограниченная параллельность)")

            def load_order_positions(order_id: str) -> List[Dict[str, Any]]:
                """
                Загрузка позиций одного заказа.
                Используем expand=assortment, чтобы сразу получить имя товара и
                не делать дополнительные запросы в _get_assortment_name.
                """
                pos_data = self._make_request(
                    f"entity/customerorder/{order_id}/positions",
                    {"limit": 1000, "expand": "assortment"}
                )
                return pos_data.get("rows", []) if pos_data and "rows" in pos_data else []

            if order_ids:
                # Ограничиваем количество одновременных запросов, чтобы не ловить 429
                max_workers = min(3, len(order_ids))
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    for positions in executor.map(load_order_positions, order_ids):
                        for pos in positions:
                            assortment = pos.get("assortment", {}) or {}
                            name = self._get_assortment_name(assortment)
                            quantity = float(pos.get("quantity", 0) or 0)
                            price = (pos.get("price") or 0) / 100  # цена в рублях
                            amount = quantity * price

                            item = products.setdefault(name, {"quantity": 0.0, "amount": 0.0})
                            item["quantity"] += quantity
                            item["amount"] += amount

            logger.info(f"📦 Уникальных товаров из заказов: {len(products)}")
        else:
            logger.info("ℹ️ Нет заказов покупателей для топа товаров")

        # ===== 2. Розничные продажи =====
        retail_params = {
            "filter": f"moment>={date_from} 00:00:00;moment<={date_to} 23:59:59",
            "limit": 1000,
            "order": "moment,desc"
        }
        retail_data = self._make_request("entity/retaildemand", retail_params)

        if retail_data and 'rows' in retail_data:
            retail_demands = retail_data['rows']
            logger.info(f"🛍 Розничные продажи для топа: {len(retail_demands)}")

            # Собираем ID розничных продаж
            retail_ids = [d.get("id") for d in retail_demands if d.get("id")]
            logger.info(f"🛍 Будет загружено позиций для {len(retail_ids)} розничных продаж (ограниченная параллельность)")

            def load_retail_positions(demand_id: str) -> List[Dict[str, Any]]:
                """
                Загрузка позиций одной розничной продажи.
                Также используем expand=assortment для получения имени товара.
                """
                pos_data = self._make_request(
                    f"entity/retaildemand/{demand_id}/positions",
                    {"limit": 1000, "expand": "assortment"}
                )
                return pos_data.get("rows", []) if pos_data and "rows" in pos_data else []

            if retail_ids:
                # Ограничиваем количество одновременных запросов, чтобы не ловить 429
                max_workers = min(3, len(retail_ids))
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    for positions in executor.map(load_retail_positions, retail_ids):
                        for pos in positions:
                            assortment = pos.get("assortment", {}) or {}
                            name = self._get_assortment_name(assortment)
                            quantity = float(pos.get("quantity", 0) or 0)
                            price = (pos.get("price") or 0) / 100  # цена в рублях
                            amount = quantity * price

                            item = products.setdefault(name, {"quantity": 0.0, "amount": 0.0})
                            item["quantity"] += quantity
                            item["amount"] += amount

            logger.info(f"🛍 Уникальных товаров с учётом розницы: {len(products)}")
        else:
            logger.info("ℹ️ Нет розничных продаж для топа товаров")

        if not products:
            logger.warning("⚠️ Нет проданных товаров за период для формирования топа")
            return None

        logger.info(f"📦 Найдено уникальных товаров (все каналы): {len(products)}")

        # Сортируем по сумме продаж, затем по количеству
        sorted_items = sorted(
            products.items(),
            key=lambda kv: (kv[1]["amount"], kv[1]["quantity"]),
            reverse=True
        )

        top_items = [
            {
                "name": name,
                "quantity": round(stat["quantity"], 2),
                "amount": round(stat["amount"], 2),
            }
            for name, stat in sorted_items[:limit]
            if stat["quantity"] > 0
        ]

        logger.info(f"✅ Сформирован топ-{len(top_items)} товаров за период")
        return top_items

    def _get_assortment_name(self, assortment: Dict[str, Any]) -> str:
        """
        Получение названия товара/услуги по объекту assortment.
        Если в позиции нет поля name, делаем дополнительный запрос по meta.href и кэшируем результат.
        """
        # Если имя уже есть в объекте – сразу возвращаем
        name = assortment.get("name")
        if name:
            return name

        meta = assortment.get("meta") or {}
        href = meta.get("href")

        if not href:
            return "Без названия"

        # Проверяем кэш по href
        cached = self._assortment_cache.get(href)
        if cached:
            return cached

        try:
            logger.debug(f"🔍 Запрос наименование ассортимента по href: {href}")
            resp = requests.get(href, headers=self.headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("name") or "Без названия"
                self._assortment_cache[href] = name
                return name
            else:
                logger.warning(f"⚠️ Не удалось получить наименование ассортимента ({resp.status_code}) по href: {href}")
        except Exception as e:
            logger.error(f"❌ Ошибка при получении наименования ассортимента: {e}")

        return "Без названия"

    def get_quick_report(self) -> Optional[QuickReport]:
        """
        Оптимизированная версия быстрого отчета с параллельными запросами
        """
        logger.info("🚀 Формирование быстрого отчета (оптимизированная версия)...")

        # Получаем даты для всех периодов
        today_from, today_to = get_period_dates('today')
        week_from, week_to = get_period_dates('week')
        month_from, month_to = get_period_dates('month')

        # Форматируем даты для отображения
        from datetime import datetime
        today_date = datetime.now().strftime('%d.%m.%Y')
        week_period = f"{week_from} - {week_to}"
        month_name = datetime.now().strftime('%B %Y')

        try:
            # ✅ ОПТИМИЗАЦИЯ: Параллельные запросы для всех периодов
            with ThreadPoolExecutor(max_workers=3) as executor:
                # Запускаем все запросы параллельно
                future_today_retail = executor.submit(self.get_retail_sales_report, today_from, today_to)
                future_today_orders = executor.submit(self.get_sales_report, today_from, today_to)

                future_week_retail = executor.submit(self.get_retail_sales_report, week_from, week_to)
                future_week_orders = executor.submit(self.get_sales_report, week_from, week_to)

                future_month_retail = executor.submit(self.get_retail_sales_report, month_from, month_to)
                future_month_orders = executor.submit(self.get_sales_report, month_from, month_to)

                # Получаем результаты
                today_retail = future_today_retail.result()
                today_orders = future_today_orders.result()
                week_retail = future_week_retail.result()
                week_orders = future_week_orders.result()
                month_retail = future_month_retail.result()
                month_orders = future_month_orders.result()

            # Формируем отчет
            quick_report = QuickReport(
                today_date=today_date,
                week_period=week_period,
                month_name=month_name,
                today_data={
                    'retail_sales': today_retail.total_sales if today_retail else 0,
                    'retail_count': today_retail.total_orders if today_retail else 0,
                    'order_sales': today_orders.total_sales if today_orders else 0,
                    'order_count': today_orders.total_orders if today_orders else 0
                },
                week_data={
                    'retail_sales': week_retail.total_sales if week_retail else 0,
                    'retail_count': week_retail.total_orders if week_retail else 0,
                    'order_sales': week_orders.total_sales if week_orders else 0,
                    'order_count': week_orders.total_orders if week_orders else 0
                },
                month_data={
                    'retail_sales': month_retail.total_sales if month_retail else 0,
                    'retail_count': month_retail.total_orders if month_retail else 0,
                    'order_sales': month_orders.total_sales if month_orders else 0,
                    'order_count': month_orders.total_orders if month_orders else 0
                }
            )

            logger.info(f"✅ Быстрый отчет сформирован (параллельные запросы)")
            return quick_report

        except Exception as e:
            logger.error(f"❌ Ошибка формирования быстрого отчета: {e}", exc_info=True)
            return None



def get_period_dates(period_type: str) -> tuple:
    """
    Получение дат начала и конца периода

    Args:
        period_type: 'today', 'week', 'month', 'yesterday'

    Returns:
        tuple: (date_from, date_to) в формате 'YYYY-MM-DD'
    """
    today = datetime.now().date()

    if period_type == 'today':
        date_from = date_to = today.strftime('%Y-%m-%d')

    elif period_type == 'yesterday':
        yesterday = today - timedelta(days=1)
        date_from = date_to = yesterday.strftime('%Y-%m-%d')

    elif period_type == 'week':
        # Текущая неделя (понедельник - воскресенье)
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        date_from = start_of_week.strftime('%Y-%m-%d')
        date_to = end_of_week.strftime('%Y-%m-%d')

    elif period_type == 'month':
        # Текущий месяц
        date_from = today.replace(day=1).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')

    elif period_type == 'last_week':
        # Прошлая неделя
        today = datetime.now().date()
        start_of_last_week = today - timedelta(days=today.weekday() + 7)
        end_of_last_week = start_of_last_week + timedelta(days=6)
        date_from = start_of_last_week.strftime('%Y-%m-%d')
        date_to = end_of_last_week.strftime('%Y-%m-%d')

    elif period_type == 'last_month':
        # Прошлый месяц
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_month - timedelta(days=1)
        first_day_of_last_month = last_day_of_last_month.replace(day=1)
        date_from = first_day_of_last_month.strftime('%Y-%m-%d')
        date_to = last_day_of_last_month.strftime('%Y-%m-%d')

    elif period_type == 'year_ago':
        # Тот же день год назад (приближенно: минус 365 дней)
        year_ago = today - timedelta(days=365)
        date_from = date_to = year_ago.strftime('%Y-%m-%d')

    else:
        # По умолчанию сегодня
        date_from = date_to = today.strftime('%Y-%m-%d')

    return date_from, date_to


class AnalyticsCalculator:
    """Калькулятор для аналитики и сравнения периодов"""

    @staticmethod
    def calculate_growth(current: float, previous: float) -> Dict[str, Any]:
        """Расчет роста/падения показателей"""
        if previous == 0:
            return {
                'change': current,
                'percent': 100 if current > 0 else 0,
                'direction': 'up' if current > 0 else 'same'
            }

        change = current - previous
        percent = (change / abs(previous)) * 100

        return {
            'change': change,
            'percent': percent,
            'direction': 'up' if percent > 0 else 'down' if percent < 0 else 'same'
        }

    @staticmethod
    def compare_reports(current_report: MoyskladReport, previous_report: MoyskladReport) -> str:
        """Сравнение двух отчетов"""
        sales_growth = AnalyticsCalculator.calculate_growth(
            current_report.total_sales,
            previous_report.total_sales
        )

        orders_growth = AnalyticsCalculator.calculate_growth(
            current_report.total_orders,
            previous_report.total_orders
        )

        avg_order_growth = AnalyticsCalculator.calculate_growth(
            current_report.average_order,
            previous_report.average_order
        )

        products_growth = AnalyticsCalculator.calculate_growth(
            current_report.products_count,
            previous_report.products_count
        )

        # Форматируем результат
        result = (
            f"📊 *Сравнение периодов*\n\n"
            f"*Текущий период:* {current_report.period}\n"
            f"*Предыдущий период:* {previous_report.period}\n\n"

            f"💰 *Продажи:* {current_report.total_sales:,.2f} ₽\n"
            f"   Изменение: {sales_growth['change']:+,.2f} ₽ "
            f"({sales_growth['percent']:+.1f}%)\n\n"

            f"📦 *Заказы:* {current_report.total_orders}\n"
            f"   Изменение: {orders_growth['change']:+d} "
            f"({orders_growth['percent']:+.1f}%)\n\n"

            f"🧮 *Средний чек:* {current_report.average_order:,.2f} ₽\n"
            f"   Изменение: {avg_order_growth['change']:+,.2f} ₽ "
            f"({avg_order_growth['percent']:+.1f}%)\n\n"

            f"📈 *Товаров продано:* {current_report.products_count}\n"
            f"   Изменение: {products_growth['change']:+d} "
            f"({products_growth['percent']:+.1f}%)\n"
        )

        return result