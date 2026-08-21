"""
suppliers/manager.py
Авто-закупка товаров у поставщиков при каждом заказе.

Приоритеты:
  Steam      → giftapi → dessly → ggsel → digiseller → manual
  Apple      → ggsel → digiseller → manual
  AI         → digiseller → manual
  Стриминг   → ggsel → digiseller → manual
  Готовые    → stock (склад) → manual
"""
import os
import logging
import aiohttp
import hashlib
import json
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("suppliers")


@dataclass
class DeliveryResult:
    success: bool
    data: str            # текст для клиента
    supplier: str
    order_ref: str = ""
    error: str = ""


# ══════════════════════════════════════════════════════════════════
# PRODUCT → SUPPLIER MAPPING
# ══════════════════════════════════════════════════════════════════
SUPPLIER_CHAIN = {
    # Готовые аккаунты — берём со склада
    "acc_cgp": ["stock", "manual"],
    "acc_clp": ["stock", "manual"],
    "acc_nf":  ["stock", "manual"],
    "acc_sp":  ["stock", "manual"],
    "acc_dc":  ["stock", "manual"],
    "acc_mj":  ["stock", "manual"],
    "acc_yt":  ["stock", "manual"],
    "acc_steam": ["stock", "manual"],
    "acc_one": ["stock", "manual"],
    # Steam Wallet → giftapi → dessly → digiseller
    "sw5":  ["giftapi", "dessly", "digiseller", "manual"],
    "sw10": ["giftapi", "dessly", "digiseller", "manual"],
    "sw1":  ["giftapi", "dessly", "digiseller", "manual"],
    # Xbox / PS
    "gp": ["giftapi", "digiseller", "manual"],
    "ps": ["giftapi", "digiseller", "manual"],
    # Apple
    "apus": ["ggsel", "digiseller", "manual"],
    "aptr": ["ggsel", "digiseller", "manual"],
    "icl":  ["ggsel", "digiseller", "manual"],
    "apm":  ["ggsel", "digiseller", "manual"],
    "aptv": ["ggsel", "digiseller", "manual"],
    # AI
    "cgp1": ["digiseller", "manual"],
    "cgp3": ["digiseller", "manual"],
    "clp":  ["digiseller", "manual"],
    "mjs":  ["digiseller", "manual"],
    "mjb":  ["digiseller", "manual"],
    "pplx": ["digiseller", "manual"],
    "cop":  ["digiseller", "manual"],
    "suno": ["digiseller", "manual"],
    "grk":  ["digiseller", "manual"],
    # Стриминг
    "sp":   ["ggsel", "digiseller", "manual"],
    "yt":   ["ggsel", "digiseller", "manual"],
    "nf":   ["digiseller", "manual"],
    "dc":   ["ggsel", "digiseller", "manual"],
    "cv":   ["digiseller", "manual"],
}

