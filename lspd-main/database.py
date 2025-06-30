import os
import psycopg2 # Nova biblioteca para PostgreSQL
from datetime import datetime, timedelta

# Importa o nome do banco de dados do config.py (apenas para referência, DATABASE_URL será usado)
# from config import DATABASE_NAME # Esta linha pode ser removida se DATABASE_NAME não for mais usado

def get_db_connection():
    """
    Retorna uma conexão com o banco de dados PostgreSQL.
    A DATABASE_URL é automaticamente fornecida pelo Railway ao seu serviço de bot.
    """
    try:
        # Pega a DATABASE_URL das variáveis de ambiente do Railway
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("Variável de ambiente 'DATABASE_URL' não encontrada. Verifique as configurações do Railway.")
        
        conn = psycopg2.connect(database_url)
        # Por padrão, psycopg2.extras.DictCursor é uma boa alternativa para sqlite3.Row
        # Mas para simplificar aqui, vamos usar o cursor padrão e acessar por índice ou nome da coluna se usarmos fetchall().
        # Para acessar por nome como dicionário, você precisaria de:
        # import psycopg2.extras
        # cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # No entanto, os seus cogs já esperam dicionários de sqlite3.Row, então vamos mapear.
        print("DEBUG DB: Conectado ao PostgreSQL com sucesso.")
        return conn
    except Exception as e:
        print(f"ERRO: Falha ao conectar ao PostgreSQL: {e}")
        raise # Levanta a exceção para que o bot não continue se não houver conexão com o DB

def setup_database():
    """
    Cria as tabelas 'punches' e 'tickets' se elas não existirem no PostgreSQL.
    Ajustado para sintaxe PostgreSQL.
    """
    conn = None # Inicializa conn como None para o bloco finally
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Tabela para registros de picagem de ponto
        # id SERIAL PRIMARY KEY: Equivalente a AUTOINCREMENT no SQLite para PostgreSQL
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS punches (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL, -- BIGINT para IDs de usuário do Discord
                username VARCHAR(255) NOT NULL,
                punch_in_time TIMESTAMP WITH TIME ZONE, -- TIMESTAMP para armazenar data e hora com fuso horário
                punch_out_time TIMESTAMP WITH TIME ZONE
            )
        ''')
        
        # Tabela para registros de tickets
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id SERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL UNIQUE, -- BIGINT para IDs de canal do Discord
                creator_id BIGINT NOT NULL,
                creator_name VARCHAR(255) NOT NULL,
                category VARCHAR(255) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL
            )
        ''')
        conn.commit() # Salva as mudanças no banco de dados.
        print("DEBUG: Tabelas de banco de dados 'punches' e 'tickets' verificadas/criadas no PostgreSQL.")
    except Exception as e:
        print(f"ERRO: Falha ao configurar tabelas no PostgreSQL: {e}")
        if conn:
            conn.rollback() # Reverte em caso de erro
        raise # Re-levanta a exceção
    finally:
        if conn:
            conn.close()

# --- Funções para Picagem de Ponto ---

def record_punch_in(user_id: int, username: str) -> bool:
    """
    Registra a entrada em serviço de um usuário no PostgreSQL.
    Retorna True se a entrada foi registrada, False se o usuário já estava em serviço.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica se o usuário já está em serviço (punch_out_time IS NULL)
        cursor.execute("SELECT id FROM punches WHERE user_id = %s AND punch_out_time IS NULL", (user_id,))
        if cursor.fetchone():
            return False # Usuário já está em serviço

        current_time = datetime.now() # PostgreSQL lida bem com objetos datetime diretamente
        cursor.execute("INSERT INTO punches (user_id, username, punch_in_time) VALUES (%s, %s, %s)",
                       (user_id, username, current_time))
        conn.commit()
        return True
    except Exception as e:
        print(f"ERRO: Falha ao registrar entrada de ponto no PostgreSQL para {username}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def record_punch_out(user_id: int) -> tuple[bool, timedelta | None]:
    """
    Registra a saída de serviço de um usuário no PostgreSQL.
    Retorna (True, timedelta) se a saída foi registrada com a duração,
    (False, None) se o usuário não estava em serviço.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Procura o último registro de entrada sem saída para este usuário.
        cursor.execute("SELECT id, punch_in_time FROM punches WHERE user_id = %s AND punch_out_time IS NULL ORDER BY id DESC LIMIT 1", (user_id,))
        active_punch = cursor.fetchone()

        if active_punch:
            # psycopg2 fetchone() retorna uma tupla ou None. Acessar por índice.
            punch_id, punch_in_time = active_punch[0], active_punch[1] 
            
            current_time = datetime.now()
            time_diff = current_time - punch_in_time
            
            # Atualiza o registro com o horário de saída.
            cursor.execute("UPDATE punches SET punch_out_time = %s WHERE id = %s",
                           (current_time, punch_id))
            conn.commit()
            return True, time_diff
        else:
            return False, None
    except Exception as e:
        print(f"ERRO: Falha ao registrar saída de ponto no PostgreSQL para {user_id}: {e}")
        if conn:
            conn.rollback()
        return False, None
    finally:
        if conn:
            conn.close()

