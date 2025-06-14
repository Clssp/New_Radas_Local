# auth_utils.py

import streamlit as st
from supabase import create_client, Client
from gotrue.errors import AuthApiError

@st.cache_resource
def init_supabase_client():
    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]
    return create_client(supabase_url, supabase_key)

supabase: Client = init_supabase_client()

# --- FUNÇÕES DE AUTENTICAÇÃO ---

def get_google_auth_url(redirect_url: str):
    """Gera a URL de autenticação do Google, forçando o fluxo implícito."""
    try:
        data = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_url,
                "flow_type": "implicit"  # <-- A CORREÇÃO CRÍTICA ESTÁ AQUI
            }
        })
        return data.url
    except Exception as e:
        st.error(f"Não foi possível gerar a URL de login: {e}")
        return None

def exchange_code_for_session(auth_code: str):
    """Troca o código de autorização do Google por uma sessão de usuário."""
    try:
        session_data = supabase.auth.exchange_code_for_session({
            "auth_code": auth_code,
        })
        st.session_state.user_session = session_data.session
        return True
    except Exception as e:
        st.error(f"Falha na autenticação final: {e}")
        return False

def sign_up(email, password):
    """Realiza o cadastro de um novo usuário no Supabase."""
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        mensagem = "✅ Cadastro realizado! Verifique seu e-mail para confirmar a conta."
        return True, mensagem
    except AuthApiError as e:
        if "User already registered" in e.message:
            mensagem = "⚠️ Este e-mail já está cadastrado. Tente fazer o login."
        else:
            mensagem = f"❌ Erro no cadastro: {e.message}"
        return False, mensagem
    except Exception as e:
        mensagem = f"❌ Ocorreu um erro inesperado: {e}"
        return False, mensagem

def sign_in(email, password):
    """Realiza o login de um usuário no Supabase."""
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user_session = res.session
        return True, None
    except AuthApiError as e:
        return False, f"❌ Erro de login: {e.message}"
    except Exception as e:
        return False, f"❌ Ocorreu um erro inesperado: {e}"

def sign_out():
    """Realiza o logout do usuário."""
    try:
        supabase.auth.sign_out()
        st.session_state.user_session = None
    except Exception as e:
        st.error(f"Erro ao fazer logout: {e}")