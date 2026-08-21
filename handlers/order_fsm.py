"""
handlers/order_fsm.py
FSM-диалог для сбора данных покупателя перед оплатой.

Флоу:
  купить товар → собрать поля → выбрать оплату → оплатить → выдать
"""
import json
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from delivery_fields import DELIVERY_FIELDS, PRODUCT_FIELDS_MAP

router_order = Router()
log = logging.getLogger("order_fsm")


class OrderStates(StatesGroup):
    collecting = State()   # собираем поля
    confirming = State()   # подтверждение перед оплатой


def fmt(kopecks: int) -> str:
    return f"{kopecks // 100} ₽"


# ── Начать оформление заказа ──────────────────────────────────────────
async def start_order(callback_or_msg, user: dict, db, state: FSMContext, product_id: str):
    """Точка входа — вызывается при нажатии 'Купить' или 'В корзину'."""
    product = await db.get_product(product_id)
    if not product:
        if isinstance(callback_or_msg, CallbackQuery):
            await callback_or_msg.answer("Товар не найден", show_alert=True)
        return

    schema_key = PRODUCT_FIELDS_MAP.get(product_id, "")
    fields = DELIVERY_FIELDS.get(schema_key, [])

    # Сохраняем в FSM
    await state.set_state(OrderStates.collecting)
    await state.update_data(
        product_id=product_id,
        product_name=product['name'],
        product_price=product['price'],
        fields=fields,
        field_index=0,
        collected={},
    )

    if not fields:
        # Нет полей — сразу к подтверждению
        await show_confirmation(callback_or_msg, user, product, {}, state)
        return

    # Первый вопрос
    await ask_field(callback_or_msg, fields[0], product)


async def ask_field(event, field: dict, product: dict):
    """Показать вопрос для одного поля."""
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отменить заказ", callback_data="order_cancel")

    text = (
        f"🛒 <b>Оформление: {product['name']}</b>\n"
        f"Цена: <b>{product['price']//100} ₽</b>\n\n"
        f"📝 <b>{field['label']}</b>\n\n"
        f"ℹ️ {field['hint']}\n\n"
        f"Введите ответ в чат:"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=b.as_markup())
        await event.answer()
    else:
        await event.answer(text, reply_markup=b.as_markup())


async def show_confirmation(event, user: dict, product: dict, collected: dict, state: FSMContext):
    """Показать итог перед оплатой."""
    await state.set_state(OrderStates.confirming)

    lines = [
        f"✅ <b>Подтвердите заказ</b>\n",
        f"📦 <b>{product['name']}</b> — {product['price']//100} ₽\n",
    ]

    if collected:
        lines.append("📋 <b>Ваши данные:</b>")
        schema_key = PRODUCT_FIELDS_MAP.get(product['id'], "")
        fields = DELIVERY_FIELDS.get(schema_key, [])
        for f in fields:
            val = collected.get(f['id'], '—')
            lines.append(f"• {f['label']}: <code>{val}</code>")
        lines.append("")

    lines.append("Всё верно? Нажмите «Оплатить» для продолжения.")

    b = InlineKeyboardBuilder()
    b.button(text=f"💳 Оплатить {product['price']//100} ₽", callback_data="order_pay")
    b.button(text="✏️ Изменить данные", callback_data="order_edit")
    b.button(text="❌ Отменить", callback_data="order_cancel")
    b.adjust(1)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text("\n".join(lines), reply_markup=b.as_markup())
    else:
        await event.answer("\n".join(lines), reply_markup=b.as_markup())


# ── Получить введённые данные ─────────────────────────────────────────
@router_order.message(OrderStates.collecting)
async def receive_field(msg: Message, user: dict, db, state: FSMContext):
    data = await state.get_data()
    fields: list = data['fields']
    idx: int = data['field_index']
    collected: dict = data['collected']
    product_id: str = data['product_id']
    product = await db.get_product(product_id)

    current_field = fields[idx]
    value = msg.text.strip() if msg.text else ""

    if not value:
        await msg.answer("⚠️ Пустой ответ — попробуйте ещё раз.")
        return

    # Простая валидация
    if current_field.get('validator') == 'email':
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            await msg.answer("⚠️ Неверный формат email. Попробуйте ещё раз.\nПример: example@gmail.com")
            return

    if current_field.get('validator') == 'steam_url':
        if 'steamcommunity.com' not in value:
            await msg.answer(
                "⚠️ Неверная ссылка Steam.\n"
                "Нужна ссылка вида: https://steamcommunity.com/id/yourname"
            )
            return

    # Сохраняем ответ
    collected[current_field['id']] = value
    next_idx = idx + 1

    if next_idx >= len(fields):
        # Все поля собраны
        await state.update_data(collected=collected, field_index=next_idx)
        await show_confirmation(msg, user, product, collected, state)
    else:
        # Следующее поле
        await state.update_data(collected=collected, field_index=next_idx)
        await ask_field(msg, fields[next_idx], product)


# ── Нажал "Оплатить" ─────────────────────────────────────────────────
@router_order.callback_query(OrderStates.confirming, F.data == "order_pay")
async def order_pay(cb: CallbackQuery, user: dict, db, state: FSMContext):
    data = await state.get_data()
    product_id = data['product_id']
    collected  = data.get('collected', {})

    try:
        order_id = await db.create_order(
            user_id=user['id'],
            product_id=product_id,
            delivery_data=collected,
            source='bot',
        )
    except Exception as e:
        await cb.answer(f"Ошибка: {e}", show_alert=True)
        return

    await state.clear()

    from keyboards import kb_pay_methods
    product = await db.get_product(product_id)
    await cb.message.edit_text(
        f"💳 <b>Оплата заказа #{order_id}</b>\n\n"
        f"{product['name']} — <b>{product['price']//100} ₽</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb_pay_methods(order_id)
    )
    await cb.answer()


# ── Редактировать данные ──────────────────────────────────────────────
@router_order.callback_query(OrderStates.confirming, F.data == "order_edit")
async def order_edit(cb: CallbackQuery, db, state: FSMContext):
    data = await state.get_data()
    product = await db.get_product(data['product_id'])
    fields = data['fields']

    if not fields:
        await cb.answer("Нет полей для редактирования")
        return

    # Сбрасываем и начинаем заново
    await state.update_data(field_index=0, collected={})
    await state.set_state(OrderStates.collecting)
    await ask_field(cb, fields[0], product)


# ── Отменить заказ ────────────────────────────────────────────────────
@router_order.callback_query(F.data == "order_cancel")
async def order_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    from keyboards import kb_main
    await cb.message.edit_text(
        "❌ <b>Заказ отменён</b>\n\nВозвращаемся в главное меню.",
        reply_markup=kb_main()
    )
    await cb.answer()


# ── Кнопки "Купить" в каталоге ────────────────────────────────────────
@router_order.callback_query(F.data.startswith("buy:"))
async def cb_buy(cb: CallbackQuery, user: dict, db, state: FSMContext):
    product_id = cb.data.split(":")[1]
    await start_order(cb, user, db, state, product_id)


@router_order.callback_query(F.data.startswith("add:"))
async def cb_add(cb: CallbackQuery, user: dict, db, state: FSMContext):
    """'В корзину' — тоже сразу собираем данные."""
    product_id = cb.data.split(":")[1]
    await start_order(cb, user, db, state, product_id)
