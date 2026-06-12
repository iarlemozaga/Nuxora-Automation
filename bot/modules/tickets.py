import asyncio
import io
import json
import os
import re

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from shared.db import execute, log, settings
from shared.guard import is_guild_active

GUILD_ID = int(os.getenv("GUILD_ID", "0"))

DEFAULT_TICKET_TYPES = [
    {
        "id": "suporte",
        "label": "Suporte",
        "emoji": "🛠️",
        "description": "Abra um ticket para suporte geral.",
        "style": "gray",
        "category_id": "",
        "allowed_role_ids": [],
    },
    {
        "id": "denuncia",
        "label": "Denúncia",
        "emoji": "🚨",
        "description": "Abra um ticket para denúncias.",
        "style": "red",
        "category_id": "",
        "allowed_role_ids": [],
    },
    {
        "id": "bug",
        "label": "Bug",
        "emoji": "🐞",
        "description": "Reporte bugs ou problemas técnicos.",
        "style": "blurple",
        "category_id": "",
        "allowed_role_ids": [],
    },
]


def parse_color(hex_color: str):
    try:
        return int(str(hex_color).replace("#", ""), 16)
    except Exception:
        return 0x8B0000


def button_style(style_name: str | None):
    style_name = str(style_name or "gray").lower()

    styles = {
        "gray": discord.ButtonStyle.gray,
        "grey": discord.ButtonStyle.gray,
        "red": discord.ButtonStyle.red,
        "danger": discord.ButtonStyle.red,
        "green": discord.ButtonStyle.green,
        "success": discord.ButtonStyle.green,
        "blue": discord.ButtonStyle.blurple,
        "blurple": discord.ButtonStyle.blurple,
        "primary": discord.ButtonStyle.blurple,
    }

    return styles.get(style_name, discord.ButtonStyle.gray)


def safe_channel_name(text: str) -> str:
    text = str(text or "ticket").lower()
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    text = "".join(c if c in allowed else "-" for c in text)

    while "--" in text:
        text = text.replace("--", "-")

    return text.strip("-")[:80] or "ticket"


def parse_role_ids(value):
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "").replace(";", ",").split(",")

    ids = []

    for item in raw:
        item = str(item).strip()

        if item.isdigit():
            ids.append(int(item))

    return ids


def normalize_ticket_type(item: dict):
    return {
        "id": safe_channel_name(item.get("id", "ticket")),
        "label": str(item.get("label", item.get("id", "Ticket")) or "Ticket"),
        "emoji": str(item.get("emoji", "🎫") or "🎫"),
        "description": str(
            item.get("description", "Sem descrição.") or "Sem descrição."
        ),
        "style": str(item.get("style", "gray") or "gray"),
        "category_id": str(item.get("category_id", "") or "").strip(),
        "allowed_role_ids": parse_role_ids(item.get("allowed_role_ids", [])),
    }


async def save_setting(guild_id: int, key: str, value: str):
    await execute(
        """
        INSERT INTO guild_settings (guild_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT (guild_id, key)
        DO UPDATE SET value = EXCLUDED.value
        """,
        (str(guild_id), key, str(value)),
    )


async def get_ticket_settings(guild_id=None):
    cfg = await settings(guild_id)

    try:
        ticket_types = json.loads(cfg.get("ticket_types", "[]"))
    except Exception:
        ticket_types = []

    if not isinstance(ticket_types, list) or not ticket_types:
        ticket_types = DEFAULT_TICKET_TYPES

    normalized_types = []

    for item in ticket_types:
        if isinstance(item, dict):
            normalized_types.append(normalize_ticket_type(item))

    if not normalized_types:
        normalized_types = [normalize_ticket_type(t) for t in DEFAULT_TICKET_TYPES]

    return {
        "title": cfg.get("ticket_panel_title", "🎫 Central de Atendimento"),
        "description": cfg.get(
            "ticket_panel_description",
            "Selecione abaixo o tipo de atendimento que você precisa.",
        ),
        "color": parse_color(cfg.get("ticket_panel_color", "#8B0000")),
        "footer": cfg.get("ticket_panel_footer", ""),
        "image": cfg.get("ticket_panel_image_url", ""),
        "thumbnail": cfg.get("ticket_panel_thumbnail_url", ""),
        "default_category_id": int(cfg.get("ticket_category_id", "0") or 0),
        "default_staff_role_id": int(cfg.get("ticket_staff_role_id", "0") or 0),
        "logs_channel_id": int(cfg.get("logs_channel_id", "0") or 0),
        "ticket_types": normalized_types,
    }


