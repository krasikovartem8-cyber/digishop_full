"""
delivery_fields.py — схема полей для каждого товара.
Определяет что нужно собрать у покупателя перед выдачей.
"""

# Поля: id, label, hint, placeholder, type, validator
DELIVERY_FIELDS = {

    # ── Steam Wallet ── профиль Steam
    "steam_wallet": [
        {
            "id": "steam_url",
            "label": "Ссылка на профиль Steam",
            "hint": (
                "Как найти:\n"
                "1. Откройте Steam → ваш профиль\n"
                "2. Нажмите «Редактировать профиль» → скопируйте URL\n"
                "Пример: https://steamcommunity.com/id/yourname"
            ),
            "placeholder": "https://steamcommunity.com/id/yourname",
            "type": "text",
            "validator": "steam_url",
        }
    ],

    # ── Apple ID (gift card) ── email куда придёт карта
    "apple_id": [
        {
            "id": "apple_email",
            "label": "Apple ID (email аккаунта)",
            "hint": (
                "На этот email придёт подарочная карта App Store.\n"
                "⚠️ Регион аккаунта должен совпадать с регионом карты!\n"
                "• Карта США → нужен аккаунт App Store USA\n"
                "• Карта Турция → нужен аккаунт App Store Turkey"
            ),
            "placeholder": "example@icloud.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── Apple Family (iCloud, Music, TV+) ── email для приглашения
    "apple_family": [
        {
            "id": "apple_email",
            "label": "Ваш Apple ID (email)",
            "hint": (
                "На этот Apple ID придёт приглашение в семейный план.\n"
                "Убедитесь что он активен и почта подтверждена."
            ),
            "placeholder": "example@icloud.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── Spotify ── email + адрес для семейного плана
    "spotify": [
        {
            "id": "spotify_email",
            "label": "Email аккаунта Spotify",
            "hint": "На этот аккаунт придёт приглашение в Premium-план.",
            "placeholder": "example@gmail.com",
            "type": "email",
            "validator": "email",
        },
        {
            "id": "address",
            "label": "Адрес проживания",
            "hint": (
                "Spotify требует адрес для семейного плана.\n"
                "Укажите любой реальный адрес в вашем городе.\n"
                "Пример: Москва, ул. Тверская 1"
            ),
            "placeholder": "Город, улица, дом",
            "type": "text",
            "validator": "text",
        }
    ],

    # ── YouTube Premium ── Google email
    "youtube": [
        {
            "id": "google_email",
            "label": "Email аккаунта Google (Gmail)",
            "hint": (
                "На этот аккаунт придёт приглашение в семейный план YouTube Premium.\n"
                "Должен быть активный Google-аккаунт."
            ),
            "placeholder": "example@gmail.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── Netflix ── имя профиля
    "netflix": [
        {
            "id": "profile_name",
            "label": "Имя для вашего профиля",
            "hint": "Мы создадим отдельный профиль с этим именем на общем аккаунте.",
            "placeholder": "Например: Артём",
            "type": "text",
            "validator": "name",
        }
    ],

    # ── ChatGPT ── email OpenAI
    "chatgpt": [
        {
            "id": "openai_email",
            "label": "Email аккаунта OpenAI",
            "hint": (
                "Если у вас нет аккаунта — зарегистрируйтесь на chat.openai.com\n"
                "На этот аккаунт будет добавлена подписка ChatGPT Plus."
            ),
            "placeholder": "example@gmail.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── Claude ── email Anthropic
    "claude": [
        {
            "id": "anthropic_email",
            "label": "Email аккаунта Anthropic",
            "hint": (
                "Зарегистрируйтесь на claude.ai если нет аккаунта.\n"
                "На него будет добавлена подписка Claude Pro."
            ),
            "placeholder": "example@gmail.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── Midjourney ── Discord username + email
    "midjourney": [
        {
            "id": "discord_username",
            "label": "Discord Username",
            "hint": (
                "Как найти:\n"
                "Discord → Настройки → Мой аккаунт → Имя пользователя\n"
                "Пример: username (без @)"
            ),
            "placeholder": "username",
            "type": "text",
            "validator": "text",
        },
        {
            "id": "discord_email",
            "label": "Email аккаунта Discord",
            "hint": "Email на который зарегистрирован ваш Discord.",
            "placeholder": "example@gmail.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── GitHub Copilot ── GitHub username
    "copilot": [
        {
            "id": "github_username",
            "label": "GitHub Username",
            "hint": "Найдите на github.com → Settings → Public profile",
            "placeholder": "ваш-github-логин",
            "type": "text",
            "validator": "text",
        }
    ],

    # ── Suno ── email
    "suno": [
        {
            "id": "suno_email",
            "label": "Email аккаунта Suno",
            "hint": "Зарегистрируйтесь на suno.com если нет аккаунта.",
            "placeholder": "example@gmail.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── Grok ── X (Twitter) email
    "grok": [
        {
            "id": "x_email",
            "label": "Email аккаунта X (Twitter)",
            "hint": "Grok Premium привязан к аккаунту X. Укажите email входа.",
            "placeholder": "example@gmail.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── Perplexity ── email
    "perplexity": [
        {
            "id": "perplexity_email",
            "label": "Email для Perplexity Pro",
            "hint": "Зарегистрируйтесь на perplexity.ai. На этот аккаунт придёт подписка.",
            "placeholder": "example@gmail.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── Xbox Game Pass ── Microsoft email + регион
    "gamepass": [
        {
            "id": "ms_email",
            "label": "Email аккаунта Microsoft (Xbox)",
            "hint": "Тот же email что используете для Xbox / Windows.",
            "placeholder": "example@outlook.com",
            "type": "email",
            "validator": "email",
        },
        {
            "id": "ms_region",
            "label": "Регион аккаунта Microsoft",
            "hint": (
                "⚠️ Для активации турецкого Game Pass нужен регион Турция.\n"
                "Как сменить: account.microsoft.com → Данные профиля → Страна\n"
                "Укажите текущий регион:"
            ),
            "placeholder": "Россия / Турция / другой",
            "type": "text",
            "validator": "text",
        }
    ],

    # ── PS Plus ── PSN email
    "psplus": [
        {
            "id": "psn_email",
            "label": "Email аккаунта PlayStation (PSN)",
            "hint": "Email на который зарегистрирован ваш PlayStation аккаунт.",
            "placeholder": "example@gmail.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── Canva Pro ── email
    "canva": [
        {
            "id": "canva_email",
            "label": "Email аккаунта Canva",
            "hint": "На этот аккаунт придёт приглашение в Pro-команду.",
            "placeholder": "example@gmail.com",
            "type": "email",
            "validator": "email",
        }
    ],

    # ── Discord ── ключ активации (данные не нужны)
    "discord": [],

    # ── Готовые аккаунты ── ничего не нужно, выдаём логин/пароль
    "ready_acc": [],
}

# Маппинг product_id → schema_key
PRODUCT_FIELDS_MAP = {
    "acc_cgp": "ready_acc", "acc_clp": "ready_acc", "acc_nf": "ready_acc",
    "acc_sp": "ready_acc", "acc_dc": "ready_acc", "acc_mj": "ready_acc",
    "acc_yt": "ready_acc", "acc_steam": "ready_acc", "acc_one": "ready_acc",
    "cgp1": "chatgpt", "cgp3": "chatgpt",
    "clp":  "claude",
    "mjs":  "midjourney", "mjb": "midjourney",
    "pplx": "perplexity",
    "cop":  "copilot",
    "suno": "suno",
    "grk":  "grok",
    "apus": "apple_id", "aptr": "apple_id",
    "icl":  "apple_family", "apm": "apple_family", "aptv": "apple_family",
    "sw5":  "steam_wallet", "sw10": "steam_wallet", "sw1": "steam_wallet",
    "gp":   "gamepass",
    "ps":   "psplus",
    "sp":   "spotify",
    "yt":   "youtube",
    "nf":   "netflix",
    "dc":   "discord",
    "cv":   "canva",
}
