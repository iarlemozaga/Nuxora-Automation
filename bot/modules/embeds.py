import os

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, Modal, TextInput, View

GUILD_ID = int(os.getenv("GUILD_ID", "0"))

# =========================
# CONFIG FIXA DO EMBED
# =========================

EMBED_COLOR = 0x8B0000

FIXED_FOOTER_TEXT = "NightFall Roleplay • Sistema oficial"
FIXED_FOOTER_ICON = ""  # opcional: coloque uma URL de imagem aqui


class EmbedModal(Modal):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(title="Criar Embed")

        self.channel = channel

        self.title_input = TextInput(label="Título", max_length=256, required=True)

        self.desc_input = TextInput(
            label="Mensagem",
            style=discord.TextStyle.long,
            max_length=4000,
            required=True,
        )

        self.image_input = TextInput(
            label="Imagem URL",
            required=False,
            placeholder="Imagem grande do embed",
            max_length=500,
        )

        self.thumbnail_input = TextInput(
            label="Thumbnail URL",
            required=False,
            placeholder="Imagem pequena no canto superior",
            max_length=500,
        )

        self.button_url_input = TextInput(
            label="Link do botão",
            required=False,
            placeholder="https://exemplo.com",
            max_length=500,
        )

        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.image_input)
        self.add_item(self.thumbnail_input)
        self.add_item(self.button_url_input)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.title_input.value,
            description=self.desc_input.value,
            color=EMBED_COLOR,
        )

        image_url = self.image_input.value.strip() if self.image_input.value else ""
        thumbnail_url = (
            self.thumbnail_input.value.strip() if self.thumbnail_input.value else ""
        )
        button_url = (
            self.button_url_input.value.strip() if self.button_url_input.value else ""
        )

        if image_url:
            embed.set_image(url=image_url)

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        if FIXED_FOOTER_ICON:
            embed.set_footer(text=FIXED_FOOTER_TEXT, icon_url=FIXED_FOOTER_ICON)
        else:
            embed.set_footer(text=FIXED_FOOTER_TEXT)

        view = None

        if button_url:
            if not button_url.startswith(("http://", "https://")):
                await interaction.response.send_message(
                    "❌ O link do botão precisa começar com `http://` ou `https://`.",
                    ephemeral=True,
                )
                return

            view = View()
            view.add_item(
                Button(
                    label="Abrir link", style=discord.ButtonStyle.red, url=button_url
                )
            )

        await self.channel.send(embed=embed, view=view)

        await interaction.response.send_message("✅ Embed enviada.", ephemeral=True)


class Embeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="embed", description="Envia uma embed personalizada")
    @app_commands.default_permissions(manage_messages=True)
    async def embed(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EmbedModal(interaction.channel))


async def setup(bot):
    await bot.add_cog(Embeds(bot))
