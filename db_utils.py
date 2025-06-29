# Conteúdo completo para o arquivo: db_utils.py

import streamlit as st
from supabase import create_client, Client
from supabase_client import supabase_client
from datetime import datetime, date
import json
import pandas as pd

# --- Funções de Usuário Padrão ---

@st.cache_data(ttl=300)
def get_user_profile(user_id: str):
    """Busca e retorna o perfil completo de um usuário pelo seu ID."""
    try:
        response = supabase_client.table('profiles').select('*').eq('id', user_id).single().execute()
        return response.data
    except Exception:
        return None

@st.cache_data(ttl=60)
def get_user_markets(user_id: str):
    """Retorna a lista de mercados monitorados por um usuário."""
    try:
        response = supabase_client.table('mercados_monitorados').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao buscar mercados: {e}")
        return []

def find_market_by_term_and_location(user_id: str, termo: str, localizacao: str):
    """Encontra um mercado específico para evitar duplicatas."""
    try:
        response = supabase_client.table('mercados_monitorados').select('id').eq('user_id', user_id).eq('termo', termo).eq('localizacao', localizacao).limit(1).single().execute()
        return response.data['id']
    except Exception:
        return None

def add_market(user_id: str, termo: str, localizacao: str, tipo_negocio: str):
    """Adiciona um novo mercado, limpando o cache para atualizar a lista."""
    try:
        existing_market_id = find_market_by_term_and_location(user_id, termo, localizacao)
        if existing_market_id:
            return existing_market_id
        response = supabase_client.table('mercados_monitorados').insert({'user_id': user_id, 'termo': termo, 'localizacao': localizacao, 'tipo_negocio': tipo_negocio}).execute()
        st.cache_data.clear()
        return response.data[0]['id']
    except Exception as e:
        raise e

def add_snapshot(market_id: int, user_id: str, dados_json: str) -> int | None:
    """Adiciona um novo snapshot e retorna o ID do novo registro."""
    try:
        response = supabase_client.table('snapshots_dados').insert({'mercado_id': market_id, 'user_id': user_id, 'dados_json': json.loads(dados_json)}).execute()
        st.cache_data.clear()
        return response.data[0]['id']
    except Exception as e:
        st.error(f"Erro ao salvar snapshot: {e}")
        return None

@st.cache_data(ttl=300)
def get_latest_snapshot(market_id: int):
    """Pega o snapshot mais recente de um mercado."""
    try:
        response = supabase_client.table('snapshots_dados').select('*').eq('mercado_id', market_id).order('data_snapshot', desc=True).limit(1).single().execute()
        return response.data
    except Exception:
        return None

def get_latest_snapshot_date(market_id: int):
    """Pega a data do snapshot mais recente, reutilizando a função cacheada."""
    try:
        snapshot = get_latest_snapshot(market_id)
        return datetime.fromisoformat(snapshot['data_snapshot'].replace('Z', '+00:00')) if snapshot else None
    except Exception:
        return None

# --- Novas Funções para Análise Temporal (KPIs) ---

def add_kpi_entry(snapshot_id: int, market_id: int, user_id: str, analysis_data: dict):
    """Extrai KPIs de uma análise e os insere na tabela kpi_history."""
    try:
        sentiments = analysis_data.get('analise_sentimentos', {})
        competidores = analysis_data.get('competidores', [])
        avg_rating_list = [c.get('rating', 0) for c in competidores if c.get('rating') is not None]
        avg_rating = sum(avg_rating_list) / len(avg_rating_list) if avg_rating_list else 0

        kpi_data = {
            'snapshot_id': snapshot_id, 'market_id': market_id, 'user_id': user_id,
            'analysis_date': date.today().isoformat(),
            'competitor_count': len(competidores),
            'avg_rating': round(avg_rating, 2),
            'positive_sentiment': sentiments.get('Positivo', 0),
            'neutral_sentiment': sentiments.get('Neutro', 0),
            'negative_sentiment': sentiments.get('Negativo', 0),
            'executive_summary': analysis_data.get('sumario_executivo', '')
        }
        supabase_client.table('kpi_history').insert(kpi_data).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar histórico de KPI: {e}")
        return False

@st.cache_data(ttl=300)
def get_kpi_history(market_id: int) -> pd.DataFrame:
    """Busca o histórico de KPIs para um mercado e retorna como um DataFrame Pandas."""
    try:
        response = supabase_client.table('kpi_history').select('*').eq('market_id', market_id).order('analysis_date', desc=False).execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df['analysis_date'] = pd.to_datetime(df['analysis_date'])
            df.set_index('analysis_date', inplace=True)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao buscar histórico de KPIs: {e}")
        return pd.DataFrame()

