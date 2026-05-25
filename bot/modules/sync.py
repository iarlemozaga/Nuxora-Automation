import base64
import json

import aiohttp
import discord
from discord.ext import commands, tasks
from modules.allowlist import (
    AllowlistStartView,
    build_allowlist_panel_embed,
)
from shared.db import log, row, rows, settings
from shared.guard import is_guild_active
# =========================
# HELPERS
# =========================


async def url_to_data_uri(url: str) -> str | None:
    url = str(url or "").strip()

    if not url:
        return None

    if not (url.startswith("https://") or url.startswith("http://")):
        print(f"❌ URL inválida para imagem do perfil do bot: {url}", flush=True)
        return None

    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status >= 400:
                    print(
                        f"❌ Erro ao baixar imagem do perfil do bot: HTTP {resp.status}",
                        flush=True,
                    )
                    return None

                content_type = (
                    (resp.headers.get("Content-Type") or "image/png")
                    .split(";", 1)[0]
                    .strip()
                )
                data = await resp.read()

        if not data:
            print("❌ Imagem do perfil do bot vazia.", flush=True)
            return None

        if len(data) > 8 * 1024 * 1024:
            print("❌ Imagem do perfil do bot maior que 8MB.", flush=True)
            return None

        if content_type == "image/jpg":
            content_type = "image/jpeg"

        if content_type not in [
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
        ]:
            content_type = "image/png"

        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{content_type};base64,{encoded}"

    except Exception as e:
        print(f"❌ Erro ao converter imagem do perfil do bot: {e}", flush=True)
        return None


def parse_staff_message_id(staff_note: str | None):
    if not staff_note:
        return None

    if "staff_message_id:" not in staff_note:
        return None

    try:
        return int(staff_note.split("staff_message_id:", 1)[1].strip())
    except Exception:
        return None


def get_nickname_from_answers(answers: list[dict]) -> str | None:
    """
    Usa SEMPRE a primeira resposta da allowlist como nickname.
    Então a primeira pergunta do formulário deve ser o nome do personagem.
    """

    if not answers:
        print(
            "❌ Nickname dashboard não alterado: lista de respostas vazia.",
            flush=True,
        )
        return None

    first_answer = str(answers[0].get("answer", "")).strip()

    if not first_answer:
        print(
            "❌ Nickname dashboard não alterado: primeira resposta vazia.",
            flush=True,
        )
        return None

    nickname = first_answer.splitlines()[0].strip()

    if not nickname:
        print(
            "❌ Nickname dashboard não alterado: nickname vazio após limpeza.",
            flush=True,
        )
        return None

    return nickname[:32]


async def change_member_nickname(
    member: discord.Member,
    answers: list[dict],
    reason: str,
):
    print("=== TENTANDO ALTERAR NICKNAME PELO DASHBOARD ===", flush=True)
    print(f"Usuário alvo: {member} / {member.id}", flush=True)
    print(
        f"Primeira resposta: {answers[0] if answers else 'SEM RESPOSTAS'}",
        flush=True,
    )

    nickname = get_nickname_from_answers(answers)

    print(f"Nickname detectado: {nickname}", flush=True)

    if not nickname:
        return False

    try:
        await member.edit(nick=nickname, reason=reason)

        print(
            f"✅ Nickname alterado com sucesso via dashboard: {member.id} -> {nickname}",
            flush=True,
        )
        return True

    except discord.Forbidden:
        print(
            "❌ Sem permissão/hierarquia para alterar nickname via dashboard. "
            "Mesmo com Administrator, o cargo do bot precisa estar acima do cargo mais alto do usuário.",
            flush=True,
        )
        return False

    except discord.HTTPException as e:
        print(f"❌ Erro HTTP ao alterar nickname via dashboard: {e}", flush=True)
        return False

    except Exception as e:
        print(f"❌ Erro inesperado ao alterar nickname via dashboard: {e}", flush=True)
        return False


def parse_hex_color(value: str, fallback: int):
    try:
        value = str(value or "").replace("#", "").strip()
        return int(value, 16)
    except Exception:
        return fallback


