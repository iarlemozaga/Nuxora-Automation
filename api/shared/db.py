import os
import json
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
from datetime import datetime

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://nightfall:nightfall_password@nightfall-postgres:5432/nightfall"
)

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
    "allowlist_questions": json.dumps([
        "Nome do Personagem",
        "Idade",
        "Conte sua lore",
        "Experiência com RP",
        "Horários disponíveis"
    ], ensure_ascii=False),
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
    "hytale_enabled": "false"
}


@contextmanager
def connect():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn


def now():
    return datetime.utcnow().isoformat()


def init_db():
    with connect() as conn:
        conn.execute(SCHEMA)

        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                """
                INSERT INTO settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO NOTHING
                """,
                (key, str(value))
            )

        conn.commit()


def qmark_to_psycopg(query: str) -> str:
    return query.replace("?", "%s")


def rows(query, params=()):
    query = qmark_to_psycopg(query)

    with connect() as conn:
        cur = conn.execute(query, params)
        return list(cur.fetchall())


def row(query, params=()):
    data = rows(query, params)
    return data[0] if data else None


def execute(query, params=()):
    query = qmark_to_psycopg(query)
    lowered = query.strip().lower()

    with connect() as conn:
        if lowered.startswith("insert"):
            # A tabela settings não possui coluna id.
            if "into settings" in lowered:
                conn.execute(query, params)
                conn.commit()
                return None

            try:
                cur = conn.execute(query + " RETURNING id", params)
                conn.commit()
                value = cur.fetchone()
                return value["id"] if value else None
            except Exception:
                conn.rollback()
                conn.execute(query, params)
                conn.commit()
                return None

        conn.execute(query, params)
        conn.commit()
        return None


def get_settings():
    return {r["key"]: r["value"] for r in rows("SELECT key, value FROM settings")}


def set_setting(key, value):
    execute(
        """
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """,
        (key, str(value))
    )
