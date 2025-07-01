import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime

# Importa configurações
from config import TOKEN, ROLE_ID

# Setup da base de dados e função para limpar a tabela de picagem
from database import setup_database, clear_punches_table

# Função auxiliar para formatar logs
def log_message(level: str, message: str, emoji: str = "") -> str:
    """Formata mensagens de log com timestamp, nível e emoji opcional."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{level.upper():<7}] {emoji} {message}"

# Intents - Certifique-se de que estas estão ativadas no Discord Developer Portal!
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True
intents.presences = True

# Bot com prefixo "!"
bot = commands.Bot(command_prefix='!', intents=intents)

# --- COMANDO: !mascote ---
@bot.command(name="mascote", help="Exibe a mascote atual da LSPD.")
async def hello(ctx):
    """Exibe a mascote atual da LSPD, restrito a membros com o cargo especificado."""
    if not isinstance(ctx.author, discord.Member):
        await ctx.send("Este comando só pode ser usado num servidor.", ephemeral=True)
        print(log_message("WARNING", f"Comando !mascote usado fora de servidor por {ctx.author}"))
        return

    role = discord.utils.get(ctx.author.roles, id=ROLE_ID)
    if role is None:
        await ctx.send("🚫 Não tens permissões para isso.", ephemeral=True)
        print(log_message("WARNING", f"Comando !mascote negado para {ctx.author.display_name} ({ctx.author.id}): sem cargo necessário"))
    else:
        await ctx.send("A atual mascote da LSPD é o SKIBIDI ZEKA!")
        print(log_message("INFO", f"Comando !mascote executado por {ctx.author.display_name} ({ctx.author.id})"))

# --- COMANDO: !clear ---
@bot.command(name="clear", help="Limpa um número especificado de mensagens no canal. Uso: !clear <quantidade>")
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int):
    """
    Limpa um número especificado de mensagens no canal onde o comando foi invocado.
    Requer permissão de 'Gerenciar Mensagens'.
    """
    if not isinstance(ctx.author, discord.Member):
        await ctx.send("Este comando só pode ser usado num servidor.", ephemeral=True)
        print(log_message("WARNING", f"Comando !clear usado fora de servidor por {ctx.author}"))
        return

    if amount <= 0:
        await ctx.send("Por favor, especifique um número positivo de mensagens para limpar.", ephemeral=True)
        print(log_message("WARNING", f"Comando !clear com valor inválido ({amount}) por {ctx.author.display_name} ({ctx.author.id})"))
        return

    await ctx.defer(ephemeral=True)

    try:
        deleted = await ctx.channel.purge(limit=amount + 1)  # +1 para incluir a mensagem do comando
        await ctx.send(f"✅ Foram limpas {len(deleted) - 1} mensagens.", ephemeral=True)
        print(log_message("INFO", f"Comando !clear executado por {ctx.author.display_name} ({ctx.author.id}). Limpou {len(deleted) - 1} mensagens no canal {ctx.channel.name}", "🧹"))
    except discord.Forbidden:
        await ctx.send("❌ Não tenho permissão para gerenciar mensagens neste canal. Verifique as minhas permissões.", ephemeral=True)
        print(log_message("ERROR", f"Permissão negada ao limpar mensagens no canal {ctx.channel.name} por {ctx.author.display_name} ({ctx.author.id})", "🚫"))
    except discord.HTTPException as e:
        await ctx.send(f"❌ Ocorreu um erro ao tentar limpar mensagens: {e}", ephemeral=True)
        print(log_message("ERROR", f"Erro HTTP ao limpar mensagens no canal {ctx.channel.name} por {ctx.author.display_name} ({ctx.author.id}): {e}", "❌"))
    except Exception as e:
        await ctx.send(f"❌ Ocorreu um erro inesperado: {e}", ephemeral=True)
        print(log_message("ERROR", f"Erro inesperado ao limpar mensagens por {ctx.author.display_name} ({ctx.author.id}): {e}", "❌"))

# --- COMANDO: !clearpunchdb ---
@bot.command(name="clearpunchdb", help="Limpa todos os registos da base de dados de picagem de ponto.")
@commands.has_permissions(administrator=True)
async def clear_punch_db_command(ctx):
    """
    Limpa todos os registos da tabela 'punches' na base de dados.
    Requer permissão de 'Administrador'.
    """
    if not isinstance(ctx.author, discord.Member):
        await ctx.send("Este comando só pode ser usado num servidor.", ephemeral=True)
        print(log_message("WARNING", f"Comando !clearpunchdb usado fora de servidor por {ctx.author}"))
        return

    await ctx.defer(ephemeral=True)

    try:
        success = clear_punches_table()
        if success:
            await ctx.send("✅ Todos os registos da base de dados de picagem de ponto foram limpos com sucesso!", ephemeral=True)
            print(log_message("INFO", f"Comando !clearpunchdb executado por {ctx.author.display_name} ({ctx.author.id}). Registos de picagem limpos", "🗑️"))
        else:
            await ctx.send("❌ Ocorreu um erro ao tentar limpar os registos da base de dados de picagem de ponto.", ephemeral=True)
            print(log_message("ERROR", f"Erro ao limpar registos de picagem por {ctx.author.display_name} ({ctx.author.id})", "❌"))
    except Exception as e:
        await ctx.send(f"❌ Ocorreu um erro inesperado ao limpar a base de dados: {e}", ephemeral=True)
        print(log_message("ERROR", f"Erro inesperado ao limpar registos de picagem por {ctx.author.display_name} ({ctx.author.id}): {e}", "❌"))

# --- Evento on_ready ---
@bot.event
async def on_ready():
    print(log_message("INFO", f"Bot conectado como {bot.user.name} ({bot.user.id})", "✅"))
    
    # Configura base de dados
    try:
        setup_database()
        print(log_message("INFO", "Base de dados configurada", "📦"))
    except Exception as e:
        print(log_message("ERROR", f"Falha ao configurar base de dados: {e}", "❌"))
        return

    # Carrega cogs
    cogs_folder = './cogs'
    if not os.path.exists(cogs_folder):
        print(log_message("WARNING", f"Pasta '{cogs_folder}' não encontrada. Verifique a estrutura do projeto", "⚠️"))
        return

    print(log_message("INFO", "Iniciando carregamento de cogs...", "🔄"))
    for filename in os.listdir(cogs_folder):
        if filename.endswith('.py') and not filename.startswith('__'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(log_message("INFO", f"Cog {filename[:-3]} carregado", "✅"))
            except Exception as e:
                print(log_message("ERROR", f"Erro ao carregar cog {filename[:-3]}: {e}", "❌"))

    print(log_message("INFO", "Todos os cogs foram carregados", "🚀"))
    print("-" * 50)

    # Sincronização de slash commands (comente após a primeira sincronização bem-sucedida)
    try:
        await bot.tree.sync()
        print(log_message("INFO", "Comandos de aplicação (slash commands) sincronizados com o Discord", "🔄"))
    except Exception as e:
        print(log_message("ERROR", f"Falha ao sincronizar comandos de aplicação: {e}", "❌"))

# --- Executa o bot ---
if __name__ == '__main__':
    if TOKEN is None:
        print(log_message("ERROR", "DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente", "❌"))
        print(log_message("INFO", "Defina a variável de ambiente DISCORD_BOT_TOKEN com o token do seu bot"))
    else:
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(log_message("ERROR", f"Erro ao iniciar o bot: {e}", "❌"))
