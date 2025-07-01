import discord
from discord.ext import commands, tasks
from discord import app_commands # Importa app_commands para slash commands
from datetime import datetime, timedelta, timezone # Importa timezone para lidar com datas UTC

# Importa funções do nosso módulo database (agora para PostgreSQL)
from database import get_punches_for_period
# Importa configurações do nosso módulo config
from config import ROLE_ID # ROLE_ID ainda é usado para permissões do comando /horas

class ReportsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # A tarefa de relatório semanal automático foi removida.
        print("ReportsCog está pronto. Tarefa de relatório semanal automático desativada.")

    # A função cog_unload() e a tarefa weekly_report_task (e seu before_loop) foram removidas.

    # Função auxiliar para gerar e enviar o relatório, agora sempre acionada por comando
    async def _generate_and_send_report(self, interaction: discord.Interaction, start_date: datetime, end_date: datetime):
        """
        Gera e envia o relatório de horas de serviço para um período específico.
        Sempre espera start_date e end_date do comando.
        """
        # Garante que as datas são timezone-aware em UTC para a comparação com o DB
        start_of_period = start_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end_of_period = end_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
            
        if start_of_period > end_of_period:
            await interaction.followup.send("Erro: A data de início não pode ser posterior à data de fim.", ephemeral=True)
            print(f"Erro na data do relatório: Data de início ({start_of_period}) posterior à data de fim ({end_of_period}).")
            return

        print(f"Gerando relatório de {start_of_period.strftime('%d/%m/%Y %H:%M')} a {end_of_period.strftime('%d/%m/%Y %H:%M')}")

        records = get_punches_for_period(start_of_period, end_of_period)
        user_total_times = {}

        if not records:
            await interaction.followup.send("Nenhum registro de ponto encontrado para o período especificado.", ephemeral=True)
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

        # Envia o relatório para o canal do comando
        await interaction.followup.send(embed=embed, ephemeral=True)
        print(f"Relatório acionado por comando enviado por {interaction.user.display_name}.")
        
    # --- COMANDO DE BARRA PARA RELATÓRIO DE HORAS ---
    @app_commands.command(name="horas", description="Gera um relatório de horas de serviço por período.")
    @app_commands.describe(
        data_inicio="A data de início do período (DD/MM/YYYY).",
        data_fim="A data de fim do período (DD/MM/YYYY)."
    )
    # Verifica se o utilizador tem o cargo especificado em ROLE_ID
    @app_commands.checks.has_role(ROLE_ID) 
    async def horas_command(self, interaction: discord.Interaction, data_inicio: str, data_fim: str):
        """
        Comando de barra para gerar um relatório de horas de serviço para um período específico.
        """
        await interaction.response.defer(ephemeral=True) # Defer para que o bot "pense"

        try:
            # Converte as strings de data para objetos datetime
            start_date = datetime.strptime(data_inicio, '%d/%m/%Y')
            end_date = datetime.strptime(data_fim, '%d/%m/%Y')
            
            # Chama a função auxiliar para gerar e enviar o relatório
            await self._generate_and_send_report(interaction, start_date, end_date)

        except ValueError:
            await interaction.followup.send("Formato de data inválido. Use DD/MM/YYYY. Ex: `/horas 01/01/2025 31/01/2025`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Ocorreu um erro ao gerar o relatório: `{e}`", ephemeral=True)
            print(f"Erro ao gerar relatório de ponto via /horas: {e}")

async def setup(bot):
    await bot.add_cog(ReportsCog(bot))
