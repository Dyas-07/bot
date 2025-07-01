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
    ROLE_ID
)
from database import add_ticket_to_db, remove_ticket_from_db, get_all_open_tickets

# Função auxiliar para formatar logs (consistente com main.py e punch_card.py)
def log_message(level: str, message: str, emoji: str = "") -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{level.upper():<7}] {emoji} {message}"

# Variável global para armazenar as mensagens customizadas para tickets
TICKET_MESSAGES = {}

# Função para carregar as mensagens customizadas do arquivo JSON
def load_ticket_messages():
    global TICKET_MESSAGES
    try:
        with open(TICKET_MESSAGES_FILE, 'r', encoding='utf-8') as f:
            TICKET_MESSAGES = json.load(f)
        print(log_message("INFO", f"Mensagens de ticket carregadas de {TICKET_MESSAGES_FILE}", "📄"))
    except FileNotFoundError:
        print(log_message("ERROR", f"Arquivo de mensagens de ticket '{TICKET_MESSAGES_FILE}' não encontrado", "❌"))
        print(log_message("INFO", "Usando estrutura de mensagens padrão"))
        TICKET_MESSAGES = {}
    except json.JSONDecodeError as e:
        print(log_message("ERROR", f"Erro ao decodificar JSON em {TICKET_MESSAGES_FILE}: {e}", "❌"))
        print(log_message("INFO", "Usando estrutura de mensagens padrão"))
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
        
        # Garante que as mensagens já foram carregadas
        if not TICKET_MESSAGES:
            load_ticket_messages()

        # Valida as categorias contra TICKET_CATEGORIES
        valid_categories = {cat[0] for cat in TICKET_CATEGORIES}
        json_categories = TICKET_MESSAGES.get("categories", {}).keys()
        missing_categories = valid_categories - set(json_categories)
        if missing_categories:
            print(log_message("WARNING", f"Categorias em TICKET_CATEGORIES não encontradas em ticket_messages.json: {missing_categories}", "⚠️"))

        for label, _, emoji, category_id in TICKET_CATEGORIES:
            category_data = TICKET_MESSAGES.get("categories", {}).get(label, {})
            dropdown_description = category_data.get("dropdown_description", f"Descrição padrão para {label}")
            if len(dropdown_description) > 100:
                dropdown_description = dropdown_description[:97] + "..."

            if category_id:
                options.append(discord.SelectOption(label=label, description=dropdown_description, emoji=emoji, value=label))
            else:
                print(log_message("WARNING", f"Categoria '{label}' sem ID de categoria configurado. Ignorada no dropdown", "⚠️"))

        super().__init__(
            placeholder=TICKET_MESSAGES.get("ticket_panel_embed", {}).get("dropdown_placeholder", "Selecione uma categoria..."),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        selected_category_label = self.values[0]
        selected_category_info = next((cat for cat in TICKET_CATEGORIES if cat[0] == selected_category_label), None)

        if not selected_category_info:
            await interaction.followup.send("Erro: Categoria selecionada inválida.", ephemeral=True)
            print(log_message("ERROR", f"Categoria inválida '{selected_category_label}' selecionada por {interaction.user.display_name} ({interaction.user.id})", "❌"))
            return

        category_name, _, _, category_id = selected_category_info

        # Verificação do limite de tickets
        all_open_tickets = get_all_open_tickets()
        user_open_tickets = [ticket for ticket in all_open_tickets if ticket['creator_id'] == interaction.user.id]
        MAX_OPEN_TICKETS = 2
        if len(user_open_tickets) >= MAX_OPEN_TICKETS:
            await interaction.followup.send(
                f"Você já tem {MAX_OPEN_TICKETS} tickets abertos. Por favor, feche um ticket existente antes de abrir um novo.",
                ephemeral=True
            )
            print(log_message("WARNING", f"Usuário {interaction.user.display_name} ({interaction.user.id}) tentou abrir ticket, mas atingiu o limite de {MAX_OPEN_TICKETS}", "⚠️"))
            return

        # Verifica se o usuário já tem um ticket aberto na mesma categoria
        existing_ticket = next((t for t in user_open_tickets if t['category'] == category_name), None)
        if existing_ticket:
            existing_channel = self.cog.bot.get_channel(existing_ticket['channel_id'])
            channel_mention = existing_channel.mention if existing_channel else f"ID do Canal: {existing_ticket['channel_id']}"
            await interaction.followup.send(
                TICKET_MESSAGES.get("ticket_already_open", "Você já tem um ticket aberto: {canal_mencao}").format(canal_mencao=channel_mention),
                ephemeral=True
            )
            print(log_message("WARNING", f"Usuário {interaction.user.display_name} ({interaction.user.id}) tentou abrir ticket em {category_name}, mas já tem um: {channel_mention}", "⚠️"))
            return

        try:
            guild = interaction.guild
            category_channel = guild.get_channel(category_id)
            if not category_channel or not isinstance(category_channel, discord.CategoryChannel):
                await interaction.followup.send(f"Erro: A categoria '{category_name}' não foi encontrada ou não é uma categoria válida.", ephemeral=True)
                print(log_message("ERROR", f"Categoria {category_name} (ID: {category_id}) não encontrada ou inválida", "❌"))
                return

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True, attach_files=True, manage_channels=True)
            }
            if self.cog.ticket_moderator_role:
                overwrites[self.cog.ticket_moderator_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)

            ticket_channel = await category_channel.create_text_channel(
                name=f"ticket-{interaction.user.name.lower().replace(' ', '-')}",
                overwrites=overwrites,
                topic=f"Ticket de suporte para {interaction.user.display_name} ({category_name} - ID: {interaction.user.id})"
            )

            # Adiciona o ticket ao banco de dados
            add_ticket_to_db(ticket_channel.id, interaction.user.id, interaction.user.display_name, category_name)
            print(log_message("INFO", f"Ticket criado por {interaction.user.display_name} ({interaction.user.id}) em {ticket_channel.name} ({category_name})", "🎫"))

            # Criação da embed de boas-vindas
            category_messages = TICKET_MESSAGES.get("categories", {}).get(category_name, {})
            welcome_embed_data = category_messages.get("welcome_embed", TICKET_MESSAGES.get("ticket_welcome_embed", {}))
            
            embed = discord.Embed(
                title=welcome_embed_data.get("title", "Bem-vindo ao seu Ticket").format(categoria=category_name, usuario=interaction.user.display_name),
                description=welcome_embed_data.get("description", "Descrição padrão").format(categoria=category_name, usuario=interaction.user.display_name),
                color=discord.Color.from_str(welcome_embed_data.get("color", "#7289DA"))
            )

            # Adiciona campos (fields) da embed
            for field in welcome_embed_data.get("fields", []):
                embed.add_field(
                    name=field.get("name", " "),
                    value=field.get("value", " ").format(categoria=category_name, usuario=interaction.user.display_name),
                    inline=field.get("inline", False)
                )

            # Adiciona thumbnail, se disponível
            thumbnail_url = welcome_embed_data.get("thumbnail_url", None)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            # Adiciona footer
            embed.set_footer(text=welcome_embed_data.get("footer", "").format(
                id_ticket=ticket_channel.id,
                usuario=interaction.user.display_name,
                data_hora=datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M')
            ))

            # Envia a mensagem de boas-vindas
            await ticket_channel.send(
                content=f"{interaction.user.mention} {self.cog.ticket_moderator_role.mention if self.cog.ticket_moderator_role else ''}",
                embed=embed,
                view=TicketControlView(self.cog)
            )

            await interaction.followup.send(
                TICKET_MESSAGES.get("ticket_created_success", "Seu ticket foi criado em {canal_mencao}!").format(canal_mencao=ticket_channel.mention),
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                TICKET_MESSAGES.get("error_creating_ticket", "Erro ao criar ticket: `{erro}`").format(erro=str(e)),
                ephemeral=True
            )
            print(log_message("ERROR", f"Erro ao criar ticket para {interaction.user.display_name} ({interaction.user.id}): {e}", "❌"))

