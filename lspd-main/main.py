import discord
from discord.ext import commands
import os
import asyncio

# Importa configurações
from config import TOKEN, ROLE_ID

# Setup da base de dados
from database import setup_database

# Intents - Certifique-se de que estas estão ativadas no Discord Developer Portal!
# MESSAGE_CONTENT é crucial para comandos de prefixo.
# MEMBERS e PRESENCES são necessários para cogs como status_changer e funcionalidades que interagem com membros.
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True
intents.presences = True 

# Bot com prefixo "!"
bot = commands.Bot(command_prefix='!', intents=intents)

# --- COMANDO COM PREFIXO (!mascote) ---
@bot.command(name="mascote", help="Exibe a mascote atual da LSPD.")
async def hello(ctx):
    if not isinstance(ctx.author, discord.Member):
        # Em ephemeral=True, as mensagens só são visíveis para quem as enviou
        await ctx.send("Este comando só pode ser usado num servidor.", ephemeral=True)
        return

    # Tenta obter o cargo pelo ID configurado em config.py
    # Se ROLE_ID for None ou o cargo não for encontrado, a permissão será negada.
    role = discord.utils.get(ctx.author.roles, id=ROLE_ID)

    if role is None:
        await ctx.send("🚫 Não tens permissões para isso.", ephemeral=True)
    else:
        await ctx.send("A atual mascote da LSPD é o SKIBIDI ZEKA!")

# --- Evento on_ready ---
@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user.name} ({bot.user.id})')

    # Configura base de dados (cria tabelas se não existirem)
    # IMPORTANTE: A função setup_database agora cria tabelas para PostgreSQL
    setup_database()
    print('📦 Base de dados configurada.')

    # Carrega cogs
    cogs_folder = './cogs'
    if not os.path.exists(cogs_folder):
        print(f"⚠️ Pasta '{cogs_folder}' não encontrada. Certifique-se de que seus cogs estão na subpasta 'cogs'.")
        return

    for filename in os.listdir(cogs_folder):
        # Garante que apenas ficheiros .py válidos sejam carregados (ignora __init__.py e __pycache__)
        if filename.endswith('.py') and not filename.startswith('__'):
            try:
                # Carrega a extensão (cog)
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'✅ Cog {filename[:-3]} carregado.')
            except Exception as e:
                print(f'❌ Erro ao carregar cog {filename[:-3]}: {e}')

    print('🚀 Todos os cogs foram carregados.')
    print('------') 

    # IMPORTANTE: Se você planeja usar Slash Commands (comandos de aplicação),
    # descomente a linha abaixo para sincronizá-los com o Discord.
    # Isto geralmente é feito APENAS uma vez após grandes mudanças nos slash commands.
    # await bot.tree.sync()

# --- Executa o bot ---
if __name__ == '__main__':
    # Certifique-se de que seu DISCORD_BOT_TOKEN está configurado nas variáveis de ambiente no Railway
    if TOKEN is None:
        print("ERRO: DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
        print("Por favor, defina a variável de ambiente DISCORD_BOT_TOKEN com o token do seu bot.")
    else:
        bot.run(TOKEN)
