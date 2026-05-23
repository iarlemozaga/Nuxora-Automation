import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from shared.db import init_db

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

EXTENSIONS = [
    "modules.allowlist",
    "modules.suggestions",
    "modules.embeds",
    "modules.tickets",
    "modules.autorole",
    "modules.member_logs",
    "modules.sync"
]


async def load_extensions():
    print("=== CARREGANDO EXTENSIONS ===", flush=True)

    for ext in EXTENSIONS:
        try:
            await bot.load_extension(ext)
            print(f"✅ Extension carregada: {ext}", flush=True)
        except Exception as e:
            print(f"❌ Erro ao carregar extension {ext}: {e}", flush=True)
            raise


@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    synced = await bot.tree.sync(guild=guild)

    print("=== BOT ONLINE ===", flush=True)
    print(f"Bot: {bot.user}", flush=True)
    print(f"Guild ID: {GUILD_ID}", flush=True)
    print(f"Comandos sincronizados: {len(synced)}", flush=True)

    for c in synced:
        print(f"/{c.name}", flush=True)


async def main():
    await init_db()

    async with bot:
        await load_extensions()
        await bot.start(TOKEN)


asyncio.run(main())