class TicketControlView(discord.ui.View):
    def __init__(self, cog_instance):
        super().__init__(timeout=None)
        self.cog = cog_instance

    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_button")
    async def close_ticket_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        is_moderator = self.cog.ticket_moderator_role and self.cog.ticket_moderator_role in interaction.user.roles
        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == interaction.channel.id), None)
        is_creator = ticket_data and ticket_data['creator_id'] == interaction.user.id

        if not is_moderator and not is_creator:
            await interaction.followup.send(
                TICKET_MESSAGES.get("no_permission_close_ticket", "Você não tem permissão para fechar este ticket."),
                ephemeral=True
            )
            print(log_message("WARNING", f"Usuário {interaction.user.display_name} ({interaction.user.id}) tentou fechar ticket sem permissão", "🚫"))
            return

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await interaction.channel.send(TICKET_MESSAGES.get("close_message", "Fechando ticket em 5 segundos..."))
        await asyncio.sleep(5)

        await self.cog.create_ticket_transcript(interaction.channel)

        try:
            await interaction.channel.delete()
            remove_ticket_from_db(interaction.channel.id)
            print(log_message("INFO", f"Ticket {interaction.channel.name} fechado por {interaction.user.display_name} ({interaction.user.id})", "🔒"))
        except Exception as e:
            await interaction.followup.send(f"Erro ao deletar o canal: {e}", ephemeral=True)
            print(log_message("ERROR", f"Erro ao deletar ticket {interaction.channel.name}: {e}", "❌"))
            for item in self.children:
                item.disabled = False
            await interaction.message.edit(view=self)

    @discord.ui.button(label="Transcrever Ticket", style=discord.ButtonStyle.secondary, emoji="📄", custom_id="transcript_ticket_button")
    async def transcript_ticket_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        is_moderator = self.cog.ticket_moderator_role and self.cog.ticket_moderator_role in interaction.user.roles
        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == interaction.channel.id), None)
        is_creator = ticket_data and ticket_data['creator_id'] == interaction.user.id

        if not is_moderator and not is_creator:
            await interaction.followup.send(
                TICKET_MESSAGES.get("no_permission_transcript_ticket", "Você não tem permissão para transcrever este ticket."),
                ephemeral=True
            )
            print(log_message("WARNING", f"Usuário {interaction.user.display_name} ({interaction.user.id}) tentou transcrever ticket sem permissão", "🚫"))
            return

        await interaction.followup.send(TICKET_MESSAGES.get("transcript_creating", "Criando transcrito do ticket..."), ephemeral=True)
        await self.cog.create_ticket_transcript(interaction.channel)
        await interaction.followup.send(TICKET_MESSAGES.get("transcript_success", "Transcrito criado e enviado para o canal de logs!"), ephemeral=True)

