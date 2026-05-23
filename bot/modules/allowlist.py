import asyncio
import json
import os

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from shared.db import execute, log, now, row, settings

GUILD_ID = int(os.getenv("GUILD_ID", "0"))

ACTIVE_ALLOWLISTS = set()


# =========================
# HELPERS
# =========================


def parse_color(hex_color: str):
    try:
        return int(str(hex_color).replace("#", ""), 16)
    except Exception:
        return 0x8B0000


def chunks(text: str, limit: int = 1024):
    text = str(text or "")

    if len(text) <= limit:
        return [text]

    result = []

    while text:
        result.append(text[:limit])
        text = text[limit:]

    return result


def safe_channel_name(text: str):
    text = str(text).lower()
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"

    text = "".join(c if c in allowed else "-" for c in text)

    while "--" in text:
        text = text.replace("--", "-")

    return text.strip("-")[:80] or "allowlist"


def get_nickname_from_answers(answers: list[dict]) -> str | None:
    """
    Usa sempre a primeira resposta da allowlist como nickname.
    Então a primeira pergunta deve ser o nome do personagem.
    """

    if not answers:
        print("❌ Nickname não alterado: nenhuma resposta encontrada.", flush=True)
        return None

    first_answer = str(answers[0].get("answer", "")).strip()

    if not first_answer:
        print("❌ Nickname não alterado: primeira resposta vazia.", flush=True)
        return None

    nickname = first_answer.splitlines()[0].strip()

    if not nickname:
        print("❌ Nickname não alterado: nickname vazio após limpeza.", flush=True)
        return None

    return nickname[:32]


async def change_member_nickname(
    member: discord.Member, answers: list[dict], reason: str
):
    print("=== TENTANDO ALTERAR NICKNAME ===", flush=True)
    print(f"Usuário alvo: {member} / {member.id}", flush=True)
    print(
        f"Primeira resposta: {answers[0] if answers else 'SEM RESPOSTAS'}", flush=True
    )

    nickname = get_nickname_from_answers(answers)

    print(f"Nickname detectado: {nickname}", flush=True)

    if not nickname:
        print("❌ Nickname vazio. Nada alterado.", flush=True)
        return False

    try:
        await member.edit(nick=nickname, reason=reason)

        print(
            f"✅ Nickname alterado com sucesso: {member.id} -> {nickname}", flush=True
        )
        return True

    except discord.Forbidden:
        print(
            "❌ Discord Forbidden: sem permissão/hierarquia para alterar nickname. "
            "O cargo do bot precisa estar ACIMA do cargo mais alto do usuário.",
            flush=True,
        )
        return False

    except discord.HTTPException as e:
        print(f"❌ Erro HTTP ao alterar nickname: {e}", flush=True)
        return False

    except Exception as e:
        print(f"❌ Erro inesperado ao alterar nickname: {e}", flush=True)
        return False


async def build_allowlist_panel_embed():
    cfg = await settings()

    embed = discord.Embed(
        title=cfg.get("allowlist_title", "Registro de Cidadania"),
        description=cfg.get(
            "allowlist_description",
            "Clique no botão abaixo para iniciar sua allowlist.",
        ),
        color=parse_color(cfg.get("bot_color", "#8B0000")),
    )

    embed.add_field(
        name="Como funciona",
        value=(
            "1️⃣ Clique em **Iniciar Allowlist**\n"
            "2️⃣ O bot criará um canal privado para você\n"
            "3️⃣ Responda as perguntas uma por uma\n"
            "4️⃣ Aguarde análise da equipe"
        ),
        inline=False,
    )

    footer = cfg.get("allowlist_footer", "")
    if footer:
        embed.set_footer(text=footer)

    image = cfg.get("allowlist_image_url", "")
    if image:
        embed.set_image(url=image)

    thumbnail = cfg.get("allowlist_thumbnail_url", "")
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    return embed


