import asyncio
import os
from datetime import datetime

import aiohttp
import asyncpg
import discord
from discord.ext import commands, tasks

from shared.guard import is_guild_active

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://nuxora:nuxora_password@nuxora-postgres:5432/nuxora",
)

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "").strip()
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "").strip()
TWITCH_CHECK_INTERVAL_SECONDS = int(
    os.getenv("TWITCH_CHECK_INTERVAL_SECONDS", "300") or 300
)


def utc_now() -> str:
    return datetime.utcnow().isoformat()


def fmt_template(template: str, data: dict) -> str:
    text = str(template or "")

    for key, value in data.items():
        text = text.replace("{" + key + "}", str(value or ""))

    return text


def parse_color(value: str | None) -> int:
    raw = str(value or "#9146FF").replace("#", "").strip()

    try:
        return int(raw, 16)
    except Exception:
        return 0x9146FF


class LiveNotifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch_token = None
        self.twitch_token_ready = asyncio.Lock()

        print("✅ LiveNotifications cog inicializado", flush=True)

        self.check_lives.change_interval(
            seconds=max(60, TWITCH_CHECK_INTERVAL_SECONDS)
        )
        self.check_lives.start()

    def cog_unload(self):
        self.check_lives.cancel()

    async def db_fetch(self, query: str, *args):
        conn = await asyncpg.connect(DATABASE_URL)

        try:
            return await conn.fetch(query, *args)
        finally:
            await conn.close()

    async def db_execute(self, query: str, *args):
        conn = await asyncpg.connect(DATABASE_URL)

        try:
            return await conn.execute(query, *args)
        finally:
            await conn.close()

    async def get_twitch_token(self):
        if self.twitch_token:
            return self.twitch_token

        async with self.twitch_token_ready:
            if self.twitch_token:
                return self.twitch_token

            if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
                print(
                    "⚠️ TWITCH_CLIENT_ID/TWITCH_CLIENT_SECRET não configurados. Lives desativadas.",
                    flush=True,
                )
                return None

            url = "https://id.twitch.tv/oauth2/token"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    params={
                        "client_id": TWITCH_CLIENT_ID,
                        "client_secret": TWITCH_CLIENT_SECRET,
                        "grant_type": "client_credentials",
                    },
                ) as resp:
                    data = await resp.json(content_type=None)

                    if resp.status >= 400:
                        print(
                            f"❌ Erro Twitch token HTTP {resp.status}: {data}",
                            flush=True,
                        )
                        return None

                    self.twitch_token = data.get("access_token")

                    print("✅ Twitch app token obtido.", flush=True)

                    return self.twitch_token

    async def fetch_streams(self, logins: list[str]) -> dict:
        token = await self.get_twitch_token()

        if not token or not logins:
            return {}

        result = {}

        async with aiohttp.ClientSession() as session:
            for i in range(0, len(logins), 100):
                chunk = logins[i : i + 100]
                params = []

                for login in chunk:
                    params.append(("user_login", login))

                async with session.get(
                    "https://api.twitch.tv/helix/streams",
                    params=params,
                    headers={
                        "Client-ID": TWITCH_CLIENT_ID,
                        "Authorization": f"Bearer {token}",
                    },
                ) as resp:
                    data = await resp.json(content_type=None)

                    if resp.status == 401:
                        self.twitch_token = None

                        print(
                            "⚠️ Twitch token expirou. Tentará renovar no próximo ciclo.",
                            flush=True,
                        )

                        return {}

                    if resp.status >= 400:
                        print(
                            f"❌ Erro Twitch streams HTTP {resp.status}: {data}",
                            flush=True,
                        )
                        continue

                    for stream in data.get("data", []):
                        result[str(stream.get("user_login", "")).lower()] = stream

        return result

    async def send_live_notification(self, item, stream):
        guild_id = str(item["guild_id"])
        channel_id = int(str(item["discord_channel_id"]))

        if not await is_guild_active(guild_id):
            print(
                f"🔒 Live notification ignorada: servidor bloqueado ou inativo {guild_id}",
                flush=True,
            )
            return False

        guild = self.bot.get_guild(int(guild_id))

        if not guild:
            try:
                guild = await self.bot.fetch_guild(int(guild_id))
            except Exception as e:
                print(f"❌ Guild não encontrada para live {guild_id}: {e}", flush=True)
                return False

        channel = guild.get_channel(channel_id)

        if not channel:
            try:
                channel = await guild.fetch_channel(channel_id)
            except Exception as e:
                print(f"❌ Canal de live não encontrado {channel_id}: {e}", flush=True)
                return False

        streamer = str(item["streamer_login"]).lower()
        url = f"https://twitch.tv/{streamer}"

        data = {
            "streamer": stream.get("user_name") or streamer,
            "login": streamer,
            "title": stream.get("title") or "",
            "game": stream.get("game_name") or "Sem categoria",
            "url": url,
            "viewers": stream.get("viewer_count") or 0,
        }

        message = fmt_template(item["message"], data).strip()
        embed_title = fmt_template(item["embed_title"], data).strip()
        embed_description = fmt_template(item["embed_description"], data).strip()

        embed = discord.Embed(
            title=embed_title or f"{data['streamer']} está ao vivo!",
            description=embed_description or f"Assista agora: {url}",
            color=parse_color(item["embed_color"]),
            url=url,
        )

        embed.add_field(name="Canal", value=data["streamer"], inline=True)
        embed.add_field(name="Jogo", value=data["game"], inline=True)
        embed.add_field(name="Viewers", value=str(data["viewers"]), inline=True)

        thumb_url = stream.get("thumbnail_url") or ""

        if thumb_url:
            thumb_url = thumb_url.replace("{width}", "1280").replace("{height}", "720")
            embed.set_image(url=f"{thumb_url}?t={int(datetime.utcnow().timestamp())}")

        embed.set_footer(text="Nuxora • Live Notifications")

        try:
            if message:
                await channel.send(content=message, embed=embed)
            else:
                await channel.send(embed=embed)

            print(
                f"✅ Live avisada: {streamer} em {guild.name} / {channel_id}",
                flush=True,
            )

            return True

        except Exception as e:
            print(f"❌ Erro ao enviar aviso de live {streamer}: {e}", flush=True)
            return False

    @tasks.loop(seconds=300)
    async def check_lives(self):
        if not self.bot.is_ready():
            return

        items = await self.db_fetch(
            """
            SELECT *
            FROM live_notifications
            WHERE is_enabled = TRUE
            ORDER BY id ASC
            """
        )

        if not items:
            return

        active_items = []

        for item in items:
            guild_id = str(item["guild_id"])

            if not await is_guild_active(guild_id):
                print(
                    f"🔒 Live notification ignorada: servidor bloqueado ou inativo {guild_id}",
                    flush=True,
                )
                continue

            active_items.append(item)

        if not active_items:
            return

        logins = sorted(
            {str(item["streamer_login"]).lower() for item in active_items}
        )

        streams = await self.fetch_streams(logins)

        for item in active_items:
            notification_id = item["id"]
            streamer = str(item["streamer_login"]).lower()
            stream = streams.get(streamer)

            if stream:
                stream_id = str(stream.get("id") or "")

                already_notified = (
                    bool(item["is_live"])
                    and str(item.get("last_stream_id") or "") == stream_id
                )

                if already_notified:
                    continue

                sent = await self.send_live_notification(item, stream)

                if sent:
                    await self.db_execute(
                        """
                        UPDATE live_notifications
                        SET is_live = TRUE,
                            last_stream_id = $1,
                            last_notified_at = $2,
                            updated_at = $3
                        WHERE id = $4
                        """,
                        stream_id,
                        utc_now(),
                        utc_now(),
                        notification_id,
                    )

            else:
                if item["is_live"]:
                    await self.db_execute(
                        """
                        UPDATE live_notifications
                        SET is_live = FALSE,
                            updated_at = $1
                        WHERE id = $2
                        """,
                        utc_now(),
                        notification_id,
                    )

                    print(f"ℹ️ Live offline: {streamer}", flush=True)

    @check_lives.before_loop
    async def before_check_lives(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(LiveNotifications(bot))
