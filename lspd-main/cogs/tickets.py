import discord
from discord.ext import commands
from discord import app_commands
from typing import Union
import json
import os
from datetime import datetime, timezone
import asyncio

from config import (
    TICKET_PANEL_CHANNEL_ID, TICKET_PANEL_MESSAGE_FILE, TICKET_MESSAGES_FILE,
    TICKET_CATEGORIES, TICKET_MODERATOR_ROLE_ID, TICKET_TRANSCRIPTS_CHANNEL_ID,
    ROLE_ID, TICKET_MODERATOR_ROLES
)
from database import add_ticket_to_db, remove_ticket_from_db, get_all_open_tickets

# Função auxiliar para formatar logs
def log_message(level: str, message: str, emoji: str = "") -> str:
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{level.upper():<7}] {emoji} {message}"

# Variável global para armazenar as mensagens customizadas
TICKET_MESSAGES = {}

def load_ticket_messages():
    global TICKET_MESSAGES
    try:
        with open(TICKET_MESSAGES_FILE, 'r', encoding='utf-8') as f:
            TICKET_MESSAGES = json.load(f)
        print(log_message("INFO", f"Mensagens de ticket carregadas de {TICKET_MESSAGES_FILE}", "📄"))
    except FileNotFoundError:
        print(log_message("ERROR", f"Arquivo '{TICKET_MESSAGES_FILE}' não encontrado", "❌"))
        TICKET_MESSAGES = {}
    except json.JSONDecodeError as e:
        print(log_message("ERROR", f"Erro ao decodificar JSON em {TICKET_MESSAGES_FILE}: {e}", "❌"))
        TICKET_MESSAGES = {}

# --- Views e Componentes ---

class TicketPanelView(discord.ui.View):
    def __init__(self, cog_instance):
        super().__init__(timeout=None)
        self.cog = cog_instance
        self.add_item(TicketCategorySelect(cog_instance))

