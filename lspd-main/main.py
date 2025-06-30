import discord
from discord.ext import commands
import os
import asyncio

# Importa configurações
from config import TOKEN, ROLE_ID

# Setup da base de dados e a nova função para limpar a tabela de picagem
from database import setup_database, clear_punches_table

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
        await ctx.send("Este comando só pode ser usado num servidor.", ephemeral=True)
        return

    role = discord.utils.get(ctx.author.roles, id=ROLE_ID)

    if role is None:
        await ctx.send("🚫 Não tens permissões para isso.", ephemeral=True)
    else:
        await ctx.send("A atual mascote da LSPD é o SKIBIDI ZEKA!")

# --- COMANDO: !clear ---
@bot.command(name="clear", help="Limpa um número especificado de mensagens no canal. Uso: !clear <quantidade>")
async def clear_messages(ctx, amount: int):
    """
    Limpa um número especificado de mensagens no canal onde o comando foi invocado.
    Apenas utilizadores com o cargo especificado em ROLE_ID podem usar.
    """
    if not isinstance(ctx.author, discord.Member):
        await ctx.send("Este comando só pode ser usado num servidor.", ephemeral=True)
        return

    required_role = discord.utils.get(ctx.author.roles, id=ROLE_ID)

    if required_role is None:
        await ctx.send("🚫 Não tens permissões para usar este comando. Requer o cargo autorizado.", ephemeral=True)
        return

    if amount <= 0:
        await ctx.send("Por favor, especifique um número positivo de mensagens para limpar.", ephemeral=True)
        return
    
    await ctx.defer(ephemeral=True) 

    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
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

# --- NOVO COMANDO: !clearpunchdb ---
@bot.command(name="clearpunchdb", help="Limpa todos os registos da base de dados de picagem de ponto.")
async def clear_punch_db_command(ctx):
    """
    Limpa todos os registos da tabela 'punches' na base de dados.
    Apenas utilizadores com o cargo especificado em ROLE_ID podem usar.
    """
    if not isinstance(ctx.author, discord.Member):
        await ctx.send("Este comando só pode ser usado num servidor.", ephemeral=True)
        return

    required_role = discord.utils.get(ctx.author.roles, id=ROLE_ID)

    if required_role is None:
        await ctx.send("🚫 Não tens permissões para usar este comando. Requer o cargo autorizado.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    success = clear_punches_table() # Chama a nova função do database.py

    if success:
        await ctx.followup.send("✅ Todos os registos da base de dados de picagem de ponto foram limpos com sucesso!", ephemeral=True)
        print(f"Comando !clearpunchdb executado por {ctx.author.display_name}. Registos de picagem de ponto limpos.")
    else:
        await ctx.followup.send("❌ Ocorreu um erro ao tentar limpar os registos da base de dados de picagem de ponto.", ephemeral=True)
        print(f"Erro ao executar !clearpunchdb por {ctx.author.display_name}.")

# --- Evento on_ready ---
@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user.name} ({bot.user.id})')

    setup_database()
    print('📦 Base de dados configurada.')

    cogs_folder = './cogs'
    if not os.path.exists(cogs_folder):
        print(f"⚠️ Pasta '{cogs_folder}' não encontrada. Certifique-se de que seus cogs estão na subpasta 'cogs'.")
        return

    for filename in os.listdir(cogs_folder):
        if filename.endswith('.py') and not filename.startswith('__'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'✅ Cog {filename[:-3]} carregado.')
            except Exception as e:
                print(f'❌ Erro ao carregar cog {filename[:-3]}: {e}')

    print('🚀 Todos os cogs foram carregados.')
    print('------') 

    # await bot.tree.sync()

# --- Executa o bot ---
if __name__ == '__main__':
    if TOKEN is None:
        print("ERRO: DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
        print("Por favor, defina a variável de ambiente DISCORD_BOT_TOKEN com o token do seu bot.")
    else:
        bot.run(TOKEN)
