import json
import discord
from discord.ext import commands, tasks

from shared.db import rows, row, settings, log
from modules.allowlist import (
    AllowlistStartView,
    build_allowlist_panel_embed,
)


# =========================
# HELPERS
# =========================

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
        print("❌ Nickname dashboard não alterado: lista de respostas vazia.", flush=True)
        return None

    first_answer = str(answers[0].get("answer", "")).strip()

    if not first_answer:
        print("❌ Nickname dashboard não alterado: primeira resposta vazia.", flush=True)
        return None

    nickname = first_answer.splitlines()[0].strip()

    if not nickname:
        print("❌ Nickname dashboard não alterado: nickname vazio após limpeza.", flush=True)
        return None

    return nickname[:32]


async def change_member_nickname(
    member: discord.Member,
    answers: list[dict],
    reason: str
):
    print("=== TENTANDO ALTERAR NICKNAME PELO DASHBOARD ===", flush=True)
    print(f"Usuário alvo: {member} / {member.id}", flush=True)
    print(f"Primeira resposta: {answers[0] if answers else 'SEM RESPOSTAS'}", flush=True)

    nickname = get_nickname_from_answers(answers)

    print(f"Nickname detectado: {nickname}", flush=True)

    if not nickname:
        return False

    try:
        await member.edit(
            nick=nickname,
            reason=reason
        )

        print(f"✅ Nickname alterado com sucesso via dashboard: {member.id} -> {nickname}", flush=True)
        return True

    except discord.Forbidden:
        print(
            "❌ Sem permissão/hierarquia para alterar nickname via dashboard. "
            "Mesmo com Administrator, o cargo do bot precisa estar acima do cargo mais alto do usuário.",
            flush=True
        )
        return False

    except discord.HTTPException as e:
        print(f"❌ Erro HTTP ao alterar nickname via dashboard: {e}", flush=True)
        return False

    except Exception as e:
        print(f"❌ Erro inesperado ao alterar nickname via dashboard: {e}", flush=True)
        return False

async def send_allowlist_result_channel(
    guild: discord.Guild,
    member: discord.Member,
    status: str,
    answers: list[dict],
    cfg: dict
):
    if status == "approved":
        channel_id = int(cfg.get("approved_channel_id", "0") or 0)
        title = "✅ Allowlist aprovada"
        description = f"{member.mention} foi aprovado na allowlist!"
        color = discord.Color.green()

    elif status == "rejected":
        channel_id = int(cfg.get("rejected_channel_id", "0") or 0)
        title = "❌ Allowlist reprovada"
        description = f"{member.mention} foi reprovado na allowlist."
        color = discord.Color.red()

    else:
        return

    if not channel_id:
        print(f"Canal público de resultado não configurado para status: {status}", flush=True)
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

    character_name = None

    if answers and answers[0].get("answer"):
        character_name = str(answers[0]["answer"]).strip().splitlines()[0][:64]

    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )

    if character_name:
        embed.add_field(
            name="Personagem",
            value=character_name,
            inline=False
        )

    embed.add_field(
        name="Usuário",
        value=f"{member.mention} (`{member.id}`)",
        inline=False
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="NightFall • Allowlist")

    try:
        await channel.send(embed=embed)
        print(f"✅ Resultado público enviado via dashboard para canal {channel_id}: {status}", flush=True)
    except Exception as e:
        print(f"❌ Erro ao enviar resultado público via dashboard: {e}", flush=True)
# =========================
# SYNC COG
# =========================

class DashboardSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_log_id = 0
        print("✅ DashboardSync cog inicializado", flush=True)
        self.sync_dashboard.start()

    def cog_unload(self):
        self.sync_dashboard.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        latest = await row(
            "SELECT id FROM logs ORDER BY id DESC LIMIT 1"
        )

        self.last_log_id = latest["id"] if latest else 0

        print("=== DASHBOARD SYNC ON_READY ===", flush=True)
        print(f"Último log conhecido: {self.last_log_id}", flush=True)

    @tasks.loop(seconds=3)
    async def sync_dashboard(self):
        if not self.bot.is_ready():
            return

        logs = await rows(
            """
            SELECT *
            FROM logs
            WHERE id > ?
            ORDER BY id ASC
            """,
            (self.last_log_id,)
        )

        if not logs:
            return

        print(f"=== SYNC ENCONTROU {len(logs)} LOG(S) NOVO(S) ===", flush=True)

        for item in logs:
            self.last_log_id = item["id"]

            event = item["event"]

            print(f"Log #{item['id']} event={event}", flush=True)

            if event == "application_status":
                await self.handle_application_status(item)

            elif event == "settings_updated":
                await self.handle_settings_updated(item)

    async def get_guild(self):
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

        application = await row(
            "SELECT * FROM applications WHERE id=?",
            (app_id,)
        )

        if not application:
            print(f"❌ Aplicação #{app_id} não encontrada.", flush=True)
            return

        guild = await self.get_guild()

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

        cfg = await settings()

        role = None
        title = None
        desc = None
        color = None

        if status == "approved":
            role_id = int(cfg.get("approved_role_id", "0") or 0)
            role = guild.get_role(role_id)

            title = "✅ Allowlist aprovada"
            desc = "Parabéns! Sua allowlist foi aprovada."
            color = discord.Color.green()

        elif status == "interview":
            role_id = int(cfg.get("interview_role_id", "0") or 0)
            role = guild.get_role(role_id)

            title = "🎤 Encaminhado para entrevista"
            desc = "Sua allowlist foi analisada e você foi chamado para entrevista."
            color = discord.Color.blurple()

        elif status == "rejected":
            title = "❌ Allowlist reprovada"
            desc = "Sua allowlist foi analisada e foi reprovada."
            color = discord.Color.red()

        else:
            print(f"⚠️ Status ignorado no sync: {status}", flush=True)
            return

        try:
            answers = json.loads(application["answers"] or "[]")
        except Exception as e:
            print(f"❌ Erro ao carregar answers da application #{app_id}: {e}", flush=True)
            answers = []

        print(f"Answers carregadas no sync: {answers}", flush=True)

        # Primeiro altera nickname, ANTES de adicionar cargo.
        # Primeiro altera nickname, ANTES de adicionar cargo.
        # Primeiro altera nickname, ANTES de adicionar cargo.
        if member and status == "approved":
            print("=== ALTERANDO NICKNAME ANTES DO CARGO VIA DASHBOARD ===", flush=True)

            await change_member_nickname(
                member=member,
                answers=answers,
                reason="Allowlist aprovada via dashboard: primeira resposta usada como nome"
            )

            # Remove cargo antigo ao aprovar, se configurado.
            remove_role_id = int(cfg.get("remove_role_on_approved_id", "0") or 0)

            if remove_role_id:
                remove_role = guild.get_role(remove_role_id)

                if remove_role:
                    try:
                        await member.remove_roles(
                            remove_role,
                            reason="Allowlist aprovada via dashboard: removendo cargo anterior"
                        )
                        print(
                            f"✅ Cargo removido via dashboard ao aprovar: {remove_role.name} / {remove_role.id}",
                            flush=True
                        )
                    except Exception as e:
                        print(f"❌ Erro ao remover cargo via dashboard: {e}", flush=True)
                else:
                    print(
                        f"⚠️ Cargo para remover via dashboard não encontrado: {remove_role_id}",
                        flush=True
                    )

        # Depois adiciona cargo.
        if member and role:
            try:
                await member.add_roles(
                    role,
                    reason=f"Allowlist via dashboard: {status}"
                )
                print(f"✅ Cargo adicionado via dashboard: {role.name} / {role.id}", flush=True)

            except Exception as e:
                print(f"❌ Erro ao adicionar cargo via dashboard: {e}", flush=True)

        elif member and status in ["approved", "interview"]:
            print(f"⚠️ Cargo não encontrado para status {status}.", flush=True)

        result_embed = discord.Embed(
            title=title,
            description=desc,
            color=color
        )

        if member:
            result_embed.add_field(
                name="Usuário",
                value=member.mention,
                inline=False
            )

            await send_allowlist_result_channel(
                guild=guild,
                member=member,
                status=status,
                answers=answers,
                cfg=cfg
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
            guild=guild
        )

        await log("discord_synced_application", {
            "application_id": app_id,
            "status": status,
            "member_id": member_id
        })

        print(f"✅ Dashboard -> Discord sincronizado: application #{app_id} -> {status}", flush=True)

    # =========================
    # BLOQUEAR MENSAGEM DA STAFF
    # =========================

    async def lock_staff_message(self, application, status, title, color, guild):
        cfg = await settings()

        staff_channel_id = int(cfg.get("staff_channel_id", "0") or 0)
        staff_message_id = parse_staff_message_id(application.get("staff_note"))

        if not staff_channel_id or not staff_message_id:
            print(
                f"⚠️ Não consegui bloquear mensagem da staff da application #{application['id']}: "
                "staff_channel_id ou staff_message_id ausente.",
                flush=True
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
                inline=False
            )
        else:
            embed = discord.Embed(
                title=f"Allowlist #{application['id']} — {status.upper()}",
                description=f"Resultado definido pelo dashboard: **{title}**",
                color=color
            )

        try:
            await message.edit(embed=embed, view=None)
            print(f"✅ Mensagem da staff bloqueada: application #{application['id']}", flush=True)

        except Exception as e:
            print(f"❌ Erro ao editar mensagem da staff: {e}", flush=True)

    # =========================
    # SETTINGS -> DISCORD
    # =========================

    async def handle_settings_updated(self, item):
        print("=== SYNC SETTINGS UPDATED RECEBIDO ===", flush=True)

        cfg = await settings()

        channel_id = int(cfg.get("allowlist_panel_channel_id", "0") or 0)
        message_id = int(cfg.get("allowlist_panel_message_id", "0") or 0)

        if not channel_id or not message_id:
            print(
                "⚠️ Painel de allowlist ainda não foi vinculado. "
                "Use /painel_allowlist novamente.",
                flush=True
            )
            return

        channel = self.bot.get_channel(channel_id)

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

        embed = await build_allowlist_panel_embed()

        try:
            await message.edit(
                embed=embed,
                view=AllowlistStartView()
            )

            print("✅ Painel de allowlist atualizado no Discord.", flush=True)

        except Exception as e:
            print(f"❌ Erro ao atualizar painel: {e}", flush=True)


async def setup(bot):
    await bot.add_cog(DashboardSync(bot))
