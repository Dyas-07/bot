import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta

# Importa funções do nosso módulo database (agora para PostgreSQL)
from database import get_punches_for_period
# Importa configurações do nosso módulo config
from config import WEEKLY_REPORT_CHANNEL_ID, ROLE_ID

class ReportsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Inicia a tarefa em loop para enviar relatórios semanais quando o cog é carregado.
        self.weekly_report_task.start()
        print("ReportsCog está pronto. Tarefa de relatório semanal iniciada.")

    def cog_unload(self):
        """Garante que a tarefa em loop seja parada quando o cog é descarregado."""
        self.weekly_report_task.cancel()
        print("ReportsCog descarregado. Tarefa de relatório semanal parada.")

    @tasks.loop(hours=24 * 7) # Executa a cada 7 dias (uma semana)
    async def weekly_report_task(self):
        """
        Esta tarefa envia um relatório semanal das horas de serviço.
        Ela é configurada para rodar a cada 7 dias.
        """
        await self.bot.wait_until_ready() # Garante que o bot esteja pronto antes de iniciar a tarefa.
        print(f"Tarefa de relatório semanal executando... ({datetime.now().strftime('%d/%m/%Y %H:%M')})")
        
        # Chama a função principal de geração de relatório com o período padrão da semana passada.
        await self._generate_and_send_report()

    # Função auxiliar para gerar e enviar o relatório, reutilizável por loop e comando
    async def _generate_and_send_report(self, start_date: datetime = None, end_date: datetime = None, ctx: commands.Context = None):
        """
        Gera e envia o relatório de horas de serviço para um período específico.
        Se start_date e end_date não forem fornecidos, usa a semana passada.
        O 'ctx' é opcional e é usado se o relatório for acionado por um comando.
        """
        now = datetime.now()

        if start_date is None or end_date is None:
            # Lógica para a semana passada (padrão)
            # Define o início da semana como segunda-feira (weekday() retorna 0 para segunda)
            # Subtrai 7 dias para ir para a semana passada
            start_of_period = now - timedelta(days=now.weekday() + 7) 
            start_of_period = start_of_period.replace(hour=0, minute=0, second=0, microsecond=0)

            end_of_period = start_of_period + timedelta(days=6) # Fim da semana passada (domingo)
            end_of_period = end_of_period.replace(hour=23, minute=59, second=59, microsecond=999999) # Inclui o dia inteiro
        else:
            # Usa as datas fornecidas pelo comando
            start_of_period = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_period = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            if start_of_period > end_of_period:
                if ctx: # Se for um comando, responde no contexto do comando
                    await ctx.send("Erro: A data de início não pode ser posterior à data de fim.", ephemeral=True)
                print(f"Erro na data do relatório: Data de início ({start_of_period}) posterior à data de fim ({end_of_period}).")
                return

        print(f"Gerando relatório de {start_of_period.strftime('%d/%m/%Y %H:%M')} a {end_of_period.strftime('%d/%m/%Y %H:%M')}")

        records = get_punches_for_period(start_of_period, end_of_period)
        user_total_times = {}

        if not records:
            if ctx:
                await ctx.send("Nenhum registro de ponto encontrado para o período especificado.", ephemeral=True)
            else: # Para o relatório automático
                report_channel = self.bot.get_channel(WEEKLY_REPORT_CHANNEL_ID)
                if report_channel:
                    await report_channel.send(f"**Relatório Semanal de Serviço ({start_of_period.strftime('%d/%m/%Y')} - {end_of_period.strftime('%d/%m/%Y')})**\n\nNenhum registro de serviço encontrado para o período especificado.")
            return

        for record in records:
            user_id = record['user_id']
            username = record['username']
            # punch_in_time e punch_out_time já vêm como strings ISO do DB para compatibilidade
            punch_in = datetime.fromisoformat(record['punch_in_time'])
            punch_out = datetime.fromisoformat(record['punch_out_time'])
            
            duration = punch_out - punch_in
            
            user_total_times.setdefault(user_id, {'username': username, 'total_duration': timedelta(0)})
            user_total_times[user_id]['total_duration'] += duration

        # --- CONSTRUÇÃO DA EMBED DO RELATÓRIO ---
        embed = discord.Embed(
            title=f"📊 Relatório de Horas de Serviço (LSPD)",
            description=f"**Período:** `{start_of_period.strftime('%d/%m/%Y')} - {end_of_period.strftime('%d/%m/%Y')}`",
            color=discord.Color.from_rgb(50, 205, 50) # Verde vibrante
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1260308350776774817/1386713008256061512/Untitled_1024_x_1024_px_4.png") # Logo LSPD
        
        # Ordena os utilizadores pelo tempo total em serviço (do maior para o menor)
        sorted_users = sorted(user_total_times.items(), key=lambda item: item[1]['total_duration'], reverse=True)

        # Adiciona os membros como campos da embed
        if sorted_users:
            current_field_value = ""
            field_count = 0
            
            for i, (user_id, data) in enumerate(sorted_users):
                username = data['username']
                total_duration = data['total_duration']
                
                total_seconds = int(total_duration.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                formatted_total_time = f"{hours}h {minutes}m {seconds}s"
                
                # Linha para o relatório
                line = f"**{i+1}. {username}** (`{user_id}`)\nTempo Total: `{formatted_total_time}`"
                
                # Verifica se a linha atual e o separador excederão o limite do campo (1024 chars)
                if len(current_field_value) + len(line) + 1 > 1024 and current_field_value: 
                    embed.add_field(name=f"Membros em Serviço (parte {field_count + 1})", value=current_field_value, inline=False)
                    current_field_value = line
                    field_count += 1
                else:
                    if current_field_value:
                        current_field_value += "\n" + line
                    else:
                        current_field_value = line
            
            # Adiciona o último campo (se não estiver vazio)
            if current_field_value:
                if field_count == 0: # Se tudo coube em um único campo
                    embed.add_field(name="Membros em Serviço", value=current_field_value, inline=False)
                else: # Se foram criados múltiplos campos
                    embed.add_field(name=f"Membros em Serviço (parte {field_count + 1})", value=current_field_value, inline=False)

        embed.set_footer(
            text="Relatório gerado automaticamente pelo Sistema de Ponto LSPD.",
            icon_url="https://cdn.discordapp.com/attachments/1387870298526978231/1387874932561547437/IMG_6522.jpg" # Logo "Developed by Dyas"
        )
        # --- FIM DA CONSTRUÇÃO DA EMBED ---

        # Envia o relatório para o canal de logs ou para o contexto do comando
        if ctx: # Se foi acionado por um comando, responde no canal do comando
            await ctx.send(embed=embed, ephemeral=True)
            print("Relatório acionado por comando enviado.")
        else: # Se foi acionado pela tarefa automática, envia para o canal de relatório semanal
            report_channel = self.bot.get_channel(WEEKLY_REPORT_CHANNEL_ID)
            if report_channel:
                await report_channel.send(embed=embed)
                print("Relatório semanal automático enviado com sucesso.")
            else:
                print(f"Erro: Canal de relatório semanal com ID {WEEKLY_REPORT_CHANNEL_ID} não encontrado para envio automático.")
        
    # --- COMANDO PARA FORÇAR O RELATÓRIO SEMANAL ---
    @commands.command(name="forcereport", help="Força a geração e o envio do relatório de horas de serviço. Use !forcereport [DD/MM/YYYY] [DD/MM/YYYY] para um período específico.")
    @commands.has_permissions(administrator=True) # Apenas administradores podem usar
    async def force_weekly_report(self, ctx: commands.Context, start_date_str: str = None, end_date_str: str = None):
        """
        Comando para acionar manualmente a geração do relatório.
        Pode receber datas opcionais no formato DD/MM/YYYY.
        """
        await ctx.defer(ephemeral=True) # Defer para que o bot "pense"

        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%d/%m/%Y')
            except ValueError:
                await ctx.send("Formato de data inválido para a data de início. Use DD/MM/YYYY. Ex: `!forcereport 01/01/2025 31/01/2025`", ephemeral=True)
                return
            
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%d/%m/%Y')
            except ValueError:
                await ctx.send("Formato de data inválido para a data de fim. Use DD/MM/YYYY. Ex: `!forcereport 01/01/2025 31/01/2025`", ephemeral=True)
                return
            
        if (start_date_str and not end_date_str) or (not start_date_str and end_date_str):
            await ctx.send("Para um período específico, forneça AMBAS as datas (início e fim).", ephemeral=True)
            return

        # Chama a função auxiliar que agora aceita as datas e o contexto
        await self._generate_and_send_report(start_date=start_date, end_date=end_date, ctx=ctx)

async def setup(bot):
    await bot.add_cog(ReportsCog(bot))