# Маппинг product_id → ID товара у поставщика (заполняется из env)
def load_product_map() -> dict:
    return {
        "digiseller": {
            "cgp1": os.getenv("DS_CHATGPT_1M", ""),
            "cgp3": os.getenv("DS_CHATGPT_3M", ""),
            "clp":  os.getenv("DS_CLAUDE_PRO", ""),
            "mjs":  os.getenv("DS_MJ_STD", ""),
            "mjb":  os.getenv("DS_MJ_BASIC", ""),
            "pplx": os.getenv("DS_PERPLEXITY", ""),
            "cop":  os.getenv("DS_COPILOT", ""),
            "suno": os.getenv("DS_SUNO", ""),
            "grk":  os.getenv("DS_GROK", ""),
            "apus": os.getenv("DS_APPLE_US", ""),
            "aptr": os.getenv("DS_APPLE_TR", ""),
            "sp":   os.getenv("DS_SPOTIFY", ""),
            "yt":   os.getenv("DS_YOUTUBE", ""),
            "nf":   os.getenv("DS_NETFLIX", ""),
            "dc":   os.getenv("DS_DISCORD", ""),
            "cv":   os.getenv("DS_CANVA", ""),
            "sw5":  os.getenv("DS_STEAM_500", ""),
            "sw10": os.getenv("DS_STEAM_1000", ""),
            "sw1":  os.getenv("DS_STEAM_100", ""),
            "gp":   os.getenv("DS_GAMEPASS", ""),
            "ps":   os.getenv("DS_PSPLUS", ""),
        },
        "ggsel": {
            "apus": os.getenv("GGSEL_APPLE_US", ""),
            "aptr": os.getenv("GGSEL_APPLE_TR", ""),
            "sw5":  os.getenv("GGSEL_STEAM_500", ""),
            "sw10": os.getenv("GGSEL_STEAM_1000", ""),
            "sw1":  os.getenv("GGSEL_STEAM_100", ""),
            "sp":   os.getenv("GGSEL_SPOTIFY", ""),
            "yt":   os.getenv("GGSEL_YOUTUBE", ""),
            "dc":   os.getenv("GGSEL_DISCORD", ""),
        },
        "giftapi": {
            "sw5":  os.getenv("GIFTAPI_STEAM_500", ""),
            "sw10": os.getenv("GIFTAPI_STEAM_1000", ""),
            "sw1":  os.getenv("GIFTAPI_STEAM_100", ""),
            "gp":   os.getenv("GIFTAPI_GAMEPASS", ""),
            "ps":   os.getenv("GIFTAPI_PSPLUS", ""),
        },
        "dessly": {
            "sw5":  os.getenv("DESSLY_STEAM_500", ""),
            "sw10": os.getenv("DESSLY_STEAM_1000", ""),
            "sw1":  os.getenv("DESSLY_STEAM_100", ""),
        },
    }


# ══════════════════════════════════════════════════════════════════
# DIGISELLER
# ══════════════════════════════════════════════════════════════════
async def buy_digiseller(product_id: str, order_id: int) -> DeliveryResult:
    seller_id = os.getenv("DIGISELLER_SELLER_ID", "")
    api_key   = os.getenv("DIGISELLER_API_KEY", "")
    pmap = load_product_map()["digiseller"]
    ds_id = pmap.get(product_id, "")

    if not seller_id or not api_key or not ds_id:
        return DeliveryResult(False, "", "digiseller",
                              error="Digiseller не настроен или нет ID товара")
    try:
        # Получаем токен
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        sign = hashlib.sha256(f"{api_key}{ts}".encode()).hexdigest()
        async with aiohttp.ClientSession() as s:
            r = await s.post("https://api.digiseller.com/api/apilogin", json={
                "seller_id": seller_id,
                "timestamp": ts,
                "sign": sign,
            }, timeout=aiohttp.ClientTimeout(total=15))
            auth = await r.json()

        token = auth.get("token", "")
        if not token:
            return DeliveryResult(False, "", "digiseller", error="Нет токена Digiseller")

        # Покупаем
        async with aiohttp.ClientSession() as s:
            r = await s.post(
                "https://api.digiseller.com/api/purchase/unique-code",
                headers={"Authorization": token},
                json={"product_id": ds_id, "count": 1, "comment": f"order_{order_id}"},
                timeout=aiohttp.ClientTimeout(total=20)
            )
            data = await r.json()

        if data.get("retval") != 0:
            return DeliveryResult(False, "", "digiseller",
                                  error=f"Digiseller: {data.get('retdesc','Ошибка')}")

        keys = data.get("content", {}).get("keys", [])
        key_text = "\n".join(f"<code>{k}</code>" for k in keys) if keys else str(data.get("content", ""))
        return DeliveryResult(
            success=True,
            data=f"🗝 <b>Данные для активации</b>\n\n{key_text}",
            supplier="digiseller",
            order_ref=str(data.get("inv", order_id)),
        )
    except Exception as e:
        log.error(f"Digiseller error: {e}")
        return DeliveryResult(False, "", "digiseller", error=str(e))