def get_ticket_owner_id(channel: discord.TextChannel) -> int | None:
    topic = channel.topic or ""

    for part in topic.split(";"):
        part = part.strip()

        if part.startswith("ticket_owner_id="):
            try:
                return int(part.split("=", 1)[1])
            except Exception:
                return None

    return None


def get_ticket_type(channel: discord.TextChannel) -> str:
    topic = channel.topic or ""

    for part in topic.split(";"):
        part = part.strip()

        if part.startswith("ticket_type="):
            return part.split("=", 1)[1]

    return "ticket"


def parse_member_id(value: str) -> int | None:
    value = str(value or "").strip()

    if value.startswith("<@") and value.endswith(">"):
        value = value.replace("<@", "").replace("!", "").replace(">", "")

    return int(value) if value.isdigit() else None


async def resolve_guild_member(guild: discord.Guild, value: str):
    member_id = parse_member_id(value)

    if not member_id:
        return None

    member = guild.get_member(member_id)

    if member:
        return member

    try:
        return await guild.fetch_member(member_id)
    except Exception:
        return None


async def get_logs_channel(guild: discord.Guild):
    cfg = await get_ticket_settings(guild.id)

    if not cfg["logs_channel_id"]:
        return None

    return guild.get_channel(cfg["logs_channel_id"])


async def make_transcript(channel: discord.TextChannel) -> discord.File:
    lines = []

    async for message in channel.history(limit=500, oldest_first=True):
        author = f"{message.author} ({message.author.id})"
        content = message.content or ""

        if message.attachments:
            links = " ".join(a.url for a in message.attachments)
            content = f"{content}\n[ANEXOS] {links}".strip()

        lines.append(f"[{message.created_at.isoformat()}] {author}: {content}")

    data = "\n".join(lines) if lines else "Sem mensagens no ticket."
    buffer = io.BytesIO(data.encode("utf-8"))

    return discord.File(buffer, filename=f"transcript-{channel.name}.txt")


def member_has_ticket_staff_access(
    guild: discord.Guild,
    member: discord.Member,
    cfg: dict,
    ticket_type: dict | None = None,
) -> bool:
    if member.guild_permissions.manage_channels:
        return True

    default_role_id = cfg["default_staff_role_id"]

    if default_role_id:
        role = guild.get_role(default_role_id)

        if role and role in member.roles:
            return True

    if ticket_type:
        for role_id in ticket_type.get("allowed_role_ids", []):
            role = guild.get_role(int(role_id))

            if role and role in member.roles:
                return True

    return False


async def is_ticket_staff(interaction: discord.Interaction) -> bool:
    cfg = await get_ticket_settings(interaction.guild.id)
    ticket_type_id = get_ticket_type(interaction.channel)
    ticket_type = next(
        (t for t in cfg["ticket_types"] if t["id"] == ticket_type_id), None
    )

    return member_has_ticket_staff_access(
        interaction.guild,
        interaction.user,
        cfg,
        ticket_type,
    )


async def can_close_ticket(interaction: discord.Interaction) -> bool:
    owner_id = get_ticket_owner_id(interaction.channel)

    if owner_id and interaction.user.id == owner_id:
        return True

    return await is_ticket_staff(interaction)


async def resolve_ticket_type(type_id: str | None, guild_id=None):
    cfg = await get_ticket_settings(guild_id)

    type_id = safe_channel_name(type_id or "")

    if type_id:
        ticket_type = next((t for t in cfg["ticket_types"] if t["id"] == type_id), None)

        if ticket_type:
            return cfg, ticket_type

    return cfg, cfg["ticket_types"][0]


async def ensure_guild_active_interaction(
    interaction: discord.Interaction,
    unavailable_message: str = "Os tickets estão temporariamente indisponíveis.",
) -> bool:
    if not interaction.guild:
        return True

    if await is_guild_active(interaction.guild.id):
        return True

    await interaction.response.send_message(
        f"🔒 Este servidor está bloqueado no Nuxora. {unavailable_message}",
        ephemeral=True,
    )

    return False


async def build_ticket_panel_embed(guild_id=None):
    cfg = await get_ticket_settings(guild_id)

    embed = discord.Embed(
        title=cfg["title"], description=cfg["description"], color=cfg["color"]
    )

    if cfg["footer"]:
        embed.set_footer(text=cfg["footer"])

    if cfg["image"]:
        embed.set_image(url=cfg["image"])

    if cfg["thumbnail"]:
        embed.set_thumbnail(url=cfg["thumbnail"])

    return embed


