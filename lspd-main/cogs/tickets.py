import discord
from discord.ext import commands
import asyncio
import os
import json
from datetime import datetime

# Importa as configurações
from config import (
    TICKET_PANEL_CHANNEL_ID,
    TICKET_TRANSCRIPTS_CHANNEL_ID,
    TICKET_MODERATOR_ROLE_ID,
    TICKET_PANEL_MESSAGE_FILE,
    TICKET_CATEGORIES,
    TICKET_MESSAGES_FILE
)

# Importa as funções do banco de dados para tickets (agora para PostgreSQL)
from database import add_ticket_to_db, remove_ticket_from_db, get_all_open_tickets

# Variável global para armazenar as mensagens customizadas para tickets
TICKET_MESSAGES = {}

# Função para carregar as mensagens customizadas do arquivo JSON
def load_ticket_messages():
    global TICKET_MESSAGES
    try:
        # Tenta carregar o ficheiro JSON
        with open(TICKET_MESSAGES_FILE, 'r', encoding='utf-8') as f:
            TICKET_MESSAGES = json.load(f)
        print(f"Mensagens de ticket carregadas de {TICKET_MESSAGES_FILE}")
    except FileNotFoundError:
        print(f"Erro: Arquivo de mensagens de ticket '{TICKET_MESSAGES_FILE}' não encontrado.")
        print("Será usada uma estrutura de mensagens padrão. Por favor, crie este arquivo ou verifique o caminho.")
        # Se o ficheiro não for encontrado, usa uma estrutura padrão para evitar KeyErrors
        TICKET_MESSAGES = {
            "ticket_panel_embed": {
                "title": "Painel de Criação de Tickets",
                "description": "Selecione uma categoria de ticket abaixo para iniciar o seu pedido de suporte.",
                "color": "#FFD700",
                "footer": "Clique na categoria para abrir um ticket."
            },
            "categories": {
                "Reportar Jogador": {
                    "dropdown_description": "Use para relatar violações de regras de jogadores.",
                    "welcome_embed": {
                        "title": "🚨 Ticket de Reporte de Jogador",
                        "description": "Olá {usuario}, bem-vindo ao seu ticket de reporte de jogador. Por favor, descreva o incidente com o máximo de detalhes possível, incluindo a data, hora, envolvidos e evidências (prints/vídeos).",
                        "color": "#FF0000",
                        "thumbnail_url": None
                    }
                },
                "Suporte Geral": {
                    "dropdown_description": "Para dúvidas e assistência geral.",
                    "welcome_embed": {
                        "title": "❓ Ticket de Suporte Geral",
                        "description": "Olá {usuario}, bem-vindo ao seu ticket de suporte geral. Por favor, descreva a sua dúvida ou problema. Nossa equipe responderá em breve.",
                        "color": "#0000FF",
                        "thumbnail_url": None
                    }
                },
                "Recursos Humanos": {
                    "dropdown_description": "Assuntos de RH, candidaturas, etc.",
                    "welcome_embed": {
                        "title": "👔 Ticket de Recursos Humanos",
                        "description": "Olá {usuario}, bem-vindo ao seu ticket de RH. Por favor, explique a sua questão ou o motivo do seu contato. A equipe de RH entrará em contato em breve.",
                        "color": "#00FF00",
                        "thumbnail_url": None
                    }
                }
            },
            "ticket_welcome_embed": {
                "title": "Bem-vindo ao seu Ticket da LSPD ({categoria})",
                "description": "Aguarde enquanto um membro da nossa equipe se junta a você para ajudar. Por favor, descreva o seu problema ou questão.",
                "color": "#00FFFF",
                "footer": "Ticket ID: {id_ticket} | Criado por: {usuario} em {data_hora}"
            },
            "ticket_created_success": "Seu ticket foi criado em {canal_mencao}!",
            "ticket_already_open": "Você já tem um ticket aberto nesta categoria: {canal_mencao}. Por favor, use-o ou feche-o antes de abrir um novo.",
            "error_creating_ticket": "Ocorreu um erro ao criar seu ticket. Por favor, tente novamente mais tarde ou contate um administrador. Erro: `{erro}`",
            "no_permission_close_ticket": "Você não tem permissão para fechar este ticket.",
            "close_message": "Fechando ticket em 5 segundos...",
            "transcript_creating": "Criando transcrito do ticket...",
            "transcript_success": "Transcrito criado e enviado para o canal de logs!",
            "transcript_embed": {
                "title": "📄 Transcrito do Ticket: #{canal}",
                "description": "Criado por: **{criador}**\nCategoria: **{categoria}**",
                "color": "#D3D3D3",
                "footer": "Transcrito gerado em: {data_hora}"
            }
        }
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON no arquivo de mensagens de ticket: {e}. Verifique a sintaxe JSON.")
        print("Será usada uma estrutura de mensagens padrão para evitar erros.")
        TICKET_MESSAGES = {} # Garante que é um dicionário vazio para evitar erros (e o código acima preenche o padrão)


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
        
        # Garante que as mensagens já foram carregadas antes de construir as opções
        if not TICKET_MESSAGES:
            load_ticket_messages()

        for label, _, emoji, category_id in TICKET_CATEGORIES:
            # Buscando a descrição do dropdown do JSON
            category_data = TICKET_MESSAGES.get("categories", {}).get(label, {})
            dropdown_description = category_data.get("dropdown_description", f"Descrição padrão para {label}")

            # Limitar a descrição a 100 caracteres para compatibilidade com Discord
            if len(dropdown_description) > 100:
                dropdown_description = dropdown_description[:97] + "..." 

            if category_id: # Apenas adiciona categorias que tenham um ID de categoria configurado
                options.append(discord.SelectOption(label=label, description=dropdown_description, emoji=emoji, value=label))
            else:
                print(f"Aviso: Categoria '{label}' sem ID de categoria configurado. Será ignorada no dropdown.")

        super().__init__(
            placeholder=TICKET_MESSAGES.get("ticket_panel_embed", {}).get("description", "Selecione uma categoria de ticket...")[:100],
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True) # Defer para que o bot "pense"
        
        selected_category_label = self.values[0]
        selected_category_info = next((cat for cat in TICKET_CATEGORIES if cat[0] == selected_category_label), None)

        if not selected_category_info:
            await interaction.followup.send("Erro: Categoria selecionada inválida.", ephemeral=True)
            return

        category_name, _, _, category_id = selected_category_info

        # --- VERIFICAÇÃO DO LIMITE DE TICKETS ---
        all_open_tickets = get_all_open_tickets()
        user_open_tickets = [ticket for ticket in all_open_tickets if ticket['creator_id'] == interaction.user.id]

        MAX_OPEN_TICKETS = 2 # Defina o limite de tickets abertos por utilizador aqui
        if len(user_open_tickets) >= MAX_OPEN_TICKETS:
            await interaction.followup.send(
                f"Você já tem {MAX_OPEN_TICKETS} tickets abertos. Por favor, feche um ticket existente antes de abrir um novo.",
                ephemeral=True
            )
            return 
        # --- FIM DA VERIFICAÇÃO ---

        # Verifica se o usuário já tem um ticket aberto na mesma categoria (melhorado com base no DB)
        existing_ticket_in_db_for_category = next((t for t in user_open_tickets if t['category'] == category_name), None)

        if existing_ticket_in_db_for_category:
            existing_channel_obj = self.cog.bot.get_channel(existing_ticket_in_db_for_category['channel_id'])
            channel_mention = existing_channel_obj.mention if existing_channel_obj else f"ID do Canal: {existing_ticket_in_db_for_category['channel_id']}"

            await interaction.followup.send(
                TICKET_MESSAGES.get("ticket_already_open", "Você já tem um ticket aberto nesta categoria: {canal_mencao}").format(
                    canal_mencao=channel_mention
                ),
                ephemeral=True
            )
            return
        
        try:
            guild = interaction.guild
            category_channel = guild.get_channel(category_id)
            if not category_channel or not isinstance(category_channel, discord.CategoryChannel):
                await interaction.followup.send(f"Erro: A categoria '{category_name}' não foi encontrada ou não é uma categoria válida. Contate um administrador.", ephemeral=True)
                print(f"Erro: Categoria {category_name} (ID: {category_id}) não é válida ou não encontrada.")
                return

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
                # Permissões do bot para gerenciar o canal
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True, attach_files=True, manage_channels=True)
            }
            # Adiciona permissões para o cargo de moderador de tickets, se configurado
            if self.cog.ticket_moderator_role:
                overwrites[self.cog.ticket_moderator_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)

            ticket_channel = await category_channel.create_text_channel(
                name=f"ticket-{interaction.user.name.lower().replace(' ', '-')}",
                overwrites=overwrites,
                topic=f"Ticket de suporte para {interaction.user.display_name} ({category_name} - ID: {interaction.user.id})"
            )

            # Adiciona o ticket ao banco de dados (função agora adaptada para PostgreSQL)
            add_ticket_to_db(ticket_channel.id, interaction.user.id, interaction.user.display_name, category_name)

            # --- Obtendo a embed de boas-vindas específica da categoria ---
            category_messages = TICKET_MESSAGES.get("categories", {}).get(category_name, {})
            welcome_embed_data = category_messages.get("welcome_embed", {})

            # Usar títulos e descrições específicos da categoria, com fallback para genéricos
            embed_title = welcome_embed_data.get("title", TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("title", "")).format(
                categoria=category_name,
                usuario=interaction.user.display_name
            )
            # Garantir que a descrição NUNCA seja vazia, mesmo com placeholders
            embed_description = welcome_embed_data.get("description", TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("description", "Descrição padrão para o seu ticket. Nossa equipe entrará em contato em breve.")).format(
                categoria=category_name, # Passa categoria para format
                usuario=interaction.user.display_name # Passa usuario para format
            )
            
            # Converte a cor hexadecimal para discord.Color
            embed_color_str = welcome_embed_data.get("color", TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("color", "#0000FF"))
            embed_color = discord.Color.from_str(embed_color_str)
            
            embed = discord.Embed(
                title=embed_title,
                description=embed_description,
                color=embed_color
            )

            # Adicionar URL da Thumbnail se existir
            thumbnail_url = welcome_embed_data.get("thumbnail_url", TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("thumbnail_url", None))
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            # O footer é comum para todos os tickets, então pegamos do nível superior
            embed.set_footer(text=TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("footer", "").format(
                id_ticket=ticket_channel.id,
                usuario=interaction.user.display_name,
                data_hora=datetime.now().strftime('%d/%m/%Y %H:%M')
            ))
            
            # Envia a mensagem de boas-vindas com a View de controle do ticket
            await ticket_channel.send(
                content=f"{interaction.user.mention} {self.cog.ticket_moderator_role.mention if self.cog.ticket_moderator_role else ''}",
                embed=embed,
                view=TicketControlView(self)
            )

            await interaction.followup.send(
                TICKET_MESSAGES.get("ticket_created_success", "Seu ticket foi criado em {canal_mencao}!").format(
                    canal_mencao=ticket_channel.mention
                ),
                ephemeral=True
            )
            print(f"Ticket criado por {interaction.user.display_name} em {ticket_channel.name}.")

        except Exception as e:
            await interaction.followup.send(
                TICKET_MESSAGES.get("error_creating_ticket", "Ocorreu um erro ao criar seu ticket. Por favor, tente novamente mais tarde ou contate um administrador. Erro: `{erro}`").format(
                    erro=e
                ),
                ephemeral=True
            )
            print(f"Erro ao criar ticket para {interaction.user.display_name}: {e}")

