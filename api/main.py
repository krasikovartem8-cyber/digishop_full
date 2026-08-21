"""
api/main.py
FastAPI бэкенд для сайта.
Сайт и бот используют одну PostgreSQL БД.

Endpoints:
  GET  /api/products         — каталог товаров
  GET  /api/products/{id}    — один товар + поля
  POST /api/orders           — создать заказ
  GET  /api/orders/{id}      — статус заказа
  POST /api/auth/tg          — авторизация через Telegram
  GET  /api/me               — профиль
  GET  /api/me/orders        — мои заказы
  POST /api/webhook/yookassa — вебхук оплаты
  POST /api/webhook/crypto   — вебхук CryptoBot
"""
import json
import os
import hmac
import hashlib
import logging
import asyncpg
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("api")

app = FastAPI(title="DigiShop API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # В продакшене заменить на домен
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── БД пул ───────────────────────────────────────────────────────
_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if not _pool:
        _pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL", "postgresql://digishop:DigiShopPass2026!@localhost:5432/digishop"),
            min_size=2, max_size=10
        )
    return _pool


async def get_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


# ── Auth ─────────────────────────────────────────────────────────
def verify_session(token: str, conn) -> int:
    """Проверяет токен сессии, возвращает user_id."""
    pass  # реализовано через Depends ниже

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: asyncpg.Connection = Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Не авторизован")
    token = authorization[7:]
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = await db.fetchrow(
        """SELECT u.* FROM web_sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.token_hash=$1 AND s.expires_at > NOW() AND NOT u.is_banned""",
        token_hash
    )
    if not row:
        raise HTTPException(401, "Сессия истекла")
    return dict(row)


# ═══════════════════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════════════════
@app.get("/api/products")
async def get_products(category: Optional[str] = None, db: asyncpg.Connection = Depends(get_db)):
    if category:
        rows = await db.fetch(
            "SELECT * FROM products WHERE is_active AND category=$1 ORDER BY sort_order",
            category
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM products WHERE is_active ORDER BY sort_order"
        )
    return [dict(r) for r in rows]


@app.get("/api/products/{product_id}")
async def get_product(product_id: str, db: asyncpg.Connection = Depends(get_db)):
    from delivery_fields import DELIVERY_FIELDS, PRODUCT_FIELDS_MAP
    row = await db.fetchrow("SELECT * FROM products WHERE id=$1 AND is_active", product_id)
    if not row:
        raise HTTPException(404, "Товар не найден")
    p = dict(row)
    schema_key = PRODUCT_FIELDS_MAP.get(product_id, "")
    p["delivery_fields"] = DELIVERY_FIELDS.get(schema_key, [])
    return p


# ═══════════════════════════════════════════════════════════════
# ORDERS
# ═══════════════════════════════════════════════════════════════
class CreateOrderRequest(BaseModel):
    product_id: str
    delivery_data: dict = {}
    payment_method: str = "card"