class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._ticket_panel_message_id = None
        self.ticket_moderator_role = None
        load_ticket_messages()

    async def _load_ticket_panel_message_id(self):
        try:
            with open(TICKET_PANEL_MESSAGE_FILE, 'r', encoding='utf-8') as f:
                self._ticket_panel_message_id = int(f.read().strip())
            print(log_message("INFO", f"ID da mensagem do painel de tickets carregado: {self._ticket_panel_message_id}", "📄"))
        except (FileNotFoundError, ValueError):
            self._ticket_panel_message_id = None
            print(log_message("WARNING", f"Arquivo {TICKET_PANEL_MESSAGE_FILE} não encontrado ou inválido", "⚠️"))

    async def _save_ticket_panel_message_id(self, message_id: int):
        self._ticket_panel_message_id = message_id
        with open(TICKET_PANEL_MESSAGE_FILE, 'w', encoding='utf-8') as f:
            f.write(str(message_id))
        print(log_message("INFO", f"ID da mensagem do painel de tickets salvo: {self._ticket_panel_message_id}", "💾"))

    @commands.Cog.listener()
    async def on_ready(self):
        print(log_message("INFO", "TicketsCog está pronto", "✅"))
        await self._load_ticket_panel_message_id()

        if self._ticket_panel_message_id:
            try:
                channel = self.bot.get_channel(TICKET_PANEL_CHANNEL_ID)
                if channel:
                    await channel.fetch_message(self._ticket_panel_message_id)
                    self.bot.add_view(TicketPanelView(self), message_id=self._ticket_panel_message_id)
                    print(log_message("INFO", f"View do painel de tickets persistente adicionada para mensagem ID: {self._ticket_panel_message_id}", "🔗"))
                else:
                    print(log_message("WARNING", f"Canal do painel de tickets (ID: {TICKET_PANEL_CHANNEL_ID}) não encontrado", "⚠️"))
                    self._ticket_panel_message_id = None
            except discord.NotFound:
                print(log_message("WARNING", f"Mensagem do painel de tickets (ID: {self._ticket_panel_message_id}) não encontrada", "⚠️"))
                self._ticket_panel_message_id = None
            except Exception as e:
                print(log_message("ERROR", f"Erro ao re-associar View do painel de tickets: {e}", "❌"))
                self._ticket_panel_message_id = None

        if TICKET_MODERATOR_ROLE_ID:
            if self.bot.guilds:
                guild = self.bot.get_guild(self.bot.guilds[0].id)
                if guild:
                    self.ticket_moderator_role = guild.get_role(TICKET_MODERATOR_ROLE_ID)
                    if not self.ticket_moderator_role:
                        print(log_message("WARNING", f"Cargo de moderador de tickets (ID: {TICKET_MODERATOR_ROLE_ID}) não encontrado na guild '{guild.name}'", "⚠️"))
                else:
                    print(log_message("WARNING", "Bot não conseguiu obter a guild para popular o cargo de moderador de tickets", "⚠️"))
            else:
                print(log_message("WARNING", "Bot não está em nenhuma guild para popular o cargo de moderador de tickets", "⚠️"))
        else:
            print(log_message("WARNING", "TICKET_MODERATOR_ROLE_ID não configurado", "⚠️"))

        open_tickets = get_all_open_tickets()
        for ticket in open_tickets:
            try:
                channel = self.bot.get_channel(ticket['channel_id'])
                if channel:
                    async for message in channel.history(limit=50):
                        welcome_embed_title_prefix = TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("title", "").split('{')[0].strip()
                        if message.author == self.bot.user and message.embeds and (message.embeds[0].title or "").startswith(welcome_embed_title_prefix):
                            self.bot.add_view(TicketControlView(self), message_id=message.id)
                            print(log_message("INFO", f"View de controle persistente adicionada para ticket {channel.name}", "🔗"))
                            break
                    else:
                        print(log_message("WARNING", f"Mensagem de controle do ticket {channel.name} não encontrada", "⚠️"))
                else:
                    print(log_message("WARNING", f"Canal do ticket {ticket['channel_id']} não encontrado, removendo do DB", "⚠️"))
                    remove_ticket_from_db(ticket['channel_id'])
            except Exception as e:
                print(log_message("ERROR", f"Erro ao re-adicionar view para ticket {ticket['channel_id']}: {e}", "❌"))

    @commands.command(name="setuptickets", help="Envia o painel de criação de tickets para o canal configurado.")
    @commands.has_permissions(administrator=True)
    async def setup_tickets_panel(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)

        channel = self.bot.get_channel(TICKET_PANEL_CHANNEL_ID)
        if not channel:
            await ctx.send(f"Erro: Canal do painel de tickets (ID: {TICKET_PANEL_CHANNEL_ID}) não encontrado.", ephemeral=True)
            print(log_message("ERROR", f"Canal do painel de tickets (ID: {TICKET_PANEL_CHANNEL_ID}) não encontrado para !setuptickets", "❌"))
            return

        if not TICKET_MESSAGES:
            load_ticket_messages()
            if not TICKET_MESSAGES:
                await ctx.send("Erro: Não foi possível carregar ticket_messages.json.", ephemeral=True)
                print(log_message("ERROR", "Falha ao carregar ticket_messages.json para !setuptickets", "❌"))
                return

        panel_embed_data = TICKET_MESSAGES.get("ticket_panel_embed", {})
        embed = discord.Embed(
            title=panel_embed_data.get("title", "Sistema de Tickets"),
            description=panel_embed_data.get("description", "Selecione uma categoria para abrir um ticket."),
            color=discord.Color.from_str(panel_embed_data.get("color", "#36393F"))
        )
        if "fields" in panel_embed_data:
            for field in panel_embed_data["fields"]:
                embed.add_field(
                    name=field.get("name", " "),
                    value=field.get("value", " "),
                    inline=field.get("inline", False)
                )
        embed.set_thumbnail(url=panel_embed_data.get("thumbnail_url", None))
        embed.set_footer(text=panel_embed_data.get("footer", "").format(data_hora=datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M')))

        view = TicketPanelView(self)

        try:
            if self._ticket_panel_message_id:
                message = await channel.fetch_message(self._ticket_panel_message_id)
                await message.edit(embed=embed, view=view)
                await ctx.send("Painel de tickets atualizado com sucesso!", ephemeral=True)
                print(log_message("INFO", f"Painel de tickets atualizado (ID: {self._ticket_panel_message_id}) por {ctx.author.display_name} ({ctx.author.id})", "🔄"))
            else:
                message = await channel.send(embed=embed, view=view)
                await self._save_ticket_panel_message_id(message.id)
                await ctx.send("Painel de tickets enviado com sucesso!", ephemeral=True)
                print(log_message("INFO", f"Painel de tickets enviado (ID: {message.id}) por {ctx.author.display_name} ({ctx.author.id})", "📩"))
        except discord.NotFound:
            message = await channel.send(embed=embed, view=view)
            await self._save_ticket_panel_message_id(message.id)
            await ctx.send("Painel de tickets recriado com sucesso!", ephemeral=True)
            print(log_message("INFO", f"Painel de tickets recriado (ID: {message.id}) por {ctx.author.display_name} ({ctx.author.id})", "📩"))
        except Exception as e:
            await ctx.send(f"Erro ao enviar/atualizar painel de tickets: {e}", ephemeral=True)
            print(log_message("ERROR", f"Erro ao enviar/atualizar painel de tickets por {ctx.author.display_name} ({ctx.author.id}): {e}", "❌"))

    async def create_ticket_transcript(self, channel: discord.TextChannel):
        transcript_channel = self.bot.get_channel(TICKET_TRANSCRIPTS_CHANNEL_ID)
        if not transcript_channel:
            print(log_message("ERROR", f"Canal de transcritos (ID: {TICKET_TRANSCRIPTS_CHANNEL_ID}) não encontrado", "❌"))
            return

        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == channel.id), None)
        creator_name = ticket_data['creator_name'] if ticket_data else "Desconhecido"
        category_name = ticket_data['category'] if ticket_data else "N/A"

        transcript_content = (
            f"--- Transcrito do Ticket: {channel.name} ({category_name}) ---\n"
            f"Criado por: {creator_name} ({ticket_data['creator_id'] if ticket_data else 'Desconhecido ID'}) em {ticket_data['created_at'] if ticket_data else 'N/A'}\n"
            f"Fechado em: {datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        )

        messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
        welcome_embed_title_prefix = TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("title", "").split('{')[0].strip()

        for msg in messages:
            is_bot_generated_welcome = msg.author == self.bot.user and msg.embeds and (msg.embeds[0].title or "").startswith(welcome_embed_title_prefix)
            is_bot_generated_close = msg.author == self.bot.user and msg.content == TICKET_MESSAGES.get("close_message", "Fechando ticket em 5 segundos...")
            if is_bot_generated_welcome or is_bot_generated_close:
                continue

            timestamp_str = msg.created_at.astimezone().strftime('%d/%m/%Y %H:%M:%S')
            transcript_content += f"[{timestamp_str}] {msg.author.display_name}: {msg.content}\n"
            for attachment in msg.attachments:
                transcript_content += f"     [Anexo: {attachment.url}]\n"
            if msg.embeds:
                for embed in msg.embeds:
                    desc_preview = (embed.description[:100] + "...") if embed.description and len(embed.description) > 100 else (embed.description or "")
                    transcript_content += f"     [Embed: Título='{embed.title or 'Sem Título'}', Descrição='{desc_preview}']\n"

        transcript_content += f"\n--- Fim do Transcrito ---\n"

        file_path = f"{channel.name}_transcript.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(transcript_content)

        try:
            file_to_send = discord.File(file_path, filename=f"{channel.name}.txt")
            transcript_embed_data = TICKET_MESSAGES.get("transcript_embed", {})
            embed = discord.Embed(
                title=transcript_embed_data.get("title", "").format(canal=channel.name),
                description=transcript_embed_data.get("description", "").format(criador=creator_name, categoria=category_name),
                color=discord.Color.from_str(transcript_embed_data.get("color", "#99AAB5"))
            )
            embed.set_thumbnail(url=transcript_embed_data.get("thumbnail_url", None))
            embed.set_footer(text=transcript_embed_data.get("footer", "").format(data_hora=datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M')))
            await transcript_channel.send(embed=embed, file=file_to_send)
            print(log_message("INFO", f"Transcrito do ticket {channel.name} enviado para o canal de logs", "📄"))
        except Exception as e:
            print(log_message("ERROR", f"Erro ao enviar transcrito do ticket {channel.name}: {e}", "❌"))
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    @app_commands.command(name="add", description="Adiciona um usuário ou cargo ao ticket atual.")
    @app_commands.describe(membro_ou_cargo="O usuário ou cargo a ser adicionado.")
    @app_commands.checks.has_role(TICKET_MODERATOR_ROLE_ID)
    async def add_to_ticket(self, interaction: discord.Interaction, membro_ou_cargo: Union[discord.Member, discord.Role]):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Este comando só pode ser usado em um canal de texto.", ephemeral=True)
            print(log_message("WARNING", f"Comando /add usado fora de canal de texto por {interaction.user.display_name} ({interaction.user.id})", "⚠️"))
            return

        open_tickets = get_all_open_tickets()
        is_ticket_channel = any(ticket['channel_id'] == interaction.channel.id for ticket in open_tickets)
        if not is_ticket_channel:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)
            print(log_message("WARNING", f"Comando /add usado fora de canal de ticket por {interaction.user.display_name} ({interaction.user.id})", "⚠️"))
            return

        try:
            await interaction.channel.set_permissions(membro_ou_cargo, view_channel=True, send_messages=True, attach_files=True)
            await interaction.response.send_message(f"✅ {membro_ou_cargo.mention} foi adicionado(a) ao ticket.", ephemeral=True)
            print(log_message("INFO", f"{interaction.user.display_name} ({interaction.user.id}) adicionou {membro_ou_cargo.name} ao ticket {interaction.channel.name}", "➕"))
        except discord.Forbidden:
            await interaction.response.send_message("❌ Não tenho permissão para gerenciar permissões neste canal.", ephemeral=True)
            print(log_message("ERROR", f"Permissão negada ao adicionar {membro_ou_cargo.name} ao ticket {interaction.channel.name}", "🚫"))
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao adicionar {membro_ou_cargo.name}: {e}", ephemeral=True)
            print(log_message("ERROR", f"Erro ao adicionar {membro_ou_cargo.name} ao ticket {interaction.channel.name}: {e}", "❌"))

    @app_commands.command(name="rename", description="Muda o nome do canal do ticket atual.")
    @app_commands.describe(novo_nome="O novo nome para o canal do ticket.")
    @app_commands.checks.has_role(TICKET_MODERATOR_ROLE_ID)
    async def rename_ticket(self, interaction: discord.Interaction, novo_nome: str):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Este comando só pode ser usado em um canal de texto.", ephemeral=True)
            print(log_message("WARNING", f"Comando /rename usado fora de canal de texto por {interaction.user.display_name} ({interaction.user.id})", "⚠️"))
            return

        open_tickets = get_all_open_tickets()
        is_ticket_channel = any(ticket['channel_id'] == interaction.channel.id for ticket in open_tickets)
        if not is_ticket_channel:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)
            print(log_message("WARNING", f"Comando /rename usado fora de canal de ticket por {interaction.user.display_name} ({interaction.user.id})", "⚠️"))
            return

        if len(novo_nome) > 100:
            await interaction.response.send_message("O nome do canal não pode ter mais de 100 caracteres.", ephemeral=True)
            print(log_message("WARNING", f"Nome de canal muito longo ({len(novo_nome)} caracteres) por {interaction.user.display_name} ({interaction.user.id})", "⚠️"))
            return

        formatted_name = novo_nome.lower().replace(' ', '-')
        formatted_name = ''.join(c for c in formatted_name if c.isalnum() or c == '-')

        try:
            old_name = interaction.channel.name
            await interaction.channel.edit(name=formatted_name)
            await interaction.response.send_message(f"✅ Nome do ticket alterado de `{old_name}` para `{formatted_name}`.", ephemeral=True)
            print(log_message("INFO", f"{interaction.user.display_name} ({interaction.user.id}) renomeou ticket de {old_name} para {formatted_name}", "✏️"))
        except discord.Forbidden:
            await interaction.response.send_message("❌ Não tenho permissão para gerenciar canais.", ephemeral=True)
            print(log_message("ERROR", f"Permissão negada ao renomear ticket {interaction.channel.name}", "🚫"))
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao renomear o ticket: {e}", ephemeral=True)
            print(log_message("ERROR", f"Erro ao renomear ticket {interaction.channel.name}: {e}", "❌"))

    @commands.command(name="cleartickets", help="Deleta todos os canais de ticket abertos e remove-os do DB.")
    @commands.has_permissions(administrator=True)
    async def clear_all_tickets_prefix(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)

        open_tickets = get_all_open_tickets()
        if not open_tickets:
            await ctx.send("Não há tickets abertos para limpar.", ephemeral=True)
            print(log_message("INFO", f"Comando !cleartickets executado por {ctx.author.display_name} ({ctx.author.id}): nenhum ticket aberto", "ℹ️"))
            return

        deleted_count = 0
        failed_deletions = []

        await ctx.send(f"A iniciar limpeza de {len(open_tickets)} tickets...", ephemeral=True)
        print(log_message("INFO", f"Iniciando limpeza de {len(open_tickets)} tickets por {ctx.author.display_name} ({ctx.author.id})", "🧹"))

        for ticket in open_tickets:
            channel_id = ticket['channel_id']
            channel_name = f"ticket-{ticket.get('creator_name', 'unknown').lower().replace(' ', '-')}"
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.delete(reason="Comando !cleartickets")
                    remove_ticket_from_db(channel_id)
                    deleted_count += 1
                    print(log_message("INFO", f"Ticket {channel_name} (ID: {channel_id}) deletado e removido do DB", "🗑️"))
                else:
                    remove_ticket_from_db(channel_id)
                    deleted_count += 1
                    print(log_message("INFO", f"Ticket {channel_name} (ID: {channel_id}) não encontrado no Discord, removido do DB", "🗑️"))
            except discord.NotFound:
                remove_ticket_from_db(channel_id)
                deleted_count += 1
                print(log_message("INFO", f"Ticket {channel_name} (ID: {channel_id}) já não existia no Discord, removido do DB", "🗑️"))
            except Exception as e:
                failed_deletions.append(f"Ticket {channel_name} (ID: {channel_id}): {e}")
                print(log_message("ERROR", f"Erro ao deletar ticket {channel_name} (ID: {channel_id}): {e}", "❌"))

        if failed_deletions:
            error_message = "\n".join(failed_deletions)
            await ctx.send(
                f"Limpeza concluída. {deleted_count} tickets limpos.\n"
                f"Erros:\n```\n{error_message}\n```",
                ephemeral=True
            )
            print(log_message("WARNING", f"Limpeza de tickets com {len(failed_deletions)} erros", "⚠️"))
        else:
            await ctx.send(f"Limpeza concluída! {deleted_count} tickets limpos.", ephemeral=True)
            print(log_message("INFO", f"Comando !cleartickets finalizado: {deleted_count} tickets limpos", "✅"))

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))
