import hashlib
import json
import os
import secrets
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://nuxora:nuxora_password@nuxora-postgres:5432/nuxora"
)

API_SECRET = os.getenv("API_SECRET", "dev-secret")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT,
        role TEXT NOT NULL DEFAULT 'customer',
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id SERIAL PRIMARY KEY,
        token TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS customer_guilds (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        guild_id TEXT UNIQUE NOT NULL,
        guild_name TEXT NOT NULL,
        plan TEXT NOT NULL DEFAULT 'manual',
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        PRIMARY KEY (guild_id, key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS applications (
        id SERIAL PRIMARY KEY,
        guild_id TEXT NOT NULL DEFAULT 'global',
        discord_id TEXT NOT NULL,
        discord_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        answers TEXT NOT NULL,
        staff_note TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS suggestions (
        id SERIAL PRIMARY KEY,
        guild_id TEXT NOT NULL DEFAULT 'global',
        discord_id TEXT NOT NULL,
        discord_name TEXT NOT NULL,
        content TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'analysis',
        message_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS logs (
        id SERIAL PRIMARY KEY,
        guild_id TEXT NOT NULL DEFAULT 'global',
        event TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS live_notifications (
        id SERIAL PRIMARY KEY,
        guild_id TEXT NOT NULL,
        platform TEXT NOT NULL DEFAULT 'twitch',
        streamer_login TEXT NOT NULL,
        discord_channel_id TEXT NOT NULL,
        message TEXT NOT NULL DEFAULT '',
        embed_title TEXT NOT NULL DEFAULT '',
        embed_description TEXT NOT NULL DEFAULT '',
        embed_color TEXT NOT NULL DEFAULT '#9146FF',
        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        is_live BOOLEAN NOT NULL DEFAULT FALSE,
        last_stream_id TEXT,
        last_notified_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (guild_id, platform, streamer_login)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS id SERIAL
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'sessions_token_unique'
        ) THEN
            ALTER TABLE sessions
            ADD CONSTRAINT sessions_token_unique UNIQUE (token);
        END IF;
    END
    $$;
    """,
    """
    ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS guild_id TEXT NOT NULL DEFAULT 'global'
    """,
    """
    ALTER TABLE suggestions
    ADD COLUMN IF NOT EXISTS guild_id TEXT NOT NULL DEFAULT 'global'
    """,
    """
    ALTER TABLE logs
    ADD COLUMN IF NOT EXISTS guild_id TEXT NOT NULL DEFAULT 'global'
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_applications_guild_status
    ON applications(guild_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_suggestions_guild_status
    ON suggestions(guild_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_logs_guild_id_event
    ON logs(guild_id, id, event)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_live_notifications_guild
    ON live_notifications(guild_id, is_enabled)
    """,
]


def now():
    return datetime.utcnow().isoformat()


def normalize_query(query: str) -> str:
    return query.replace("?", "%s")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, digest = password_hash.split(":", 1)
        check = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return secrets.compare_digest(check, digest)
    except Exception:
        return False


def init_db():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(987654321)")

        try:
            for statement in SCHEMA_STATEMENTS:
                try:
                    conn.execute(statement)
                except Exception as e:
                    msg = str(e)

                    if (
                        "already exists" in msg
                        or "duplicate key value violates unique constraint" in msg
                        or "multiple primary keys" in msg
                        or "already a primary key" in msg
                    ):
                        print(f"⚠️ Schema já existente ignorado: {msg}", flush=True)
                        continue

                    print(f"⚠️ Erro no schema: {msg}", flush=True)

        finally:
            conn.execute("SELECT pg_advisory_unlock(987654321)")


def rows_sync(query: str, params=()):
    query = normalize_query(query)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        cur = conn.execute(query, params)
        return list(cur.fetchall())


def row_sync(query: str, params=()):
    query = normalize_query(query)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        cur = conn.execute(query, params)
        return cur.fetchone()


def execute_sync(query: str, params=()):
    query = normalize_query(query).strip()
    ql = query.lower()

    with psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row) as conn:
        if (
            ql.startswith("insert")
            and "returning" not in ql
            and "on conflict" not in ql
        ):
            try:
                cur = conn.execute(query + " RETURNING id", params)
                data = cur.fetchone()
                return data["id"] if data and "id" in data else None
            except Exception:
                conn.execute(query, params)
                return None

        cur = conn.execute(query, params)

        try:
            data = cur.fetchone()
            if data and "id" in data:
                return data["id"]
        except Exception:
            pass

        return None


def get_settings():
    data = rows_sync("SELECT key, value FROM settings")
    return {r["key"]: r["value"] for r in data}


def set_setting(key: str, value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)

    execute_sync(
        """
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT (key)
        DO UPDATE SET value = EXCLUDED.value
        """,
        (key, str(value)),
    )


def get_guild_settings(guild_id: str):
    data = rows_sync(
        "SELECT key, value FROM guild_settings WHERE guild_id=?",
        (str(guild_id),),
    )
    return {r["key"]: r["value"] for r in data}


def set_guild_setting(guild_id: str, key: str, value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)

    execute_sync(
        """
        INSERT INTO guild_settings (guild_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT (guild_id, key)
        DO UPDATE SET value = EXCLUDED.value
        """,
        (str(guild_id), key, str(value)),
    )


def create_session(user_id: int):
    token = secrets.token_urlsafe(48)

    execute_sync(
        """
        INSERT INTO sessions (token, user_id, created_at)
        VALUES (?, ?, ?)
        """,
        (token, user_id, now()),
    )

    return token


def get_user_by_token(token: str):
    return row_sync(
        """
        SELECT users.*
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token=?
        """,
        (token,),
    )


def log_sync(event: str, payload, guild_id: str = "global"):
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False)

    execute_sync(
        """
        INSERT INTO logs (guild_id, event, payload, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(guild_id), event, payload, now()),
    )


# =========================
# ASYNC COMPAT PARA O BOT
# =========================
# Os módulos do bot usam await row(), await rows(), await execute(), await settings().
# Aqui adaptamos as funções síncronas para async.


async def rows(query: str, params=()):
    return rows_sync(query, params)


async def row(query: str, params=()):
    return row_sync(query, params)


async def execute(query: str, params=()):
    return execute_sync(query, params)


async def settings(guild_id=None):
    if guild_id:
        return get_guild_settings(str(guild_id))

    return get_settings()


async def log(event: str, payload, guild_id: str = "global"):
    return log_sync(event, payload, guild_id)


async def ensure_guild(guild_id: str, guild_name: str = "Servidor"):
    existing = row_sync(
        "SELECT guild_id FROM customer_guilds WHERE guild_id=?",
        (str(guild_id),),
    )

    if existing:
        return existing

    return None