async def create_ticket_channel(
    guild: discord.Guild,
    user: discord.Member,
    ticket_type_data: dict,
    opened_by: discord.Member | discord.User | None = None,
    custom_title: str | None = None,
):
    cfg = await get_ticket_settings(guild.id)

    custom_category_id = int(ticket_type_data.get("category_id") or 0)
    category_id = custom_category_id or cfg["default_category_id"]

    category = guild.get_channel(category_id) if category_id else None

    default_staff_role = (
        guild.get_role(cfg["default_staff_role_id"])
        if cfg["default_staff_role_id"]
        else None
    )

    allowed_role_ids = parse_role_ids(ticket_type_data.get("allowed_role_ids", []))
    allowed_roles = []

    for role_id in allowed_role_ids:
        role = guild.get_role(int(role_id))

        if role:
            allowed_roles.append(role)

    if not allowed_roles and default_staff_role:
        allowed_roles.append(default_staff_role)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            attach_files=True,
            read_message_history=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True,
            attach_files=True,
        ),
    }

    for role in allowed_roles:
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            attach_files=True,
            read_message_history=True,
            manage_channels=True,
        )

    ticket_id = safe_channel_name(ticket_type_data.get("id", "ticket"))
    label = ticket_type_data.get("label", ticket_id)
    emoji = ticket_type_data.get("emoji", "🎫")

    channel_name = safe_channel_name(f"ticket-{ticket_id}-{user.display_name}")

    role_ids_text = ",".join(str(r.id) for r in allowed_roles)
    opener_id = opened_by.id if opened_by else user.id

    topic = (
        f"ticket_owner_id={user.id};"
        f"ticket_type={ticket_id};"
        f"ticket_staff_role_ids={role_ids_text};"
        f"ticket_opened_by={opener_id}"
    )

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category if isinstance(category, discord.CategoryChannel) else None,
        overwrites=overwrites,
        topic=topic,
        reason=f"Ticket aberto para {user} por {opened_by or user}",
    )

    ticket_description = str(
        ticket_type_data.get("description")
        or "Explique sua solicitação com detalhes.\nA staff responsável responderá assim que possível."
    ).strip()

    embed = discord.Embed(
        title=custom_title or f"{emoji} Ticket de {label}",
        description=f"{user.mention}, seu ticket foi aberto.\n\n{ticket_description}",
        color=cfg["color"],
    )

    embed.add_field(name="Tipo", value=label, inline=True)
    embed.add_field(name="Aberto para", value=user.mention, inline=True)

    if opened_by and opened_by.id != user.id:
        embed.add_field(name="Criado por", value=opened_by.mention, inline=True)

    if allowed_roles:
        embed.add_field(
            name="Equipe responsável",
            value=" ".join(role.mention for role in allowed_roles),
            inline=False,
        )

    mention_content = user.mention

    if allowed_roles:
        mention_content += " " + " ".join(role.mention for role in allowed_roles)

    await channel.send(content=mention_content, embed=embed, view=TicketControlView())

    await log(
        "ticket_created",
        {
            "channel_id": channel.id,
            "owner_id": user.id,
            "ticket_type": ticket_id,
            "category_id": category_id,
            "allowed_role_ids": [r.id for r in allowed_roles],
            "opened_by": opener_id,
        },
    )

    return channel