def format_allowlist_text(text: str, member, application, answers):
    character_name = ""

    try:
        if answers and answers[0].get("answer"):
            character_name = str(answers[0]["answer"]).strip().splitlines()[0]
    except Exception:
        character_name = ""

    username = str(application.get("discord_name") or "")

    return (
        str(text or "")
        .replace("{user}", member.mention if member else username)
        .replace("{username}", member.name if member else username)
        .replace("{display_name}", member.display_name if member else username)
        .replace("{id}", str(application.get("discord_id") or ""))
        .replace("{character}", character_name)
    )


async def send_allowlist_result_channel(
    guild: discord.Guild,
    member: discord.Member,
    status: str,
    answers: list[dict],
    cfg: dict,
):
    if status == "approved":
        channel_id = int(cfg.get("approved_channel_id", "0") or 0)
        title = cfg.get("allowlist_approved_title") or "✅ Allowlist aprovada"
        description = (
            cfg.get("allowlist_approved_description")
            or "Parabéns, {user}! Sua allowlist foi aprovada."
        )
        color = discord.Color(
            parse_hex_color(cfg.get("allowlist_approved_color"), 0x2ECC71)
        )
        footer = cfg.get("allowlist_approved_footer") or "Nuxora • Allowlist"

    elif status == "rejected":
        channel_id = int(cfg.get("rejected_channel_id", "0") or 0)
        title = cfg.get("allowlist_rejected_title") or "❌ Allowlist reprovada"
        description = (
            cfg.get("allowlist_rejected_description")
            or "{user}, sua allowlist foi analisada e foi reprovada."
        )
        color = discord.Color(
            parse_hex_color(cfg.get("allowlist_rejected_color"), 0xE74C3C)
        )
        footer = cfg.get("allowlist_rejected_footer") or "Nuxora • Allowlist"

    else:
        return

    if not channel_id:
        print(
            f"Canal público de resultado não configurado para status: {status}",
            flush=True,
        )
        return

    channel = guild.get_channel(channel_id)

    if not channel:
        try:
            channel = await guild.fetch_channel(channel_id)
        except Exception:
            channel = None

    if not channel:
        print(f"Canal público de resultado não encontrado: {channel_id}", flush=True)
        return

    fake_application = {
        "discord_name": str(member),
        "discord_id": str(member.id),
    }

    title = format_allowlist_text(title, member, fake_application, answers)
    description = format_allowlist_text(description, member, fake_application, answers)
    footer = format_allowlist_text(footer, member, fake_application, answers)

    character_name = None

    if answers and answers[0].get("answer"):
        character_name = str(answers[0]["answer"]).strip().splitlines()[0][:64]

    embed = discord.Embed(title=title, description=description, color=color)

    if character_name:
        embed.add_field(name="Personagem", value=character_name, inline=False)

    embed.add_field(
        name="Usuário",
        value=f"{member.mention} (`{member.id}`)",
        inline=False,
    )

    embed.set_thumbnail(url=member.display_avatar.url)

    if footer:
        embed.set_footer(text=footer)

    try:
        await channel.send(embed=embed)
        print(
            f"✅ Resultado público enviado via dashboard para canal {channel_id}: {status}",
            flush=True,
        )
    except Exception as e:
        print(f"❌ Erro ao enviar resultado público via dashboard: {e}", flush=True)


# =========================
# SYNC COG
# =========================


class DashboardSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_log_id = None
        print("✅ DashboardSync cog inicializado", flush=True)
        self.sync_dashboard.start()

    def cog_unload(self):
        self.sync_dashboard.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print("=== DASHBOARD SYNC ON_READY ===", flush=True)
        print(f"Último log conhecido: {self.last_log_id}", flush=True)

    @tasks.loop(seconds=3)
    async def sync_dashboard(self):
        if not self.bot.is_ready():
            return

        if self.last_log_id is None:
            latest = await row("SELECT id FROM logs ORDER BY id DESC LIMIT 1")
            self.last_log_id = latest["id"] if latest else 0

            print("=== DASHBOARD SYNC INIT ===", flush=True)
            print(f"Iniciando a partir do log: {self.last_log_id}", flush=True)
            return

        logs = await rows(
            """
            SELECT *
            FROM logs
            WHERE id > ?
            ORDER BY id ASC
            """,
            (self.last_log_id,),
        )

        if not logs:
            return

        print(f"=== SYNC ENCONTROU {len(logs)} LOG(S) NOVO(S) ===", flush=True)

        for item in logs:
            self.last_log_id = item["id"]

            event = item["event"]

            print(f"Log #{item['id']} event={event}", flush=True)
            try:
                payload = json.loads(item.get("payload") or "{}")
            except Exception:
                payload = {}

            guild_id = str(payload.get("guild_id") or item.get("guild_id") or "")

            if guild_id.isdigit():
                active = await is_guild_active(guild_id)

                if not active:
                    print(
                        f"🔒 Ignorando log #{item['id']} porque o servidor está bloqueado ou inativo: {guild_id}",
                        flush=True,
                    )
                    continue

            if event == "application_status":
                await self.handle_application_status(item)

            elif event == "settings_updated":
                await self.handle_settings_updated(item)

            elif event == "send_embed":
                await self.handle_send_embed(item)

            elif event == "apply_bot_profile":
                await self.handle_apply_bot_profile(item)

    async def get_guild(self, guild_id=None):
        if guild_id:
            guild = self.bot.get_guild(int(guild_id))
            if guild:
                return guild
            try:
                return await self.bot.fetch_guild(int(guild_id))
            except Exception:
                return None

        if self.bot.guilds:
            return self.bot.guilds[0]

        return None

    # =========================
    # DASHBOARD -> DISCORD
    # =========================

    async def handle_application_status(self, item):
        print("=== SYNC APPLICATION STATUS RECEBIDO ===", flush=True)
        print(f"Log ID: {item['id']}", flush=True)
        print(f"Payload bruto: {item['payload']}", flush=True)

        try:
            payload = json.loads(item["payload"])
        except Exception as e:
            print(f"❌ Erro ao ler payload do log: {e}", flush=True)
            return

        app_id = payload.get("id")
        status = payload.get("status")

        print(f"Application ID: {app_id}", flush=True)
        print(f"Status recebido do dashboard: {status}", flush=True)

        application = await row("SELECT * FROM applications WHERE id=?", (app_id,))

        if not application:
            print(f"❌ Aplicação #{app_id} não encontrada.", flush=True)
            return

        guild_id = (
            application.get("guild_id")
            or payload.get("guild_id")
            or item.get("guild_id")
        )

        guild = await self.get_guild(guild_id)

        if not guild:
            print("❌ Guild não encontrada no sync.", flush=True)
            return

        member_id = int(application["discord_id"])
        member = guild.get_member(member_id)

        if not member:
            try:
                member = await guild.fetch_member(member_id)
            except Exception as e:
                print(f"❌ Não consegui buscar membro {member_id}: {e}", flush=True)
                member = None

        cfg = await settings(guild.id)

        try:
            answers = json.loads(application["answers"] or "[]")
        except Exception as e:
            print(
                f"❌ Erro ao carregar answers da application #{app_id}: {e}",
                flush=True,
            )
            answers = []

        print(f"Answers carregadas no sync: {answers}", flush=True)

        role = None
        footer = "Nuxora • Allowlist"

        if status == "approved":
            role_id = int(cfg.get("approved_role_id", "0") or 0)
            role = guild.get_role(role_id)

            title = cfg.get("allowlist_approved_title") or "✅ Allowlist aprovada"
            desc = (
                cfg.get("allowlist_approved_description")
                or "Parabéns, {user}! Sua allowlist foi aprovada."
            )
            color = discord.Color(
                parse_hex_color(cfg.get("allowlist_approved_color"), 0x2ECC71)
            )
            footer = cfg.get("allowlist_approved_footer") or "Nuxora • Allowlist"

        elif status == "interview":
            role_id = int(cfg.get("interview_role_id", "0") or 0)
            role = guild.get_role(role_id)

            title = (
                cfg.get("allowlist_interview_title") or "🎤 Encaminhado para entrevista"
            )
            desc = (
                cfg.get("allowlist_interview_description")
                or "{user}, sua allowlist foi analisada e você foi chamado para entrevista."
            )
            color = discord.Color(
                parse_hex_color(cfg.get("allowlist_interview_color"), 0x5865F2)
            )
            footer = cfg.get("allowlist_interview_footer") or "Nuxora • Allowlist"

        elif status == "rejected":
            title = cfg.get("allowlist_rejected_title") or "❌ Allowlist reprovada"
            desc = (
                cfg.get("allowlist_rejected_description")
                or "{user}, sua allowlist foi analisada e foi reprovada."
            )
            color = discord.Color(
                parse_hex_color(cfg.get("allowlist_rejected_color"), 0xE74C3C)
            )
            footer = cfg.get("allowlist_rejected_footer") or "Nuxora • Allowlist"

        else:
            print(f"⚠️ Status ignorado no sync: {status}", flush=True)
            return

        title = format_allowlist_text(title, member, application, answers)
        desc = format_allowlist_text(desc, member, application, answers)
        footer = format_allowlist_text(footer, member, application, answers)

        if member and status == "approved":
            print("=== ALTERANDO NICKNAME ANTES DO CARGO VIA DASHBOARD ===", flush=True)

            await change_member_nickname(
                member=member,
                answers=answers,
                reason="Allowlist aprovada via dashboard: primeira resposta usada como nome",
            )

            remove_roles_raw = str(
                cfg.get("remove_role_on_approved_id", "") or ""
            ).strip()

            if remove_roles_raw:
                roles_to_remove = []

                for rid in [
                    x.strip()
                    for x in remove_roles_raw.split(",")
                    if x.strip().isdigit()
                ]:
                    role_to_remove = guild.get_role(int(rid))

                    if role_to_remove:
                        roles_to_remove.append(role_to_remove)

                if roles_to_remove:
                    try:
                        await member.remove_roles(
                            *roles_to_remove,
                            reason="Allowlist aprovada via dashboard: removendo cargos anteriores",
                        )
                        print(
                            "✅ Cargos removidos via dashboard ao aprovar", flush=True
                        )
                    except Exception as e:
                        print(
                            f"❌ Erro ao remover cargos via dashboard: {e}",
                            flush=True,
                        )

        if member and role:
            try:
                await member.add_roles(
                    role,
                    reason=f"Allowlist via dashboard: {status}",
                )
                print(
                    f"✅ Cargo adicionado via dashboard: {role.name} / {role.id}",
                    flush=True,
                )

            except Exception as e:
                print(f"❌ Erro ao adicionar cargo via dashboard: {e}", flush=True)

        elif member and status in ["approved", "interview"]:
            print(f"⚠️ Cargo não encontrado para status {status}.", flush=True)

        result_embed = discord.Embed(title=title, description=desc, color=color)

        if footer:
            result_embed.set_footer(text=footer)

        if member:
            result_embed.add_field(name="Usuário", value=member.mention, inline=False)

            await send_allowlist_result_channel(
                guild=guild,
                member=member,
                status=status,
                answers=answers,
                cfg=cfg,
            )

            try:
                await member.send(embed=result_embed)
            except Exception:
                pass

        await self.lock_staff_message(
            application=application,
            status=status,
            title=title,
            color=color,
            guild=guild,
        )

        await log(
            "discord_synced_application",
            {"application_id": app_id, "status": status, "member_id": member_id},
        )

        print(
            f"✅ Dashboard -> Discord sincronizado: application #{app_id} -> {status}",
            flush=True,
        )

    # =========================
    # BLOQUEAR MENSAGEM DA STAFF
    # =========================

    async def lock_staff_message(self, application, status, title, color, guild):
        cfg = await settings(guild.id)

        staff_channel_id = int(cfg.get("staff_channel_id", "0") or 0)
        staff_message_id = parse_staff_message_id(application.get("staff_note"))

        if not staff_channel_id or not staff_message_id:
            print(
                f"⚠️ Não consegui bloquear mensagem da staff da application #{application['id']}: "
                "staff_channel_id ou staff_message_id ausente.",
                flush=True,
            )
            return

        channel = guild.get_channel(staff_channel_id)

        if not channel:
            try:
                channel = await guild.fetch_channel(staff_channel_id)
            except Exception as e:
                print(f"❌ Canal da staff não encontrado: {e}", flush=True)
                channel = None

        if not channel:
            print("❌ Canal da staff não encontrado.", flush=True)
            return

        try:
            message = await channel.fetch_message(staff_message_id)
        except Exception as e:
            print(f"❌ Mensagem da staff não encontrada: {e}", flush=True)
            return

        old_embed = message.embeds[0] if message.embeds else None

        if old_embed:
            embed = old_embed.copy()
            embed.title = f"{old_embed.title or 'Allowlist'} — {status.upper()}"
            embed.color = color
            embed.add_field(
                name="Resultado definido pelo dashboard",
                value=f"**{title}**",
                inline=False,
            )
        else:
            embed = discord.Embed(
                title=f"Allowlist #{application['id']} — {status.upper()}",
                description=f"Resultado definido pelo dashboard: **{title}**",
                color=color,
            )

        try:
            await message.edit(embed=embed, view=None)
            print(
                f"✅ Mensagem da staff bloqueada: application #{application['id']}",
                flush=True,
            )

        except Exception as e:
            print(f"❌ Erro ao editar mensagem da staff: {e}", flush=True)

    # =========================
    # EMBED DASHBOARD -> DISCORD
    # =========================

    async def handle_send_embed(self, item):
        print("=== SYNC SEND EMBED RECEBIDO ===", flush=True)

        try:
            payload = json.loads(item.get("payload") or "{}")
        except Exception as e:
            print(f"❌ Erro ao ler payload do embed: {e}", flush=True)
            return

        guild_id = str(payload.get("guild_id") or item.get("guild_id") or "")
        channel_id_raw = str(payload.get("channel_id") or "")

        if not guild_id.isdigit() or not channel_id_raw.isdigit():
            print(
                f"❌ Payload inválido para embed: guild_id={guild_id} channel_id={channel_id_raw}",
                flush=True,
            )
            return

        guild = await self.get_guild(guild_id)

        if not guild:
            print(f"❌ Guild não encontrada para embed: {guild_id}", flush=True)
            return

        channel_id = int(channel_id_raw)
        channel = guild.get_channel(channel_id)

        if not channel:
            try:
                channel = await guild.fetch_channel(channel_id)
            except Exception as e:
                print(
                    f"❌ Canal não encontrado para embed: {channel_id} / {e}",
                    flush=True,
                )
                channel = None

        if not channel:
            return

        color_raw = str(payload.get("color") or "#8B0000").replace("#", "").strip()

        try:
            color = int(color_raw, 16)
        except Exception:
            color = 0x8B0000

        embed = discord.Embed(
            title=str(payload.get("title") or ""),
            description=str(payload.get("description") or ""),
            color=color,
        )

        footer = str(payload.get("footer") or "").strip()
        image_url = str(payload.get("image_url") or "").strip()
        thumbnail_url = str(payload.get("thumbnail_url") or "").strip()

        if footer:
            embed.set_footer(text=footer)

        if image_url:
            embed.set_image(url=image_url)

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        try:
            await channel.send(embed=embed)
            print(f"✅ Embed enviado pelo painel no canal {channel_id}", flush=True)
        except Exception as e:
            print(f"❌ Erro ao enviar embed pelo painel: {e}", flush=True)

    # =========================
    # BOT PROFILE DASHBOARD -> DISCORD
    # =========================

    async def handle_apply_bot_profile(self, item):
        print("=== SYNC APPLY BOT PROFILE RECEBIDO ===", flush=True)

        try:
            payload = json.loads(item.get("payload") or "{}")
        except Exception as e:
            print(f"❌ Erro ao ler payload apply_bot_profile: {e}", flush=True)
            return

        guild_id = str(payload.get("guild_id") or item.get("guild_id") or "")

        if not guild_id.isdigit():
            print(f"❌ Guild ID inválido no apply_bot_profile: {guild_id}", flush=True)
            return

        guild = await self.get_guild(guild_id)

        if not guild:
            print(f"❌ Guild não encontrada para perfil do bot: {guild_id}", flush=True)
            return

        cfg = await settings(guild.id)

        nick = str(cfg.get("bot_profile_nick") or "").strip()
        avatar_url = str(cfg.get("bot_profile_avatar_url") or "").strip()
        banner_url = str(cfg.get("bot_profile_banner_url") or "").strip()
        bio = str(cfg.get("bot_profile_bio") or "").strip()

        body = {}

        if nick:
            body["nick"] = nick[:32]

        avatar_data = await url_to_data_uri(avatar_url)
        banner_data = await url_to_data_uri(banner_url)

        if avatar_data:
            body["avatar"] = avatar_data

        if banner_data:
            body["banner"] = banner_data

        if bio:
            body["bio"] = bio[:190]

        if not body:
            print("⚠️ Nenhum campo de perfil preenchido para aplicar.", flush=True)
            return

        url = f"https://discord.com/api/v10/guilds/{guild.id}/members/@me"

        headers = {
            "Authorization": f"Bot {self.bot.http.token}",
            "Content-Type": "application/json",
        }

        print(
            f"Aplicando perfil do bot na guild {guild.name} / {guild.id}: campos={list(body.keys())}",
            flush=True,
        )

        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=body) as resp:
                text = await resp.text()

                print(
                    f"Resposta Discord apply_bot_profile: HTTP {resp.status} / {text}",
                    flush=True,
                )

                if resp.status not in [200, 204]:
                    print("❌ Discord recusou alteração do perfil do bot.", flush=True)
                    return

        print(
            f"✅ Perfil do bot aplicado na guild {guild.name} / {guild.id}",
            flush=True,
        )

    # =========================
    # SETTINGS -> DISCORD
    # =========================

    async def handle_settings_updated(self, item):
        print("=== SYNC SETTINGS UPDATED RECEBIDO ===", flush=True)

        payload = {}

        try:
            payload = json.loads(item.get("payload") or "{}")
        except Exception:
            payload = {}

        guild_id = payload.get("guild_id") or item.get("guild_id")
        guild = await self.get_guild(guild_id)

        if not guild:
            print("❌ Guild não encontrada para atualizar painel.", flush=True)
            return

        cfg = await settings(guild.id)

        channel_id = int(cfg.get("allowlist_panel_channel_id", "0") or 0)
        message_id = int(cfg.get("allowlist_panel_message_id", "0") or 0)

        if not channel_id or not message_id:
            print(
                "⚠️ Painel de allowlist ainda não foi vinculado. "
                "Use /painel_allowlist novamente.",
                flush=True,
            )
            return

        channel = guild.get_channel(channel_id)

        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                print(f"❌ Canal do painel não encontrado: {e}", flush=True)
                channel = None

        if not channel:
            print("❌ Canal do painel não encontrado.", flush=True)
            return

        try:
            message = await channel.fetch_message(message_id)
        except Exception as e:
            print(f"❌ Mensagem do painel não encontrada: {e}", flush=True)
            return

        embed = await build_allowlist_panel_embed(guild.id)

        try:
            await message.edit(embed=embed, view=AllowlistStartView())

            print("✅ Painel de allowlist atualizado no Discord.", flush=True)

        except Exception as e:
            print(f"❌ Erro ao atualizar painel: {e}", flush=True)


async def setup(bot):
    await bot.add_cog(DashboardSync(bot))
