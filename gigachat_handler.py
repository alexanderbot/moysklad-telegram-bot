"""
GigaChat AI-ассистент для работы с данными МойСклад.

Реализует диалоговый режим: пользователь задаёт вопрос на русском языке,
GigaChat определяет нужную функцию, бот получает данные и возвращает ответ.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole, Function, FunctionParameters

from config import config, today_moscow
from moysklad_api import MoyskladAPI
from security import security

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Описание функций (инструментов) для GigaChat
# ──────────────────────────────────────────────────────────────────────────────

_PERIOD_PROP = {
    "type": "string",
    "description": (
        "Период отчёта: 'today' (сегодня), 'yesterday' (вчера), "
        "'week' (текущая неделя), 'month' (текущий месяц), "
        "'last_week' (прошлая неделя), 'last_month' (прошлый месяц)"
    ),
}

MOYSKLAD_FUNCTIONS = [
    Function(
        name="get_quick_report",
        description=(
            "Получить быстрый сводный отчёт по продажам за сегодня, текущую неделю и текущий месяц. "
            "Используй, когда пользователь спрашивает: 'как дела', 'сводку', 'итоги', "
            "'что за день', 'сколько продали сегодня/неделю/месяц'."
        ),
        parameters=FunctionParameters(type="object", properties={}, required=[]),
    ),
    Function(
        name="get_sales_report",
        description=(
            "Получить отчёт по заказам покупателей за указанный период. "
            "Используй, когда спрашивают о заказах, продажах, выручке за конкретный период."
        ),
        parameters=FunctionParameters(
            type="object",
            properties={"period": _PERIOD_PROP},
            required=["period"],
        ),
    ),
    Function(
        name="get_retail_report",
        description=(
            "Получить отчёт по розничным продажам (чеки, кассы) за указанный период. "
            "Используй для вопросов о розничных продажах, чеках, кассах."
        ),
        parameters=FunctionParameters(
            type="object",
            properties={"period": _PERIOD_PROP},
            required=["period"],
        ),
    ),
    Function(
        name="get_stock_report",
        description=(
            "Получить остатки товаров на складе. "
            "Используй для вопросов об остатках, запасах, наличии товара, что заканчивается."
        ),
        parameters=FunctionParameters(type="object", properties={}, required=[]),
    ),
    Function(
        name="get_top_products",
        description=(
            "Получить топ-10 самых продаваемых товаров за период. "
            "Используй для вопросов о популярных товарах, лидерах продаж, рейтинге товаров."
        ),
        parameters=FunctionParameters(
            type="object",
            properties={"period": _PERIOD_PROP},
            required=["period"],
        ),
    ),
    Function(
        name="get_demand_report",
        description=(
            "Получить отчёт по отгрузкам (доставкам) за указанный период. "
            "Используй для вопросов об отгрузках, доставках."
        ),
        parameters=FunctionParameters(
            type="object",
            properties={"period": _PERIOD_PROP},
            required=["period"],
        ),
    ),
]

SYSTEM_PROMPT = (
    "Ты — умный ИИ-ассистент для работы с данными торгового склада в системе МойСклад. "
    "Ты помогаешь владельцу бизнеса быстро получать нужные данные: продажи, остатки, заказы, топ товаров. "
    "Всегда отвечай кратко, по делу, на русском языке. "
    "Используй эмодзи для наглядности. "
    "Когда пользователь задаёт вопрос о данных склада — ВСЕГДА вызывай подходящую функцию. "
    "Не придумывай данные — только используй результаты функций. "
    "Если данных нет, честно скажи об этом."
)


def _period_to_dates(period: str) -> tuple[str, str]:
    """Преобразует строку периода в даты date_from, date_to."""
    today = today_moscow()

    if period == "today":
        return str(today), str(today)
    elif period == "yesterday":
        d = today - timedelta(days=1)
        return str(d), str(d)
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        return str(start), str(today)
    elif period == "last_week":
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return str(start), str(end)
    elif period == "month":
        start = today.replace(day=1)
        return str(start), str(today)
    elif period == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        start = last_prev.replace(day=1)
        return str(start), str(last_prev)
    else:
        return str(today), str(today)


async def _call_moysklad_function(func_name: str, args: dict, api: MoyskladAPI) -> str:
    """Вызывает нужный метод MoyskladAPI и возвращает результат в виде строки."""
    try:
        if func_name == "get_quick_report":
            report = await api.get_quick_report()
            if report is None:
                return "Не удалось получить данные из МойСклад."
            return report.format_quick_report()

        elif func_name == "get_sales_report":
            period = args.get("period", "today")
            date_from, date_to = _period_to_dates(period)
            report = await api.get_sales_report(date_from, date_to)
            if report is None:
                return "Не удалось получить данные о заказах."
            return (
                f"Заказы покупателей за период {date_from} — {date_to}:\n"
                f"• Количество заказов: {report.total_orders}\n"
                f"• Общая сумма: {report.total_sales:,.2f} ₽\n"
                f"• Средний чек: {report.average_order:,.2f} ₽\n"
                f"• Товаров в заказах: {report.products_count}"
            )

        elif func_name == "get_retail_report":
            period = args.get("period", "today")
            date_from, date_to = _period_to_dates(period)
            report = await api.get_retail_sales_report(date_from, date_to)
            if report is None:
                return "Не удалось получить данные о розничных продажах."
            return (
                f"Розничные продажи за период {date_from} — {date_to}:\n"
                f"• Количество чеков: {report.total_orders}\n"
                f"• Общая сумма: {report.total_sales:,.2f} ₽\n"
                f"• Средний чек: {report.average_order:,.2f} ₽\n"
                f"• Возвраты: {report.returns_count} шт на {report.returns_sum:,.2f} ₽"
            )

        elif func_name == "get_stock_report":
            data = await api.get_stock_report()
            if not data or "rows" not in data:
                return "Не удалось получить остатки со склада."
            rows = data["rows"]
            low_stock = [r for r in rows if r.get("stock", 0) <= 0]
            total = len(rows)
            lines = [f"Всего позиций на складе: {total}", f"Позиций с нулевым остатком: {len(low_stock)}"]
            if low_stock[:10]:
                lines.append("\nТовары с нулевым остатком (первые 10):")
                for item in low_stock[:10]:
                    lines.append(f"  • {item.get('name', '—')}: {item.get('stock', 0)} шт")
            return "\n".join(lines)

        elif func_name == "get_top_products":
            period = args.get("period", "month")
            date_from, date_to = _period_to_dates(period)
            products = await api.get_top_products(date_from, date_to, limit=10)
            if not products:
                return "Не удалось получить топ товаров."
            lines = [f"Топ-10 товаров за {date_from} — {date_to}:"]
            for i, p in enumerate(products[:10], 1):
                lines.append(
                    f"{i}. {p.get('name', '—')} — "
                    f"{p.get('quantity', 0):.0f} шт / {p.get('amount', 0):,.2f} ₽"
                )
            return "\n".join(lines)

        elif func_name == "get_demand_report":
            period = args.get("period", "today")
            date_from, date_to = _period_to_dates(period)
            report = await api.get_demand_report(date_from, date_to)
            if report is None:
                return "Не удалось получить данные об отгрузках."
            return (
                f"Отгрузки за период {date_from} — {date_to}:\n"
                f"• Количество отгрузок: {report.total_orders}\n"
                f"• Общая сумма: {report.total_sales:,.2f} ₽\n"
                f"• Средняя отгрузка: {report.average_order:,.2f} ₽"
            )

        else:
            return f"Неизвестная функция: {func_name}"

    except Exception as e:
        logger.error(f"Ошибка вызова функции {func_name}: {e}", exc_info=True)
        return f"Произошла ошибка при получении данных: {e}"


class GigaChatAssistant:
    """Управляет диалогом с GigaChat и вызовами МойСклад API."""

    def __init__(self):
        self._credentials = config.GIGACHAT_CREDENTIALS

    def is_configured(self) -> bool:
        return bool(self._credentials)

    async def ask(
        self,
        user_message: str,
        api_token: str,
        history: list[dict],
    ) -> tuple[str, list[dict]]:
        """
        Обрабатывает сообщение пользователя.

        Args:
            user_message: Текст вопроса от пользователя.
            api_token: Расшифрованный токен МойСклад пользователя.
            history: История диалога [{role, content}, ...] (макс. 10 сообщений).

        Returns:
            (ответ_строкой, обновлённая_история)
        """
        api = MoyskladAPI(api_token)
        try:
            messages = [Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT)]

            for msg in history[-10:]:
                role = MessagesRole.USER if msg["role"] == "user" else MessagesRole.ASSISTANT
                messages.append(Messages(role=role, content=msg["content"]))

            messages.append(Messages(role=MessagesRole.USER, content=user_message))

            with GigaChat(
                credentials=self._credentials,
                verify_ssl_certs=False,
                scope="GIGACHAT_API_PERS",
            ) as gc:
                payload = Chat(
                    messages=messages,
                    functions=MOYSKLAD_FUNCTIONS,
                    function_call="auto",
                    max_tokens=1500,
                )
                response = gc.chat(payload)

            choice = response.choices[0]
            finish_reason = choice.finish_reason

            if finish_reason == "function_call":
                func_call = choice.message.function_call
                func_name = func_call.name
                raw_args = func_call.arguments
                if isinstance(raw_args, dict):
                    func_args = raw_args
                elif isinstance(raw_args, str) and raw_args:
                    func_args = json.loads(raw_args)
                else:
                    func_args = {}

                logger.info(f"GigaChat вызывает функцию: {func_name}({func_args})")
                func_result = await _call_moysklad_function(func_name, func_args, api)

                func_result_json = json.dumps({"result": func_result}, ensure_ascii=False)

                messages.append(Messages(role=MessagesRole.ASSISTANT, content="", function_call=func_call))
                messages.append(Messages(role=MessagesRole.FUNCTION, content=func_result_json, name=func_name))

                with GigaChat(
                    credentials=self._credentials,
                    verify_ssl_certs=False,
                    scope="GIGACHAT_API_PERS",
                ) as gc:
                    final_payload = Chat(messages=messages, max_tokens=1500)
                    final_response = gc.chat(final_payload)

                answer = final_response.choices[0].message.content or "Не удалось сформировать ответ."
            else:
                answer = choice.message.content or "Не удалось получить ответ."

            new_history = history + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": answer},
            ]
            return answer, new_history[-20:]

        except Exception as e:
            logger.error(f"Ошибка GigaChat: {e}", exc_info=True)
            raise
        finally:
            await api.aclose()


gigachat_assistant = GigaChatAssistant()
