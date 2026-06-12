import json
import os
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from shared.db import (
    create_session,
    execute,
    get_guild_settings,
    get_user_by_token,
    hash_password,
    init_db,
    now,
    row,
    rows,
    set_guild_setting,
    set_setting,
    verify_password,
)

init_db()

app = FastAPI(title="Nuxora SaaS API")


@app.middleware("http")
async def strip_api_prefix(request, call_next):
    path = request.scope.get("path", "")

    if path == "/api":
        request.scope["path"] = "/"
    elif path.startswith("/api/"):
        request.scope["path"] = path[4:]

    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# BODY MODELS
# =========================


class LoginBody(BaseModel):
    username: str
    password: str


class RegisterBody(BaseModel):
    username: str
    password: str
    email: str | None = ""


class GuildBody(BaseModel):
    guild_id: str
    guild_name: str


class StatusBody(BaseModel):
    status: str
    staff_note: str | None = None


class SettingsBody(BaseModel):
    settings: dict


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


class AdminCreateUserBody(BaseModel):
    username: str
    password: str
    email: str | None = ""
    role: str | None = "customer"


class AdminLinkGuildBody(BaseModel):
    user_id: int
    guild_id: str
    guild_name: str
    plan: str | None = "manual"
    status: str | None = "active"


class AdminUserStatusBody(BaseModel):
    is_active: bool


class AdminResetPasswordBody(BaseModel):
    new_password: str


class SendEmbedBody(BaseModel):
    channel_id: str
    title: str | None = ""
    description: str | None = ""
    color: str | None = "#8B0000"
    footer: str | None = ""
    image_url: str | None = ""
    thumbnail_url: str | None = ""


class BotProfileBody(BaseModel):
    nick: str | None = ""
    avatar_url: str | None = ""
    banner_url: str | None = ""
    bio: str | None = ""


class BotActivityBody(BaseModel):
    text: str | None = ""
    activity_type: str | None = "playing"


class LiveNotificationBody(BaseModel):
    streamer_login: str
    discord_channel_id: str
    message: str | None = ""
    embed_title: str | None = ""
    embed_description: str | None = ""
    embed_color: str | None = "#9146FF"
    is_enabled: bool | None = True


class LiveNotificationUpdateBody(BaseModel):
    streamer_login: str | None = None
    discord_channel_id: str | None = None
    message: str | None = None
    embed_title: str | None = None
    embed_description: str | None = None
    embed_color: str | None = None
    is_enabled: bool | None = None


# =========================
# DEFAULT SETTINGS
# =========================