# ══════════════════════════════════════════════════════════════════
# GGSEL
# ══════════════════════════════════════════════════════════════════
async def buy_ggsel(product_id: str, order_id: int) -> DeliveryResult:
    api_key = os.getenv("GGSEL_API_KEY", "")
    pmap = load_product_map()["ggsel"]
    pid = pmap.get(product_id, "")
    if not api_key or not pid:
        return DeliveryResult(False, "", "ggsel", error="GGSel не настроен")
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.post(
                "https://ggsel.net/api/v1/orders",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"product_id": pid, "quantity": 1, "external_id": str(order_id)},
                timeout=aiohttp.ClientTimeout(total=20)
            )
            data = await r.json()
        if not data.get("success"):
            return DeliveryResult(False, "", "ggsel", error=data.get("message", "GGSel error"))
        keys = data.get("keys", [])
        key_text = "\n".join(f"<code>{k}</code>" for k in keys)
        return DeliveryResult(
            success=True,
            data=f"🗝 <b>Ключ активации</b>\n\n{key_text}",
            supplier="ggsel",
            order_ref=str(data.get("order_id", order_id)),
        )
    except Exception as e:
        log.error(f"GGSel error: {e}")
        return DeliveryResult(False, "", "ggsel", error=str(e))


# ══════════════════════════════════════════════════════════════════
# GIFTAPI
# ══════════════════════════════════════════════════════════════════
async def buy_giftapi(product_id: str, order_id: int) -> DeliveryResult:
    token = os.getenv("GIFTAPI_TOKEN", "")
    pmap = load_product_map()["giftapi"]
    pid = pmap.get(product_id, "")
    if not token or not pid:
        return DeliveryResult(False, "", "giftapi", error="GiftAPI не настроен")
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.post(
                "https://giftapi.ru/api/orders/",
                headers={"Authorization": f"Token {token}", "Content-Type": "application/json"},
                json={"product": pid, "quantity": 1, "external_id": str(order_id)},
                timeout=aiohttp.ClientTimeout(total=20)
            )
            data = await r.json()
        if data.get("error"):
            return DeliveryResult(False, "", "giftapi", error=data["error"])
        keys = data.get("keys", [])
        key_text = "\n".join(f"<code>{k.get('key','')}</code>" for k in keys)
        return DeliveryResult(
            success=True,
            data=f"🗝 <b>Ключ активации</b>\n\n{key_text}",
            supplier="giftapi",
            order_ref=str(data.get("id", order_id)),
        )
    except Exception as e:
        log.error(f"GiftAPI error: {e}")
        return DeliveryResult(False, "", "giftapi", error=str(e))


# ══════════════════════════════════════════════════════════════════
# DESSLY
# ══════════════════════════════════════════════════════════════════
async def buy_dessly(product_id: str, order_id: int) -> DeliveryResult:
    api_key = os.getenv("DESSLY_API_KEY", "")
    shop_id = os.getenv("DESSLY_SHOP_ID", "")
    pmap = load_product_map()["dessly"]
    pid = pmap.get(product_id, "")
    if not api_key or not pid:
        return DeliveryResult(False, "", "dessly", error="Dessly не настроен")
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.post(
                "https://api.dessly.com/v1/purchase",
                headers={"X-Api-Key": api_key},
                json={"product_id": pid, "shop_id": shop_id, "order_ref": str(order_id)},
                timeout=aiohttp.ClientTimeout(total=20)
            )
            data = await r.json()
        if data.get("status") != "ok":
            return DeliveryResult(False, "", "dessly", error=data.get("error", "Dessly error"))
        codes = data.get("codes", [])
        code_text = "\n".join(f"<code>{c}</code>" for c in codes)
        return DeliveryResult(
            success=True,
            data=f"🗝 <b>Код активации</b>\n\n{code_text}",
            supplier="dessly",
            order_ref=str(data.get("id", order_id)),
        )
    except Exception as e:
        log.error(f"Dessly error: {e}")
        return DeliveryResult(False, "", "dessly", error=str(e))


