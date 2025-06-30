import discord
from discord.ext import commands, tasks
import random
import asyncio

# Importa as configurações de status do nosso arquivo config.py
from config import DEFAULT_STATUS_TYPE, BOT_ACTIVITIES, ACTIVITY_CHANGE_INTERVAL_SECONDS

class StatusChangerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._current_activity_index = 0
        self._last_set_activity = None # Para manter o estado da atividade

        # Inicia a tarefa de alternar atividades se houver alguma configurada
        if BOT_ACTIVITIES:
            self.change_activity_task.start()
        else:
            print("Nenhuma atividade de bot configurada em BOT_ACTIVITIES. A tarefa de mudança de atividade não será iniciada.")

    def cog_unload(self):
        """Garante que a tarefa em loop seja parada quando o cog é descarregado."""
        if BOT_ACTIVITIES:
            self.change_activity_task.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Define o status inicial do bot quando ele está pronto.
        Se houver atividades configuradas, a primeira será usada.
        Caso contrário, o bot ficará sem atividade definida.
        """
        print("StatusChangerCog está pronto.")
        # Se houver atividades, define a primeira como atividade inicial
        if BOT_ACTIVITIES and not self.change_activity_task.running:
            # Se a tarefa não está rodando (e.g., BOT_ACTIVITIES estava vazia e foi preenchida depois)
            # ou se é o primeiro on_ready, define a primeira atividade.
            activity_type, message, url = BOT_ACTIVITIES[0]
            activity = self._create_activity(activity_type, message, url)
            await self.bot.change_presence(activity=activity, status=DEFAULT_STATUS_TYPE)
            self._last_set_activity = activity
            print(f"Status inicial do bot definido: {activity.name} ({activity_type.name})")
        elif not BOT_ACTIVITIES:
            # Se não houver atividades configuradas, apenas define o status padrão.
            await self.bot.change_presence(status=DEFAULT_STATUS_TYPE)
            print(f"Status inicial do bot definido (sem atividade): {DEFAULT_STATUS_TYPE}")
        elif self.change_activity_task.running and self._last_set_activity:
            # Se a tarefa já está rodando (bot reconectou) e já tinha uma atividade, tenta redefinir a última
            await self.bot.change_presence(activity=self._last_set_activity, status=DEFAULT_STATUS_TYPE)
            print(f"Bot reconectado, mantendo status: {self._last_set_activity.name}")
        else:
            # fallback genérico se as condições acima não cobrirem (raro)
            await self.bot.change_presence(status=DEFAULT_STATUS_TYPE)
            print(f"Bot reconectado, status padrão definido.")


    def _create_activity(self, activity_type: discord.ActivityType, message: str, url: str = None):
        """Função auxiliar para criar um objeto de atividade com base no tipo."""
        if activity_type == discord.ActivityType.playing:
            return discord.Game(name=message)
        elif activity_type == discord.ActivityType.watching:
            return discord.Activity(type=discord.ActivityType.watching, name=message)
        elif activity_type == discord.ActivityType.listening:
            return discord.Activity(type=discord.ActivityType.listening, name=message)
        elif activity_type == discord.ActivityType.streaming:
            # Para streaming, o URL é necessário. Se não fornecido, volta para Playing.
            if url:
                return discord.Streaming(name=message, url=url)
            else:
                print(f"Aviso: Tipo de atividade STREAMING selecionado para '{message}', mas nenhuma URL foi fornecida. Usando Playing em vez disso.")
                return discord.Game(name=message)
        else:
            # Default para Game se o tipo não for reconhecido
            print(f"Aviso: Tipo de atividade '{activity_type}' não reconhecido. Usando Playing para '{message}'.")
            return discord.Game(name=message)


    @tasks.loop(seconds=ACTIVITY_CHANGE_INTERVAL_SECONDS)
    async def change_activity_task(self):
        """
        Tarefa em loop para alternar a atividade do bot periodicamente.
        """
        if not BOT_ACTIVITIES:
            print("Nenhuma atividade configurada para alternar. Parando a tarefa de mudança de atividade.")
            self.change_activity_task.cancel()
            return

        activity_type, message, url = BOT_ACTIVITIES[self._current_activity_index]
        activity = self._create_activity(activity_type, message, url)

        try:
            await self.bot.change_presence(activity=activity, status=DEFAULT_STATUS_TYPE)
            self._last_set_activity = activity # Armazena a última atividade definida
            print(f"Atividade do bot alterada para: {message} ({activity_type.name})")
        except Exception as e:
            print(f"Erro ao tentar mudar a atividade do bot: {e}")

        # Avança para a próxima atividade ou volta para o início
        self._current_activity_index = (self._current_activity_index + 1) % len(BOT_ACTIVITIES)


    @change_activity_task.before_loop
    async def before_change_activity_task(self):
        """Espera o bot estar pronto antes de iniciar a tarefa de mudança de atividade."""
        await self.bot.wait_until_ready()
        print("Tarefa de mudança de atividade aguardando o bot ficar pronto...")


    # --- Comandos Manuais de Status (apenas para administradores) ---

    @commands.command(name="setstatus", help="Define o status do bot. Uso: !setstatus <online|idle|dnd|invisible>")
    @commands.has_permissions(administrator=True)
    async def set_status_command(self, ctx, status: str):
        """
        Define o status online/idle/dnd/invisible do bot.
        """
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible
        }

        chosen_status = status_map.get(status.lower())
        if chosen_status:
            try:
                # Tenta manter a última atividade definida, se houver
                current_activity = self._last_set_activity if self._last_set_activity else None
                await self.bot.change_presence(activity=current_activity, status=chosen_status)
                await ctx.send(f"Status do bot alterado para: **{status.upper()}**.")
                print(f"Admin {ctx.author} alterou o status do bot para {status.upper()}")
            except Exception as e:
                await ctx.send(f"Erro ao alterar o status: {e}")
        else:
            await ctx.send("Status inválido. Use: `online`, `idle`, `dnd` ou `invisible`.")

    @commands.command(name="setactivity", help="Define a atividade do bot. Uso: !setactivity <playing|watching|listening|streaming> <mensagem> [url]")
    @commands.has_permissions(administrator=True)
    async def set_activity_command(self, ctx, activity_type_str: str, *, message_and_url: str):
        """
        Define a atividade do bot (jogando, assistindo, ouvindo, transmitindo).
        """
        activity_type_map = {
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening,
            "streaming": discord.ActivityType.streaming
        }

        chosen_activity_type = activity_type_map.get(activity_type_str.lower())
        if not chosen_activity_type:
            await ctx.send("Tipo de atividade inválido. Use: `playing`, `watching`, `listening` ou `streaming`.")
            return

        # Divide a mensagem para encontrar uma URL no final, se houver
        parts = message_and_url.rsplit(' ', 1)
        message = parts[0]
        url = None
        if len(parts) > 1 and (parts[1].startswith("http://") or parts[1].startswith("https://")):
            # Verifica se a última parte é realmente uma URL válida para streaming
            if chosen_activity_type == discord.ActivityType.streaming:
                message = parts[0]
                url = parts[1]
            else: # Se não é streaming, a URL é parte da mensagem normal
                message = message_and_url
                url = None
        elif chosen_activity_type == discord.ActivityType.streaming and len(parts) == 1:
            # Se é streaming e só tem uma parte, assumimos que é a URL e a mensagem está vazia ou a URL é a mensagem
            # Vamos pedir para o utilizador fornecer a mensagem e a URL separadamente
            await ctx.send("Para `streaming`, por favor forneça a mensagem e o URL. Ex: `!setactivity streaming Patrulha https://www.twitch.tv/seu_canal`")
            return

        # Se for streaming e não tiver URL, informa o usuário
        if chosen_activity_type == discord.ActivityType.streaming and not url:
            await ctx.send("Para a atividade `streaming`, você deve fornecer uma URL válida do Twitch ou YouTube.")
            return

        activity = self._create_activity(chosen_activity_type, message, url)

        try:
            # Para definir uma atividade manual, paramos a tarefa de alternância
            if self.change_activity_task.is_running():
                self.change_activity_task.cancel()
                print("Tarefa de mudança de atividade suspensa para atividade manual.")

            await self.bot.change_presence(activity=activity, status=DEFAULT_STATUS_TYPE)
            self._last_set_activity = activity # Armazena a atividade manual
            await ctx.send(f"Atividade do bot alterada para **{chosen_activity_type.name.upper()}**: `{message}`.")
            print(f"Admin {ctx.author} alterou a atividade do bot para {chosen_activity_type.name.upper()}: '{message}'")
        except Exception as e:
            await ctx.send(f"Erro ao alterar a atividade: {e}")

    @commands.command(name="resetactivity", help="Reinicia a alternância automática de atividades do bot.")
    @commands.has_permissions(administrator=True)
    async def reset_activity_command(self, ctx):
        """
        Reinicia a alternância automática de atividades.
        """
        if BOT_ACTIVITIES:
            if not self.change_activity_task.is_running():
                self._current_activity_index = 0 # Reinicia o contador para começar da primeira atividade
                self.change_activity_task.start()
                await ctx.send("Alternância automática de atividades reiniciada.")
                print("Alternância automática de atividades reiniciada por admin.")
            else:
                await ctx.send("A alternância automática de atividades já está ativa.")
        else:
            await ctx.send("Não há atividades configuradas para reiniciar a alternância automática.")


async def setup(bot):
    """
    Função necessária para que o Discord.py possa carregar este cog.
    """
    await bot.add_cog(StatusChangerCog(bot))