DEFAULT_GUILD_SETTINGS = {
    "allowlist_title": "Allowlist",
    "allowlist_description": "Clique no botão abaixo para iniciar sua allowlist.",
    "allowlist_footer": "Nuxora",
    "allowlist_questions": json.dumps(
        [
            "Nome do Personagem",
            "Idade",
            "Conte sua história",
            "Por que deseja entrar no servidor?",
            "Você leu as regras?",
        ],
        ensure_ascii=False,
    ),
    "allowlist_answer_role_mappings": json.dumps([], ensure_ascii=False),
    "allowlist_category_id": "",
    "allowlist_panel_channel_id": "",
    "allowlist_panel_message_id": "",
    "allowlist_image_url": "",
    "allowlist_thumbnail_url": "",
    "staff_channel_id": "",
    "suggestion_channel_id": "",
    "approved_role_id": "",
    "remove_role_on_approved_id": "",
    "interview_role_id": "",
    "approved_channel_id": "",
    "rejected_channel_id": "",
    "allowlist_approved_title": "✅ Allowlist aprovada",
    "allowlist_approved_description": "Parabéns, {user}! Sua allowlist foi aprovada.",
    "allowlist_approved_color": "#2ecc71",
    "allowlist_approved_footer": "Nuxora • Allowlist",
    "allowlist_rejected_title": "❌ Allowlist reprovada",
    "allowlist_rejected_description": "{user}, sua allowlist foi analisada e foi reprovada.",
    "allowlist_rejected_color": "#e74c3c",
    "allowlist_rejected_footer": "Nuxora • Allowlist",
    "allowlist_interview_title": "🎤 Encaminhado para entrevista",
    "allowlist_interview_description": "{user}, sua allowlist foi analisada e você foi chamado para entrevista.",
    "allowlist_interview_color": "#5865F2",
    "allowlist_interview_footer": "Nuxora • Allowlist",
    "autorole_role_id": "",
    "bot_color": "#8B0000",
    "bot_profile_nick": "",
    "bot_profile_avatar_url": "",
    "bot_profile_banner_url": "",
    "bot_profile_bio": "",
    "ticket_panel_title": "Central de Atendimento",
    "ticket_panel_description": "Escolha abaixo o tipo de ticket que deseja abrir.",
    "ticket_panel_footer": "Nuxora",
    "ticket_panel_image_url": "",
    "ticket_panel_thumbnail_url": "",
    "ticket_panel_color": "#8B0000",
    "ticket_category_id": "",
    "ticket_staff_role_id": "",
    "logs_channel_id": "",
    "ticket_types": json.dumps(
        [
            {
                "id": "suporte",
                "label": "Suporte",
                "emoji": "🛠️",
                "description": "Abra um ticket de suporte.",
                "style": "gray",
                "category_id": "",
                "allowed_role_ids": [],
            }
        ],
        ensure_ascii=False,
    ),
    "member_join_channel_id": "",
    "member_leave_channel_id": "",
    "member_join_title": "👋 Bem-vindo(a)",
    "member_join_description": "{user} entrou em {server}!",
    "member_join_footer": "Nuxora",
    "member_join_color": "#8B0000",
    "member_join_image_url": "",
    "member_leave_title": "📤 Membro saiu",
    "member_leave_description": "{username} deixou {server}.",
    "member_leave_footer": "Nuxora",
    "member_leave_color": "#8B0000",
    "member_leave_image_url": "",
}


# =========================
# HELPERS
# =========================


def clean_guild_id(guild_id: str) -> str:
    return "".join(ch for ch in str(guild_id) if ch.isdigit())


def clean_id(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def ensure_guild_settings(guild_id: str):
    guild_id = str(guild_id)
    current = get_guild_settings(guild_id)

    for key, value in DEFAULT_GUILD_SETTINGS.items():
        if key not in current:
            set_guild_setting(guild_id, key, value)


def require_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.split(" ", 1)[1].strip()
    user = get_user_by_token(token)

    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return user


def require_admin(user=Depends(require_user)):
    if user.get("role") not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Acesso restrito ao admin")

    return user


def require_guild_access(guild_id: str, user: dict):
    guild_id = clean_guild_id(guild_id)

    if not guild_id:
        raise HTTPException(status_code=400, detail="guild_id inválido")

    if user.get("role") in ["owner", "admin"]:
        g = row("SELECT * FROM customer_guilds WHERE guild_id=?", (guild_id,))

        if not g:
            execute(
                """
                INSERT INTO customer_guilds
                (user_id, guild_id, guild_name, plan, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    guild_id,
                    f"Servidor {guild_id}",
                    "manual",
                    "active",
                    now(),
                    now(),
                ),
            )
            ensure_guild_settings(guild_id)

        return True

    g = row(
        """
        SELECT *
        FROM customer_guilds
        WHERE guild_id=? AND user_id=? AND status=?
        """,
        (guild_id, user["id"], "active"),
    )

    if not g:
        raise HTTPException(status_code=403, detail="Sem acesso a este servidor")

    return True


def require_guild_access_allow_blocked_for_admin(guild_id: str, user: dict):
    guild_id = clean_guild_id(guild_id)

    if user.get("role") in ["owner", "admin"]:
        g = row("SELECT * FROM customer_guilds WHERE guild_id=?", (guild_id,))
        if not g:
            raise HTTPException(status_code=404, detail="Servidor não encontrado")
        return True

    return require_guild_access(guild_id, user)


def add_log(guild_id: str, event: str, payload: dict):
    execute(
        """
        INSERT INTO logs (guild_id, event, payload, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(guild_id), event, json.dumps(payload, ensure_ascii=False), now()),
    )


# =========================
# AUTH
# =========================


@app.post("/auth/register")
def register_disabled(body: RegisterBody):
    raise HTTPException(
        status_code=403,
        detail="Cadastro público desativado. Solicite acesso ao administrador.",
    )


@app.post("/auth/login")
def login(body: LoginBody):
    username = body.username.strip()

    user = row("SELECT * FROM users WHERE username=?", (username,))

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Login inválido")

    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Conta bloqueada")

    return {
        "token": create_session(user["id"]),
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
        },
    }