# --- Funções de Limite Diário e Configurações ---

@st.cache_data(ttl=300)
def get_platform_setting(setting_name: str) -> str:
    """Busca o valor de uma configuração global da plataforma."""
    try:
        response = supabase_client.table('platform_settings').select('setting_value').eq('setting_name', setting_name).single().execute()
        return response.data['setting_value']
    except Exception:
        return '10' if setting_name == 'daily_analysis_limit' else None

def check_and_update_daily_limit(user_id: str) -> bool:
    """Verifica se o usuário pode realizar uma análise e atualiza o contador usando o limite global."""
    try:
        limit = int(get_platform_setting('daily_analysis_limit'))
        profile = supabase_client.table('profiles').select('daily_analysis_count, last_analysis_date').eq('id', user_id).single().execute().data
        if not profile: return False

        today = date.today()
        count = profile.get('daily_analysis_count', 0)
        last_analysis_date_obj = datetime.strptime(profile.get('last_analysis_date'), '%Y-%m-%d').date() if profile.get('last_analysis_date') else None

        if last_analysis_date_obj != today:
            supabase_client.table('profiles').update({'daily_analysis_count': 1, 'last_analysis_date': today.isoformat()}).eq('id', user_id).execute()
            st.cache_data.clear(); return True
        
        if count < limit:
            supabase_client.table('profiles').update({'daily_analysis_count': count + 1}).eq('id', user_id).execute()
            st.cache_data.clear(); return True
        else:
            return False
    except Exception as e:
        st.error(f"Erro ao verificar limite diário: {e}"); return False

def get_user_analysis_info(user_id: str) -> dict:
    """Apenas LÊ as informações de limite do usuário."""
    try:
        limit = int(get_platform_setting('daily_analysis_limit'))
        profile = get_user_profile(user_id)
        if not profile: return {'count': limit, 'limit_reached': True}

        today = date.today()
        count = profile.get('daily_analysis_count', 0)
        last_analysis_date_obj = datetime.strptime(profile.get('last_analysis_date'), '%Y-%m-%d').date() if profile.get('last_analysis_date') else None

        if last_analysis_date_obj != today:
            return {'count': 0, 'limit_reached': 0 >= limit}
        
        return {'count': count, 'limit_reached': count >= limit}
    except Exception:
        return {'count': 10, 'limit_reached': True}

# --- Funções de Administrador ---

def _create_admin_client() -> Client | None:
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["service_key"])
    except KeyError:
        st.error("A chave 'service_key' do Supabase não foi encontrada."); return None
    except Exception as e:
        st.error(f"Erro ao criar cliente de admin: {e}"); return None

def is_user_admin(user_id: str) -> bool:
    try:
        response = supabase_client.table('admins').select('user_id', count='exact').eq('user_id', user_id).execute()
        return response.count > 0
    except Exception:
        return False

def get_platform_stats_admin():
    admin_client = _create_admin_client()
    if not admin_client: return {}
    try:
        stats = {}
        users_resp = admin_client.rpc('count_total_users', {}).execute()
        stats['total_users'] = users_resp.data or 0
        snapshots_resp = admin_client.table("snapshots_dados").select("id", count='exact').execute()
        stats['total_snapshots'] = snapshots_resp.count
        markets_resp = admin_client.table("mercados_monitorados").select("id", count='exact').execute()
        stats['total_markets'] = markets_resp.count
        return stats
    except Exception as e:
        st.error(f"Erro ao buscar estatísticas da plataforma: {e}"); return {}

def update_platform_setting_admin(setting_name: str, new_value: str):
    admin_client = _create_admin_client()
    if not admin_client: st.error("Falha na autenticação de administrador."); return False
    try:
        admin_client.table('platform_settings').update({'setting_value': new_value}).eq('setting_name', setting_name).execute()
        st.cache_data.clear(); return True
    except Exception as e:
        st.error(f"Erro ao atualizar a configuração: {e}"); return False

def get_all_users_admin():
    admin_client = _create_admin_client()
    if not admin_client: return []
    try:
        users_resp = admin_client.rpc('get_all_users_with_details', {}).execute()
        return users_resp.data
    except Exception as e:
        st.error(f"Erro ao buscar lista de usuários: {e}."); return []

def update_user_profile_admin(user_id: str, data: dict):
    admin_client = _create_admin_client()
    if not admin_client: return False
    try:
        admin_client.table("profiles").update(data).eq("id", user_id).execute()
        st.cache_data.clear(); return True
    except Exception as e:
        st.error(f"Erro ao atualizar perfil: {e}"); return False