def build_staff_application_embeds(
    app_id: int, user: discord.Member | discord.User, answers: list[dict], color: int
):
    embeds = []

    current = discord.Embed(
        title=f"📋 Nova Allowlist #{app_id}",
        description=f"Enviada por {user.mention}",
        color=color,
    )

    current.set_author(name=user.display_name, icon_url=user.display_avatar.url)

    current.set_footer(text=f"User ID: {user.id}")

    field_count = 0

    for index, answer in enumerate(answers, 1):
        question = str(answer.get("question", f"Pergunta {index}"))
        response = str(answer.get("answer", "Sem resposta"))

        response_chunks = chunks(response, 1024)

        for part_index, part in enumerate(response_chunks, 1):
            if field_count >= 24:
                embeds.append(current)

                current = discord.Embed(
                    title=f"📋 Nova Allowlist #{app_id} — continuação", color=color
                )

                field_count = 0

            field_name = f"{index}. {question}"

            if len(response_chunks) > 1:
                field_name += f" — parte {part_index}/{len(response_chunks)}"

            current.add_field(
                name=field_name[:256], value=part or "Sem resposta", inline=False
            )

            field_count += 1

    embeds.append(current)

    return embeds


async def send_allowlist_result_channel(
    guild: discord.Guild,
    member: discord.Member,
    status: str,
    answers: list[dict],
    cfg: dict,
):
    if status == "approved":
        channel_id = int(cfg.get("approved_channel_id", "0") or 0)
        title = "✅ CIDADANIA CONCEDIDA!"
        description = f"{member.mention} você foi aceito em Nightfall. Seu sangue agora corre sob o Eclipse Eterno e sua vaga em Porto Âmbar está garantida.A engrenagem do destino começou a girar para você!"
        color = discord.Color.green()

    elif status == "rejected":
        channel_id = int(cfg.get("rejected_channel_id", "0") or 0)
        title = "❌ PORTÕES FECHADOS!"
        description = f"{member.mention} o rito de entrada falhou e a sua linhagem foi recusada pelo Conselho. Você não alcançou o rigor necessário para pisar em solo sagrado.Por enquanto, sua história permanece nas sombras."
        color = discord.Color.red()

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
        print(f"Canal público de resultado não encontrado: {channel_id}", flush=True)
        return

    character_name = None

    if answers and answers[0].get("answer"):
        character_name = str(answers[0]["answer"]).strip().splitlines()[0][:64]

    embed = discord.Embed(title=title, description=description, color=color)

    # if character_name:
    #     embed.add_field(
    #         name="Personagem",
    #         value=character_name,
    #         inline=False
    #     )

    embed.add_field(name="Usuário", value=f"{member.mention}", inline=False)

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="NightFall • Allowlist")

    try:
        await channel.send(embed=embed)
        print(
            f"✅ Resultado público enviado para canal {channel_id}: {status}",
            flush=True,
        )
    except Exception as e:
        print(f"❌ Erro ao enviar resultado público da allowlist: {e}", flush=True)


# =========================
# BOTÕES DA STAFF
# =========================