@app.get("/me")
def me(user=Depends(require_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email"),
        "role": user["role"],
        "is_active": user.get("is_active", True),
    }


@app.patch("/me/password")
def change_my_password(body: ChangePasswordBody, user=Depends(require_user)):
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Nova senha muito curta")

    db_user = row("SELECT * FROM users WHERE id=?", (user["id"],))

    if not db_user or not verify_password(
        body.current_password,
        db_user["password_hash"],
    ):
        raise HTTPException(status_code=401, detail="Senha atual inválida")

    execute(
        "UPDATE users SET password_hash=? WHERE id=?",
        (hash_password(body.new_password), user["id"]),
    )

    execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))

    return {"ok": True}


# =========================
# DISCORD INVITE
# =========================


@app.get("/discord/invite-url")
def discord_invite_url(user=Depends(require_user)):
    client_id = os.getenv("DISCORD_CLIENT_ID", "").strip()
    permissions = os.getenv("DISCORD_BOT_PERMISSIONS", "8").strip() or "8"

    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="DISCORD_CLIENT_ID não configurado no .env",
        )

    query = urlencode(
        {
            "client_id": client_id,
            "permissions": permissions,
            "scope": "bot applications.commands",
        }
    )

    return {"url": f"https://discord.com/oauth2/authorize?{query}"}


# =========================
# GUILDS
# =========================


@app.get("/guilds")
def list_guilds(user=Depends(require_user)):
    if user.get("role") in ["owner", "admin"]:
        gs = rows("SELECT * FROM customer_guilds ORDER BY id DESC")
    else:
        gs = rows(
            "SELECT * FROM customer_guilds WHERE user_id=? ORDER BY id DESC",
            (user["id"],),
        )

    return {"guilds": gs}


