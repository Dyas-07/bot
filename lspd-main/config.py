import os
import discord

# --- Configurações de Conexão e Banco de Dados ---
TOKEN = os.getenv('DISCORD_BOT_TOKEN') # O token do bot, lido de uma variável de ambiente

# IDs dos Canais (Lidos de variáveis de ambiente)
# Certifique-se de que estas variáveis de ambiente estão definidas em seu .env (local) ou no Railway.
PUNCH_CHANNEL_ID = int(os.getenv('PUNCH_CHANNEL_ID')) if os.getenv('PUNCH_CHANNEL_ID') else None # Canal onde os botões de ponto são enviados
WEEKLY_REPORT_CHANNEL_ID = int(os.getenv('WEEKLY_REPORT_CHANNEL_ID')) if os.getenv('WEEKLY_REPORT_CHANNEL_ID') else None # Canal para relatórios semanais automáticos
PUNCH_LOGS_CHANNEL_ID = int(os.getenv('PUNCH_LOGS_CHANNEL_ID')) if os.getenv('PUNCH_LOGS_CHANNEL_ID') else None # Canal para logs de entrada/saída de ponto
TICKET_PANEL_CHANNEL_ID = int(os.getenv('TICKET_PANEL_CHANNEL_ID')) if os.getenv('TICKET_PANEL_CHANNEL_ID') else None # Canal onde o painel de tickets é enviado
TICKET_TRANSCRIPTS_CHANNEL_ID = int(os.getenv('TICKET_TRANSCRIPTS_CHANNEL_ID')) if os.getenv('TICKET_TRANSCRIPTS_CHANNEL_ID') else None # Canal para enviar transcritos de tickets

# Nome dos arquivos onde os IDs das mensagens serão salvos (para persistência das Views).
PUNCH_MESSAGE_FILE = 'punch_message_id.txt'
TICKET_PANEL_MESSAGE_FILE = 'ticket_panel_message_id.txt'
TICKET_MESSAGES_FILE = 'ticket_messages.json'

# ID do Cargo Autorizado (para comandos administrativos gerais, como !mascote, !forcereport, !clear, !clearpunchdb)
ROLE_ID = int(os.getenv('ROLE_ID')) if os.getenv('ROLE_ID') else None
# ID do cargo que pode fechar tickets (e.g., um cargo de Moderador ou Admin no sistema de tickets)
TICKET_MODERATOR_ROLE_ID = int(os.getenv('TICKET_MODERATOR_ROLE_ID')) if os.getenv('TICKET_MODERATOR_ROLE_ID') else None


# --- Configurações do Sistema de Tickets ---

# Categorias de tickets para o dropdown do painel de tickets:
# Cada tupla deve ser: (label no dropdown, descrição curta para o dropdown, emoji, ID da categoria no Discord)
# Os IDs das categorias do Discord (e.g., TICKET_CATEGORY_PLAYER_REPORT_ID) devem ser obtidos do seu servidor e
# adicionados como variáveis de ambiente em seu .env ou no Railway.
TICKET_CATEGORIES = [
    ("Administração", "Entrar em contacto diretamente com a Administração.", "💼", int(os.getenv('TICKET_CATEGORY_ADMINISTRATION')) if os.getenv('TICKET_CATEGORY_ADMINISTRATION') else None),
    ("Suporte Geral", "Para dúvidas e assistência geral.", "❓", int(os.getenv('TICKET_CATEGORY_GENERAL_SUPPORT_ID')) if os.getenv('TICKET_CATEGORY_GENERAL_SUPPORT_ID') else None),
    ("Recursos Humanos", "Assuntos de Recursos Humanos.", "👔", int(os.getenv('TICKET_CATEGORY_HR_ID')) if os.getenv('TICKET_CATEGORY_HR_ID') else None),
    ("Eventos", "Contactar a equipa de eventos.", "🎆", int(os.getenv('TICKET_CATEGORY_EVENTS')) if os.getenv('TICKET_CATEGORY_EVENTS') else None),
]


# --- Configurações de Status e Atividade do Bot ---
DEFAULT_STATUS_TYPE = discord.Status.online

BOT_ACTIVITIES = [
    (discord.ActivityType.playing, "LSPD - KUMA RP", None),
    (discord.ActivityType.streaming, "Moon Clara", "https://www.twitch.tv/xirilikika"),
    (discord.ActivityType.streaming, "Sofia Bicho", "https://www.twitch.tv/sofialameiras"),
    (discord.ActivityType.streaming, "Zuka ZK", "https://www.twitch.tv/hyag0o0"),
    (discord.ActivityType.streaming, "Mika Gomez", "https://www.twitch.tv/laraxcross")
]

ACTIVITY_CHANGE_INTERVAL_SECONDS = 30 # 30 segundos

# --- Configurações de Fuso Horário ---
# Fuso horário para exibição das horas no Discord.
# Use nomes de fusos horários do banco de dados IANA (ex: 'Europe/Lisbon', 'America/Sao_Paulo', 'America/New_York')
# Veja a lista completa aqui: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
DISPLAY_TIMEZONE = 'Europe/Lisbon' # Altere para o seu fuso horário desejado