class StaffDecisionView(View):
    def __init__(self, application_id: int, user_id: int):
        super().__init__(timeout=None)
        self.application_id = application_id
        self.user_id = user_id

    async def finish(
        self,
        interaction: discord.Interaction,
        status: str,
        title: str,
        color: discord.Color,
        role_key: str | None = None,
    ):
        print("=== DECISÃO DE ALLOWLIST PELO DISCORD ===", flush=True)
        print(f"Application ID: {self.application_id}", flush=True)
        print(f"Status escolhido: {status}", flush=True)
        print(f"Staff: {interaction.user} / {interaction.user.id}", flush=True)

        application = await row(
            "SELECT * FROM applications WHERE id=?", (self.application_id,)
        )

        if not application:
            await interaction.response.send_message(
                "❌ Esta candidatura não existe mais no banco.", ephemeral=True
            )
            await interaction.message.edit(view=None)
            return

        current_status = application["status"]

        if current_status != "pending":
            await interaction.message.edit(view=None)
            await interaction.response.send_message(
                f"⚠️ Esta allowlist já foi finalizada como **{current_status}**. "
                "Os botões foram bloqueados.",
                ephemeral=True,
            )
            return

        cfg = await settings()

        member = interaction.guild.get_member(self.user_id)

        if not member:
            try:
                member = await interaction.guild.fetch_member(self.user_id)
            except Exception:
                member = None

        if not member:
            await interaction.response.send_message(
                "❌ Membro não encontrado no servidor.", ephemeral=True
            )
            return

        try:
            answers = json.loads(application["answers"] or "[]")
        except Exception:
            answers = []

        print(f"Answers carregadas: {answers}", flush=True)

        # Primeiro altera nickname, ANTES de adicionar cargo.
        # Isso evita problema de hierarquia se o cargo aprovado ficar acima do bot.
        # Primeiro altera nickname, ANTES de adicionar cargo.
        # Isso evita problema de hierarquia se o cargo aprovado ficar acima do bot.
        # Primeiro altera nickname, ANTES de adicionar cargo.
        # Isso evita problema de hierarquia se o cargo aprovado ficar acima do bot.
        if status == "approved":
            print("=== ALTERANDO NICKNAME ANTES DO CARGO ===", flush=True)

            await change_member_nickname(
                member=member,
                answers=answers,
                reason="Allowlist aprovada: primeira resposta usada como nome",
            )

            # Remove cargos antigos ao aprovar, se configurado.
            remove_roles_raw = str(cfg.get("remove_role_on_approved_id", "")).strip()

            if remove_roles_raw:
                remove_role_ids = [
                    r.strip()
                    for r in remove_roles_raw.split(",")
                    if r.strip().isdigit()
                ]

                roles_to_remove = []

                for role_id in remove_role_ids:
                    role = interaction.guild.get_role(int(role_id))

                    if role:
                        roles_to_remove.append(role)
                    else:
                        print(
                            f"⚠️ Cargo para remover não encontrado: {role_id}",
                            flush=True,
                        )

                if roles_to_remove:
                    try:
                        await member.remove_roles(
                            *roles_to_remove,
                            reason="Allowlist aprovada: removendo cargos anteriores",
                        )

                        print(
                            f"✅ Cargos removidos ao aprovar: "
                            f"{', '.join([r.name for r in roles_to_remove])}",
                            flush=True,
                        )

                    except Exception as e:
                        print(f"❌ Erro ao remover cargos ao aprovar: {e}", flush=True)

        # Depois adiciona cargo.
        if role_key:
            role_id = int(cfg.get(role_key, "0") or 0)
            role = interaction.guild.get_role(role_id)

            if role:
                try:
                    await member.add_roles(role, reason=f"Allowlist status: {status}")
                    print(f"✅ Cargo adicionado: {role.name} / {role.id}", flush=True)
                except Exception as e:
                    print(f"❌ Erro ao adicionar cargo: {e}", flush=True)
            else:
                print(
                    f"⚠️ Cargo não encontrado para role_key={role_key}, role_id={role_id}",
                    flush=True,
                )

        await execute(
            "UPDATE applications SET status=?, updated_at=? WHERE id=?",
            (status, now(), self.application_id),
        )

        await log(
            "application_decision_discord",
            {
                "application_id": self.application_id,
                "user_id": self.user_id,
                "status": status,
                "staff_id": interaction.user.id,
            },
        )

        result_embed = discord.Embed(
            title=title,
            description=f"Usuário: {member.mention}\nStatus: **{status}**",
            color=color,
        )

        old_embed = (
            interaction.message.embeds[0] if interaction.message.embeds else None
        )

        if old_embed:
            locked_embed = old_embed.copy()
            locked_embed.title = f"{old_embed.title or 'Allowlist'} — {status.upper()}"
            locked_embed.color = color
            locked_embed.add_field(
                name="Resultado definido pela staff",
                value=f"**{title}** por {interaction.user.mention}",
                inline=False,
            )
            await interaction.message.edit(embed=locked_embed, view=None)
        else:
            await interaction.message.edit(view=None)

        await interaction.response.send_message(embed=result_embed)

        await send_allowlist_result_channel(
            guild=interaction.guild,
            member=member,
            status=status,
            answers=answers,
            cfg=cfg,
        )
        try:
            await member.send(embed=result_embed)
        except discord.Forbidden:
            pass

    @discord.ui.button(
        label="Aprovar",
        style=discord.ButtonStyle.green,
        custom_id="staff_decision:approve",
    )
    async def approve(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.finish(
            interaction=interaction,
            status="approved",
            title="✅ Allowlist aprovada",
            color=discord.Color.green(),
            role_key="approved_role_id",
        )

    @discord.ui.button(
        label="Entrevista",
        style=discord.ButtonStyle.blurple,
        custom_id="staff_decision:interview",
    )
    async def interview(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.finish(
            interaction=interaction,
            status="interview",
            title="🎤 Encaminhado para entrevista",
            color=discord.Color.blurple(),
            role_key="interview_role_id",
        )

    @discord.ui.button(
        label="Reprovar",
        style=discord.ButtonStyle.red,
        custom_id="staff_decision:reject",
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(
            interaction=interaction,
            status="rejected",
            title="❌ Allowlist reprovada",
            color=discord.Color.red(),
            role_key=None,
        )


# =========================
# SISTEMA DE CANAL PRIVADO
# =========================


async def create_allowlist_channel(interaction: discord.Interaction):
    cfg = await settings()
    guild = interaction.guild
    user = interaction.user

    category_id = int(cfg.get("allowlist_category_id", "0") or 0)
    category = guild.get_channel(category_id) if category_id else None

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
        ),
    }

    channel_name = safe_channel_name(f"allowlist-{user.display_name}")

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category if isinstance(category, discord.CategoryChannel) else None,
        overwrites=overwrites,
        topic=f"allowlist_user_id={user.id}",
        reason=f"Allowlist iniciada por {user}",
    )

    return channel