# ══════════════════════════════════════════════════════════════════
# СКЛАД (готовые аккаунты из БД)
# ══════════════════════════════════════════════════════════════════
async def buy_from_stock(product_id: str, order_id: int, db) -> DeliveryResult:
    try:
        async with db.pool.acquire() as conn:
            item = await conn.fetchrow(
                "SELECT id, data_encrypted FROM stock_items "
                "WHERE product_id=$1 AND NOT is_used "
                "ORDER BY added_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED",
                product_id
            )
            if not item:
                return DeliveryResult(False, "", "stock", error="Нет в наличии на складе")
            await conn.execute(
                "UPDATE stock_items SET is_used=TRUE, used_by_order=$1, used_at=NOW() WHERE id=$2",
                order_id, item['id']
            )
        from security import decrypt
        data = decrypt(item['data_encrypted'])
        return DeliveryResult(
            success=True,
            data=f"🔑 <b>Данные аккаунта</b>\n\n{data}",
            supplier="stock",
        )
    except Exception as e:
        log.error(f"Stock error: {e}")
        return DeliveryResult(False, "", "stock", error=str(e))


# ══════════════════════════════════════════════════════════════════
# РУЧНАЯ ВЫДАЧА
# ══════════════════════════════════════════════════════════════════
async def notify_manual(product_id: str, order_id: int, bot, admin_ids: list) -> DeliveryResult:
    """Уведомляет администраторов о ручной выдаче."""
    for aid in admin_ids:
        try:
            await bot.send_message(
                aid,
                f"⚠️ <b>Ручная выдача!</b>\n\n"
                f"Заказ #{order_id} · товар: <code>{product_id}</code>\n\n"
                f"Отправь данные командой:\n"
                f"<code>/give {order_id} данные здесь</code>"
            )
        except Exception:
            pass
    return DeliveryResult(
        success=True,
        data=(
            f"⏳ <b>Заказ #{order_id} принят!</b>\n\n"
            f"Обрабатываем вручную — данные придут в течение <b>15–30 минут</b>.\n\n"
            f"Если прошло больше часа — напишите в поддержку."
        ),
        supplier="manual",
    )


# ══════════════════════════════════════════════════════════════════
# МЕНЕДЖЕР — выбирает поставщика и закупает
# ══════════════════════════════════════════════════════════════════
async def deliver_product(
    product_id: str,
    order_id: int,
    db,
    bot=None,
    admin_ids: list = None,
) -> DeliveryResult:
    """
    Главная функция выдачи товара.
    Перебирает поставщиков по приоритету, при ошибке — следующий.
    """
    chain = SUPPLIER_CHAIN.get(product_id, ["manual"])
    last_error = "Нет поставщика"

    for supplier in chain:
        log.info(f"Trying supplier={supplier} for product={product_id} order={order_id}")
        try:
            if supplier == "stock":
                result = await buy_from_stock(product_id, order_id, db)
            elif supplier == "digiseller":
                result = await buy_digiseller(product_id, order_id)
            elif supplier == "ggsel":
                result = await buy_ggsel(product_id, order_id)
            elif supplier == "giftapi":
                result = await buy_giftapi(product_id, order_id)
            elif supplier == "dessly":
                result = await buy_dessly(product_id, order_id)
            elif supplier == "manual":
                result = await notify_manual(product_id, order_id, bot, admin_ids or [])
            else:
                continue

            if result.success:
                log.info(f"Delivered order={order_id} via {supplier}")
                return result

            last_error = result.error
            log.warning(f"Supplier {supplier} failed: {result.error}")

        except Exception as e:
            last_error = str(e)
            log.error(f"Supplier {supplier} exception: {e}")
            continue

    return DeliveryResult(False, "", "none", error=last_error)
