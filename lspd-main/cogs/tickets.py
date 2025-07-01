import discord
from discord.ext import commands
from discord import app_commands # Importa app_commands para slash commands
from typing import Union # Mantém Union para type hinting de Member/Role
import json
import os
from datetime import datetime, timezone
import asyncio

from config import (
    TICKET_PANEL_CHANNEL_ID, TICKET_PANEL_MESSAGE_FILE, TICKET_MESSAGES_FILE,
    TICKET_CATEGORIES, TICKET_MODERATOR_ROLE_ID, TICKET_TRANSCRIPTS_CHANNEL_ID,
    ROLE_ID # Importa ROLE_ID para permissões de administração geral
)
from database import add_ticket_to_db, remove_ticket_from_db, get_all_open_tickets

# Carrega as mensagens do arquivo JSON
def load_ticket_messages():
    try:
        with open(TICKET_MESSAGES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Erro: Arquivo de mensagens de ticket '{TICKET_MESSAGES_FILE}' não encontrado.")
        print("Será usada uma estrutura de mensagens padrão. Por favor, crie este arquivo ou verifique o caminho.")
        # Estrutura padrão para evitar erros, mas que deve ser substituída pelo arquivo real
        return {
            "ticket_panel_embed": {
                "title": "Sistema de Tickets - LSPD | KUMA RP",
                "description": "Bem-vindo ao sistema de tickets da LSPD!\nSeleciona abaixo a categoria que mais se adequa ao teu pedido. Cada opção serve para um tipo específico de situação, seja ela administrativa, recursos humanos ou recrutamento.",
                "color": "#36393F",
                "thumbnail_url": "https://cdn.discordapp.com/attachments/1260308350776774817/1386713008256061512/Untitled_1024_x_1024_px_4.png",
                "fields": [
                    {"name": "📌 Usa este sistema apenas quando necessário.", "value": "Traz sempre o máximo de informação e provas (se aplicável) para facilitar o atendimento.", "inline": False},
                    {"name": "⏰ Os tickets são respondidos por ordem de chegada.\n👇 Escolhe uma categoria no menu dropdown abaixo:", "value": " ", "inline": False}
                ],
                "footer": "Kuma RP - Sistema de Tickets • {data_hora}",
                "dropdown_placeholder": "Make a selection"
            },
            "categories": {
                "Administração": {
                    "dropdown_description": "Entrar em contacto diretamente com a Administração.",
                    "welcome_embed": {
                        "title": "Bem Vindo ao Suporte do KumaRP",
                        "description": "O teu ticket foi aberto com sucesso! A equipa de suporte irá analisá-lo e responder assim que possível.\n\n",
                        "color": "#36393F",
                        "thumbnail_url": "https://cdn.discordapp.com/attachments/1260308350776774817/1386713008256061512/Untitled_1024_x_1024_px_4.png",
                        "fields": [
                            {"name": "Kuma RP | Organizações", "value": " ", "inline": False},
                            {"name": "Enquanto aguardas:", "value": "🔸 Certifica-te de que forneceste todas as informações necessárias.\n🔸 Evita enviar mensagens desnecessárias para não atrasar a resposta.\n🔸 Mantém o respeito e aguarda pacientemente.", "inline": False},
                            {"name": "🔒 O ticket será fechado pela Staff após a conclusão do mesmo.", "value": " ", "inline": False},
                            {"name": "Instruções Específicas para Administração:", "value": "Por favor, **descreva a sua questão ou o motivo do seu contato com a equipe de Administração** com o máximo de detalhes possível. Nossa equipe irá analisar o seu pedido em breve.", "inline": False}
                        ],
                        "footer": "Kuma RP - Sistema de Tickets • {data_hora}"
                    }
                },
                "Suporte Geral": {
                    "dropdown_description": "Para dúvidas e assistência geral.",
                    "welcome_embed": {
                        "title": "Bem Vindo ao Suporte do KumaRP",
                        "description": "O teu ticket foi aberto com sucesso! A equipa de suporte irá analisá-lo e responder assim que possível.\n\n",
                        "color": "#36393F",
                        "thumbnail_url": "https://cdn.discordapp.com/attachments/1260308350776774817/1386713008256061512/Untitled_1024_x_1024_px_4.png",
                        "fields": [
                            {"name": "Kuma RP | Organizações", "value": " ", "inline": False},
                            {"name": "Enquanto aguardas:", "value": "🔸 Certifica-te de que forneceste todas as informações necessárias.\n🔸 Evita enviar mensagens desnecessárias para não atrasar a resposta.\n🔸 Mantém o respeito e aguarda pacientemente.", "inline": False},
                            {"name": "🔒 O ticket será fechado pela Staff após a conclusão do mesmo.", "value": " ", "inline": False},
                            {"name": "Instruções Específicas para Suporte Geral:", "value": "Por favor, **descreva a sua dúvida ou problema detalhadamente**. Nossa equipe está aqui para ajudar e responderá em breve.", "inline": False}
                        ],
                        "footer": "Kuma RP - Sistema de Tickets • {data_hora}"
                    }
                },
                "Recursos Humanos": {
                    "dropdown_description": "Assuntos de Recursos Humanos.",
                    "welcome_embed": {
                        "title": "Bem Vindo ao Suporte do KumaRP",
                        "description": "O teu ticket foi aberto com sucesso! A equipa de suporte irá analisá-lo e responder assim que possível.\n\n",
                        "color": "#36393F",
                        "thumbnail_url": "https://cdn.discordapp.com/attachments/1260308350776774817/1386713008256061512/Untitled_1024_x_1024_px_4.png",
                        "fields": [
                            {"name": "Kuma RP | Organizações", "value": " ", "inline": False},
                            {"name": "Enquanto aguardas:", "value": "🔸 Certifica-te de que forneceste todas as informações necessárias.\n🔸 Evita enviar mensagens desnecessárias para não atrasar a resposta.\n🔸 Mantém o respeito e aguarda pacientemente.", "inline": False},
                            {"name": "🔒 O ticket será fechado pela Staff após a conclusão do mesmo.", "value": " ", "inline": False},
                            {"name": "Instruções Específicas para Recursos Humanos:", "value": "Por favor, **explique a sua questão ou o motivo do seu contato com a equipe de RH**. Seja o mais claro possível para que possamos encaminhá-lo para a pessoa certa.", "inline": False}
                        ],
                        "footer": "Kuma RP - Sistema de Tickets • {data_hora}"
                    }
                },
                "Eventos": {
                    "dropdown_description": "Contactar a equipa de eventos.",
                    "welcome_embed": {
                        "title": "Bem Vindo ao Suporte do KumaRP",
                        "description": "O teu ticket foi aberto com sucesso! A equipa de suporte irá analisá-lo e responder assim que possível.\n\n",
                        "color": "#36393F",
                        "thumbnail_url": "https://cdn.discordapp.com/attachments/1260308350776774817/1386713008256061512/Untitled_1024_x_1024_px_4.png",
                        "fields": [
                            {"name": "Kuma RP | Organizações", "value": " ", "inline": False},
                            {"name": "Enquanto aguardas:", "value": "🔸 Certifica-te de que forneceste todas as informações necessárias.\n🔸 Evita enviar mensagens desnecessárias para não atrasar a resposta.\n🔸 Mantém o respeito e aguarda pacientemente.", "inline": False},
                            {"name": "🔒 O ticket será fechado pela Staff após a conclusão do mesmo.", "value": " ", "inline": False},
                            {"name": "Instruções Específicas para Eventos:", "value": "Por favor, **descreva a sua ideia ou questão relacionada a eventos**. Nossa equipe de eventos irá analisar e responder em breve.", "inline": False}
                        ],
                        "footer": "Kuma RP - Sistema de Tickets • {data_hora}"
                    }
                }
            },
            "ticket_welcome_embed": {
                "title": "🎉 Bem-vindo ao seu Ticket da LSPD!",
                "description": "Aguarde enquanto um membro da nossa equipe se junta a você para ajudar com o seu ticket na categoria **{categoria}**. Por favor, descreva o seu problema ou questão em detalhes para agilizar o suporte.",
                "color": "#7289DA",
                "footer": "Ticket ID: {id_ticket} | Criado por: {usuario} em {data_hora}",
                "thumbnail_url": "https://cdn.discordapp.com/attachments/1260308350776774817/1386713008256061512/Untitled_1024_x_1024_px_4.png"
            },
            "ticket_created_success": "Seu ticket foi criado em {canal_mencao}! Por favor, dirija-se a ele para continuar.",
            "ticket_already_open": "Você já tem um ticket aberto. Por favor, finalize-o ou use-o antes de abrir um novo: {canal_mencao}",
            "error_creating_ticket": "Ocorreu um erro ao criar seu ticket. Por favor, tente novamente mais tarde ou contate um administrador. Erro: `{erro}`",
            "no_permission_close_ticket": "Você não tem permissão para fechar este ticket.",
            "no_permission_transcript_ticket": "Você não tem permissão para transcrever este ticket.",
            "close_message": "Ticket fechado em 5 segundos. Criando transcrito...",
            "transcript_creating": "Criando transcrito do ticket...",
            "transcript_success": "Transcrito criado e enviado para o canal de logs!",
            "transcript_embed": {
                "title": "📄 Transcrito do Ticket: #{canal}",
                "description": "Ticket criado por: **{criador}**\nCategoria: **{categoria}**\n\nEste é o histórico completo da conversa.",
                "color": "#99AAB5",
                "footer": "Transcrito gerado em: {data_hora}",
                "thumbnail_url": "https://cdn.discordapp.com/attachments/1260308350776774817/1386713008256061512/Untitled_1024_x_1024_px_4.png"
            }
        }

TICKET_MESSAGES = load_ticket_messages()

# --- Views para o Sistema de Tickets ---

class TicketCategorySelect(discord.ui.Select):
    def __init__(self, cog_instance):
        super().__init__(
            placeholder=TICKET_MESSAGES['ticket_panel_embed'].get('dropdown_placeholder', 'Selecione uma categoria...'), # Usa o novo placeholder
            min_values=1,
            max_values=1,
            custom_id="ticket_category_select"
        )
        self.cog = cog_instance

        # Adiciona as opções dinamicamente
        for label, description, emoji_str, category_id in TICKET_CATEGORIES:
            # Verifica se o category_id é válido antes de adicionar a opção
            if category_id is None:
                print(f"AVISO: Categoria de ticket '{label}' tem ID de categoria ausente (None). Esta opção não será adicionada ao seletor.")
                continue # Pula esta opção se o ID for None

            self.add_option(
                label=label,
                description=description,
                emoji=emoji_str,
                value=str(category_id) # O valor deve ser uma string
            )

    async def callback(self, interaction: discord.Interaction):
        selected_category_id = int(self.values[0])
        selected_category_name = None
        selected_category_data = None

        for label, _, _, category_id in TICKET_CATEGORIES:
            if category_id == selected_category_id:
                selected_category_name = label
                selected_category_data = TICKET_MESSAGES['categories'].get(label)
                break

        if not selected_category_name or not selected_category_data:
            await interaction.response.send_message("Erro: Categoria de ticket inválida selecionada.", ephemeral=True)
            return

        user = interaction.user
        guild = interaction.guild

        # Verifica se o usuário já tem um ticket aberto
        open_tickets = get_all_open_tickets()
        for ticket in open_tickets:
            if ticket['creator_id'] == user.id:
                existing_channel = guild.get_channel(ticket['channel_id'])
                if existing_channel:
                    await interaction.response.send_message(
                        TICKET_MESSAGES['ticket_already_open'].format(canal_mencao=existing_channel.mention),
                        ephemeral=True
                    )
                    return

        # Cria o canal do ticket
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, manage_channels=True)
        }
        
        # Adiciona permissão para o cargo de moderador de tickets, se configurado
        if TICKET_MODERATOR_ROLE_ID:
            moderator_role = guild.get_role(TICKET_MODERATOR_ROLE_ID)
            if moderator_role:
                overwrites[moderator_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        try:
            category_channel = guild.get_channel(selected_category_id)
            if not isinstance(category_channel, discord.CategoryChannel):
                await interaction.response.send_message(f"Erro: A ID da categoria '{selected_category_name}' configurada ({selected_category_id}) não corresponde a uma categoria de canal válida no Discord.", ephemeral=True)
                return

            ticket_channel = await category_channel.create_text_channel(
                name=f"ticket-{user.name.lower().replace(' ', '-')}",
                overwrites=overwrites
            )
            
            # Adiciona o ticket ao banco de dados
            ticket_added = add_ticket_to_db(ticket_channel.id, user.id, user.display_name, selected_category_name)
            if not ticket_added:
                await ticket_channel.delete(reason="Falha ao adicionar ticket ao DB.")
                await interaction.response.send_message(
                    TICKET_MESSAGES['error_creating_ticket'].format(erro="Falha interna no banco de dados."),
                    ephemeral=True
                )
                return

            # Envia a mensagem de boas-vindas no canal do ticket
            welcome_embed_data = selected_category_data['welcome_embed']
            welcome_embed = discord.Embed(
                title=welcome_embed_data['title'],
                description=welcome_embed_data['description'].format(usuario=user.mention),
                color=discord.Color.from_str(welcome_embed_data['color'])
            )
            if 'thumbnail_url' in welcome_embed_data:
                welcome_embed.set_thumbnail(url=welcome_embed_data['thumbnail_url'])

            if 'fields' in welcome_embed_data and isinstance(welcome_embed_data['fields'], list):
                for field in welcome_embed_data['fields']:
                    name = field.get('name', ' ')
                    value = field.get('value', ' ')
                    inline = field.get('inline', False)
                    welcome_embed.add_field(name=name, value=value.format(usuario=user.mention) if '{usuario}' in value else value, inline=inline)
            
            if 'footer' in welcome_embed_data:
                current_time_str = datetime.now().strftime('%d/%m/%Y às %H:%M') # Formato "Today at 1:05"
                welcome_embed.set_footer(text=welcome_embed_data['footer'].format(data_hora=current_time_str))


            ticket_view = TicketButtonsView(self.cog, ticket_channel.id)
            await ticket_channel.send(user.mention, embed=welcome_embed, view=ticket_view) # Envia a menção e o embed

            await interaction.response.send_message(
                TICKET_MESSAGES['ticket_created_success'].format(canal_mencao=ticket_channel.mention),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                TICKET_MESSAGES['error_creating_ticket'].format(erro="Permissões insuficientes para criar canais."),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                TICKET_MESSAGES['error_creating_ticket'].format(erro=str(e)),
                ephemeral=True
            )
            print(f"Erro ao criar ticket: {e}")


class TicketButtonsView(discord.ui.View):
    def __init__(self, cog_instance, ticket_channel_id):
        super().__init__(timeout=None)
        self.cog = cog_instance
        self.ticket_channel_id = ticket_channel_id

    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_button")
    async def close_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("Este comando só pode ser usado num servidor.", ephemeral=True)
            return

        member = interaction.user
        # Verifica se o utilizador tem o cargo de moderador de tickets ou permissão de administrador
        is_moderator = False
        if TICKET_MODERATOR_ROLE_ID:
            moderator_role = interaction.guild.get_role(TICKET_MODERATOR_ROLE_ID)
            if moderator_role and moderator_role in member.roles:
                is_moderator = True
        
        if not is_moderator and not member.guild_permissions.administrator:
            await interaction.response.send_message(TICKET_MESSAGES['no_permission_close_ticket'], ephemeral=True)
            return

        await interaction.response.send_message(TICKET_MESSAGES['close_message'], ephemeral=True)
        await asyncio.sleep(5) # Dá tempo para o usuário ler a mensagem

        channel = interaction.channel
        if channel.id == self.ticket_channel_id: # Garante que estamos no canal certo
            await self.cog.create_transcript_and_delete_channel(channel)
        else:
            await interaction.followup.send("Erro: Este botão não pode ser usado neste canal ou o ticket ID não corresponde.", ephemeral=True)

    @discord.ui.button(label="Transcrever Ticket", style=discord.ButtonStyle.secondary, emoji="📄", custom_id="transcript_ticket_button")
    async def transcript_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("Este comando só pode ser usado num servidor.", ephemeral=True)
            return

        member = interaction.user
        # Verifica se o utilizador tem o cargo de moderador de tickets ou permissão de administrador
        is_moderator = False
        if TICKET_MODERATOR_ROLE_ID:
            moderator_role = interaction.guild.get_role(TICKET_MODERATOR_ROLE_ID)
            if moderator_role and moderator_role in member.roles:
                is_moderator = True
        
        if not is_moderator and not member.guild_permissions.administrator:
            await interaction.response.send_message(TICKET_MESSAGES['no_permission_transcript_ticket'], ephemeral=True)
            return
        
        await interaction.response.send_message(TICKET_MESSAGES['transcript_creating'], ephemeral=True)
        channel = interaction.channel
        if channel.id == self.ticket_channel_id:
            await self.cog.create_transcript(channel)
            await interaction.followup.send(TICKET_MESSAGES['transcript_success'], ephemeral=True)
        else:
            await interaction.followup.send("Erro: Este botão não pode ser usado neste canal ou o ticket ID não corresponde.", ephemeral=True)


class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._ticket_panel_message_id = None

    async def _load_ticket_panel_message_id(self):
        try:
            with open(TICKET_PANEL_MESSAGE_FILE, 'r', encoding='utf-8') as f:
                self._ticket_panel_message_id = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            self._ticket_panel_message_id = None
        print(f"ID da mensagem do painel de tickets carregado: {self._ticket_panel_message_id}")

    async def _save_ticket_panel_message_id(self, message_id: int):
        self._ticket_panel_message_id = message_id
        with open(TICKET_PANEL_MESSAGE_FILE, 'w', encoding='utf-8') as f:
            f.write(str(message_id))
        print(f"ID da mensagem do painel de tickets salvo: {self._ticket_panel_message_id}")

    @commands.Cog.listener()
    async def on_ready(self):
        print("TicketCog está pronto.")
        await self._load_ticket_panel_message_id()

        if self._ticket_panel_message_id:
            try:
                channel = self.bot.get_channel(TICKET_PANEL_CHANNEL_ID)
                if channel:
                    await channel.fetch_message(self._ticket_panel_message_id)
                    self.bot.add_view(TicketPanelView(self))
                    print(f"View do painel de tickets persistente adicionada para a mensagem ID: {self._ticket_panel_message_id}")
                else:
                    print(f"Aviso: Canal do painel de tickets (ID: {TICKET_PANEL_CHANNEL_ID}) não encontrado para re-associar a View.")
                    self._ticket_panel_message_id = None
            except discord.NotFound:
                print(f"Aviso: Mensagem do painel de tickets (ID: {self._ticket_panel_message_id}) não encontrada, será recriada no próximo setup com !setuptickets.")
                self._ticket_panel_message_id = None
            except Exception as e:
                print(f"Erro ao re-associar a View do painel de tickets: {e}")
                self._ticket_panel_message_id = None
        
        # Re-associa as views dos tickets abertos no DB
        open_tickets_db = get_all_open_tickets()
        for ticket in open_tickets_db:
            try:
                channel = self.bot.get_channel(ticket['channel_id'])
                if channel:
                    # Não precisamos de buscar a mensagem, apenas adicionar a view ao bot
                    # O bot irá automaticamente associar a view a mensagens com o custom_id correto
                    self.bot.add_view(TicketButtonsView(self, ticket['channel_id']))
                    print(f"View de botões de ticket persistente adicionada para o canal ID: {ticket['channel_id']}")
                else:
                    print(f"Aviso: Canal de ticket (ID: {ticket['channel_id']}) do DB não encontrado. Removendo do DB.")
                    remove_ticket_from_db(ticket['channel_id']) # Remove do DB se o canal não existe
            except Exception as e:
                print(f"Erro ao re-associar View de botões de ticket para canal {ticket['channel_id']}: {e}")

    async def create_transcript(self, channel: discord.TextChannel):
        transcript = []
        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            author = message.author.display_name
            content = message.clean_content # Conteúdo da mensagem sem menções
            attachments = [att.url for att in message.attachments]
            
            transcript_entry = f"[{timestamp}] {author}: {content}"
            if attachments:
                transcript_entry += f" (Anexos: {', '.join(attachments)})"
            transcript.append(transcript_entry)

        transcript_text = "\n".join(transcript)
        
        # Salva o transcrito em um arquivo temporário
        transcript_filename = f"transcript-{channel.name}.txt"
        with open(transcript_filename, 'w', encoding='utf-8') as f:
            f.write(transcript_text)

        # Envia o arquivo para o canal de transcritos
        transcript_channel = self.bot.get_channel(TICKET_TRANSCRIPTS_CHANNEL_ID)
        if transcript_channel:
            # Obtém informações do ticket do DB
            open_tickets = get_all_open_tickets()
            ticket_info = next((t for t in open_tickets if t['channel_id'] == channel.id), None)

            if ticket_info:
                creator_name = ticket_info['creator_name']
                category = ticket_info['category']
                created_at = datetime.fromisoformat(ticket_info['created_at']).strftime('%d/%m/%Y %H:%M:%S')
            else:
                creator_name = "Desconhecido"
                category = "Desconhecida"
                created_at = "Desconhecido"

            embed_data = TICKET_MESSAGES['transcript_embed']
            transcript_embed = discord.Embed(
                title=embed_data['title'].format(canal=channel.name),
                description=embed_data['description'].format(criador=creator_name, categoria=category),
                color=discord.Color.from_str(embed_data['color'])
            )
            transcript_embed.set_footer(
                text=embed_data['footer'].format(data_hora=datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S UTC'))
            )
            if 'thumbnail_url' in embed_data:
                transcript_embed.set_thumbnail(url=embed_data['thumbnail_url'])

            with open(transcript_filename, 'rb') as f:
                discord_file = discord.File(f, filename=transcript_filename)
                await transcript_channel.send(embed=transcript_embed, file=discord_file)
            print(f"Transcrito para {channel.name} enviado para o canal de logs.")
        else:
            print(f"Erro: Canal de transcritos com ID {TICKET_TRANSCRIPTS_CHANNEL_ID} não encontrado.")

        # Limpa o arquivo temporário
        os.remove(transcript_filename)

    async def create_transcript_and_delete_channel(self, channel: discord.TextChannel):
        await self.create_transcript(channel)
        remove_ticket_from_db(channel.id) # Remove do DB antes de deletar o canal
        await channel.delete(reason="Ticket fechado e transcrito.")
        print(f"Canal {channel.name} deletado.")

    @commands.command(name="setuptickets", help="Envia o painel de criação de tickets para o canal configurado.")
    @commands.has_permissions(administrator=True)
    async def setup_ticket_panel(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)

        channel = self.bot.get_channel(TICKET_PANEL_CHANNEL_ID)
        if not channel:
            await ctx.send(f"Erro: Canal do painel de tickets com ID {TICKET_PANEL_CHANNEL_ID} não encontrado em suas configurações.", ephemeral=True)
            return

        embed_data = TICKET_MESSAGES['ticket_panel_embed']
        embed = discord.Embed(
            title=embed_data['title'],
            description=embed_data['description'],
            color=discord.Color.from_str(embed_data['color'])
        )
        if 'thumbnail_url' in embed_data:
            embed.set_thumbnail(url=embed_data['thumbnail_url'])

        # Adiciona campos (fields) da configuração JSON para o painel
        if 'fields' in embed_data and isinstance(embed_data['fields'], list):
            for field in embed_data['fields']:
                name = field.get('name', ' ')
                value = field.get('value', ' ')
                inline = field.get('inline', False)
                embed.add_field(name=name, value=value, inline=inline)
        
        # Adiciona o footer do painel com a data atual
        if 'footer' in embed_data:
            current_time_str = datetime.now().strftime('%d/%m/%Y %H:%M') # Formato "6/9/2025 13:54"
            embed.set_footer(text=embed_data['footer'].format(data_hora=current_time_str))

        view = TicketPanelView(self)

        try:
            if self._ticket_panel_message_id:
                message = await channel.fetch_message(self._ticket_panel_message_id)
                await message.edit(embed=embed, view=view)
                await ctx.send("Painel de tickets atualizado com sucesso!", ephemeral=True)
            else:
                message = await channel.send(embed=embed, view=view)
                await self._save_ticket_panel_message_id(message.id)
                await ctx.send("Painel de tickets enviado com sucesso!", ephemeral=True)
        except discord.NotFound:
            print("Mensagem do painel de tickets não encontrada, recriando...")
            message = await channel.send(embed=embed, view=view)
            await self._save_ticket_panel_message_id(message.id)
            await ctx.send("Mensagem de picagem de ponto recriada com sucesso!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Erro ao enviar/atualizar painel de tickets: {e}", ephemeral=True)
            print(f"Erro ao enviar/atualizar painel de tickets: {e}")

    # --- Comandos de Barra para Tickets ---

    @app_commands.command(name="add", description="Adiciona um usuário ou cargo ao ticket atual.")
    @app_commands.describe(membro_ou_cargo="O usuário ou cargo a ser adicionado.")
    @app_commands.checks.has_role(TICKET_MODERATOR_ROLE_ID) # Apenas moderadores de tickets podem usar
    async def add_to_ticket(self, interaction: discord.Interaction, membro_ou_cargo: Union[discord.Member, discord.Role]):
        """
        Adiciona um usuário ou cargo ao canal do ticket atual.
        """
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Este comando só pode ser usado em um canal de texto.", ephemeral=True)
            return

        # Verifica se o canal é um canal de ticket
        open_tickets = get_all_open_tickets()
        is_ticket_channel = any(ticket['channel_id'] == interaction.channel.id for ticket in open_tickets)

        if not is_ticket_channel:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)
            return
        
        try:
            # Concede permissões de visualização e envio de mensagens
            await interaction.channel.set_permissions(membro_ou_cargo, view_channel=True, send_messages=True, attach_files=True)
            await interaction.response.send_message(f"✅ {membro_ou_cargo.mention} foi adicionado(a) a este ticket.", ephemeral=True)
            print(f"{interaction.user.display_name} adicionou {membro_ou_cargo.name} ao ticket {interaction.channel.name}")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Não tenho permissão para gerenciar permissões neste canal. Verifique minhas permissões.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ocorreu um erro ao adicionar {membro_ou_cargo.name}: {e}", ephemeral=True)
            print(f"Erro ao adicionar membro/cargo ao ticket: {e}")

    @app_commands.command(name="rename", description="Muda o nome do canal do ticket atual.")
    @app_commands.describe(novo_nome="O novo nome para o canal do ticket.")
    @app_commands.checks.has_role(TICKET_MODERATOR_ROLE_ID) # Apenas moderadores de tickets podem usar
    async def rename_ticket(self, interaction: discord.Interaction, novo_nome: str):
        """
        Muda o nome do canal do ticket atual.
        """
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Este comando só pode ser usado em um canal de texto.", ephemeral=True)
            return

        # Verifica se o canal é um canal de ticket
        open_tickets = get_all_open_tickets()
        is_ticket_channel = any(ticket['channel_id'] == interaction.channel.id for ticket in open_tickets)

        if not is_ticket_channel:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)
            return

        # Limita o comprimento do nome do canal para evitar erros do Discord
        if len(novo_nome) > 100:
            await interaction.response.send_message("O nome do canal não pode ter mais de 100 caracteres.", ephemeral=True)
            return

        # Formata o nome para ser amigável ao Discord (minúsculas, sem espaços, etc.)
        formatted_name = novo_nome.lower().replace(' ', '-')
        # Remove caracteres especiais que o Discord não permite em nomes de canal
        formatted_name = ''.join(c for c in formatted_name if c.isalnum() or c == '-')

        try:
            old_name = interaction.channel.name
            await interaction.channel.edit(name=formatted_name)
            await interaction.response.send_message(f"✅ Nome do ticket alterado de `{old_name}` para `{formatted_name}`.", ephemeral=True)
            print(f"{interaction.user.display_name} renomeou o ticket de {old_name} para {formatted_name}")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Não tenho permissão para gerenciar canais. Verifique minhas permissões.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ocorreu um erro ao renomear o ticket: {e}", ephemeral=True)
            print(f"Erro ao renomear ticket: {e}")


class TicketPanelView(discord.ui.View):
    def __init__(self, cog_instance):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect(cog_instance))

async def setup(bot):
    await bot.add_cog(TicketCog(bot))
