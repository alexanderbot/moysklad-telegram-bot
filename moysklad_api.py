import asyncio
import httpx
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from config import today_moscow

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
    """Класс для работы с API МойСклад (асинхронный)"""

    BASE_URL = "https://api.moysklad.ru/api/remap/1.2"

    def __init__(self, api_token: str):
        self.api_token = api_token
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._assortment_cache: Dict[str, str] = {}

    async def aclose(self):
        """Закрытие HTTP-клиента"""
        await self._client.aclose()

    async def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Выполнение запроса к API"""
        url = f"{self.BASE_URL}/{endpoint}"

        logger.info(f"🌐 Запрос к API: {endpoint}")
        logger.info(f"📋 Параметры запроса: {params}")

        try:
            response = await self._client.get(url, params=params)

            logger.info(f"📡 Статус ответа: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Успешный ответ. Всего записей: {data.get('meta', {}).get('size', 'unknown')}")
                logger.info(f"📊 Возвращено записей: {len(data.get('rows', []))}")
                return data
            elif response.status_code == 401:
                logger.error("❌ Ошибка 401: Неверный API-токен")
                return None
            elif response.status_code == 400:
                logger.error("❌ Ошибка 400: Неверные параметры запроса")
                logger.error(f"📄 Ответ: {response.text[:500]}")
                return None
            else:
                logger.error(f"❌ Ошибка API: {response.status_code}")
                logger.error(f"📄 Ответ: {response.text[:500]}")
                return None

        except httpx.TimeoutException:
            logger.error("⏰ Таймаут при подключении к API МойСклад")
            return None
        except httpx.ConnectError:
            logger.error("🔌 Ошибка подключения к API МойСклад")
            return None
        except httpx.RequestError as e:
            logger.error(f"❌ Ошибка запроса: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка: {e}")
            return None

    async def get_sales_report(self, date_from: str, date_to: str) -> Optional[MoyskladReport]:
        """Получение отчета по заказам покупателей за период"""
        logger.info(f"📊 Запрос отчета продаж с {date_from} по {date_to}")

        params = {
            "filter": f"created>={date_from} 00:00:00;created<={date_to} 23:59:59",
            "limit": 1000,
            "order": "created,desc",
            "expand": "positions"
        }

        endpoint = "entity/customerorder"

        orders: list[dict] = []
        offset = 0
        while True:
            params["offset"] = offset
            page_data = await self._make_request(endpoint, params)

            if not page_data or "rows" not in page_data:
                if offset == 0:
                    logger.error("❌ Нет данных от API")
                    return None
                break

            rows = page_data.get("rows", [])
            orders.extend(rows)
            logger.info(f"✅ Получено заказов с позициями (накопительно): {len(orders)}")

            if len(rows) < params["limit"]:
                break

            offset += params["limit"]

            if offset > 100000:
                logger.warning("⚠️ Достигнут защитный лимит 100000 заказов покупателей")
                break

        filtered_orders = []
        for order in orders:
            created_date = order.get('created')
            if created_date:
                order_date = created_date[:10]
                if date_from <= order_date <= date_to:
                    filtered_orders.append(order)
                else:
                    logger.debug(f"Заказ {order.get('name')} с датой {order_date} вне периода")
            else:
                filtered_orders.append(order)

        orders = filtered_orders
        logger.info(f"📅 После фильтрации по дате: {len(orders)} заказов")

        if len(orders) == 0:
            logger.warning(f"⚠️ Нет заказов за период {date_from} - {date_to}")
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

        for order in orders:
            order_sum = order.get('sum', 0) / 100
            total_sales += order_sum

            order_id = order.get('id')
            order_name = order.get('name', f"Заказ {order_id[:8]}" if order_id else "Без номера")
            order_date = order.get('created', '')[:10] if order.get('created') else 'Неизвестно'

            if order_id:
                positions = order.get('positions', {}).get('rows', [])
                if positions:
                    for pos in positions:
                        quantity = pos.get('quantity', 0)
                        products_count += quantity

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

        period = f"{date_from} - {date_to}" if date_from != date_to else date_from

        return MoyskladReport(
            period=period,
            total_sales=total_sales,
            total_orders=total_orders,
            average_order=average_order,
            products_count=int(products_count),
            details=details[:10]
        )

    async def get_demand_report(self, date_from: str, date_to: str) -> Optional[MoyskladReport]:
        """Получение отчета по отгрузкам за период"""
        logger.info(f"📊 Запрос отчета по отгрузкам с {date_from} по {date_to}")

        params = {
            "filter": f"moment>={date_from} 00:00:00;moment<={date_to} 23:59:59",
            "limit": 1000,
            "order": "moment,desc",
            "expand": "positions"
        }

        endpoint = "entity/demand"
        demands: list[dict] = []
        offset = 0
        while True:
            params["offset"] = offset
            page_data = await self._make_request(endpoint, params)

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

    async def get_detailed_sales_report(self, date_from: str, date_to: str) -> Optional[Dict]:
        """Получение детального отчета о продажах"""
        params = {
            "momentFrom": f"{date_from} 00:00:00",
            "momentTo": f"{date_to} 23:59:59"
        }

        endpoint = "report/profit/byvariant"
        data = await self._make_request(endpoint, params)

        return data

    async def get_stock_report(self) -> Optional[Dict]:
        """Получение отчета по остаткам"""
        endpoint = "report/stock/all"
        data = await self._make_request(endpoint)
        return data

    async def validate_token(self) -> bool:
        """Проверка валидности API-токена"""
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/entity/counterparty",
                params={"limit": 1},
                timeout=10.0
            )
            return response.status_code == 200
        except Exception:
            return False

    async def get_retail_sales_report(self, date_from: str, date_to: str) -> Optional[RetailSalesReport]:
        """Получение отчета по розничным продажам за период"""
        logger.info(f"📊 Запрос отчета по розничным продажам с {date_from} по {date_to}")

        params = {
            "filter": f"moment>={date_from} 00:00:00;moment<={date_to} 23:59:59",
            "limit": 1000,
            "order": "moment,desc",
            "expand": "positions,retailStore,retailShift"
        }

        endpoint = "entity/retaildemand"

        retail_demands: list[dict] = []
        offset = 0
        while True:
            params["offset"] = offset
            page_data = await self._make_request(endpoint, params)

            if not page_data or "rows" not in page_data:
                if offset == 0:
                    logger.error("❌ Нет данных по розничным продажам")
                    return None
                break

            rows = page_data.get("rows", [])
            retail_demands.extend(rows)
            logger.info(f"✅ Получено розничных продаж (накопительно): {len(retail_demands)}")

            if len(rows) < params["limit"]:
                break

            offset += params["limit"]

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
            returns_data = await self._make_request("entity/retailsalesreturn", returns_params)

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

        total_sales = 0
        returns_sum = 0
        retail_points = {}
        cashiers = {}
        products_count = 0
        details = []

        logger.info(f"🔍 Обработка {len(retail_demands)} розничных продаж...")
        for demand in retail_demands:
            demand_sum = demand.get('sum', 0) / 100
            total_sales += demand_sum

            positions = demand.get('positions', {}).get('rows', [])
            for pos in positions:
                quantity = pos.get('quantity', 0)
                products_count += quantity

            store = demand.get('retailStore', {})
            store_name = store.get('name', 'Не указана')
            retail_points[store_name] = retail_points.get(store_name, 0) + demand_sum

            cashier_info = {
                'name': demand.get('name', 'Без номера'),
                'store': store_name,
                'sum': demand_sum
            }

            shift = demand.get('retailShift', {})
            if shift:
                cashier_info['shift'] = shift.get('name', 'Без смены')

            cashiers[demand.get('id')] = cashier_info

            details.append({
                'id': demand.get('id'),
                'name': demand.get('name', 'Без номера'),
                'sum': demand_sum,
                'date': demand.get('moment', '')[:10],
                'store': store_name,
                'type': 'Розничная продажа',
                'positions_count': len(positions)
            })

        logger.info(f"🔍 Обработка {len(returns)} возвратов...")
        for return_item in returns:
            return_sum = abs(return_item.get('sum', 0) / 100)
            returns_sum += return_sum

            return_store = return_item.get('retailStore', {})
            return_store_name = return_store.get('name', 'Не указана')

            return_positions = return_item.get('positions', {}).get('rows', [])
            return_products_count = 0
            for pos in return_positions:
                quantity = pos.get('quantity', 0)
                return_products_count += quantity

            products_count -= return_products_count

            if return_store_name in retail_points:
                retail_points[return_store_name] -= return_sum
            else:
                retail_points[return_store_name] = -return_sum

            details.append({
                'id': return_item.get('id'),
                'name': return_item.get('name', 'Без номера'),
                'sum': -return_sum,
                'date': return_item.get('moment', '')[:10],
                'store': return_store_name,
                'type': 'Возврат',
                'positions_count': len(return_positions)
            })

        total_orders = len(retail_demands) + len(returns)
        net_sales = total_sales - returns_sum

        if len(retail_demands) > 0:
            average_order = total_sales / len(retail_demands)
        else:
            average_order = 0

        retail_points_list = []
        for store_name, store_sales in retail_points.items():
            if store_sales > 0:
                retail_points_list.append({
                    'name': store_name,
                    'sales': store_sales,
                    'share': (store_sales / net_sales * 100) if net_sales > 0 else 0
                })

        retail_points_list.sort(key=lambda x: x['sales'], reverse=True)

        period = f"{date_from} - {date_to}" if date_from != date_to else date_from

        logger.info(f"📈 Итоги: Продаж={len(retail_demands)}, "
                    f"Возвратов={len(returns)}, "
                    f"Чистые продажи={net_sales:.2f} руб, "
                    f"Товаров={int(products_count)}")

        return RetailSalesReport(
            period=period,
            total_sales=total_sales,
            total_orders=len(retail_demands),
            average_order=average_order,
            products_count=int(max(products_count, 0)),
            details=details[:20],
            retail_points=retail_points_list[:10],
            cashiers=list(cashiers.values())[:10],
            returns_count=len(returns),
            returns_sum=returns_sum
        )


    async def get_combined_sales_report(self, date_from: str, date_to: str) -> Optional[CombinedSalesReport]:
        """Объединенный отчет: розничные продажи + заказы покупателей (параллельно)"""
        logger.info(f"📊 Запрос объединенного отчета с {date_from} по {date_to}")

        retail_report, orders_report = await asyncio.gather(
            self.get_retail_sales_report(date_from, date_to),
            self.get_sales_report(date_from, date_to),
        )

        if not retail_report or not orders_report:
            logger.error("❌ Не удалось получить один из отчетов")
            return None

        combined_total = retail_report.total_sales + orders_report.total_sales
        combined_orders = retail_report.total_orders + orders_report.total_orders

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

    async def get_top_products(self, date_from: str, date_to: str, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """Топ товаров по количеству и сумме продаж за период (заказы + розница)"""
        logger.info(f"📊 Запрос топ-{limit} товаров с {date_from} по {date_to}")

        products: Dict[str, Dict[str, float]] = {}
        semaphore = asyncio.Semaphore(3)

        async def _load_positions(endpoint: str) -> List[Dict[str, Any]]:
            async with semaphore:
                pos_data = await self._make_request(endpoint, {"limit": 1000, "expand": "assortment"})
                return pos_data.get("rows", []) if pos_data and "rows" in pos_data else []

        def _accumulate(positions_list: List[Dict[str, Any]]):
            for pos in positions_list:
                assortment = pos.get("assortment", {}) or {}
                name = assortment.get("name") or "Без названия"
                quantity = float(pos.get("quantity", 0) or 0)
                price = (pos.get("price") or 0) / 100
                amount = quantity * price
                item = products.setdefault(name, {"quantity": 0.0, "amount": 0.0})
                item["quantity"] += quantity
                item["amount"] += amount

        # ===== 1. Заказы покупателей =====
        orders_params = {
            "filter": f"created>={date_from} 00:00:00;created<={date_to} 23:59:59",
            "limit": 1000,
            "order": "created,desc"
        }
        orders_data = await self._make_request("entity/customerorder", orders_params)

        if orders_data and 'rows' in orders_data:
            orders = orders_data['rows']
            logger.info(f"📦 Заказы покупателей для топа: {len(orders)}")

            order_ids = [o.get("id") for o in orders if o.get("id")]

            if order_ids:
                all_positions = await asyncio.gather(
                    *[_load_positions(f"entity/customerorder/{oid}/positions") for oid in order_ids]
                )
                for positions in all_positions:
                    _accumulate(positions)

            logger.info(f"📦 Уникальных товаров из заказов: {len(products)}")
        else:
            logger.info("ℹ️ Нет заказов покупателей для топа товаров")

        # ===== 2. Розничные продажи =====
        retail_params = {
            "filter": f"moment>={date_from} 00:00:00;moment<={date_to} 23:59:59",
            "limit": 1000,
            "order": "moment,desc"
        }
        retail_data = await self._make_request("entity/retaildemand", retail_params)

        if retail_data and 'rows' in retail_data:
            retail_demands = retail_data['rows']
            logger.info(f"🛍 Розничные продажи для топа: {len(retail_demands)}")

            retail_ids = [d.get("id") for d in retail_demands if d.get("id")]

            if retail_ids:
                all_positions = await asyncio.gather(
                    *[_load_positions(f"entity/retaildemand/{did}/positions") for did in retail_ids]
                )
                for positions in all_positions:
                    _accumulate(positions)

            logger.info(f"🛍 Уникальных товаров с учётом розницы: {len(products)}")
        else:
            logger.info("ℹ️ Нет розничных продаж для топа товаров")

        if not products:
            logger.warning("⚠️ Нет проданных товаров за период для формирования топа")
            return None

        logger.info(f"📦 Найдено уникальных товаров (все каналы): {len(products)}")

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

    async def _get_assortment_name(self, assortment: Dict[str, Any]) -> str:
        """Получение названия товара/услуги по объекту assortment"""
        name = assortment.get("name")
        if name:
            return name

        meta = assortment.get("meta") or {}
        href = meta.get("href")

        if not href:
            return "Без названия"

        cached = self._assortment_cache.get(href)
        if cached:
            return cached

        try:
            logger.debug(f"🔍 Запрос наименования ассортимента по href: {href}")
            resp = await self._client.get(href, timeout=30.0)
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("name") or "Без названия"
                self._assortment_cache[href] = name
                return name
            else:
                logger.warning(f"⚠️ Не удалось получить наименование ассортимента ({resp.status_code})")
        except Exception as e:
            logger.error(f"❌ Ошибка при получении наименования ассортимента: {e}")

        return "Без названия"

    async def get_quick_report(self) -> Optional[QuickReport]:
        """Быстрый отчет с параллельными запросами"""
        logger.info("🚀 Формирование быстрого отчета...")

        today_from, today_to = get_period_dates('today')
        week_from, week_to = get_period_dates('week')
        month_from, month_to = get_period_dates('month')

        today_date = datetime.now().strftime('%d.%m.%Y')
        week_period = f"{week_from} - {week_to}"
        month_name = datetime.now().strftime('%B %Y')

        try:
            (
                today_retail, today_orders,
                week_retail, week_orders,
                month_retail, month_orders,
            ) = await asyncio.gather(
                self.get_retail_sales_report(today_from, today_to),
                self.get_sales_report(today_from, today_to),
                self.get_retail_sales_report(week_from, week_to),
                self.get_sales_report(week_from, week_to),
                self.get_retail_sales_report(month_from, month_to),
                self.get_sales_report(month_from, month_to),
            )

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

            logger.info("✅ Быстрый отчет сформирован")
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
    today = today_moscow()

    if period_type == 'today':
        date_from = date_to = today.strftime('%Y-%m-%d')

    elif period_type == 'yesterday':
        yesterday = today - timedelta(days=1)
        date_from = date_to = yesterday.strftime('%Y-%m-%d')

    elif period_type == 'week':
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        date_from = start_of_week.strftime('%Y-%m-%d')
        date_to = end_of_week.strftime('%Y-%m-%d')

    elif period_type == 'month':
        date_from = today.replace(day=1).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')

    elif period_type == 'last_week':
        start_of_last_week = today - timedelta(days=today.weekday() + 7)
        end_of_last_week = start_of_last_week + timedelta(days=6)
        date_from = start_of_last_week.strftime('%Y-%m-%d')
        date_to = end_of_last_week.strftime('%Y-%m-%d')

    elif period_type == 'last_month':
        first_day_of_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_month - timedelta(days=1)
        first_day_of_last_month = last_day_of_last_month.replace(day=1)
        date_from = first_day_of_last_month.strftime('%Y-%m-%d')
        date_to = last_day_of_last_month.strftime('%Y-%m-%d')

    elif period_type == 'year_ago':
        year_ago = today - timedelta(days=365)
        date_from = date_to = year_ago.strftime('%Y-%m-%d')

    else:
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