async def run_allowlist_session(
    bot: commands.Bot,
    guild: discord.Guild,
    user: discord.Member,
    channel: discord.TextChannel,
):
    try:
        cfg = await settings()

        try:
            questions = json.loads(cfg.get("allowlist_questions", "[]"))
        except Exception:
            questions = []

        if not questions:
            questions = ["Nome do Personagem", "Conte a história do seu personagem"]

        color = parse_color(cfg.get("bot_color", "#8B0000"))

        intro_embed = discord.Embed(
            title="📋 Allowlist iniciada",
            description=(
                f"{user.mention}, responda as perguntas uma por uma neste canal.\n\n"
                "A primeira resposta será usada como **nome do personagem** caso você seja aprovado.\n\n"
                "Você tem **10 minutos** para responder cada pergunta."
            ),
            color=color,
        )

        await channel.send(content=user.mention, embed=intro_embed)

        answers = []

        def check(message: discord.Message):
            return (
                message.author.id == user.id
                and message.channel.id == channel.id
                and not message.author.bot
            )

        for index, question in enumerate(questions, 1):
            question_embed = discord.Embed(
                title=f"Pergunta {index}/{len(questions)}",
                description=question,
                color=color,
            )

            if index == 1:
                question_embed.set_footer(
                    text="Esta resposta será usada como nome do personagem se aprovado."
                )

            await channel.send(embed=question_embed)

            try:
                message = await bot.wait_for("message", check=check, timeout=600)

            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ Tempo esgotado",
                    description="Você demorou muito para responder. A allowlist foi cancelada.",
                    color=discord.Color.red(),
                )

                await channel.send(embed=timeout_embed)

                await asyncio.sleep(10)

                try:
                    await channel.delete(reason="Allowlist cancelada por timeout")
                except Exception:
                    pass

                return

            answer_text = message.content.strip()

            if message.attachments:
                attachment_links = "\n".join(a.url for a in message.attachments)

                if answer_text:
                    answer_text += "\n\n" + attachment_links
                else:
                    answer_text = attachment_links

            if not answer_text:
                answer_text = "Sem resposta"

            answers.append({"question": question, "answer": answer_text})

            try:
                await message.add_reaction("✅")
            except Exception:
                pass

        existing = await row(
            "SELECT id FROM applications WHERE discord_id=? AND status='pending'",
            (str(user.id),),
        )

        if existing:
            await channel.send(
                "⚠️ Você já possui uma allowlist pendente. Esta sessão será encerrada."
            )

            await asyncio.sleep(10)

            try:
                await channel.delete(reason="Usuário já tinha allowlist pendente")
            except Exception:
                pass

            return

        app_id = await execute(
            """
            INSERT INTO applications
            (discord_id, discord_name, status, answers, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(user.id),
                str(user),
                "pending",
                json.dumps(answers, ensure_ascii=False),
                now(),
                now(),
            ),
        )

        staff_channel_id = int(cfg.get("staff_channel_id", "0") or 0)
        staff_channel = guild.get_channel(staff_channel_id)

        if not staff_channel:
            await channel.send(
                "❌ Canal da staff não configurado. Avise a administração."
            )
            return

        embeds = build_staff_application_embeds(
            app_id=app_id, user=user, answers=answers, color=color
        )

        staff_message = await staff_channel.send(
            embed=embeds[0], view=StaffDecisionView(app_id, user.id)
        )

        for embed in embeds[1:]:
            await staff_channel.send(embed=embed)

        await execute(
            "UPDATE applications SET staff_note=? WHERE id=?",
            (f"staff_message_id:{staff_message.id}", app_id),
        )

        await log(
            "application_created",
            {"application_id": app_id, "user_id": user.id, "source": "private_channel"},
        )

        done_embed = discord.Embed(
            title="✅ Allowlist enviada",
            description=(
                "Sua allowlist foi enviada para análise da equipe.\n\n"
                "Este canal será fechado em alguns segundos."
            ),
            color=discord.Color.green(),
        )

        await channel.send(embed=done_embed)

        await asyncio.sleep(15)

        try:
            await channel.delete(reason="Allowlist finalizada")
        except Exception:
            pass

    finally:
        ACTIVE_ALLOWLISTS.discard(user.id)


# =========================
# BOTÃO INICIAR ALLOWLIST
# =========================


class AllowlistStartView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="REQUISITAR CIDADANIA",
        style=discord.ButtonStyle.red,
        emoji="📑",
        custom_id="allowlist:start",
    )
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user

        if user.id in ACTIVE_ALLOWLISTS:
            await interaction.response.send_message(
                "⚠️ Você já está respondendo uma allowlist.", ephemeral=True
            )
            return

        existing = await row(
            "SELECT id FROM applications WHERE discord_id=? AND status='pending'",
            (str(user.id),),
        )

        if existing:
            await interaction.response.send_message(
                "⚠️ Você já possui uma allowlist pendente.", ephemeral=True
            )
            return

        ACTIVE_ALLOWLISTS.add(user.id)

        try:
            channel = await create_allowlist_channel(interaction)

            await interaction.response.send_message(
                f"✅ Canal privado criado: {channel.mention}", ephemeral=True
            )

            bot = interaction.client

            asyncio.create_task(
                run_allowlist_session(
                    bot=bot, guild=interaction.guild, user=user, channel=channel
                )
            )

        except Exception as e:
            ACTIVE_ALLOWLISTS.discard(user.id)

            await interaction.response.send_message(
                f"❌ Erro ao criar canal de allowlist: `{e}`", ephemeral=True
            )


# =========================
# COG
# =========================


class Allowlist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(AllowlistStartView())

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="painel_allowlist", description="Envia ou atualiza o painel de allowlist"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def painel_allowlist(self, interaction: discord.Interaction):
        embed = await build_allowlist_panel_embed()

        message = await interaction.channel.send(embed=embed, view=AllowlistStartView())

        await execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            ("allowlist_panel_channel_id", str(interaction.channel.id)),
        )

        await execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            ("allowlist_panel_message_id", str(message.id)),
        )

        await interaction.response.send_message(
            "✅ Painel de allowlist enviado e vinculado ao dashboard.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Allowlist(bot))
