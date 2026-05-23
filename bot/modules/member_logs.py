import os
import discord
from discord.ext import commands
from discord import app_commands

from shared.db import settings, execute, log

GUILD_ID = int(os.getenv("GUILD_ID", "0"))


async def save_setting(key: str, value: str):
    await execute(
        """
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (key, str(value))
    )


def parse_color(hex_color: str, default: int):
    try:
        return int(str(hex_color).replace("#", ""), 16)
    except Exception:
        return default


async def get_channel_by_setting(guild: discord.Guild, primary_key: str):
    cfg = await settings()

    channel_id = int(
        cfg.get(primary_key)
        or cfg.get("logs_channel_id")
        or os.getenv("LOGS_CHANNEL_ID", "0")
        or 0
    )

    if not channel_id:
        return None

    return guild.get_channel(channel_id)


def account_created_text(member: discord.Member):
    return (
        f"{discord.utils.format_dt(member.created_at, style='F')}\n"
        f"{discord.utils.format_dt(member.created_at, style='R')}"
    )


def joined_text(member: discord.Member):
    if not member.joined_at:
        return "Desconhecido"

    return (
        f"{discord.utils.format_dt(member.joined_at, style='F')}\n"
        f"{discord.utils.format_dt(member.joined_at, style='R')}"
    )


def replace_vars(text: str, member: discord.Member):
    if not text:
        return ""

    return (
        text
        .replace("{user}", member.mention)
        .replace("{username}", str(member))
        .replace("{display_name}", member.display_name)
        .replace("{id}", str(member.id))
        .replace("{server}", member.guild.name)
        .replace("{member_count}", str(member.guild.member_count))
    )


class MemberLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ MemberLogs cog inicializado", flush=True)

    async def build_join_embed(self, member: discord.Member):
        cfg = await settings()

        title = cfg.get("member_join_title", "👋 Bem-vindo(a) ao NightFall")
        description = cfg.get(
            "member_join_description",
            (
                "As sombras observam sua chegada.\n\n"
                "{user}, acaba de atravessar os portões de {server} e agora faz parte "
                "de um mundo marcado por sangue, guerra e segredos antigos.\n\n"
                "Que sua história seja lembrada... ou enterrada nas trevas do Eclipse Eterno."
            )
        )
        footer = cfg.get("member_join_footer", "NightFall • Boas-vindas")
        color = parse_color(cfg.get("member_join_color", "#8B0000"), 0x8B0000)

        embed = discord.Embed(
            title=replace_vars(title, member),
            description=replace_vars(description, member),
            color=color
        )

        # embed.add_field(name="Usuário", value=f"{member} (`{member.id}`)", inline=False)
        # embed.add_field(name="Conta criada", value=account_created_text(member), inline=False)
        # embed.add_field(name="Total de membros", value=str(member.guild.member_count), inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)

        if footer:
            embed.set_footer(text=replace_vars(footer, member))

        image_url = cfg.get("member_join_image_url", "")
        if image_url:
            embed.set_image(url=image_url)

        return embed

    async def build_leave_embed(self, member: discord.Member):
        cfg = await settings()

        title = cfg.get("member_leave_title", "📤 Membro saiu")
        description = cfg.get(
            "member_leave_description",
            "**{username}** deixou {server}.\n\nAs sombras registram sua partida."
        )
        footer = cfg.get("member_leave_footer", "NightFall • Saídas")
        color = parse_color(cfg.get("member_leave_color", "#8B0000"), 0x8B0000)

        embed = discord.Embed(
            title=replace_vars(title, member),
            description=replace_vars(description, member),
            color=color
        )

        embed.add_field(name="Usuário", value=f"{member} (`{member.id}`)", inline=False)
        embed.add_field(name="Conta criada", value=account_created_text(member), inline=False)
        embed.add_field(name="Entrou no servidor", value=joined_text(member), inline=False)
        embed.add_field(name="Total de membros", value=str(member.guild.member_count), inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)

        if footer:
            embed.set_footer(text=replace_vars(footer, member))

        image_url = cfg.get("member_leave_image_url", "")
        if image_url:
            embed.set_image(url=image_url)

        return embed

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        print("=== LOG ENTRADA ===", flush=True)
        print(f"Membro entrou: {member} / {member.id}", flush=True)

        channel = await get_channel_by_setting(member.guild, "member_join_channel_id")

        if not channel:
            print("Canal de log de entrada não configurado.", flush=True)
            return

        embed = await self.build_join_embed(member)
        await channel.send(embed=embed)

        await log("member_join", {
            "member_id": member.id,
            "member_name": str(member)
        })

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        print("=== LOG SAÍDA ===", flush=True)
        print(f"Membro saiu: {member} / {member.id}", flush=True)

        channel = await get_channel_by_setting(member.guild, "member_leave_channel_id")

        if not channel:
            print("Canal de log de saída não configurado.", flush=True)
            return

        embed = await self.build_leave_embed(member)
        await channel.send(embed=embed)

        await log("member_leave", {
            "member_id": member.id,
            "member_name": str(member)
        })

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="memberlog_config", description="Configura canais de entrada e saída")
    @app_commands.default_permissions(manage_guild=True)
    async def memberlog_config(
        self,
        interaction: discord.Interaction,
        canal_entrada: discord.TextChannel | None = None,
        canal_saida: discord.TextChannel | None = None,
        desativar_entrada: bool = False,
        desativar_saida: bool = False
    ):
        changes = []

        if desativar_entrada:
            await save_setting("member_join_channel_id", "0")
            changes.append("entrada desativada")

        if desativar_saida:
            await save_setting("member_leave_channel_id", "0")
            changes.append("saída desativada")

        if canal_entrada:
            await save_setting("member_join_channel_id", str(canal_entrada.id))
            changes.append(f"entrada: {canal_entrada.mention}")

        if canal_saida:
            await save_setting("member_leave_channel_id", str(canal_saida.id))
            changes.append(f"saída: {canal_saida.mention}")

        if not changes:
            cfg = await settings()
            entrada = cfg.get("member_join_channel_id") or cfg.get("logs_channel_id") or "0"
            saida = cfg.get("member_leave_channel_id") or cfg.get("logs_channel_id") or "0"

            await interaction.response.send_message(
                f"Configuração atual:\nEntrada: `{entrada}`\nSaída: `{saida}`",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "✅ Logs de membros atualizados:\n" + "\n".join(changes),
            ephemeral=True
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="memberlog_embed", description="Configura embed de entrada ou saída")
    @app_commands.default_permissions(manage_guild=True)
    async def memberlog_embed(
        self,
        interaction: discord.Interaction,
        tipo: str,
        titulo: str | None = None,
        descricao: str | None = None,
        footer: str | None = None,
        cor_hex: str | None = None,
        imagem_url: str | None = None
    ):
        tipo = tipo.lower().strip()

        if tipo not in ["entrada", "saida", "saída"]:
            await interaction.response.send_message("❌ Tipo inválido. Use `entrada` ou `saida`.", ephemeral=True)
            return

        prefix = "member_join" if tipo == "entrada" else "member_leave"
        changes = []

        if titulo is not None:
            await save_setting(f"{prefix}_title", titulo)
            changes.append("título")

        if descricao is not None:
            await save_setting(f"{prefix}_description", descricao)
            changes.append("descrição")

        if footer is not None:
            await save_setting(f"{prefix}_footer", footer)
            changes.append("footer")

        if cor_hex is not None:
            await save_setting(f"{prefix}_color", cor_hex)
            changes.append("cor")

        if imagem_url is not None:
            await save_setting(f"{prefix}_image_url", imagem_url)
            changes.append("imagem")

        await interaction.response.send_message(
            "✅ Embed de log atualizada: " + (", ".join(changes) if changes else "nada alterado."),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(MemberLogs(bot))
