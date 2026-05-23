import json
import os
from datetime import datetime

import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://nightfall:nightfall_password@nightfall-postgres:5432/nightfall",
)

_pool: asyncpg.Pool | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    discord_id TEXT NOT NULL,
    discord_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    answers TEXT NOT NULL,
    staff_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suggestions (
    id SERIAL PRIMARY KEY,
    discord_id TEXT NOT NULL,
    discord_name TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'analysis',
    message_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    event TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_discord_status ON applications(discord_id, status);
CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);
CREATE INDEX IF NOT EXISTS idx_logs_id_event ON logs(id, event);
"""

DEFAULT_SETTINGS = {
    "allowlist_title": "Registro de Cidadania",
    "allowlist_description": "Clique no botão para iniciar sua allowlist.",
    "allowlist_questions": json.dumps(
        [
            "Nome do Personagem",
            "Idade",
            "Conte sua lore",
            "Experiência com RP",
            "Horários disponíveis",
        ],
        ensure_ascii=False,
    ),
    "bot_color": os.getenv("BOT_COLOR", "#8B0000"),
    "staff_channel_id": os.getenv("STAFF_CHANNEL_ID", "0"),
    "suggestion_channel_id": os.getenv("SUGGESTION_CHANNEL_ID", "0"),
    "logs_channel_id": os.getenv("LOGS_CHANNEL_ID", "0"),
    "approved_role_id": os.getenv("APPROVED_ROLE_ID", "0"),
    "interview_role_id": os.getenv("INTERVIEW_ROLE_ID", "0"),
    "autorole_role_id": os.getenv("AUTOROLE_ROLE_ID", "0"),
    "allowlist_category_id": "0",
    "ticket_category_id": "0",
    "ticket_staff_role_id": "0",
    "ticket_panel_title": "🎫 Central de Atendimento",
    "ticket_panel_description": "Selecione abaixo o tipo de atendimento que você precisa.",
    "ticket_panel_color": "#8B0000",
    "ticket_types": "[]",
    "fivem_enabled": "false",
    "minecraft_enabled": "false",
    "conan_enabled": "false",
    "hytale_enabled": "false",
}


def now():
    return datetime.utcnow().isoformat()


async def get_pool() -> asyncpg.Pool:
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)

    return _pool


def qmark_to_pg(query: str) -> str:
    """
    Compatibilidade com os módulos existentes.
    Permite continuar usando queries com ? e converte para $1, $2...
    """
    result = []
    index = 1

    for char in query:
        if char == "?":
            result.append(f"${index}")
            index += 1
        else:
            result.append(char)

    return "".join(result)


async def init_db():
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)

        for key, value in DEFAULT_SETTINGS.items():
            await conn.execute(
                """
                INSERT INTO settings (key, value)
                VALUES ($1, $2)
                ON CONFLICT (key) DO NOTHING
                """,
                key,
                str(value),
            )


async def rows(query, params=()):
    pool = await get_pool()
    query = qmark_to_pg(query)

    async with pool.acquire() as conn:
        data = await conn.fetch(query, *params)
        return [dict(row) for row in data]


async def row(query, params=()):
    data = await rows(query, params)
    return data[0] if data else None


async def execute(query, params=()):
    pool = await get_pool()
    query = qmark_to_pg(query)

    async with pool.acquire() as conn:
        lowered = query.strip().lower()

        if lowered.startswith("insert"):
            # Só tenta retornar ID em tabelas que realmente têm coluna id.
            if "into settings" in lowered:
                await conn.execute(query, *params)
                return None

            try:
                return await conn.fetchval(query + " RETURNING id", *params)
            except Exception:
                await conn.execute(query, *params)
                return None

        await conn.execute(query, *params)
        return None

        conn.execute(query, params)
        conn.commit()
        return None


async def settings():
    data = await rows("SELECT key, value FROM settings")
    return {r["key"]: r["value"] for r in data}


async def log(event, payload):
    await execute(
        "INSERT INTO logs (event, payload, created_at) VALUES (?, ?, ?)",
        (event, json.dumps(payload, ensure_ascii=False), now()),
    )