@app.post("/guilds")
def add_guild(body: GuildBody, user=Depends(require_admin)):
    guild_id = clean_guild_id(body.guild_id)

    if not guild_id:
        raise HTTPException(status_code=400, detail="guild_id inválido")

    existing = row(
        "SELECT * FROM customer_guilds WHERE guild_id=?",
        (guild_id,),
    )

    if existing:
        execute(
            """
            UPDATE customer_guilds
            SET guild_name=?, status=?, updated_at=?
            WHERE guild_id=?
            """,
            (body.guild_name, "active", now(), guild_id),
        )
    else:
        execute(
            """
            INSERT INTO customer_guilds
            (user_id, guild_id, guild_name, plan, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                guild_id,
                body.guild_name,
                "manual",
                "active",
                now(),
                now(),
            ),
        )

    ensure_guild_settings(guild_id)

    return {"ok": True, "guild_id": guild_id}


@app.delete("/guilds/{guild_id}")
def delete_guild(guild_id: str, user=Depends(require_user)):
    guild_id = clean_guild_id(guild_id)

    if not guild_id:
        raise HTTPException(status_code=400, detail="guild_id inválido")

    if user.get("role") in ["admin", "owner"]:
        existing = row(
            "SELECT * FROM customer_guilds WHERE guild_id=?",
            (guild_id,),
        )
    else:
        existing = row(
            "SELECT * FROM customer_guilds WHERE guild_id=? AND user_id=?",
            (guild_id, user["id"]),
        )

    if not existing:
        raise HTTPException(status_code=404, detail="Servidor não encontrado")

    execute("DELETE FROM customer_guilds WHERE guild_id=?", (guild_id,))
    execute("DELETE FROM guild_settings WHERE guild_id=?", (guild_id,))
    execute("DELETE FROM live_notifications WHERE guild_id=?", (guild_id,))

    return {"ok": True, "removed": guild_id}


@app.get("/guilds/{guild_id}/dashboard")
def dashboard(guild_id: str, user=Depends(require_user)):
    guild_id = clean_guild_id(guild_id)

    require_guild_access(guild_id, user)
    ensure_guild_settings(guild_id)

    apps = rows(
        """
        SELECT *
        FROM applications
        WHERE guild_id=?
        ORDER BY id DESC
        LIMIT 500
        """,
        (guild_id,),
    )

    suggestions = rows(
        """
        SELECT *
        FROM suggestions
        WHERE guild_id=?
        ORDER BY id DESC
        LIMIT 500
        """,
        (guild_id,),
    )

    return {
        "stats": {
            "applications": len(apps),
            "pending": len([a for a in apps if a["status"] == "pending"]),
            "approved": len([a for a in apps if a["status"] == "approved"]),
            "rejected": len([a for a in apps if a["status"] == "rejected"]),
            "interview": len([a for a in apps if a["status"] == "interview"]),
            "suggestions": len(suggestions),
        },
        "applications": apps,
        "suggestions": suggestions,
        "settings": get_guild_settings(guild_id),
    }


# =========================
# APPLICATIONS / ALLOWLIST
# =========================


@app.patch("/guilds/{guild_id}/applications/{app_id}/status")
def update_application(
    guild_id: str,
    app_id: int,
    body: StatusBody,
    user=Depends(require_user),
):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    if body.status not in ["pending", "approved", "rejected", "interview"]:
        raise HTTPException(status_code=400, detail="Status inválido")

    existing = row(
        "SELECT id FROM applications WHERE id=? AND guild_id=?",
        (app_id, guild_id),
    )

    if not existing:
        raise HTTPException(status_code=404, detail="Allowlist não encontrada")

    execute(
        """
        UPDATE applications
        SET status=?, staff_note=?, updated_at=?
        WHERE id=? AND guild_id=?
        """,
        (body.status, body.staff_note, now(), app_id, guild_id),
    )

    add_log(
        guild_id,
        "application_status",
        {
            "id": app_id,
            "status": body.status,
            "source": "dashboard",
            "guild_id": guild_id,
        },
    )

    return {"ok": True}


@app.delete("/guilds/{guild_id}/applications/{app_id}")
def delete_application(
    guild_id: str,
    app_id: int,
    user=Depends(require_user),
):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    existing = row(
        "SELECT id FROM applications WHERE id=? AND guild_id=?",
        (app_id, guild_id),
    )

    if not existing:
        raise HTTPException(status_code=404, detail="Allowlist não encontrada")

    execute(
        "DELETE FROM applications WHERE id=? AND guild_id=?",
        (app_id, guild_id),
    )

    add_log(
        guild_id,
        "application_deleted",
        {"id": app_id, "source": "dashboard", "guild_id": guild_id},
    )

    return {"ok": True}


# =========================
# SUGGESTIONS
# =========================


@app.patch("/guilds/{guild_id}/suggestions/{suggestion_id}/status")
def update_suggestion(
    guild_id: str,
    suggestion_id: int,
    body: StatusBody,
    user=Depends(require_user),
):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    if body.status not in ["analysis", "accepted", "rejected", "implemented"]:
        raise HTTPException(status_code=400, detail="Status inválido")

    existing = row(
        "SELECT id FROM suggestions WHERE id=? AND guild_id=?",
        (suggestion_id, guild_id),
    )

    if not existing:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")

    execute(
        """
        UPDATE suggestions
        SET status=?, updated_at=?
        WHERE id=? AND guild_id=?
        """,
        (body.status, now(), suggestion_id, guild_id),
    )

    add_log(
        guild_id,
        "suggestion_status",
        {
            "id": suggestion_id,
            "status": body.status,
            "source": "dashboard",
            "guild_id": guild_id,
        },
    )

    return {"ok": True}


@app.delete("/guilds/{guild_id}/suggestions/{suggestion_id}")
def delete_suggestion(
    guild_id: str,
    suggestion_id: int,
    user=Depends(require_user),
):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    existing = row(
        "SELECT id FROM suggestions WHERE id=? AND guild_id=?",
        (suggestion_id, guild_id),
    )

    if not existing:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")

    execute(
        "DELETE FROM suggestions WHERE id=? AND guild_id=?",
        (suggestion_id, guild_id),
    )

    add_log(
        guild_id,
        "suggestion_deleted",
        {"id": suggestion_id, "source": "dashboard", "guild_id": guild_id},
    )

    return {"ok": True}


# =========================
# SETTINGS
# =========================


@app.put("/guilds/{guild_id}/settings")
def update_settings(guild_id: str, body: SettingsBody, user=Depends(require_user)):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    for key, value in body.settings.items():
        set_guild_setting(guild_id, key, value)

    answer_role_mappings = body.settings.get("allowlist_answer_role_mappings", [])

    add_log(
        guild_id,
        "settings_updated",
        {
            "source": "dashboard",
            "keys": list(body.settings.keys()),
            "guild_id": guild_id,
            "allowlist_answer_role_mappings_count": len(answer_role_mappings)
            if isinstance(answer_role_mappings, list)
            else 0,
        },
    )

    return {"ok": True, "settings": get_guild_settings(guild_id)}


# =========================
# EMBED DASHBOARD
# =========================


@app.post("/guilds/{guild_id}/embed")
def send_embed_from_dashboard(
    guild_id: str,
    body: SendEmbedBody,
    user=Depends(require_user),
):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    channel_id = clean_id(body.channel_id)

    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id inválido")

    title = (body.title or "").strip()
    description = (body.description or "").strip()
    footer = (body.footer or "").strip()

    if not title and not description:
        raise HTTPException(status_code=400, detail="Título ou descrição obrigatórios")

    add_log(
        guild_id,
        "send_embed",
        {
            "guild_id": guild_id,
            "channel_id": channel_id,
            "title": title,
            "description": description,
            "color": body.color or "#8B0000",
            "footer": footer,
            "image_url": body.image_url or "",
            "thumbnail_url": body.thumbnail_url or "",
            "source": "dashboard",
            "user_id": user["id"],
            "username": user["username"],
        },
    )

    return {"ok": True}


# =========================
# BOT PROFILE
# =========================


@app.post("/guilds/{guild_id}/bot-profile")
def apply_bot_profile(
    guild_id: str,
    body: BotProfileBody,
    user=Depends(require_user),
):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    nick = (body.nick or "").strip()
    avatar_url = (body.avatar_url or "").strip()
    banner_url = (body.banner_url or "").strip()
    bio = (body.bio or "").strip()

    set_guild_setting(guild_id, "bot_profile_nick", nick)
    set_guild_setting(guild_id, "bot_profile_avatar_url", avatar_url)
    set_guild_setting(guild_id, "bot_profile_banner_url", banner_url)
    set_guild_setting(guild_id, "bot_profile_bio", bio)

    add_log(
        guild_id,
        "apply_bot_profile",
        {
            "guild_id": guild_id,
            "nick": nick,
            "avatar_url": avatar_url,
            "banner_url": banner_url,
            "bio": bio,
            "bio_ignored": bool(bio),
            "source": "dashboard",
            "user_id": user["id"],
            "username": user["username"],
        },
    )

    return {"ok": True}


@app.post("/admin/bot-activity")
def admin_apply_bot_activity(
    body: BotActivityBody,
    admin=Depends(require_admin),
):
    text = (body.text or "").strip()
    activity_type = (body.activity_type or "playing").strip().lower()

    if activity_type not in ["playing", "watching", "listening", "competing"]:
        activity_type = "playing"

    if len(text) > 128:
        text = text[:128]

    set_setting("bot_activity_text", text)
    set_setting("bot_activity_type", activity_type)

    add_log(
        "global",
        "apply_bot_activity",
        {
            "guild_id": "global",
            "text": text,
            "activity_type": activity_type,
            "source": "admin_dashboard",
            "user_id": admin["id"],
            "username": admin["username"],
        },
    )

    return {"ok": True, "text": text, "activity_type": activity_type}


# =========================
# LIVE NOTIFICATIONS
# =========================


@app.get("/guilds/{guild_id}/live-notifications")
def list_live_notifications(guild_id: str, user=Depends(require_user)):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    data = rows(
        """
        SELECT *
        FROM live_notifications
        WHERE guild_id=?
        ORDER BY id DESC
        """,
        (guild_id,),
    )

    return {"items": data}


@app.post("/guilds/{guild_id}/live-notifications")
def create_live_notification(
    guild_id: str,
    body: LiveNotificationBody,
    user=Depends(require_user),
):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    streamer_login = (body.streamer_login or "").strip().lower()
    discord_channel_id = clean_id(body.discord_channel_id)

    if not streamer_login:
        raise HTTPException(status_code=400, detail="Streamer obrigatório")

    if not discord_channel_id:
        raise HTTPException(status_code=400, detail="Canal Discord inválido")

    existing = row(
        """
        SELECT id
        FROM live_notifications
        WHERE guild_id=? AND platform=? AND streamer_login=?
        """,
        (guild_id, "twitch", streamer_login),
    )

    if existing:
        execute(
            """
            UPDATE live_notifications
            SET discord_channel_id=?,
                message=?,
                embed_title=?,
                embed_description=?,
                embed_color=?,
                is_enabled=?,
                updated_at=?
            WHERE id=?
            """,
            (
                discord_channel_id,
                body.message or "",
                body.embed_title or "",
                body.embed_description or "",
                body.embed_color or "#9146FF",
                body.is_enabled if body.is_enabled is not None else True,
                now(),
                existing["id"],
            ),
        )

        return {"ok": True, "id": existing["id"], "updated": True}

    nid = execute(
        """
        INSERT INTO live_notifications
        (
            guild_id,
            platform,
            streamer_login,
            discord_channel_id,
            message,
            embed_title,
            embed_description,
            embed_color,
            is_enabled,
            is_live,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            "twitch",
            streamer_login,
            discord_channel_id,
            body.message or "",
            body.embed_title or "",
            body.embed_description or "",
            body.embed_color or "#9146FF",
            body.is_enabled if body.is_enabled is not None else True,
            False,
            now(),
            now(),
        ),
    )

    return {"ok": True, "id": nid, "created": True}


