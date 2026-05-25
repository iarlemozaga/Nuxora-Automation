import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from shared.db import init_db
from shared.guard import is_guild_active

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN não configurado no .env")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# BLOQUEIO GLOBAL POR STATUS DO SERVIDOR
# =========================


@bot.check
async def global_prefix_check(ctx):
    if not ctx.guild:
        return True

    allowed = await is_guild_active(ctx.guild.id)

    if not allowed:
        try:
            await ctx.reply(
                "🔒 Este servidor está bloqueado no Nuxora. "
                "Fale com o administrador do serviço.",
                mention_author=False,
            )
        except Exception:
            pass

    return allowed


async def global_interaction_check(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return True

    allowed = await is_guild_active(interaction.guild.id)

    if allowed:
        return True

    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "🔒 Este servidor está bloqueado no Nuxora. "
                "Fale com o administrador do serviço.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "🔒 Este servidor está bloqueado no Nuxora. "
                "Fale com o administrador do serviço.",
                ephemeral=True,
            )
    except Exception:
        pass

    return False


bot.tree.interaction_check = global_interaction_check


# =========================
# EXTENSIONS
# =========================


EXTENSIONS = [
    "modules.allowlist",
    "modules.suggestions",
    "modules.embeds",
    "modules.tickets",
    "modules.autorole",
    "modules.member_logs",
    "modules.guild_guard",
    "modules.live_notifications",
    "modules.sync",
]


async def load_extensions():
    print("=== CARREGANDO EXTENSIONS ===", flush=True)

    loaded = set()

    for ext in EXTENSIONS:
        if ext in loaded:
            print(f"⚠️ Extension duplicada ignorada na lista: {ext}", flush=True)
            continue

        loaded.add(ext)

        if ext in bot.extensions:
            print(f"⚠️ Extension já carregada, ignorando: {ext}", flush=True)
            continue

        try:
            await bot.load_extension(ext)
            print(f"✅ Extension carregada: {ext}", flush=True)

        except commands.ExtensionAlreadyLoaded:
            print(f"⚠️ Extension já estava carregada: {ext}", flush=True)

        except Exception as e:
            print(f"❌ Erro ao carregar extension {ext}: {e}", flush=True)
            raise


# =========================
# EVENTS
# =========================


@bot.event
async def on_guild_join(guild):
    from shared.db import ensure_guild

    await ensure_guild(str(guild.id), guild.name)
    print(f"✅ Guild cadastrada: {guild.name} / {guild.id}", flush=True)


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
    except Exception as e:
        print(f"❌ Erro ao sincronizar slash commands: {e}", flush=True)
        synced = []

    print("=== BOT ONLINE ===", flush=True)
    print(f"Bot: {bot.user}", flush=True)
    print("Slash commands globais sincronizados", flush=True)
    print(f"Comandos sincronizados: {len(synced)}", flush=True)

    for c in synced:
        print(f"/{c.name}", flush=True)


# =========================
# MAIN
# =========================


async def main():
    init_db()

    async with bot:
        await load_extensions()
        await bot.start(TOKEN)


asyncio.run(main())