@app.post("/api/orders")
async def create_order(
    req: CreateOrderRequest,
    user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    from security.crypto import encrypt
    from security.validators import validate_product_id, ValidationError

    try:
        validate_product_id(req.product_id)
    except ValidationError as e:
        raise HTTPException(400, str(e))

    product = await db.fetchrow(
        "SELECT * FROM products WHERE id=$1 AND is_active", req.product_id
    )
    if not product:
        raise HTTPException(404, "Товар не найден")

    dd_enc = encrypt(json.dumps(req.delivery_data)) if req.delivery_data else None

    order_id = await db.fetchval(
        """INSERT INTO orders
           (user_id, product_id, product_name, price, delivery_data_encrypted, source)
           VALUES ($1,$2,$3,$4,$5,'web') RETURNING id""",
        user['id'], req.product_id, product['name'], product['price'], dd_enc
    )

    # Создать платёж
    pay_url = None
    external_id = None

    if req.payment_method == "card":
        yookassa_id = os.getenv("YOOKASSA_SHOP_ID", "")
        yookassa_sec = os.getenv("YOOKASSA_SECRET", "")
        if yookassa_id and yookassa_sec:
            import uuid
            import aiohttp
            async with aiohttp.ClientSession() as s:
                r = await s.post(
                    "https://api.yookassa.ru/v3/payments",
                    auth=aiohttp.BasicAuth(yookassa_id, yookassa_sec),
                    json={
                        "amount": {"value": f"{product['price']/100:.2f}", "currency": "RUB"},
                        "confirmation": {"type": "redirect", "return_url": os.getenv("SITE_URL","https://digishop.ru") + f"/order/{order_id}"},
                        "capture": True,
                        "description": f"DigiShop #{order_id} — {product['name']}",
                        "metadata": {"order_id": str(order_id), "user_id": str(user['id'])},
                    },
                    headers={"Idempotence-Key": str(uuid.uuid4()), "Content-Type": "application/json"},
                )
                pay_data = await r.json()
            pay_url = pay_data.get("confirmation", {}).get("confirmation_url")
            external_id = pay_data.get("id")

    elif req.payment_method == "crypto":
        token = os.getenv("CRYPTO_PAY_TOKEN", "")
        if token:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                r = await s.post(
                    "https://pay.crypt.bot/api/createInvoice",
                    headers={"Crypto-Pay-API-Token": token},
                    json={
                        "currency_type": "fiat",
                        "fiat": "RUB",
                        "accepted_assets": "USDT,TON,BTC,ETH",
                        "amount": str(product['price'] // 100),
                        "description": f"DigiShop заказ #{order_id}",
                        "payload": f"order:{order_id}:{user['id']}",
                        "expires_in": 3600,
                    }
                )
                pay_data = await r.json()
            if pay_data.get("ok"):
                pay_url = pay_data["result"]["bot_invoice_url"]
                external_id = str(pay_data["result"]["invoice_id"])

    if external_id:
        await db.execute(
            "INSERT INTO payments (order_id, user_id, method, amount, external_id) VALUES ($1,$2,$3,$4,$5)",
            order_id, user['id'], req.payment_method, product['price'], external_id
        )

    return {
        "order_id": order_id,
        "product_name": product['name'],
        "price": product['price'],
        "pay_url": pay_url,
        "payment_method": req.payment_method,
    }


@app.get("/api/orders/{order_id}")
async def get_order(
    order_id: int,
    user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    row = await db.fetchrow(
        "SELECT id, product_name, price, status, created_at, completed_at FROM orders WHERE id=$1 AND user_id=$2",
        order_id, user['id']
    )
    if not row:
        raise HTTPException(404, "Заказ не найден")
    return dict(row)


# ═══════════════════════════════════════════════════════════════
# AUTH — вход через Telegram
# ═══════════════════════════════════════════════════════════════
class TgAuthRequest(BaseModel):
    tg_id: int
    first_name: str
    last_name: Optional[str] = None
    code: str
    ref: Optional[str] = None


@app.post("/api/auth/tg")
async def auth_tg(req: TgAuthRequest, request: Request, db: asyncpg.Connection = Depends(get_db)):
    # Проверяем код
    code_hash = hashlib.sha256(req.code.encode()).hexdigest()
    row = await db.fetchrow(
        """SELECT id FROM auth_codes
           WHERE tg_id=$1 AND code_hash=$2 AND NOT used AND expires_at > NOW() AND attempts < 5
           FOR UPDATE""",
        req.tg_id, code_hash
    )
    if not row:
        await db.execute(
            "UPDATE auth_codes SET attempts=attempts+1 WHERE tg_id=$1 AND NOT used AND expires_at>NOW()",
            req.tg_id
        )
        raise HTTPException(400, "Неверный или истёкший код")

    await db.execute("UPDATE auth_codes SET used=TRUE WHERE id=$1", row['id'])

    # Получаем / создаём юзера
    user = await db.fetchrow("SELECT * FROM users WHERE tg_id=$1", req.tg_id)
    if not user:
        import secrets, string
        alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        ref_code = ''.join(secrets.choice(alphabet) for _ in range(8))
        referrer_id = None
        if req.ref:
            r2 = await db.fetchrow("SELECT id FROM users WHERE referral_code=$1", req.ref)
            if r2:
                referrer_id = r2['id']
        user_id = await db.fetchval(
            """INSERT INTO users (tg_id, first_name, last_name, referrer_id, referral_code, balance)
               VALUES ($1,$2,$3,$4,$5,10000) RETURNING id""",
            req.tg_id, req.first_name, req.last_name, referrer_id, ref_code
        )
        user = await db.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
    else:
        await db.execute(
            "UPDATE users SET first_name=$1, last_name=$2, last_seen_at=NOW() WHERE id=$3",
            req.first_name, req.last_name, user['id']
        )

    # Создаём сессию
    import secrets as sec
    token = sec.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")
    from datetime import timedelta
    expires = datetime.utcnow() + timedelta(days=30)
    await db.execute(
        "INSERT INTO web_sessions (user_id, token_hash, ip_address, user_agent, expires_at) VALUES ($1,$2,$3,$4,$5)",
        user['id'], token_hash, ip, ua, expires
    )

    return {"token": token, "user": dict(user)}


@app.post("/api/auth/request-code")
async def request_code(tg_id: int, db: asyncpg.Connection = Depends(get_db)):
    """Генерирует код и возвращает его — бот должен отправить этот код юзеру."""
    import secrets
    code = ''.join(secrets.choice('0123456789') for _ in range(6))
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    from datetime import timedelta
    expires = datetime.utcnow() + timedelta(minutes=10)
    await db.execute("DELETE FROM auth_codes WHERE tg_id=$1 OR expires_at < NOW()", tg_id)
    await db.execute(
        "INSERT INTO auth_codes (code_hash, tg_id, expires_at) VALUES ($1,$2,$3)",
        code_hash, tg_id, expires
    )
    # В продакшене здесь отправляем через бота
    return {"code": code, "expires_in": 600}


# ═══════════════════════════════════════════════════════════════
# PROFILE
# ═══════════════════════════════════════════════════════════════
@app.get("/api/me")
async def get_me(user: dict = Depends(get_current_user)):
    safe = {k: v for k, v in user.items()
            if k not in ('password_hash', 'phone_hash')}
    return safe


@app.get("/api/me/orders")
async def get_my_orders(
    user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    rows = await db.fetch(
        """SELECT id, product_id, product_name, price, status, created_at, completed_at
           FROM orders WHERE user_id=$1 ORDER BY created_at DESC LIMIT 50""",
        user['id']
    )
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
# WEBHOOKS
# ═══════════════════════════════════════════════════════════════
@app.post("/api/webhook/yookassa")
async def yookassa_webhook(request: Request, db: asyncpg.Connection = Depends(get_db)):
    body = await request.json()
    event = body.get("event", "")
    if event != "payment.succeeded":
        return {"ok": True}

    obj = body.get("object", {})
    payment_id = obj.get("id")
    metadata = obj.get("metadata", {})
    order_id = int(metadata.get("order_id", 0))
    user_id = int(metadata.get("user_id", 0))
    pay_type = metadata.get("type", "order")

    await db.execute(
        "UPDATE payments SET status='succeeded' WHERE external_id=$1",
        payment_id
    )

    if pay_type == "topup":
        amount = int(float(obj.get("amount", {}).get("value", 0)) * 100)
        await db.execute("UPDATE users SET balance=balance+$1 WHERE id=$2", amount, user_id)
    elif order_id:
        await db.execute(
            "UPDATE orders SET status='paid', paid_at=NOW() WHERE id=$1 AND status='pending'",
            order_id
        )
        # Запускаем выдачу
        order = await db.fetchrow("SELECT product_id FROM orders WHERE id=$1", order_id)
        if order:
            import asyncio
            asyncio.create_task(_deliver_async(order_id, order['product_id'], user_id, db))

    return {"ok": True}


@app.post("/api/webhook/crypto")
async def crypto_webhook(request: Request, db: asyncpg.Connection = Depends(get_db)):
    body = await request.json()
    if body.get("update_type") != "invoice_paid":
        return {"ok": True}
    payload = body.get("payload", {}).get("payload", "")
    parts = payload.split(":")
    if parts[0] == "order" and len(parts) >= 2:
        order_id = int(parts[1])
        order = await db.fetchrow("SELECT product_id, user_id FROM orders WHERE id=$1", order_id)
        if order:
            await db.execute(
                "UPDATE orders SET status='paid', paid_at=NOW() WHERE id=$1",
                order_id
            )
            import asyncio
            asyncio.create_task(_deliver_async(order_id, order['product_id'], order['user_id'], db))
    elif parts[0] == "topup" and len(parts) == 3:
        uid = int(parts[1])
        amount = int(parts[2])
        await db.execute("UPDATE users SET balance=balance+$1 WHERE id=$2", amount, uid)
    return {"ok": True}


async def _deliver_async(order_id: int, product_id: str, user_id: int, db):
    """Фоновая задача выдачи товара."""
    try:
        from suppliers.manager import deliver_product
        result = await deliver_product(product_id, order_id, db)
        if result.success:
            from security.crypto import encrypt
            await db.execute(
                """UPDATE orders SET status='completed', completed_at=NOW(),
                   result_data_encrypted=$1, supplier=$2, supplier_ref=$3
                   WHERE id=$4""",
                encrypt(result.data), result.supplier, result.order_ref, order_id
            )
    except Exception as e:
        log.error(f"Async deliver error: {e}")


# ═══════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════
@app.on_event("startup")
async def startup():
    await get_pool()
    log.info("DigiShop API started")


@app.on_event("shutdown")
async def shutdown():
    if _pool:
        await _pool.close()