@app.patch("/guilds/{guild_id}/live-notifications/{notification_id}")
def update_live_notification(
    guild_id: str,
    notification_id: int,
    body: LiveNotificationUpdateBody,
    user=Depends(require_user),
):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    item = row(
        """
        SELECT *
        FROM live_notifications
        WHERE id=? AND guild_id=?
        """,
        (notification_id, guild_id),
    )

    if not item:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")

    streamer_login = (
        body.streamer_login.strip().lower()
        if body.streamer_login is not None
        else item["streamer_login"]
    )

    discord_channel_id = (
        clean_id(body.discord_channel_id)
        if body.discord_channel_id is not None
        else item["discord_channel_id"]
    )

    if not streamer_login:
        raise HTTPException(status_code=400, detail="Streamer obrigatório")

    if not discord_channel_id:
        raise HTTPException(status_code=400, detail="Canal Discord inválido")

    execute(
        """
        UPDATE live_notifications
        SET streamer_login=?,
            discord_channel_id=?,
            message=?,
            embed_title=?,
            embed_description=?,
            embed_color=?,
            is_enabled=?,
            updated_at=?
        WHERE id=? AND guild_id=?
        """,
        (
            streamer_login,
            discord_channel_id,
            item["message"] if body.message is None else body.message,
            item["embed_title"] if body.embed_title is None else body.embed_title,
            item["embed_description"]
            if body.embed_description is None
            else body.embed_description,
            item["embed_color"] if body.embed_color is None else body.embed_color,
            item["is_enabled"] if body.is_enabled is None else body.is_enabled,
            now(),
            notification_id,
            guild_id,
        ),
    )

    return {"ok": True}