class TicketControlView(discord.ui.View):
    def __init__(self, cog_instance):
        super().__init__(timeout=None)
        self.cog = cog_instance

    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_button")
    async def close_ticket_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        is_moderator = self.cog.ticket_moderator_role and self.cog.ticket_moderator_role in interaction.user.roles
        
        # Pega os dados do ticket do DB para verificar o criador
        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == interaction.channel.id), None)
        is_creator = ticket_data and ticket_data['creator_id'] == interaction.user.id

        if not is_moderator and not is_creator:
            await interaction.followup.send(
                TICKET_MESSAGES.get("no_permission_close_ticket", "Você não tem permissão para fechar este ticket."),
                ephemeral=True
            )
            return

        # Desabilita os botões para evitar cliques múltiplos
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await interaction.channel.send(TICKET_MESSAGES.get("close_message", "Fechando ticket em 5 segundos..."))
        await asyncio.sleep(5) # Pequena pausa antes de fechar

        # Cria o transcrito antes de deletar o canal
        await self.cog.create_ticket_transcript(interaction.channel)

        try:
            await interaction.channel.delete()
            # Remove o ticket do banco de dados (função agora adaptada para PostgreSQL)
            remove_ticket_from_db(interaction.channel.id)
            print(f"Ticket {interaction.channel.name} fechado e deletado por {interaction.user.display_name}.")
        except Exception as e:
            print(f"Erro ao deletar canal do ticket {interaction.channel.name}: {e}")
            await interaction.followup.send(f"Erro ao deletar o canal: {e}", ephemeral=True)
            # Reabilita os botões se houver um erro de deleção
            for item in self.children:
                item.disabled = False
            await interaction.message.edit(view=self)

    @discord.ui.button(label="Transcrever Ticket", style=discord.ButtonStyle.secondary, emoji="📄", custom_id="transcript_ticket_button")
    async def transcript_ticket_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # Garante que apenas moderadores ou o criador possam transcrever
        is_moderator = self.cog.ticket_moderator_role and self.cog.ticket_moderator_role in interaction.user.roles
        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == interaction.channel.id), None)
        is_creator = ticket_data and ticket_data['creator_id'] == interaction.user.id

        if not is_moderator and not is_creator:
            await interaction.followup.send(
                TICKET_MESSAGES.get("no_permission_transcript_ticket", "Você não tem permissão para transcrever este ticket."), # Adicione esta mensagem ao JSON
                ephemeral=True
            )
            return

        await interaction.followup.send(TICKET_MESSAGES.get("transcript_creating", "Criando transcrito do ticket..."), ephemeral=True)
        
        await self.cog.create_ticket_transcript(interaction.channel)
        
        await interaction.followup.send(TICKET_MESSAGES.get("transcript_success", "Transcrito criado e enviado para o canal de logs!"), ephemeral=True)

