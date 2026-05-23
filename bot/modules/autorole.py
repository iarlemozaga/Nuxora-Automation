import os
import discord
from discord.ext import commands
from discord import app_commands

from shared.db import settings, execute, log

GUILD_ID = int(os.getenv("GUILD_ID", "0"))


async def save_setting(key: str, value: str):
    await execute(
        '''
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        ''',
        (key, str(value))
    )


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ AutoRole cog inicializado")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        print("=== AUTOROLE: NOVO MEMBRO ===")
        print(f"Membro: {member} / {member.id}")

        cfg = await settings()

        role_id = int(
            cfg.get("autorole_role_id")
            or os.getenv("AUTOROLE_ROLE_ID", "0")
            or 0
        )

        print(f"Autorole configurado: {role_id}")

        if not role_id:
            print("Autorole ignorado: nenhum cargo configurado.")
            return

        role = member.guild.get_role(role_id)

        if not role:
            print(f"Autorole ignorado: cargo {role_id} não encontrado.")
            return

        try:
            await member.add_roles(
                role,
                reason="Autorole automático ao entrar no servidor"
            )

            print(f"✅ Autorole aplicado: {member.id} -> {role.name} / {role.id}")

            await log("autorole_applied", {
                "member_id": member.id,
                "role_id": role.id
            })

        except discord.Forbidden:
            print(
                "❌ Sem permissão/hierarquia para aplicar autorole. "
                "Coloque o cargo do bot acima do cargo que será aplicado."
            )

        except Exception as e:
            print(f"❌ Erro ao aplicar autorole: {e}")

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="autorole_config",
        description="Configura o cargo automático para novos membros"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def autorole_config(
        self,
        interaction: discord.Interaction,
        cargo: discord.Role | None = None,
        desativar: bool = False
    ):
        if desativar:
            await save_setting("autorole_role_id", "0")

            await interaction.response.send_message(
                "✅ Autorole desativado.",
                ephemeral=True
            )
            return

        if cargo is None:
            cfg = await settings()
            current = cfg.get("autorole_role_id", "0")

            await interaction.response.send_message(
                f"Cargo atual do autorole: `{current}`",
                ephemeral=True
            )
            return

        await save_setting("autorole_role_id", str(cargo.id))

        await interaction.response.send_message(
            f"✅ Autorole configurado para {cargo.mention}.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AutoRole(bot))