@app.delete("/guilds/{guild_id}/live-notifications/{notification_id}")
def delete_live_notification(
    guild_id: str,
    notification_id: int,
    user=Depends(require_user),
):
    guild_id = clean_guild_id(guild_id)
    require_guild_access(guild_id, user)

    existing = row(
        """
        SELECT id
        FROM live_notifications
        WHERE id=? AND guild_id=?
        """,
        (notification_id, guild_id),
    )

    if not existing:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")

    execute(
        "DELETE FROM live_notifications WHERE id=? AND guild_id=?",
        (notification_id, guild_id),
    )

    return {"ok": True}


# =========================
# ADMIN USERS
# =========================


@app.get("/admin/users")
def admin_list_users(admin=Depends(require_admin)):
    users = rows(
        """
        SELECT id, username, email, role, is_active, created_at
        FROM users
        ORDER BY id DESC
        """
    )

    return {"users": users}


@app.post("/admin/users")
def admin_create_user(body: AdminCreateUserBody, admin=Depends(require_admin)):
    username = body.username.strip()

    if len(username) < 3 or len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Usuário ou senha muito curto")

    if row("SELECT id FROM users WHERE username=?", (username,)):
        raise HTTPException(status_code=400, detail="Usuário já existe")

    role = body.role or "customer"

    if role not in ["customer", "admin", "owner"]:
        role = "customer"

    uid = execute(
        """
        INSERT INTO users
        (username, password_hash, email, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (username, hash_password(body.password), body.email or "", role, True, now()),
    )

    return {
        "ok": True,
        "user": {
            "id": uid,
            "username": username,
            "email": body.email or "",
            "role": role,
        },
    }


@app.patch("/admin/users/{user_id}/status")
def admin_update_user_status(
    user_id: int,
    body: AdminUserStatusBody,
    admin=Depends(require_admin),
):
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=400,
            detail="Você não pode bloquear sua própria conta",
        )

    user = row("SELECT id, role FROM users WHERE id=?", (user_id,))

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if user.get("role") == "owner" and admin.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Somente owner pode bloquear owner")

    execute(
        "UPDATE users SET is_active=? WHERE id=?",
        (body.is_active, user_id),
    )

    execute(
        "DELETE FROM sessions WHERE user_id=?",
        (user_id,),
    )

    new_status = "active" if body.is_active else "blocked"

    execute(
        """
        UPDATE customer_guilds
        SET status=?, updated_at=?
        WHERE user_id=?
        """,
        (new_status, now(), user_id),
    )

    return {
        "ok": True,
        "user_id": user_id,
        "is_active": body.is_active,
        "guild_status": new_status,
    }


@app.patch("/admin/users/{user_id}/password")
def admin_reset_user_password(
    user_id: int,
    body: AdminResetPasswordBody,
    admin=Depends(require_admin),
):
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Nova senha muito curta")

    user = row("SELECT id FROM users WHERE id=?", (user_id,))

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    execute(
        "UPDATE users SET password_hash=? WHERE id=?",
        (hash_password(body.new_password), user_id),
    )

    execute("DELETE FROM sessions WHERE user_id=?", (user_id,))

    return {"ok": True}


@app.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, admin=Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=400,
            detail="Você não pode excluir sua própria conta",
        )

    user = row("SELECT id, role FROM users WHERE id=?", (user_id,))

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if user.get("role") == "owner" and admin.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Somente owner pode excluir owner")

    linked_guilds = rows(
        "SELECT guild_id FROM customer_guilds WHERE user_id=?",
        (user_id,),
    )

    for g in linked_guilds:
        execute("DELETE FROM guild_settings WHERE guild_id=?", (g["guild_id"],))
        execute("DELETE FROM live_notifications WHERE guild_id=?", (g["guild_id"],))

    execute("DELETE FROM customer_guilds WHERE user_id=?", (user_id,))
    execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    execute("DELETE FROM users WHERE id=?", (user_id,))

    return {"ok": True}


# =========================
# ADMIN GUILDS
# =========================


@app.get("/admin/guilds")
def admin_list_guilds(admin=Depends(require_admin)):
    data = rows(
        """
        SELECT
            customer_guilds.*,
            users.username,
            users.email
        FROM customer_guilds
        JOIN users ON users.id = customer_guilds.user_id
        ORDER BY customer_guilds.id DESC
        """
    )

    return {"guilds": data}


@app.post("/admin/guilds/link")
def admin_link_guild(body: AdminLinkGuildBody, admin=Depends(require_admin)):
    guild_id = clean_guild_id(body.guild_id)

    if not guild_id:
        raise HTTPException(status_code=400, detail="guild_id inválido")

    user = row("SELECT id FROM users WHERE id=?", (body.user_id,))

    if not user:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    status = body.status or "active"

    if status not in ["active", "blocked"]:
        status = "active"

    existing = row("SELECT * FROM customer_guilds WHERE guild_id=?", (guild_id,))

    if existing:
        execute(
            """
            UPDATE customer_guilds
            SET user_id=?, guild_name=?, plan=?, status=?, updated_at=?
            WHERE guild_id=?
            """,
            (
                body.user_id,
                body.guild_name,
                body.plan or "manual",
                status,
                now(),
                guild_id,
            ),
        )
    else:
        execute(
            """
            INSERT INTO customer_guilds
            (user_id, guild_id, guild_name, plan, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.user_id,
                guild_id,
                body.guild_name,
                body.plan or "manual",
                status,
                now(),
                now(),
            ),
        )

    ensure_guild_settings(guild_id)

    return {"ok": True, "guild_id": guild_id}