# --- Cog Principal de Tickets ---
class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._ticket_panel_message_id = None
        self.ticket_moderator_role = None # Será populado em on_ready

        # Carrega as mensagens dos tickets no __init__ (síncrono, então está ok)
        load_ticket_messages()

    async def _load_ticket_panel_message_id(self):
        """Carrega o ID da mensagem do painel de tickets de um arquivo."""
        try:
            with open(TICKET_PANEL_MESSAGE_FILE, 'r') as f:
                self._ticket_panel_message_id = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            self._ticket_panel_message_id = None
        print(f"ID da mensagem do painel de tickets carregado: {self._ticket_panel_message_id}")

    async def _save_ticket_panel_message_id(self, message_id: int):
        """Salva o ID da mensagem do painel de tickets em um arquivo."""
        self._ticket_panel_message_id = message_id
        with open(TICKET_PANEL_MESSAGE_FILE, 'w') as f:
            f.write(str(message_id))
        print(f"ID da mensagem do painel de tickets salvo: {self._ticket_panel_message_id}")

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Quando o bot reconecta, adicionamos as Views persistentes e populamos o cargo de moderador.
        """
        print("TicketsCog está pronto.")

        await self._load_ticket_panel_message_id()

        # Re-adiciona a View do painel de tickets se o ID da mensagem for conhecido
        if self._ticket_panel_message_id:
            try:
                channel = self.bot.get_channel(TICKET_PANEL_CHANNEL_ID)
                if channel:
                    # Tenta buscar a mensagem para re-associar a View
                    message = await channel.fetch_message(self._ticket_panel_message_id) 
                    self.bot.add_view(TicketPanelView(self), message_id=self._ticket_panel_message_id)
                    print(f"View do painel de tickets persistente adicionada para a mensagem ID: {self._ticket_panel_message_id}")
                else:
                    print(f"Aviso: Canal do painel de tickets (ID: {TICKET_PANEL_CHANNEL_ID}) não encontrado para re-associar a View.")
                    self._ticket_panel_message_id = None # Redefine para recriar no próximo setup
            except discord.NotFound:
                print(f"Mensagem do painel de tickets (ID: {self._ticket_panel_message_id}) não encontrada, será recriada no próximo setup com !setuptickets.")
                self._ticket_panel_message_id = None # Redefine para recriar no próximo setup
            except Exception as e:
                print(f"Erro ao re-associar a View do painel de tickets: {e}")
                self._ticket_panel_message_id = None


        # Popula o cargo de moderador de tickets
        if TICKET_MODERATOR_ROLE_ID:
            # Obtém a primeira guild que o bot está em (assumindo que o bot está em apenas uma ou a primeira é a principal)
            if self.bot.guilds:
                guild = self.bot.get_guild(self.bot.guilds[0].id) # Pega a primeira guild que o bot está
                if guild:
                    self.ticket_moderator_role = guild.get_role(TICKET_MODERATOR_ROLE_ID)
                    if not self.ticket_moderator_role:
                        print(f"Aviso: Cargo de moderador de tickets com ID {TICKET_MODERATOR_ROLE_ID} não encontrado na guild '{guild.name}'.")
                else:
                    print("Aviso: Bot não conseguiu obter a guild para popular o cargo de moderador de tickets.")
            else:
                print("Aviso: Bot não está em nenhuma guild para popular o cargo de moderador de tickets.")
        else:
            print("Aviso: TICKET_MODERATOR_ROLE_ID não configurado. Comandos de ticket podem ter permissões limitadas.")
            
        # Re-adiciona a View dos botões de controle para todos os tickets abertos no DB
        # Isso garante que botões em tickets existentes funcionem após um reinício
        open_tickets_from_db = get_all_open_tickets()
        for ticket in open_tickets_from_db:
            try:
                channel = self.bot.get_channel(ticket['channel_id'])
                if channel:
                    # Percorre as últimas 50 mensagens para encontrar a mensagem do bot com a View de controle
                    # (aquela com a embed de boas-vindas)
                    async for message in channel.history(limit=50):
                        # Pega a parte inicial do título da embed de boas-vindas do JSON para ser mais robusto
                        welcome_embed_title_prefix = TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("title", "").split('{')[0].strip()
                        
                        if message.author == self.bot.user and message.embeds and (message.embeds[0].title or "").startswith(welcome_embed_title_prefix):
                            self.bot.add_view(TicketControlView(self), message_id=message.id)
                            print(f"View de controle persistente adicionada para ticket {channel.name}.")
                            break # Encontrou a mensagem, para de procurar
                    else: # Se o loop terminar sem encontrar a mensagem
                        print(f"Aviso: Mensagem de controle do ticket {channel.name} não encontrada para re-associar a View. Pode ter sido apagada.")
                else:
                    print(f"Aviso: Canal do ticket {ticket['channel_id']} não encontrado no Discord (provavelmente deletado manualmente), removendo do DB.")
                    remove_ticket_from_db(ticket['channel_id']) # Limpa do DB se o canal não existe
            except Exception as e:
                print(f"Erro ao re-adicionar view para ticket {ticket['channel_id']}: {e}")


    @commands.command(name="setuptickets", help="Envia o painel de criação de tickets para o canal configurado.")
    @commands.has_permissions(administrator=True) # Apenas administradores podem usar
    async def setup_tickets_panel(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True) # Defer para que o bot "pense"

        channel = self.bot.get_channel(TICKET_PANEL_CHANNEL_ID)
        if not channel:
            await ctx.send(f"Erro: Canal do painel de tickets com ID {TICKET_PANEL_CHANNEL_ID} não encontrado em suas configurações. Verifique o config.py e as variáveis de ambiente.", ephemeral=True)
            return

        # Garante que as mensagens já foram carregadas
        if not TICKET_MESSAGES:
            load_ticket_messages()
            if not TICKET_MESSAGES: # Se ainda estiver vazio, algo está errado
                await ctx.send("Erro: Não foi possível carregar as mensagens customizadas para o sistema de tickets. Verifique o arquivo ticket_messages.json.", ephemeral=True)
                return

        panel_embed_data = TICKET_MESSAGES.get("ticket_panel_embed", {})
        embed = discord.Embed(
            title=panel_embed_data.get("title", "Título Padrão do Painel"),
            description=panel_embed_data.get("description", "Descrição Padrão do Painel"),
            color=discord.Color.from_str(panel_embed_data.get("color", "#FFD700")) # Usando hexadecimal como fallback
        )
        embed.set_footer(text=panel_embed_data.get("footer", "Rodapé Padrão do Painel"))

        view = TicketPanelView(self)

        try:
            if self._ticket_panel_message_id: # Se já existe um ID de mensagem salvo
                message = await channel.fetch_message(self._ticket_panel_message_id) # Tenta buscar a mensagem existente
                await message.edit(embed=embed, view=view) # Atualiza a embed e a view
                await ctx.send("Painel de tickets atualizado com sucesso!", ephemeral=True)
            else: # Se não há ID salvo, envia uma nova mensagem
                message = await channel.send(embed=embed, view=view)
                await self._save_ticket_panel_message_id(message.id) # Salva o ID da nova mensagem
                await ctx.send("Painel de tickets enviado com sucesso!", ephemeral=True)
        except discord.NotFound: # Se o ID estava salvo mas a mensagem foi deletada
            print("Mensagem do painel de tickets não encontrada, recriando...")
            message = await channel.send(embed=embed, view=view)
            await self._save_ticket_panel_message_id(message.id)
            await ctx.send("Painel de tickets recriado com sucesso!", ephemeral=True)
        except Exception as e: # Qualquer outro erro durante o envio/atualização
            await ctx.send(f"Erro ao enviar/atualizar painel de tickets: {e}", ephemeral=True)
            print(f"Erro ao enviar/atualizar painel de tickets: {e}")

    async def create_ticket_transcript(self, channel: discord.TextChannel):
        transcript_channel = self.bot.get_channel(TICKET_TRANSCRIPTS_CHANNEL_ID)
        if not transcript_channel:
            print(f"Erro: Canal de transcritos com ID {TICKET_TRANSCRIPTS_CHANNEL_ID} não encontrado.")
            return

        ticket_data = next((t for t in get_all_open_tickets() if t['channel_id'] == channel.id), None)
        creator_name = ticket_data['creator_name'] if ticket_data else "Desconhecido"
        category_name = ticket_data['category'] if ticket_data else "N/A"
        
        transcript_content = (
            f"--- Transcrito do Ticket: {channel.name} ({category_name}) ---\n"
            f"Criado por: {creator_name} ({ticket_data['creator_id'] if ticket_data else 'Desconhecido ID'}) em {ticket_data['created_at'] if ticket_data else 'N/A'}\n"
            f"Fechado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        )
        
        messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
        
        for msg in messages:
            # Melhorar a condição para ignorar mensagens de bot na transcrição
            # Usar partes do título da embed de boas-vindas do JSON para ser mais robusto
            welcome_embed_title_prefix = TICKET_MESSAGES.get("ticket_welcome_embed", {}).get("title", "").split('{')[0].strip()

            is_bot_generated_welcome = msg.author == self.bot.user and msg.embeds and (msg.embeds[0].title or "").startswith(welcome_embed_title_prefix)
            is_bot_generated_close_message = msg.author == self.bot.user and msg.content == TICKET_MESSAGES.get("close_message", "Fechando ticket em 5 segundos...")
            
            # Ignora mensagens geradas pelo bot que são puramente de controle/painel
            if is_bot_generated_welcome or is_bot_generated_close_message:
                continue
            
            transcript_content += f"[{msg.created_at.strftime('%d/%m/%Y %H:%M:%S')}] {msg.author.display_name}: {msg.content}\n"
            for attachment in msg.attachments:
                transcript_content += f"     [Anexo: {attachment.url}]\n"
            if msg.embeds:
                for embed in msg.embeds:
                    if embed.title or embed.description:
                        # Limitar a descrição da embed para evitar transcritos muito longos
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
                description=transcript_embed_data.get("description", "").format(
                    criador=creator_name,
                    categoria=category_name
                ),
                color=discord.Color.from_str(transcript_embed_data.get("color", "#D3D3D3"))
            )
            embed.set_footer(text=transcript_embed_data.get("footer", "").format(data_hora=datetime.now().strftime('%d/%m/%Y %H:%M:%S')))
            
            await transcript_channel.send(embed=embed, file=file_to_send)
            print(f"Transcrito para {channel.name} enviado para o canal de logs.")
        except Exception as e:
            print(f"Erro ao enviar transcrito para o Discord: {e}")
        finally:
            # Garante que o ficheiro é removido após o envio
            if os.path.exists(file_path):
                os.remove(file_path)

    @commands.command(name="cleartickets", help="Deleta todos os canais de ticket abertos e remove-os do DB.")
    @commands.has_permissions(administrator=True) # Apenas administradores podem usar
    async def clear_all_tickets(self, ctx: commands.Context):
        """
        Deleta todos os canais de ticket atualmente abertos e os remove do banco de dados.
        Útil para limpar tickets de teste.
        """
        await ctx.defer(ephemeral=True) 

        open_tickets = get_all_open_tickets()
        if not open_tickets:
            await ctx.send("Não há tickets abertos para limpar.", ephemeral=True) 
            return

        deleted_count = 0
        failed_deletions = []

        await ctx.send(f"A iniciar limpeza de {len(open_tickets)} tickets...", ephemeral=True) 

        for ticket in open_tickets:
            channel_id = ticket['channel_id']
            # O nome do canal pode ser dinâmico; para logs, usamos o ID ou um nome genérico
            channel_name_for_log = f"ticket-{ticket.get('creator_name', 'unknown').lower().replace(' ', '-')}" 
            
            try:
                channel = self.bot.get_channel(channel_id)
                if channel: # Se o canal ainda existe no Discord
                    await channel.delete(reason="Comando !cleartickets executado por administrador.")
                    remove_ticket_from_db(channel_id) # Remove do DB após deletar
                    deleted_count += 1
                    print(f"Ticket {channel_name_for_log} (ID: {channel_id}) deletado e removido do DB.")
                else: # Se o canal já não existe no Discord, remove apenas do DB
                    remove_ticket_from_db(channel_id)
                    print(f"Ticket {channel_name_for_log} (ID: {channel_id}) não encontrado no Discord, removido apenas do DB.")
                    deleted_count += 1
            except discord.NotFound: # Caso raro de race condition, se já foi deletado
                remove_ticket_from_db(channel_id)
                print(f"Ticket {channel_name_for_log} (ID: {channel_id}) já não existia no Discord, removido do DB.")
                deleted_count += 1
            except Exception as e:
                failed_deletions.append(f"Ticket {channel_name_for_log} (ID: {channel_id}): {e}")
                print(f"Erro ao deletar ticket {channel_name_for_log} (ID: {channel_id}): {e}")
        
        if failed_deletions:
            error_message = "\n".join(failed_deletions)
            await ctx.send(
                f"Limpeza concluída. {deleted_count} tickets limpos (incluindo do DB).\n"
                f"Os seguintes tickets falharam ao ser deletados do Discord (mas foram removidos do DB se existiam):\n```\n{error_message}\n```",
                ephemeral=True
            )
        else:
            await ctx.send(f"Limpeza concluída! {deleted_count} tickets foram completamente limpos.", ephemeral=True)
        print(f"Comando !cleartickets finalizado. {deleted_count} tickets limpos.")

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))