class TicketCategorySelect(discord.ui.Select):
    def __init__(self, cog_instance):
        self.cog = cog_instance
        options = []
        if not TICKET_MESSAGES:
            load_ticket_messages()

        valid_categories = {cat[0] for cat in TICKET_CATEGORIES}
        json_categories = TICKET_MESSAGES.get("categories", {}).keys()
        if missing := valid_categories - set(json_categories):
            print(log_message("WARNING", f"Categorias ausentes em ticket_messages.json: {missing}", "⚠️"))

        for label, _, emoji, category_id in TICKET_CATEGORIES:
            category_data = TICKET_MESSAGES.get("categories", {}).get(label, {})
            dropdown_description = category_data.get("dropdown_description", f"Descrição para {label}")
            if len(dropdown_description) > 100:
                dropdown_description = dropdown_description[:97] + "..."
            if category_id:
                options.append(discord.SelectOption(label=label, description=dropdown_description, emoji=emoji, value=label))
            else:
                print(log_message("WARNING", f"Categoria '{label}' sem ID válido", "⚠️"))

        super().__init__(
            placeholder=TICKET_MESSAGES.get("ticket_panel_embed", {}).get("dropdown_placeholder", "Selecione uma categoria..."),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        selected_category = self.values[0]
        category_info = next((cat for cat in TICKET_CATEGORIES if cat[0] == selected_category), None)

        if not category_info:
            await interaction.followup.send("Categoria inválida.", ephemeral=True)
            print(log_message("ERROR", f"Categoria '{selected_category}' inválida para {interaction.user}", "❌"))
            return

        _, _, _, category_id = category_info

        all_open_tickets = get_all_open_tickets()
        user_tickets = [t for t in all_open_tickets if t['creator_id'] == interaction.user.id]
        if len(user_tickets) >= 2:
            await interaction.followup.send("Limite de 2 tickets atingido.", ephemeral=True)
            print(log_message("WARNING", f"Limite de tickets atingido por {interaction.user}", "⚠️"))
            return

        existing_ticket = next((t for t in user_tickets if t['category'] == selected_category), None)
        if existing_ticket:
            channel = self.cog.bot.get_channel(existing_ticket['channel_id'])
            mention = channel.mention if channel else f"ID: {existing_ticket['channel_id']}"
            await interaction.followup.send(TICKET_MESSAGES.get("ticket_already_open", "").format(canal_mencao=mention), ephemeral=True)
            print(log_message("WARNING", f"Ticket existente para {interaction.user} em {mention}", "⚠️"))
            return

        try:
            guild = interaction.guild
            category_channel = guild.get_channel(category_id)
            if not category_channel or not isinstance(category_channel, discord.CategoryChannel):
                await interaction.followup.send("Categoria inválida ou não encontrada.", ephemeral=True)
                print(log_message("ERROR", f"Categoria ID {category_id} inválida", "❌"))
                return

            # Definir permissões para restringir acesso apenas ao criador e aos cargos específicos da categoria
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),  # Bloquear acesso geral
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)  # Criador tem acesso
            }
            # Garantir que o bot tenha permissões completas
            overwrites[guild.me] = discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True, attach_files=True, manage_channels=True)
            # Adicionar os cargos moderadores específicos da categoria
            moderator_role_ids = list(dict.fromkeys(TICKET_MODERATOR_ROLES.get(selected_category, [])))  # Remove duplicatas
            for role_id in moderator_role_ids:
                moderator_role = guild.get_role(role_id)
                if moderator_role:
                    overwrites[moderator_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
                else:
                    print(log_message("WARNING", f"Cargo ID {role_id} para '{selected_category}' não encontrado", "⚠️"))
            if not moderator_role_ids:
                print(log_message("WARNING", f"Sem cargos moderadores configurados para '{selected_category}'", "⚠️"))

            ticket_channel = await category_channel.create_text_channel(
                name=f"ticket-{interaction.user.name.lower().replace(' ', '-')}",
                overwrites=overwrites,
                topic=f"Ticket para {interaction.user.display_name} ({selected_category})",
                reason=f"Ticket criado por {interaction.user.display_name}"
            )

            add_ticket_to_db(ticket_channel.id, interaction.user.id, interaction.user.display_name, selected_category)
            print(log_message("INFO", f"Ticket criado para {interaction.user} em {ticket_channel.name}", "🎫"))

            category_data = TICKET_MESSAGES.get("categories", {}).get(selected_category, {})
            welcome_data = category_data.get("welcome_embed", TICKET_MESSAGES.get("ticket_welcome_embed", {}))

            embed = discord.Embed(
                title=welcome_data.get("title", "").format(categoria=selected_category, usuario=interaction.user.display_name),
                description=welcome_data.get("description", "").format(categoria=selected_category),
                color=discord.Color.from_str(welcome_data.get("color", "#7289DA"))
            )
            for field in welcome_data.get("fields", []):
                embed.add_field(
                    name=field.get("name", ""),
                    value=field.get("value", "").format(categoria=selected_category),
                    inline=field.get("inline", False)
                )
            if thumbnail := welcome_data.get("thumbnail_url"):
                embed.set_thumbnail(url=thumbnail)
            embed.set_footer(text=welcome_data.get("footer", "").format(
                id_ticket=ticket_channel.id,
                usuario=interaction.user.display_name,
                data_hora=datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M')
            ))

            # Enviar mensagem sem menções de cargos
            await ticket_channel.send(
                content=f"{interaction.user.mention}",  # Apenas o criador, sem mentions de cargos
                embed=embed,
                view=TicketControlView(self.cog)
            )

            await interaction.followup.send(
                TICKET_MESSAGES.get("ticket_created_success", "").format(canal_mencao=ticket_channel.mention),
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(TICKET_MESSAGES.get("error_creating_ticket", "").format(erro=str(e)), ephemeral=True)
            print(log_message("ERROR", f"Erro ao criar ticket para {interaction.user}: {e}", "❌"))

class TicketControlView(discord.ui.View):
    def __init__(self, cog_instance):
        super().__init__(timeout=None)
        self.cog = cog_instance

    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == interaction.channel.id), None)
        category = ticket_data['category'] if ticket_data else ""
        is_moderator = any(guild.get_role(role_id) in interaction.user.roles for role_id in TICKET_MODERATOR_ROLES.get(category, []))
        is_creator = ticket_data and ticket_data['creator_id'] == interaction.user.id

        if not is_moderator and not is_creator:
            await interaction.followup.send(TICKET_MESSAGES.get("no_permission_close_ticket", ""), ephemeral=True)
            print(log_message("WARNING", f"Sem permissão para fechar ticket por {interaction.user}", "🚫"))
            return

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await interaction.channel.send(TICKET_MESSAGES.get("close_message", ""))
        await asyncio.sleep(5)
        await self.cog.create_ticket_transcript(interaction.channel)

        try:
            await interaction.channel.delete()
            remove_ticket_from_db(interaction.channel.id)
            print(log_message("INFO", f"Ticket {interaction.channel.name} fechado por {interaction.user}", "🔒"))
        except Exception as e:
            await interaction.followup.send(f"Erro ao deletar: {e}", ephemeral=True)
            print(log_message("ERROR", f"Erro ao deletar {interaction.channel.name}: {e}", "❌"))
            for item in self.children:
                item.disabled = False
            await interaction.message.edit(view=self)