@app.delete("/admin/guilds/{guild_id}")
def admin_delete_guild(guild_id: str, admin=Depends(require_admin)):
    guild_id = clean_guild_id(guild_id)

    if not guild_id:
        raise HTTPException(status_code=400, detail="guild_id inválido")

    execute("DELETE FROM customer_guilds WHERE guild_id=?", (guild_id,))
    execute("DELETE FROM guild_settings WHERE guild_id=?", (guild_id,))
    execute("DELETE FROM live_notifications WHERE guild_id=?", (guild_id,))

    return {"ok": True, "removed": guild_id}


# =========================
# COMPAT ROUTES
# =========================


@app.get("/dashboard")
def dashboard_compat(user=Depends(require_user)):
    gs = list_guilds(user)["guilds"]

    if not gs:
        return {
            "stats": {
                "applications": 0,
                "pending": 0,
                "approved": 0,
                "rejected": 0,
                "interview": 0,
                "suggestions": 0,
            },
            "applications": [],
            "suggestions": [],
            "settings": {},
        }

    return dashboard(gs[0]["guild_id"], user)


@app.put("/settings")
def settings_compat(body: SettingsBody, user=Depends(require_user)):
    gs = list_guilds(user)["guilds"]

    if not gs:
        raise HTTPException(status_code=400, detail="Cadastre um servidor primeiro")

    return update_settings(gs[0]["guild_id"], body, user)


@app.get("/health")
def health():
    return {"ok": True}
