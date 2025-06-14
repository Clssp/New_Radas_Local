# auth_utils.py (Versão Simplificada - Foco em E-mail/Senha)

import streamlit as st
from supabase import create_client, Client
from gotrue.errors import AuthApiError

# --- INICIALIZAÇÃO DO CLIENTE SUPABASE ---
@st.cache_resource
def init_supabase_client():
    """Inicializa e retorna o cliente Supabase de forma segura."""
    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]
    return create_client(supabase_url, supabase_key)

supabase: Client = init_supabase_client()

# --- FUNÇÕES DE AUTENTICAÇÃO ESSENCIAIS ---

def sign_up(email, password):
    """Realiza o cadastro de um novo usuário no Supabase."""
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        # Mensagem de sucesso clara para o usuário
        mensagem = "✅ Cadastro realizado! Verifique seu e-mail para confirmar a conta."
        return True, mensagem
    except AuthApiError as e:
        if "User already registered" in str(e):
            mensagem = "⚠️ Este e-mail já está cadastrado. Tente fazer o login."
        else:
            mensagem = f"❌ Erro no cadastro: {e.message}"
        return False, mensagem
    except Exception as e:
        mensagem = f"❌ Ocorreu um erro inesperado: {e}"
        return False, mensagem

def sign_in(email, password):
    """Realiza o login de um usuário no Supabase e armazena a sessão."""
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        # Armazena a sessão completa no st.session_state
        st.session_state.user_session = res.session
        return True, None
    except AuthApiError as e:
        return False, f"❌ Erro de login: {e.message}"
    except Exception as e:
        return False, f"❌ Ocorreu um erro inesperado: {e}"

def sign_out():
    """Realiza o logout do usuário e limpa a sessão."""
    try:
        supabase.auth.sign_out()
        st.session_state.user_session = None
    except Exception as e:
        st.error(f"Erro ao fazer logout: {e}")