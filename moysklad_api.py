import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
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
        report += "=" * 40 + "\n\n"

        # Сегодня
        report += f"*Сегодня ({self.today_date}):*\n"
        report += f"🛍 Розничные продажи: {self.today_data['retail_sales']:,.2f} ₽ ({today_retail_percent:.1f}%)\n"
        report += f"   Количество продаж: {self.today_data.get('retail_count', '—')}\n"
        report += f"📦 Заказы покупателей: {self.today_data['order_sales']:,.2f} ₽ ({today_orders_percent:.1f}%)\n"
        report += f"   Количество заказов: {self.today_data.get('order_count', '—')}\n"
        report += f"💰 *Итого за день:* {today_total:,.2f} ₽\n\n"

        # Неделя
        report += f"*Текущая неделя ({self.week_period}):*\n"
        report += f"🛍 Розничные продажи: {self.week_data['retail_sales']:,.2f} ₽ ({week_retail_percent:.1f}%)\n"
        report += f"   Количество продаж: {self.week_data.get('retail_count', '—')}\n"
        report += f"📦 Заказы покупателей: {self.week_data['order_sales']:,.2f} ₽ ({week_orders_percent:.1f}%)\n"
        report += f"   Количество заказов: {self.week_data.get('order_count', '—')}\n"
        report += f"💰 *Итого за неделю:* {week_total:,.2f} ₽\n\n"

        # Месяц
        report += f"*Текущий месяц ({self.month_name}):*\n"
        report += f"🛍 Розничные продажи: {self.month_data['retail_sales']:,.2f} ₽ ({month_retail_percent:.1f}%)\n"
        report += f"   Количество продаж: {self.month_data.get('retail_count', '—')}\n"
        report += f"📦 Заказы покупателей: {self.month_data['order_sales']:,.2f} ₽ ({month_orders_percent:.1f}%)\n"
        report += f"   Количество заказов: {self.month_data.get('order_count', '—')}\n"
        report += f"💰 *Итого за месяц:* {month_total:,.2f} ₽\n\n"

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
        Получение отчета о продажах за период

        Args:
            date_from: Начальная дата в формате 'YYYY-MM-DD'
            date_to: Конечная дата в формате 'YYYY-MM-DD'
        """
        logger.info(f"📊 Запрос отчета продаж с {date_from} по {date_to}")

        # Параметры запроса - используем фильтр по created
        params = {
            "filter": f"created>={date_from} 00:00:00;created<={date_to} 23:59:59",
            "limit": 1000,
            "order": "created,desc"  # Сначала новые заказы
        }

        logger.info(f"📋 Параметры запроса: {params}")

        # Получаем заказы покупателей
        endpoint = "entity/customerorder"
        logger.info(f"🌐 Запрос к эндпоинту: {endpoint}")

        data = self._make_request(endpoint, params)

        if not data:
            logger.error("❌ Нет данных от API")
            return None

        if 'rows' not in data:
            logger.error(f"❌ Нет ключа 'rows' в ответе. Ответ: {json.dumps(data, ensure_ascii=False)[:200]}")
            return None

        orders = data['rows']
        logger.info(f"✅ Получено заказов: {len(orders)}")

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
                positions = self.get_order_positions(order_id)
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

    def get_order_positions(self, order_id: str) -> List[Dict]:
        """Получение позиций заказа"""
        if not order_id:
            return []

        endpoint = f"entity/customerorder/{order_id}/positions"
        data = self._make_request(endpoint)

        if data and 'rows' in data:
            return data['rows']
        return []

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
        Эндпоинт: entity/retaildemand
        """
        logger.info(f"📊 Запрос отчета по розничным продажам с {date_from} по {date_to}")

        # Основные параметры для розничных продаж
        params = {
            "filter": f"moment>={date_from} 00:00:00;moment<={date_to} 23:59:59",
            "limit": 1000,
            "order": "moment,desc",
            "expand": "retailStore,retailShift"  # Получаем информацию о точке и смене
        }

        endpoint = "entity/retaildemand"
        logger.info(f"🌐 Запрос розничных продаж: {endpoint}")

        data = self._make_request(endpoint, params)

        if not data or 'rows' not in data:
            logger.error("❌ Нет данных по розничным продажам")
            return None

        retail_demands = data['rows']
        logger.info(f"✅ Получено розничных продаж: {len(retail_demands)}")

        # Также получаем возвраты (retailsalesreturn)
        returns_params = {
            "filter": f"moment>={date_from} 00:00:00;moment<={date_to} 23:59:59",
            "limit": 1000
        }

        returns_data = self._make_request("entity/retailsalesreturn", returns_params)
        returns = returns_data.get('rows', []) if returns_data else []
        logger.info(f"🔄 Найдено возвратов: {len(returns)}")

        # Обработка данных
        total_sales = 0
        returns_sum = 0
        retail_points = {}
        cashiers = {}
        details = []

        # Обрабатываем розничные продажи
        for demand in retail_demands:
            demand_sum = demand.get('sum', 0) / 100
            total_sales += demand_sum

            # Информация о торговой точке
            store = demand.get('retailStore', {})
            store_name = store.get('name', 'Не указана')
            retail_points[store_name] = retail_points.get(store_name, 0) + demand_sum

            # Информация о кассире/смене
            shift = demand.get('retailShift', {})
            cashier_info = {
                'name': demand.get('name', 'Без номера'),
                'store': store_name,
                'sum': demand_sum
            }

            if shift:
                cashier_info['shift'] = shift.get('name', 'Без смены')

            cashiers[demand.get('id')] = cashier_info

            # Добавляем детали
            details.append({
                'id': demand.get('id'),
                'name': demand.get('name', 'Без номера'),
                'sum': demand_sum,
                'date': demand.get('moment', '')[:10],
                'store': store_name,
                'type': 'Розничная продажа'
            })

        # Обрабатываем возвраты
        for return_item in returns:
            return_sum = abs(return_item.get('sum', 0) / 100)  # Сумма возврата отрицательная
            returns_sum += return_sum

            details.append({
                'id': return_item.get('id'),
                'name': return_item.get('name', 'Без номера'),
                'sum': -return_sum,  # Отрицательная сумма
                'date': return_item.get('moment', '')[:10],
                'store': return_item.get('retailStore', {}).get('name', 'Не указана'),
                'type': 'Возврат'
            })

        # Подсчет товаров (упрощенно)
        products_count = 0
        for demand in retail_demands:
            positions = self.get_retail_positions(demand.get('id'))
            if positions:
                for pos in positions:
                    products_count += pos.get('quantity', 0)

        total_orders = len(retail_demands)
        average_order = total_sales / total_orders if total_orders > 0 else 0

        # Форматируем торговые точки для отчета
        retail_points_list = []
        for store_name, store_sales in retail_points.items():
            retail_points_list.append({
                'name': store_name,
                'sales': store_sales,
                'share': (store_sales / total_sales * 100) if total_sales > 0 else 0
            })

        # Сортируем точки по объему продаж
        retail_points_list.sort(key=lambda x: x['sales'], reverse=True)

        logger.info(f"📈 Розничные продажи: сумма={total_sales:.2f} ₽, чеков={total_orders}")

        period = f"{date_from} - {date_to}" if date_from != date_to else date_from

        return RetailSalesReport(
            period=period,
            total_sales=total_sales,
            total_orders=total_orders,
            average_order=average_order,
            products_count=products_count,
            details=details[:15],  # Ограничиваем детали
            retail_points=retail_points_list[:10],  # Топ-10 точек
            cashiers=list(cashiers.values())[:10],  # Топ-10 кассиров
            returns_count=len(returns),
            returns_sum=returns_sum
        )

    def get_retail_positions(self, retail_id: str) -> List[Dict]:
        """Получение позиций розничной продажи"""
        if not retail_id:
            return []

        endpoint = f"entity/retaildemand/{retail_id}/positions"
        data = self._make_request(endpoint)

        if data and 'rows' in data:
            return data['rows']
        return []

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

    def get_quick_report(self) -> Optional[QuickReport]:
        """
        Получение быстрого отчета за три периода:
        1. Сегодня
        2. Текущая неделя
        3. Текущий месяц
        """
        logger.info("🚀 Формирование быстрого отчета...")

        # Получаем даты для всех периодов
        today_from, today_to = get_period_dates('today')
        week_from, week_to = get_period_dates('week')
        month_from, month_to = get_period_dates('month')

        # Форматируем даты для отображения
        today_date = datetime.now().strftime('%d.%m.%Y')
        week_period = f"{week_from} - {week_to}"
        month_name = datetime.now().strftime('%B %Y')

        try:
            # Получаем данные для каждого периода
            # Сегодня
            today_retail = self.get_retail_sales_report(today_from, today_to)
            today_orders = self.get_sales_report(today_from, today_to)

            # Неделя
            week_retail = self.get_retail_sales_report(week_from, week_to)
            week_orders = self.get_sales_report(week_from, week_to)

            # Месяц
            month_retail = self.get_retail_sales_report(month_from, month_to)
            month_orders = self.get_sales_report(month_from, month_to)

            # Формируем структуру отчета с ВСЕМИ данными
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

            logger.info(f"✅ Быстрый отчет сформирован")
            return quick_report

        except Exception as e:
            logger.error(f"❌ Ошибка формирования быстрого отчета: {e}")
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