class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._ticket_panel_message_id = None
        self.ticket_moderator_role = None  # Ignorado, usamos TICKET_MODERATOR_ROLES
        load_ticket_messages()

    async def _load_ticket_panel_message_id(self):
        try:
            with open(TICKET_PANEL_MESSAGE_FILE, 'r', encoding='utf-8') as f:
                self._ticket_panel_message_id = int(f.read().strip())
            print(log_message("INFO", f"ID do painel carregado: {self._ticket_panel_message_id}", "📄"))
        except (FileNotFoundError, ValueError):
            self._ticket_panel_message_id = None
            print(log_message("WARNING", f"Arquivo {TICKET_PANEL_MESSAGE_FILE} não encontrado", "⚠️"))

    async def _save_ticket_panel_message_id(self, message_id: int):
        self._ticket_panel_message_id = message_id
        with open(TICKET_PANEL_MESSAGE_FILE, 'w', encoding='utf-8') as f:
            f.write(str(message_id))
        print(log_message("INFO", f"ID do painel salvo: {self._ticket_panel_message_id}", "💾"))

    @commands.Cog.listener()
    async def on_ready(self):
        print(log_message("INFO", "TicketsCog pronto", "✅"))
        await self._load_ticket_panel_message_id()

        if self._ticket_panel_message_id:
            try:
                channel = self.bot.get_channel(TICKET_PANEL_CHANNEL_ID)
                if channel:
                    await channel.fetch_message(self._ticket_panel_message_id)
                    self.bot.add_view(TicketPanelView(self), message_id=self._ticket_panel_message_id)
                    print(log_message("INFO", f"View do painel reativada: {self._ticket_panel_message_id}", "🔗"))
                else:
                    print(log_message("WARNING", f"Canal {TICKET_PANEL_CHANNEL_ID} não encontrado", "⚠️"))
                    self._ticket_panel_message_id = None
            except discord.NotFound:
                print(log_message("WARNING", f"Mensagem {self._ticket_panel_message_id} não encontrada", "⚠️"))
                self._ticket_panel_message_id = None
            except Exception as e:
                print(log_message("ERROR", f"Erro ao reativar view: {e}", "❌"))
                self._ticket_panel_message_id = None

        if not TICKET_MODERATOR_ROLES:
            print(log_message("WARNING", "TICKET_MODERATOR_ROLES não configurado em config.py", "⚠️"))

        for ticket in get_all_open_tickets():
            try:
                channel = self.bot.get_channel(ticket['channel_id'])
                if channel:
                    async for message in channel.history(limit=50):
                        prefix = TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("title", "").split('{')[0].strip()
                        if message.author == self.bot.user and message.embeds and message.embeds[0].title.startswith(prefix):
                            self.bot.add_view(TicketControlView(self), message_id=message.id)
                            print(log_message("INFO", f"View reativada para {channel.name}", "🔗"))
                            break
                    else:
                        print(log_message("WARNING", f"Mensagem não encontrada em {channel.name}", "⚠️"))
                else:
                    print(log_message("WARNING", f"Canal {ticket['channel_id']} não encontrado, removido do DB", "⚠️"))
                    remove_ticket_from_db(ticket['channel_id'])
            except Exception as e:
                print(log_message("ERROR", f"Erro ao re-adicionar view em {ticket['channel_id']}: {e}", "❌"))

    @commands.command(name="setuptickets")
    @commands.has_permissions(administrator=True)
    async def setup_tickets_panel(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)

        channel = self.bot.get_channel(TICKET_PANEL_CHANNEL_ID)
        if not channel:
            await ctx.send("Canal não encontrado.", ephemeral=True)
            print(log_message("ERROR", f"Canal {TICKET_PANEL_CHANNEL_ID} não encontrado", "❌"))
            return

        if not TICKET_MESSAGES:
            load_ticket_messages()
            if not TICKET_MESSAGES:
                await ctx.send("Erro ao carregar ticket_messages.json.", ephemeral=True)
                print(log_message("ERROR", "Falha ao carregar JSON", "❌"))
                return

        panel_data = TICKET_MESSAGES.get("ticket_panel_embed", {})
        embed = discord.Embed(
            title=panel_data.get("title", ""),
            description=panel_data.get("description", ""),
            color=discord.Color.from_str(panel_data.get("color", "#36393F"))
        )
        for field in panel_data.get("fields", []):
            embed.add_field(name=field.get("name", ""), value=field.get("value", ""), inline=field.get("inline", False))
        if thumbnail := panel_data.get("thumbnail_url"):
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=panel_data.get("footer", "").format(data_hora=datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M')))

        view = TicketPanelView(self)
        try:
            if self._ticket_panel_message_id:
                message = await channel.fetch_message(self._ticket_panel_message_id)
                await message.edit(embed=embed, view=view)
                await ctx.send("Painel atualizado.", ephemeral=True)
                print(log_message("INFO", f"Painel atualizado por {ctx.author}", "🔄"))
            else:
                message = await channel.send(embed=embed, view=view)
                await self._save_ticket_panel_message_id(message.id)
                await ctx.send("Painel enviado.", ephemeral=True)
                print(log_message("INFO", f"Painel enviado por {ctx.author} (ID: {message.id})", "📩"))
        except discord.NotFound:
            message = await channel.send(embed=embed, view=view)
            await self._save_ticket_panel_message_id(message.id)
            await ctx.send("Painel recriado.", ephemeral=True)
            print(log_message("INFO", f"Painel recriado por {ctx.author} (ID: {message.id})", "📩"))
        except Exception as e:
            await ctx.send(f"Erro: {e}", ephemeral=True)
            print(log_message("ERROR", f"Erro ao enviar painel por {ctx.author}: {e}", "❌"))

    async def create_ticket_transcript(self, channel: discord.TextChannel):
        transcript_channel = self.bot.get_channel(TICKET_TRANSCRIPTS_CHANNEL_ID)
        if not transcript_channel:
            print(log_message("ERROR", f"Canal {TICKET_TRANSCRIPTS_CHANNEL_ID} não encontrado", "❌"))
            return

        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == channel.id), None)
        creator = ticket_data['creator_name'] if ticket_data else "Desconhecido"
        category = ticket_data['category'] if ticket_data else "N/A"

        content = (
            f"--- Transcrito: {channel.name} ({category}) ---\n"
            f"Criado por: {creator} ({ticket_data['creator_id'] if ticket_data else 'Desconhecido'}) em {ticket_data['created_at'] if ticket_data else 'N/A'}\n"
            f"Fechado em: {datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        )

        messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
        prefix = TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("title", "").split('{')[0].strip()

        for msg in messages:
            if (msg.author == self.bot.user and msg.embeds and msg.embeds[0].title.startswith(prefix)) or \
               (msg.author == self.bot.user and msg.content == TICKET_MESSAGES.get("close_message", "")):
                continue
            timestamp = msg.created_at.astimezone().strftime('%d/%m/%Y %H:%M:%S')
            content += f"[{timestamp}] {msg.author.display_name}: {msg.content}\n"
            for attach in msg.attachments:
                content += f"     [Anexo: {attach.url}]\n"
            if msg.embeds:
                for embed in msg.embeds:
                    desc = (embed.description[:100] + "...") if embed.description and len(embed.description) > 100 else embed.description or ""
                    content += f"     [Embed: '{embed.title or 'Sem Título'}', '{desc}']\n"

        content += "\n--- Fim do Transcrito ---\n"

        file_path = f"{channel.name}_transcript.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        try:
            file = discord.File(file_path, filename=f"{channel.name}.txt")
            transcript_data = TICKET_MESSAGES.get("transcript_embed", {})
            embed = discord.Embed(
                title=transcript_data.get("title", "").format(canal=channel.name),
                description=transcript_data.get("description", "").format(criador=creator, categoria=category),
                color=discord.Color.from_str(transcript_data.get("color", "#99AAB5"))
            )
            if thumbnail := transcript_data.get("thumbnail_url"):
                embed.set_thumbnail(url=thumbnail)
            embed.set_footer(text=transcript_data.get("footer", "").format(data_hora=datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M')))
            await transcript_channel.send(embed=embed, file=file)
            print(log_message("INFO", f"Transcrito de {channel.name} enviado", "📄"))
        except Exception as e:
            print(log_message("ERROR", f"Erro ao enviar transcrito de {channel.name}: {e}", "❌"))
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    @app_commands.command(name="add", description="Adiciona um usuário ou cargo ao ticket.")
    @app_commands.describe(target="Usuário ou cargo a adicionar.")
    async def add_to_ticket(self, interaction: discord.Interaction, target: Union[discord.Member, discord.Role]):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Use em canal de texto.", ephemeral=True)
            print(log_message("WARNING", f"/add fora de canal de texto por {interaction.user}", "⚠️"))
            return

        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == interaction.channel.id), None)
        if not ticket_data:
            await interaction.response.send_message("Use em canal de ticket.", ephemeral=True)
            print(log_message("WARNING", f"/add fora de ticket por {interaction.user}", "⚠️"))
            return

        guild = interaction.guild
        category = ticket_data['category']
        moderator_role_ids = TICKET_MODERATOR_ROLES.get(category, [])
        is_moderator = any(guild.get_role(role_id) in interaction.user.roles for role_id in moderator_role_ids)
        is_creator = ticket_data and ticket_data['creator_id'] == interaction.user.id

        if not is_moderator and not is_creator:
            await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)
            print(log_message("WARNING", f"Sem permissão para /add por {interaction.user}", "🚫"))
            return

        try:
            await interaction.channel.set_permissions(target, view_channel=True, send_messages=True, attach_files=True)
            await interaction.response.send_message(f"✅ {target.mention} adicionado.", ephemeral=True)
            print(log_message("INFO", f"{interaction.user} adicionou {target.name} a {interaction.channel.name}", "➕"))
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para alterar permissões.", ephemeral=True)
            print(log_message("ERROR", f"Permissão negada ao adicionar {target.name} por {interaction.user}", "🚫"))
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)
            print(log_message("ERROR", f"Erro ao adicionar {target.name} por {interaction.user}: {e}", "❌"))

    @app_commands.command(name="remove", description="Remove um usuário ou cargo do ticket.")
    @app_commands.describe(target="Usuário ou cargo a remover.")
    async def remove_from_ticket(self, interaction: discord.Interaction, target: Union[discord.Member, discord.Role]):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Use em canal de texto.", ephemeral=True)
            print(log_message("WARNING", f"/remove fora de canal de texto por {interaction.user}", "⚠️"))
            return

        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == interaction.channel.id), None)
        if not ticket_data:
            await interaction.response.send_message("Use em canal de ticket.", ephemeral=True)
            print(log_message("WARNING", f"/remove fora de ticket por {interaction.user}", "⚠️"))
            return

        guild = interaction.guild
        category = ticket_data['category']
        moderator_role_ids = TICKET_MODERATOR_ROLES.get(category, [])
        is_moderator = any(guild.get_role(role_id) in interaction.user.roles for role_id in moderator_role_ids)
        is_creator = ticket_data and ticket_data['creator_id'] == interaction.user.id

        if not is_moderator and not is_creator:
            await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)
            print(log_message("WARNING", f"Sem permissão para /remove por {interaction.user}", "🚫"))
            return

        try:
            await interaction.channel.set_permissions(target, overwrite=None)
            await interaction.response.send_message(f"✅ {target.mention} removido.", ephemeral=True)
            print(log_message("INFO", f"{interaction.user} removeu {target.name} de {interaction.channel.name}", "➖"))
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para alterar permissões.", ephemeral=True)
            print(log_message("ERROR", f"Permissão negada ao remover {target.name} por {interaction.user}", "🚫"))
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)
            print(log_message("ERROR", f"Erro ao remover {target.name} por {interaction.user}: {e}", "❌"))

    @app_commands.command(name="rename", description="Renomeia o canal do ticket.")
    @app_commands.describe(new_name="Novo nome do ticket.")
    async def rename_ticket(self, interaction: discord.Interaction, new_name: str):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Use em canal de texto.", ephemeral=True)
            print(log_message("WARNING", f"/rename fora de canal de texto por {interaction.user}", "⚠️"))
            return

        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == interaction.channel.id), None)
        if not ticket_data:
            await interaction.response.send_message("Use em canal de ticket.", ephemeral=True)
            print(log_message("WARNING", f"/rename fora de ticket por {interaction.user}", "⚠️"))
            return

        guild = interaction.guild
        category = ticket_data['category']
        moderator_role_ids = TICKET_MODERATOR_ROLES.get(category, [])
        is_moderator = any(guild.get_role(role_id) in interaction.user.roles for role_id in moderator_role_ids)
        is_creator = ticket_data and ticket_data['creator_id'] == interaction.user.id

        if not is_moderator and not is_creator:
            await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)
            print(log_message("WARNING", f"Sem permissão para /rename por {interaction.user}", "🚫"))
            return

        if len(new_name) > 100:
            await interaction.response.send_message("Nome muito longo (máx. 100 caracteres).", ephemeral=True)
            print(log_message("WARNING", f"Nome longo ({len(new_name)}) por {interaction.user}", "⚠️"))
            return

        formatted_name = ''.join(c for c in new_name.lower().replace(' ', '-') if c.isalnum() or c == '-')
        try:
            old_name = interaction.channel.name
            await interaction.channel.edit(name=formatted_name)
            await interaction.response.send_message(f"✅ Renomeado de `{old_name}` para `{formatted_name}`.", ephemeral=True)
            print(log_message("INFO", f"{interaction.user} renomeou {old_name} para {formatted_name}", "✏️"))
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para renomear.", ephemeral=True)
            print(log_message("ERROR", f"Permissão negada ao renomear {interaction.channel.name} por {interaction.user}", "🚫"))
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)
            print(log_message("ERROR", f"Erro ao renomear {interaction.channel.name} por {interaction.user}: {e}", "❌"))

    @commands.command(name="cleartickets")
    @commands.has_permissions(administrator=True)
    async def clear_all_tickets(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        tickets = get_all_open_tickets()
        if not tickets:
            await ctx.send("Nenhum ticket aberto.", ephemeral=True)
            print(log_message("INFO", f"Sem tickets para limpar por {ctx.author}", "ℹ️"))
            return

        deleted = 0
        failed = []
        await ctx.send(f"Limpando {len(tickets)} tickets...", ephemeral=True)
        print(log_message("INFO", f"Iniciando limpeza de {len(tickets)} tickets por {ctx.author}", "🧹"))

        for ticket in tickets:
            channel_id = ticket['channel_id']
            name = f"ticket-{ticket.get('creator_name', 'unknown').lower().replace(' ', '-')}"
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.delete(reason="!cleartickets")
                    remove_ticket_from_db(channel_id)
                    deleted += 1
                    print(log_message("INFO", f"Ticket {name} (ID: {channel_id}) deletado", "🗑️"))
                else:
                    remove_ticket_from_db(channel_id)
                    deleted += 1
                    print(log_message("INFO", f"Ticket {name} (ID: {channel_id}) removido do DB", "🗑️"))
            except discord.NotFound:
                remove_ticket_from_db(channel_id)
                deleted += 1
                print(log_message("INFO", f"Ticket {name} (ID: {channel_id}) já deletado", "🗑️"))
            except Exception as e:
                failed.append(f"{name} (ID: {channel_id}): {e}")
                print(log_message("ERROR", f"Erro ao deletar {name}: {e}", "❌"))

        if failed:
            await ctx.send(f"Limpou {deleted} tickets.\nErros:\n```\n{'\n'.join(failed)}\n```", ephemeral=True)
            print(log_message("WARNING", f"Limpeza com {len(failed)} erros", "⚠️"))
        else:
            await ctx.send(f"Limpou {deleted} tickets com sucesso.", ephemeral=True)
            print(log_message("INFO", f"Limpeza concluída: {deleted} tickets", "✅"))

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))
