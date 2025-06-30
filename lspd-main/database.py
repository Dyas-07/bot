import os
import psycopg2
from datetime import datetime, timedelta, timezone

def get_db_connection():
    """
    Retorna uma conexão com o banco de dados PostgreSQL.
    A DATABASE_URL é automaticamente fornecida pelo Railway ao seu serviço de bot.
    """
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("Variável de ambiente 'DATABASE_URL' não encontrada. Verifique as configurações do Railway.")
        
        conn = psycopg2.connect(database_url)
        print("DEBUG DB: Conectado ao PostgreSQL com sucesso.")
        return conn
    except Exception as e:
        print(f"ERRO: Falha ao conectar ao PostgreSQL: {e}")
        raise

def setup_database():
    """
    Cria as tabelas 'punches' e 'tickets' se elas não existirem no PostgreSQL.
    Ajustado para sintaxe PostgreSQL.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS punches (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username VARCHAR(255) NOT NULL,
                punch_in_time TIMESTAMP WITH TIME ZONE,
                punch_out_time TIMESTAMP WITH TIME ZONE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id SERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL UNIQUE,
                creator_id BIGINT NOT NULL,
                creator_name VARCHAR(255) NOT NULL,
                category VARCHAR(255) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL
            )
        ''')
        conn.commit()
        print("DEBUG: Tabelas de banco de dados 'punches' e 'tickets' verificadas/criadas no PostgreSQL.")
    except Exception as e:
        print(f"ERRO: Falha ao configurar tabelas no PostgreSQL: {e}")
        if conn:
            conn.rollback()
        raise
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
        
        print(f"DEBUG: record_punch_in - Verificando se {username} ({user_id}) já está em serviço...")
        cursor.execute("SELECT id FROM punches WHERE user_id = %s AND punch_out_time IS NULL", (user_id,))
        existing_punch = cursor.fetchone()
        if existing_punch:
            print(f"DEBUG: record_punch_in - {username} ({user_id}) JÁ está em serviço com ID {existing_punch[0]}.")
            return False

        current_time = datetime.now(timezone.utc)
        print(f"DEBUG: record_punch_in - Registrando entrada para {username} ({user_id}) em {current_time}...")
        cursor.execute("INSERT INTO punches (user_id, username, punch_in_time) VALUES (%s, %s, %s)",
                       (user_id, username, current_time))
        conn.commit()
        print(f"DEBUG: record_punch_in - Entrada para {username} ({user_id}) REGISTRADA e commitada.")
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
        
        print(f"DEBUG: record_punch_out - Procurando último ponto aberto para {user_id}...")
        cursor.execute("SELECT id, punch_in_time FROM punches WHERE user_id = %s AND punch_out_time IS NULL ORDER BY id DESC LIMIT 1", (user_id,))
        active_punch = cursor.fetchone()

        if active_punch:
            punch_id, punch_in_time = active_punch[0], active_punch[1] 
            print(f"DEBUG: record_punch_out - Ponto aberto encontrado: ID {punch_id}, Entrada {punch_in_time}.")
            
            current_time = datetime.now(timezone.utc)
            time_diff = current_time - punch_in_time
            
            print(f"DEBUG: record_punch_out - Atualizando ponto ID {punch_id} com saída {current_time}...")
            cursor.execute("UPDATE punches SET punch_out_time = %s WHERE id = %s",
                           (current_time, punch_id))
            conn.commit()
            print(f"DEBUG: record_punch_out - Saída para ponto ID {punch_id} REGISTRADA e commitada. Duração: {time_diff}.")
            return True, time_diff
        else:
            print(f"DEBUG: record_punch_out - NENHUM ponto aberto encontrado para {user_id}.")
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
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Garante que as datas de início e fim são timezone-aware em UTC para a comparação
        adjusted_start_time = start_time.replace(tzinfo=timezone.utc) if start_time.tzinfo is None else start_time
        adjusted_end_time = end_time.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc) if end_time.tzinfo is None else end_time

        print(f"DEBUG: get_punches_for_period - Buscando pontos de {adjusted_start_time} a {adjusted_end_time}...")
        cursor.execute("""
            SELECT user_id, username, punch_in_time, punch_out_time
            FROM punches
            WHERE punch_in_time BETWEEN %s AND %s
            AND punch_out_time IS NOT NULL
            ORDER BY punch_in_time ASC
        """, (adjusted_start_time, adjusted_end_time))

        results = []
        for row in cursor.fetchall():
            results.append({
                'user_id': row[0],
                'username': row[1],
                'punch_in_time': row[2].isoformat(),
                'punch_out_time': row[3].isoformat()
            })
        print(f"DEBUG: get_punches_for_period - Encontrados {len(results)} pontos.")
        return results
    except Exception as e:
        print(f"ERRO: Falha ao obter pontos para período no PostgreSQL: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- get_open_punches_for_auto_close() e auto_record_punch_out() REMOVIDAS ---

# --- Função para limpar a tabela de picagem de ponto ---
def clear_punches_table() -> bool:
    """
    Limpa todos os registos da tabela 'punches' no PostgreSQL.
    Retorna True se a operação for bem-sucedida, False caso contrário.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("DEBUG: clear_punches_table - Tentando limpar todos os registos da tabela 'punches'...")
        cursor.execute("DELETE FROM punches")
        conn.commit()
        print("DEBUG: clear_punches_table - Todos os registos da tabela 'punches' foram limpos com sucesso.")
        return True
    except Exception as e:
        print(f"ERRO: Falha ao limpar a tabela 'punches' no PostgreSQL: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# --- Funções para o banco de dados de tickets (adaptadas para PostgreSQL) ---

def add_ticket_to_db(channel_id: int, creator_id: int, creator_name: str, category: str):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        created_at = datetime.now(timezone.utc)
        
        print(f"DEBUG: add_ticket_to_db - Tentando adicionar ticket para canal {channel_id}...")
        cursor.execute("INSERT INTO tickets (channel_id, creator_id, creator_name, category, created_at) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (channel_id) DO NOTHING",
                      (channel_id, creator_id, creator_name, category, created_at))
        
        conn.commit()
        if cursor.rowcount > 0:
            print(f"DEBUG: Ticket {channel_id} (Criador: {creator_name}, Categoria: {category}) adicionado ao DB PostgreSQL.")
            return True
        else:
            print(f"DEBUG: Erro: Ticket para o canal {channel_id} já existe no DB PostgreSQL (ON CONFLICT).")
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
        print(f"DEBUG: remove_ticket_from_db - Tentando remover ticket para canal {channel_id}...")
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
        print(f"DEBUG: get_all_open_tickets - Buscando todos os tickets abertos...")
        cursor.execute("SELECT channel_id, creator_id, creator_name, category, created_at FROM tickets")
        tickets_raw = cursor.fetchall()
        
        tickets_formatted = []
        for t in tickets_raw:
            tickets_formatted.append({
                'channel_id': t[0],
                'creator_id': t[1],
                'creator_name': t[2],
                'category': t[3],
                'created_at': t[4].isoformat()
            })
        return tickets_formatted
    except Exception as e:
        print(f"ERRO: Falha ao obter tickets abertos do DB PostgreSQL: {e}")
        return []
    finally:
        if conn:
            conn.close()