class TicketMemberModal(discord.ui.Modal):
    def __init__(self, action: str):
        self.action = action
        title = (
            "Adicionar pessoa ao ticket"
            if action == "add"
            else "Remover pessoa do ticket"
        )
        super().__init__(title=title, timeout=300)

        self.member_value = discord.ui.TextInput(
            label="ID ou menção do usuário",
            placeholder="Ex: 123456789012345678 ou @usuario",
            required=True,
            max_length=64,
        )
        self.add_item(self.member_value)

    async def on_submit(self, interaction: discord.Interaction):
        if not await is_ticket_staff(interaction):
            await interaction.response.send_message(
                "❌ Apenas a staff pode alterar participantes do ticket.",
                ephemeral=True,
            )
            return

        owner_id = get_ticket_owner_id(interaction.channel)

        if not owner_id:
            await interaction.response.send_message(
                "❌ Este canal não parece ser um ticket.", ephemeral=True
            )
            return

        member = await resolve_guild_member(
            interaction.guild, str(self.member_value.value)
        )

        if not member:
            await interaction.response.send_message(
                "❌ Não encontrei esse usuário no servidor.", ephemeral=True
            )
            return

        if self.action == "remove" and member.id == owner_id:
            await interaction.response.send_message(
                "❌ Não é possível remover o dono do ticket por este botão.",
                ephemeral=True,
            )
            return

        if self.action == "add":
            overwrite = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                read_message_history=True,
            )
            await interaction.channel.set_permissions(
                member,
                overwrite=overwrite,
                reason=f"Adicionado ao ticket por {interaction.user}",
            )
            await interaction.response.send_message(
                f"✅ {member.mention} foi adicionado ao ticket."
            )
            await log(
                "ticket_member_added",
                {
                    "channel_id": interaction.channel.id,
                    "member_id": member.id,
                    "staff_id": interaction.user.id,
                },
            )
            return

        overwrite = discord.PermissionOverwrite(
            view_channel=False,
            send_messages=False,
            attach_files=False,
            read_message_history=False,
        )
        await interaction.channel.set_permissions(
            member,
            overwrite=overwrite,
            reason=f"Removido do ticket por {interaction.user}",
        )
        await interaction.response.send_message(
            f"✅ {member.mention} foi removido do ticket."
        )
        await log(
            "ticket_member_removed",
            {
                "channel_id": interaction.channel.id,
                "member_id": member.id,
                "staff_id": interaction.user.id,
            },
        )


class TicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await ensure_guild_active_interaction(
            interaction,
            "Os controles de ticket estão temporariamente indisponíveis.",
        )

    @discord.ui.button(
        label="Assumir",
        emoji="🙋",
        style=discord.ButtonStyle.blurple,
        custom_id="ticket:claim",
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_ticket_staff(interaction):
            await interaction.response.send_message(
                "❌ Apenas a staff pode assumir tickets.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🙋 Ticket assumido",
            description=f"{interaction.user.mention} assumiu este ticket.",
            color=discord.Color.blurple(),
        )

        await interaction.response.send_message(embed=embed)

        await log(
            "ticket_claimed",
            {"channel_id": interaction.channel.id, "staff_id": interaction.user.id},
        )

    @discord.ui.button(
        label="Adicionar pessoa",
        emoji="➕",
        style=discord.ButtonStyle.green,
        custom_id="ticket:member:add",
    )
    async def add_member(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not await is_ticket_staff(interaction):
            await interaction.response.send_message(
                "❌ Apenas a staff pode adicionar pessoas ao ticket.", ephemeral=True
            )
            return

        await interaction.response.send_modal(TicketMemberModal("add"))

    @discord.ui.button(
        label="Remover pessoa",
        emoji="➖",
        style=discord.ButtonStyle.gray,
        custom_id="ticket:member:remove",
    )
    async def remove_member(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not await is_ticket_staff(interaction):
            await interaction.response.send_message(
                "❌ Apenas a staff pode remover pessoas do ticket.", ephemeral=True
            )
            return

        await interaction.response.send_modal(TicketMemberModal("remove"))

    @discord.ui.button(
        label="Fechar",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="ticket:close",
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await can_close_ticket(interaction):
            await interaction.response.send_message(
                "❌ Você não pode fechar este ticket.", ephemeral=True
            )
            return

        await close_ticket(interaction)


async def close_ticket(interaction: discord.Interaction):
    channel = interaction.channel
    guild = interaction.guild

    owner_id = get_ticket_owner_id(channel)
    ticket_type = get_ticket_type(channel)

    await interaction.response.send_message(
        "🔒 Fechando ticket em 5 segundos. Gerando transcript...", ephemeral=False
    )

    logs_channel = await get_logs_channel(guild)

    embed = discord.Embed(
        title="🔒 Ticket fechado",
        description=(
            f"Canal: `{channel.name}`\n"
            f"Tipo: `{ticket_type}`\n"
            f"Dono: `{owner_id}`\n"
            f"Fechado por: {interaction.user.mention}"
        ),
        color=discord.Color.red(),
    )

    if logs_channel:
        try:
            transcript_for_log = await make_transcript(channel)
            await logs_channel.send(embed=embed, file=transcript_for_log)
        except Exception as e:
            print(f"Erro ao enviar transcript para logs: {e}", flush=True)

    await log(
        "ticket_closed",
        {
            "channel_id": channel.id,
            "channel_name": channel.name,
            "owner_id": owner_id,
            "ticket_type": ticket_type,
            "closed_by": interaction.user.id,
        },
    )

    await asyncio.sleep(5)

    try:
        await channel.delete(reason=f"Ticket fechado por {interaction.user}")
    except Exception as e:
        print(f"Erro ao deletar ticket: {e}", flush=True)


class DynamicTicketButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=re.compile(r"^ticket:open:(?P<ticket_type_id>[a-z0-9_-]{1,80})$"),
):
    def __init__(self, ticket_type: dict):
        self.ticket_type_id = safe_channel_name(ticket_type["id"])

        super().__init__(
            discord.ui.Button(
                label=ticket_type.get("label", self.ticket_type_id)[:80],
                emoji=ticket_type.get("emoji") or None,
                style=button_style(ticket_type.get("style")),
                custom_id=f"ticket:open:{self.ticket_type_id}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
    ):
        ticket_type_id = safe_channel_name(match.group("ticket_type_id"))
        guild_id = interaction.guild.id if interaction.guild else None
        _, ticket_type = await resolve_ticket_type(ticket_type_id, guild_id)
        return cls(ticket_type)

    async def callback(self, interaction: discord.Interaction):
        if not await ensure_guild_active_interaction(interaction):
            return

        cfg, ticket_type = await resolve_ticket_type(
            self.ticket_type_id,
            interaction.guild.id,
        )

        can_open_multiple = member_has_ticket_staff_access(
            interaction.guild,
            interaction.user,
            cfg,
            ticket_type,
        )

        if not can_open_multiple:
            for channel in interaction.guild.text_channels:
                if (
                    get_ticket_owner_id(channel) == interaction.user.id
                    and get_ticket_type(channel) == ticket_type["id"]
                ):
                    await interaction.response.send_message(
                        f"⚠️ Você já possui um ticket aberto desta categoria: {channel.mention}",
                        ephemeral=True,
                    )
                    return


        channel = await create_ticket_channel(
            guild=interaction.guild,
            user=interaction.user,
            ticket_type_data=ticket_type,
            opened_by=interaction.user,
        )

        await interaction.response.send_message(
            f"✅ Ticket criado: {channel.mention}", ephemeral=True
        )


class TicketPanelView(View):
    def __init__(self, ticket_types: list[dict] | None = None):
        super().__init__(timeout=None)

        if ticket_types is None:
            ticket_types = DEFAULT_TICKET_TYPES

        for item in ticket_types[:25]:
            self.add_item(DynamicTicketButton(normalize_ticket_type(item)))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await ensure_guild_active_interaction(interaction)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TicketControlView())
        self.bot.add_dynamic_items(DynamicTicketButton)
        print("✅ Tickets cog inicializado", flush=True)

    async def cog_load(self):
        print(
            "✅ Painel de tickets persistente registrado por custom_id dinâmico.",
            flush=True,
        )

    @app_commands.command(
        name="painel_tickets", description="Envia o painel de tickets"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def painel_tickets(self, interaction: discord.Interaction):
        cfg = await get_ticket_settings(interaction.guild.id)
        embed = await build_ticket_panel_embed(interaction.guild.id)

        await interaction.channel.send(
            embed=embed, view=TicketPanelView(cfg["ticket_types"])
        )

        await interaction.response.send_message(
            "✅ Painel de tickets enviado.", ephemeral=True
        )

    @app_commands.command(
        name="ticket_config", description="Configura o sistema de tickets pelo Discord"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_config(
        self,
        interaction: discord.Interaction,
        titulo: str | None = None,
        descricao: str | None = None,
        categoria_padrao: discord.CategoryChannel | None = None,
        cargo_staff_padrao: discord.Role | None = None,
        canal_logs: discord.TextChannel | None = None,
        cor_hex: str | None = None,
    ):
        changed = []

        if titulo is not None:
            await save_setting(interaction.guild.id, "ticket_panel_title", titulo)
            changed.append("título")

        if descricao is not None:
            await save_setting(
                interaction.guild.id, "ticket_panel_description", descricao
            )
            changed.append("descrição")

        if categoria_padrao is not None:
            await save_setting(
                interaction.guild.id, "ticket_category_id", str(categoria_padrao.id)
            )
            changed.append("categoria padrão")

        if cargo_staff_padrao is not None:
            await save_setting(
                interaction.guild.id, "ticket_staff_role_id", str(cargo_staff_padrao.id)
            )
            changed.append("cargo staff padrão")

        if canal_logs is not None:
            await save_setting(
                interaction.guild.id, "logs_channel_id", str(canal_logs.id)
            )
            changed.append("canal de logs")

        if cor_hex is not None:
            await save_setting(interaction.guild.id, "ticket_panel_color", cor_hex)
            changed.append("cor")

        await interaction.response.send_message(
            "✅ Configuração de tickets atualizada: "
            + (", ".join(changed) if changed else "nada alterado."),
            ephemeral=True,
        )

    @app_commands.command(
        name="ticket_tipo_add", description="Adiciona ou atualiza um tipo de ticket"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_tipo_add(
        self,
        interaction: discord.Interaction,
        id_tipo: str,
        label: str,
        emoji: str,
        descricao: str,
        estilo: str = "gray",
        categoria: discord.CategoryChannel | None = None,
        cargos_acesso: str | None = None,
    ):
        cfg = await get_ticket_settings(interaction.guild.id)
        ticket_types = cfg["ticket_types"]

        id_tipo = safe_channel_name(id_tipo)

        ticket_types = [t for t in ticket_types if t.get("id") != id_tipo]

        role_ids = parse_role_ids(cargos_acesso or "")

        ticket_types.append(
            {
                "id": id_tipo,
                "label": label,
                "emoji": emoji,
                "description": descricao,
                "style": estilo,
                "category_id": str(categoria.id) if categoria else "",
                "allowed_role_ids": role_ids,
            }
        )

        await save_setting(
            interaction.guild.id,
            "ticket_types",
            json.dumps(ticket_types, ensure_ascii=False),
        )

        await interaction.response.send_message(
            f"✅ Tipo de ticket `{id_tipo}` salvo.\n"
            "Use `/painel_tickets` novamente para reenviar o painel com os botões atualizados.",
            ephemeral=True,
        )

    @app_commands.command(
        name="ticket_tipo_remove", description="Remove um tipo de ticket"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_tipo_remove(self, interaction: discord.Interaction, id_tipo: str):
        cfg = await get_ticket_settings(interaction.guild.id)

        id_tipo = safe_channel_name(id_tipo)

        ticket_types = [t for t in cfg["ticket_types"] if t.get("id") != id_tipo]

        await save_setting(
            interaction.guild.id,
            "ticket_types",
            json.dumps(ticket_types, ensure_ascii=False),
        )

        await interaction.response.send_message(
            f"✅ Tipo de ticket `{id_tipo}` removido.\n"
            "Use `/painel_tickets` novamente para reenviar o painel.",
            ephemeral=True,
        )

    @app_commands.command(
        name="ticket_criar",
        description="Staff cria um ticket manual para um usuário pelo ID",
    )
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_criar(
        self,
        interaction: discord.Interaction,
        usuario_id: str,
        tipo_id: str = "suporte",
        titulo: str | None = None,
    ):
        if not usuario_id.isdigit():
            await interaction.response.send_message(
                "❌ O ID do usuário precisa conter apenas números.", ephemeral=True
            )
            return

        member_id = int(usuario_id)

        member = interaction.guild.get_member(member_id)

        if not member:
            try:
                member = await interaction.guild.fetch_member(member_id)
            except Exception:
                member = None

        if not member:
            await interaction.response.send_message(
                "❌ Não encontrei esse usuário no servidor.", ephemeral=True
            )
            return

        cfg, ticket_type = await resolve_ticket_type(tipo_id, interaction.guild.id)

        channel = await create_ticket_channel(
            guild=interaction.guild,
            user=member,
            ticket_type_data=ticket_type,
            opened_by=interaction.user,
            custom_title=titulo,
        )

        await interaction.response.send_message(
            f"✅ Ticket manual criado para {member.mention}: {channel.mention}",
            ephemeral=True,
        )

    @app_commands.command(name="fechar_ticket", description="Fecha o ticket atual")
    async def fechar_ticket(self, interaction: discord.Interaction):
        owner_id = get_ticket_owner_id(interaction.channel)

        if not owner_id:
            await interaction.response.send_message(
                "❌ Este canal não parece ser um ticket.", ephemeral=True
            )
            return

        if not await can_close_ticket(interaction):
            await interaction.response.send_message(
                "❌ Você não pode fechar este ticket.", ephemeral=True
            )
            return

        await close_ticket(interaction)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
