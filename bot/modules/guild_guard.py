import discord
from discord.ext import commands, tasks

from shared.db import row


class GuildGuard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ GuildGuard inicializado", flush=True)
        self.guard_loop.start()

    def cog_unload(self):
        self.guard_loop.cancel()

    async def get_guild_record(self, guild_id: int | str):
        return await row(
            """
            SELECT guild_id, guild_name, status
            FROM customer_guilds
            WHERE guild_id=?
            LIMIT 1
            """,
            (str(guild_id),),
        )

    async def notify_owner(self, guild: discord.Guild, message: str):
        try:
            owner = guild.owner

            if not owner:
                try:
                    owner = await guild.fetch_member(guild.owner_id)
                except Exception:
                    owner = None

            if owner:
                try:
                    await owner.send(message)
                except Exception:
                    pass

        except Exception:
            pass

    async def check_guild(self, guild: discord.Guild):
        record = await self.get_guild_record(guild.id)

        # Não existe no painel/admin: sai do servidor
        if not record:
            print(
                f"⛔ Servidor NÃO vinculado. Saindo: {guild.name} / {guild.id}",
                flush=True,
            )

            await self.notify_owner(
                guild,
                "⛔ Este servidor não está vinculado no painel Nuxora. "
                "O bot saiu automaticamente. Fale com o administrador do serviço.",
            )

            try:
                await guild.leave()
            except Exception as e:
                print(
                    f"❌ Erro ao sair do servidor não vinculado {guild.name} / {guild.id}: {e}",
                    flush=True,
                )

            return

        status = str(record.get("status") or "").lower().strip()

        # Servidor ativo: funciona normalmente
        if status == "active":
            print(
                f"✅ Servidor autorizado: {guild.name} / {guild.id}",
                flush=True,
            )
            return

        # Servidor bloqueado: permanece no servidor, mas o resto do bot ignora ações
        if status == "blocked":
            print(
                f"🔒 Servidor vinculado, mas BLOQUEADO. Bot permanecerá sem responder: "
                f"{guild.name} / {guild.id}",
                flush=True,
            )
            return

        # Qualquer status estranho: por segurança, sai
        print(
            f"⛔ Servidor com status inválido ({status}). Saindo: {guild.name} / {guild.id}",
            flush=True,
        )

        await self.notify_owner(
            guild,
            "⛔ Este servidor está com status inválido no painel Nuxora. "
            "O bot saiu automaticamente. Fale com o administrador do serviço.",
        )

        try:
            await guild.leave()
        except Exception as e:
            print(
                f"❌ Erro ao sair do servidor com status inválido {guild.name} / {guild.id}: {e}",
                flush=True,
            )

    @commands.Cog.listener()
    async def on_ready(self):
        print("=== GUILD GUARD ON_READY ===", flush=True)

        for guild in list(self.bot.guilds):
            await self.check_guild(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        print(
            f"=== BOT ADICIONADO EM SERVIDOR: {guild.name} / {guild.id} ===",
            flush=True,
        )

        await self.check_guild(guild)

    @tasks.loop(seconds=60)
    async def guard_loop(self):
        if not self.bot.is_ready():
            return

        for guild in list(self.bot.guilds):
            await self.check_guild(guild)

    @guard_loop.before_loop
    async def before_guard_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(GuildGuard(bot))
