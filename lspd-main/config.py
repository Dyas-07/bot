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
# Estes ficheiros são locais ao contêiner e não persistem entre deploys sem volumes.
# Com PostgreSQL, a persistência de dados será no DB, mas os IDs das mensagens ainda precisam ser salvos para as Views.
PUNCH_MESSAGE_FILE = 'punch_message_id.txt' # Salva o ID da mensagem do painel de ponto
TICKET_PANEL_MESSAGE_FILE = 'ticket_panel_message_id.txt' # Salva o ID da mensagem do painel de tickets
TICKET_MESSAGES_FILE = 'ticket_messages.json' # Arquivo JSON para mensagens e embeds customizadas do sistema de tickets

# Nome do arquivo do banco de dados SQLite (Não será usado com PostgreSQL, mas mantido para referência)
# DATABASE_NAME = 'punch_card.db'

# ID do Cargo Autorizado (para comandos administrativos gerais, como !mascote, !forcereport)
# Defina o ID de um cargo de administrador ou moderador no seu servidor.
ROLE_ID = int(os.getenv('ROLE_ID')) if os.getenv('ROLE_ID') else None
# ID do cargo que pode fechar tickets (e.g., um cargo de Moderador ou Admin no sistema de tickets)
TICKET_MODERATOR_ROLE_ID = int(os.getenv('TICKET_MODERATOR_ROLE_ID')) if os.getenv('TICKET_MODERATOR_ROLE_ID') else None


# --- Configurações do Sistema de Tickets ---

# Categorias de tickets para o dropdown do painel de tickets:
# Cada tupla deve ser: (label no dropdown, descrição curta para o dropdown, emoji, ID da categoria no Discord)
# Os IDs das categorias do Discord (e.g., TICKET_CATEGORY_PLAYER_REPORT_ID) devem ser obtidos do seu servidor e
# adicionados como variáveis de ambiente em seu .env ou no Railway, senão a categoria não funcionará.
TICKET_CATEGORIES = [
    ("Reportar Jogador", "Use para relatar violações de regras de jogadores.", "🚨", int(os.getenv('TICKET_CATEGORY_PLAYER_REPORT_ID')) if os.getenv('TICKET_CATEGORY_PLAYER_REPORT_ID') else None),
    ("Suporte Geral", "Para dúvidas e assistência geral.", "❓", int(os.getenv('TICKET_CATEGORY_GENERAL_SUPPORT_ID')) if os.getenv('TICKET_CATEGORY_GENERAL_SUPPORT_ID') else None),
    ("Recursos Humanos", "Assuntos de RH, candidaturas, etc.", "👔", int(os.getenv('TICKET_CATEGORY_HR_ID')) if os.getenv('TICKET_CATEGORY_HR_ID') else None),
    # Adicione mais categorias conforme necessário, e suas respectivas IDs nas variáveis de ambiente.
]


# --- Configurações de Status e Atividade do Bot ---
# O status inicial do bot ao iniciar (online, idle, dnd, invisible)
DEFAULT_STATUS_TYPE = discord.Status.online

# Lista de atividades que o bot irá alternar automaticamente (opcional)
# Cada tupla deve conter: (Tipo de Atividade, Mensagem, URL se for STREAMING)
# Tipos de Atividade disponíveis:
# discord.ActivityType.playing (jogando)
# discord.ActivityType.watching (assistindo)
# discord.ActivityType.listening (ouvindo)
# discord.ActivityType.streaming (transmitindo - requer URL)
BOT_ACTIVITIES = [
    (discord.ActivityType.playing, "LSPD - KUMA RP", None), # Exemplo: Jogando "LSPD - KUMA RP"
    (discord.ActivityType.streaming, "Moon Clara", "https://www.twitch.tv/xirilikika"), # Exemplo: Transmitindo na Twitch
    (discord.ActivityType.streaming, "Sofia Bicho", "https://www.twitch.tv/sofialameiras"),
    (discord.ActivityType.streaming, "Zuka ZK", "https://www.twitch.tv/hyag0o0"),
    (discord.ActivityType.streaming, "Mika Gomez", "https://www.twitch.tv/laraxcross")
]

# Intervalo em segundos para alternar entre as atividades (se BOT_ACTIVITIES não estiver vazio)
ACTIVITY_CHANGE_INTERVAL_SECONDS = 30 # 30 segundos
