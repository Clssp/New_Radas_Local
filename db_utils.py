import streamlit as st
from datetime import datetime, timedelta, timezone
import json
from supabase_client import supabase_client

# --- Funções para a tabela 'mercados_monitorados' ---

def find_market_by_term_and_location(user_id: str, termo: str, localizacao: str):
    """Verifica se um mercado já existe para este usuário e retorna seu ID."""
    try:
        response = supabase_client.table('mercados_monitorados').select('id').eq('user_id', user_id).eq('termo', termo).eq('localizacao', localizacao).limit(1).single().execute()
        return response.data['id']
    except Exception:
        # Se .single() não encontra nada, ele lança um erro. Retornar None é o comportamento esperado.
        return None

def get_user_markets(user_id: str):
    """Busca todos os mercados associados a um user_id."""
    try:
        response = supabase_client.table('mercados_monitorados').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao buscar mercados: {e}")
        return []

def add_market(user_id: str, termo: str, localizacao: str):
    """Adiciona um novo mercado no banco de dados e retorna seu ID."""
    try:
        response = supabase_client.table('mercados_monitorados').insert({
            'user_id': user_id,
            'termo': termo,
            'localizacao': localizacao
        }).execute()
        return response.data[0]['id']
    except Exception as e:
        st.error(f"Erro ao adicionar mercado: {e}")
        raise e

def delete_market(market_id: int):
    """Deleta um mercado e seus snapshots associados."""
    try:
        supabase_client.table('snapshots_dados').delete().eq('mercado_id', market_id).execute()
        supabase_client.table('mercados_monitorados').delete().eq('id', market_id).execute()
    except Exception as e:
        st.error(f"Erro ao deletar mercado: {e}")

# --- Funções para a tabela 'snapshots_dados' ---

def check_for_recent_snapshot(market_id: int, max_age_days: int = 7):
    """Verifica se existe um snapshot recente e o retorna (CACHE HIT)."""
    try:
        latest_snapshot = get_latest_snapshot(market_id)
        if not latest_snapshot:
            return None # Não há snapshot, CACHE MISS
        
        snapshot_date = datetime.fromisoformat(latest_snapshot['data_snapshot'])
        
        # Compara a data do snapshot com a data atual (considerando o fuso horário)
        if datetime.now(timezone.utc) - snapshot_date < timedelta(days=max_age_days):
            print(f"CACHE HIT: Encontrado snapshot recente para market_id {market_id}.")
            return latest_snapshot # Retorna o snapshot encontrado, CACHE HIT
        
        print(f"CACHE MISS: Snapshot para market_id {market_id} é muito antigo.")
        return None
    except Exception:
        return None

def add_snapshot(market_id: int, user_id: str, dados_json: str):
    """Salva um novo snapshot de análise no banco de dados."""
    try:
        supabase_client.table('snapshots_dados').insert({
            'mercado_id': market_id,
            'user_id': user_id,
            'dados_json': dados_json
        }).execute()
    except Exception as e:
        st.error(f"Erro ao salvar snapshot: {e}")
        raise e

def get_latest_snapshot(market_id: int):
    """Busca o snapshot mais recente de um mercado."""
    try:
        response = supabase_client.table('snapshots_dados').select('*').eq('mercado_id', market_id).order('data_snapshot', desc=True).limit(1).single().execute()
        return response.data
    except Exception:
        return None

def get_latest_snapshot_date(market_id: int):
    """Busca a data do snapshot mais recente de um mercado."""
    try:
        response = supabase_client.table('snapshots_dados').select('data_snapshot').eq('mercado_id', market_id).order('data_snapshot', desc=True).limit(1).single().execute()
        return datetime.fromisoformat(response.data['data_snapshot'])
    except Exception:
        return None

def get_all_snapshots(market_id: int):
    """Busca TODOS os snapshots de um mercado, ordenados."""
    try:
        response = supabase_client.table('snapshots_dados').select('*').eq('mercado_id', market_id).order('data_snapshot', desc=False).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao buscar histórico de snapshots: {e}")
        return []