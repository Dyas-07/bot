import discord
from discord.ext import commands
import os
from datetime import datetime

# Importa funções do módulo database
from database import record_punch_in, record_punch_out
# Importa configurações do módulo config
from config import PUNCH_CHANNEL_ID, PUNCH_MESSAGE_FILE, PUNCH_LOGS_CHANNEL_ID, ROLE_ID

# Função auxiliar para formatar logs
def log_message(level: str, message: str, emoji: str = "") -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{level.upper():<7}] {emoji} {message}"

# --- Classe View para os Botões de Picagem de Ponto ---
class PunchCardView(discord.ui.View):
    def __init__(self, cog_instance):
        super().__init__(timeout=None)
        self.cog = cog_instance

    @discord.ui.button(label="Entrar em Serviço", style=discord.ButtonStyle.success, emoji="🟢", custom_id="punch_in_button")
    async def punch_in_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        current_time_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        success = record_punch_in(member.id, member.display_name)
        if success:
            await interaction.response.send_message(f"Você entrou em serviço em: {current_time_str}", ephemeral=True)
            print(log_message("INFO", f"{member.display_name} ({member.id}) entrou em serviço", "🟢"))
            logs_channel = self.cog.bot.get_channel(PUNCH_LOGS_CHANNEL_ID)
            if logs_channel:
                log_message_text = f"🟢 **{member.display_name}** (`{member.id}`) entrou em serviço em: `{current_time_str}`."
                await logs_channel.send(log_message_text)
            else:
                print(log_message("ERROR", f"Canal de logs com ID {PUNCH_LOGS_CHANNEL_ID} não encontrado", "❌"))
        else:
            await interaction.response.send_message("Você já está em serviço! Utilize o botão de 'Sair' para registrar sua saída.", ephemeral=True)
            print(log_message("WARNING", f"{member.display_name} ({member.id}) tentou entrar em serviço, mas já está em serviço", "⚠️"))

    @discord.ui.button(label="Sair de Serviço", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="punch_out_button")
    async def punch_out_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        current_time_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        success, time_diff = record_punch_out(member.id)
        if success:
            total_seconds = int(time_diff.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            formatted_time_diff = f"{hours}h {minutes}m {seconds}s"
            await interaction.response.send_message(f"Você saiu de serviço em: {current_time_str}. Tempo em serviço: {formatted_time_diff}", ephemeral=True)
            print(log_message("INFO", f"{member.display_name} ({member.id}) saiu de serviço. Tempo: {formatted_time_diff}", "🔴"))
            logs_channel = self.cog.bot.get_channel(PUNCH_LOGS_CHANNEL_ID)
            if logs_channel:
                log_message_text = f"🔴 **{member.display_name}** (`{member.id}`) saiu de serviço em: `{current_time_str}`. Tempo total: `{formatted_time_diff}`."
                await logs_channel.send(log_message_text)
            else:
                print(log_message("ERROR", f"Canal de logs com ID {PUNCH_LOGS_CHANNEL_ID} não encontrado", "❌"))
        else:
            await interaction.response.send_message("Você não está em serviço! Utilize o botão de 'Entrar' para registrar sua entrada.", ephemeral=True)
            print(log_message("WARNING", f"{member.display_name} ({member.id}) tentou sair de serviço, mas não está em serviço", "⚠️"))

# --- Cog Principal de Picagem de Ponto ---
class PunchCardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._punch_message_id = None

    async def _load_punch_message_id(self):
        """Carrega o ID da mensagem de picagem de ponto de um arquivo."""
        try:
            with open(PUNCH_MESSAGE_FILE, 'r') as f:
                self._punch_message_id = int(f.read().strip())
            print(log_message("INFO", f"ID da mensagem de ponto carregado: {self._punch_message_id}", "📄"))
        except (FileNotFoundError, ValueError):
            self._punch_message_id = None
            print(log_message("WARNING", f"Arquivo {PUNCH_MESSAGE_FILE} não encontrado ou inválido", "⚠️"))

    async def _save_punch_message_id(self, message_id: int):
        """Salva o ID da mensagem de picagem de ponto em um arquivo."""
        self._punch_message_id = message_id
        with open(PUNCH_MESSAGE_FILE, 'w') as f:
            f.write(str(message_id))
        print(log_message("INFO", f"ID da mensagem de ponto salvo: {self._punch_message_id}", "💾"))

    @commands.Cog.listener()
    async def on_ready(self):
        print(log_message("INFO", "PunchCardCog está pronto", "✅"))
        await self._load_punch_message_id()

        if self._punch_message_id:
            try:
                channel = self.bot.get_channel(PUNCH_CHANNEL_ID)
                if channel:
                    await channel.fetch_message(self._punch_message_id)
                    self.bot.add_view(PunchCardView(self))
                    print(log_message("INFO", f"View de picagem de ponto persistente adicionada para mensagem ID: {self._punch_message_id}", "🔗"))
                else:
                    print(log_message("WARNING", f"Canal de picagem de ponto (ID: {PUNCH_CHANNEL_ID}) não encontrado para re-associar a View", "⚠️"))
                    self._punch_message_id = None
            except discord.NotFound:
                print(log_message("WARNING", f"Mensagem de picagem de ponto (ID: {self._punch_message_id}) não encontrada, será recriada no próximo setup", "⚠️"))
                self._punch_message_id = None
            except Exception as e:
                print(log_message("ERROR", f"Erro ao re-associar a View de picagem de ponto: {e}", "❌"))
                self._punch_message_id = None

    @commands.command(name="setuppunch", help="Envia a mensagem de picagem de ponto para o canal configurado.")
    @commands.has_permissions(administrator=True)
    async def setup_punch_message(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)

        channel = self.bot.get_channel(PUNCH_CHANNEL_ID)
        if not channel:
            await ctx.send(f"Erro: Canal de picagem de ponto com ID {PUNCH_CHANNEL_ID} não encontrado.", ephemeral=True)
            print(log_message("ERROR", f"Canal de picagem de ponto (ID: {PUNCH_CHANNEL_ID}) não encontrado para comando !setuppunch por {ctx.author.display_name} ({ctx.author.id})", "❌"))
            return

        embed = discord.Embed(
            title="🕒 Sistema de Picagem de Ponto LSPD",
            description="Utiliza os botões abaixo para registar o início ou o fim do teu serviço.",
            color=discord.Color.blue()
        )
        embed.add_field(name="", value="", inline=False)
        embed.add_field(name="", value="Este sistema garante a organização e monitorização dos horários da LSPD.", inline=False)
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1260308350776774817/1386713008256061512/Untitled_1024_x_1024_px_4.png?ex=685ea921&is=685d57a1&hm=7eade913ed0c813e52280d124181662f80d5ed179fe70b4014b2f61f7192c465&")
        embed.set_footer(
            text="Developed by Dyas",
            icon_url="https://cdn.discordapp.com/attachments/1387870298526978231/1387874932561547437/IMG_6522.jpg?ex=685eeec1&is=685d9d41&hm=0b2e06ee67f221933ead2cbabddef30e04fe115080b9d168dc4d791877d9d9d1&",
        )

        view = PunchCardView(self)

        try:
            if self._punch_message_id:
                message = await channel.fetch_message(self._punch_message_id)
                await message.edit(embed=embed, view=view)
                await ctx.send("Mensagem de picagem de ponto atualizada com sucesso!", ephemeral=True)
                print(log_message("INFO", f"Mensagem de picagem de ponto atualizada (ID: {self._punch_message_id}) por {ctx.author.display_name} ({ctx.author.id})", "🔄"))
            else:
                message = await channel.send(embed=embed, view=view)
                await self._save_punch_message_id(message.id)
                await ctx.send("Mensagem de picagem de ponto enviada com sucesso!", ephemeral=True)
                print(log_message("INFO", f"Mensagem de picagem de ponto enviada (ID: {message.id}) por {ctx.author.display_name} ({ctx.author.id})", "📩"))
        except discord.NotFound:
            print(log_message("WARNING", f"Mensagem de picagem de ponto (ID: {self._punch_message_id}) não encontrada, recriando...", "⚠️"))
            message = await channel.send(embed=embed, view=view)
            await self._save_punch_message_id(message.id)
            await ctx.send("Mensagem de picagem de ponto recriada com sucesso!", ephemeral=True)
            print(log_message("INFO", f"Mensagem de picagem de ponto recriada (ID: {message.id}) por {ctx.author.display_name} ({ctx.author.id})", "📩"))
        except Exception as e:
            await ctx.send(f"Erro ao enviar/atualizar mensagem de picagem de ponto: {e}", ephemeral=True)
            print(log_message("ERROR", f"Erro ao enviar/atualizar mensagem de picagem de ponto por {ctx.author.display_name} ({ctx.author.id}): {e}", "❌"))

async def setup(bot):
    await bot.add_cog(PunchCardCog(bot))