def get_punches_for_period(start_time: datetime, end_time: datetime):
    """
    Retorna todos os registros de picagem de ponto dentro de um período específico no PostgreSQL.
    Ajusta a data de fim para incluir o dia inteiro.
    Retorna uma lista de dicionários para compatibilidade com os cogs.
    """
    # PostgreSQL lida bem com timestamps, não precisa de isoformat para a query, mas para o output dos cogs, sim.
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Garante que a end_time inclua todo o último dia (até o último microssegundo)
        adjusted_end_time = end_time.replace(hour=23, minute=59, second=59, microsecond=999999)

        cursor.execute("""
            SELECT user_id, username, punch_in_time, punch_out_time
            FROM punches
            WHERE punch_in_time BETWEEN %s AND %s  -- Filtra pela hora de entrada
            AND punch_out_time IS NOT NULL       -- Apenas registros completos (com entrada e saída)
            ORDER BY punch_in_time ASC           -- Ordena por hora de entrada
        """, (start_time, adjusted_end_time)) # Passa objetos datetime diretamente

        # Convertendo para o formato de dicionário que os cogs esperam
        results = []
        for row in cursor.fetchall():
            results.append({
                'user_id': row[0],
                'username': row[1],
                'punch_in_time': row[2].isoformat(), # Converte para string ISO para compatibilidade
                'punch_out_time': row[3].isoformat() # Converte para string ISO para compatibilidade
            })
        return results
    except Exception as e:
        print(f"ERRO: Falha ao obter pontos para período no PostgreSQL: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_open_punches_for_auto_close():
    """
    Retorna todos os registros de ponto que estão abertos (punch_out_time IS NULL) no PostgreSQL.
    Retorna uma lista de dicionários para compatibilidade com os cogs.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, username, punch_in_time
            FROM punches
            WHERE punch_out_time IS NULL
        """)
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'punch_in_time': row[3].isoformat() # Converte para string ISO para compatibilidade
            })
        return results
    except Exception as e:
        print(f"ERRO: Falha ao obter pontos abertos no PostgreSQL: {e}")
        return []
    finally:
        if conn:
            conn.close()

def auto_record_punch_out(punch_id: int, auto_punch_out_time: datetime):
    """
    Registra uma saída automática para um registro de ponto específico no PostgreSQL.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE punches SET punch_out_time = %s WHERE id = %s",
                       (auto_punch_out_time, punch_id)) # Passa objeto datetime diretamente
        conn.commit()
    except Exception as e:
        print(f"ERRO: Falha ao registrar saída automática de ponto no PostgreSQL para ID {punch_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# --- Funções para o banco de dados de tickets (adaptadas para PostgreSQL) ---

def add_ticket_to_db(channel_id: int, creator_id: int, creator_name: str, category: str):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        created_at = datetime.now()
        
        cursor.execute("INSERT INTO tickets (channel_id, creator_id, creator_name, category, created_at) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (channel_id) DO NOTHING",
                      (channel_id, creator_id, creator_name, category, created_at))
        # ON CONFLICT DO NOTHING para lidar com UNIQUE constraint sem erro
        
        conn.commit()
        # Verificar se a linha foi realmente inserida (para o retorno True/False)
        if cursor.rowcount > 0:
            print(f"DEBUG: Ticket {channel_id} (Criador: {creator_name}, Categoria: {category}) adicionado ao DB PostgreSQL.")
            return True
        else:
            print(f"DEBUG: Erro: Ticket para o canal {channel_id} já existe no DB PostgreSQL.")
            return False
    except Exception as e:
        print(f"ERRO: Falha ao adicionar ticket ao DB PostgreSQL para {channel_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def remove_ticket_from_db(channel_id: int):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tickets WHERE channel_id = %s", (channel_id,))
        conn.commit()
        print(f"DEBUG: Ticket para o canal {channel_id} removido do DB PostgreSQL.")
    except Exception as e:
        print(f"ERRO: Falha ao remover ticket do DB PostgreSQL para {channel_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def get_all_open_tickets():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id, creator_id, creator_name, category, created_at FROM tickets")
        tickets_raw = cursor.fetchall()
        
        # Converte para lista de dicionários para manter a compatibilidade
        tickets_formatted = []
        for t in tickets_raw:
            tickets_formatted.append({
                'channel_id': t[0],
                'creator_id': t[1],
                'creator_name': t[2],
                'category': t[3],
                'created_at': t[4].isoformat() # Converte para string ISO para compatibilidade
            })
        return tickets_formatted
    except Exception as e:
        print(f"ERRO: Falha ao obter tickets abertos do DB PostgreSQL: {e}")
        return []
    finally:
        if conn:
            conn.close()
