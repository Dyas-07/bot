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

# --- NOVO COMANDO: !clear ---
@bot.command(name="clear", help="Limpa um número especificado de mensagens no canal. Uso: !clear <quantidade>")
# @commands.has_permissions(manage_messages=True) # Removido para usar permissão por cargo
async def clear_messages(ctx, amount: int):
    """
    Limpa um número especificado de mensagens no canal onde o comando foi invocado.
    Apenas utilizadores com o cargo especificado em ROLE_ID podem usar.
    """
    # Verifica se o comando foi usado num servidor
    if not isinstance(ctx.author, discord.Member):
        await ctx.send("Este comando só pode ser usado num servidor.", ephemeral=True)
        return

    # Tenta obter o cargo pelo ID configurado em config.py
    required_role = discord.utils.get(ctx.author.roles, id=ROLE_ID)

    # Verifica se o utilizador tem o cargo necessário
    if required_role is None:
        await ctx.send("🚫 Não tens permissões para usar este comando. Requer o cargo autorizado.", ephemeral=True)
        return

    if amount <= 0:
        await ctx.send("Por favor, especifique um número positivo de mensagens para limpar.", ephemeral=True)
        return
    
    # Defer a resposta para que o bot "pense" enquanto processa.
    # ephemeral=True para que a mensagem de deferência seja privada.
    await ctx.defer(ephemeral=True) 

    try:
        # +1 para incluir a própria mensagem do comando !clear
        deleted = await ctx.channel.purge(limit=amount + 1)
        # Envia uma confirmação privada para o utilizador que usou o comando
        await ctx.followup.send(f"✅ Foram limpas {len(deleted) - 1} mensagens.", ephemeral=True)
        print(f"Comando !clear executado por {ctx.author.display_name}. Limpou {len(deleted) - 1} mensagens no canal {ctx.channel.name}.")
    except discord.Forbidden:
        await ctx.followup.send("❌ Não tenho permissão para gerenciar mensagens neste canal. Por favor, verifique as minhas permissões.", ephemeral=True)
        print(f"Erro de permissão ao tentar limpar mensagens no canal {ctx.channel.name}.")
    except discord.HTTPException as e:
        await ctx.followup.send(f"❌ Ocorreu um erro ao tentar limpar mensagens: {e}", ephemeral=True)
        print(f"Erro HTTP ao tentar limpar mensagens no canal {ctx.channel.name}: {e}")
    except Exception as e:
        await ctx.followup.send(f"❌ Ocorreu um erro inesperado: {e}", ephemeral=True)
        print(f"Erro inesperado ao limpar mensagens: {e}")

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
