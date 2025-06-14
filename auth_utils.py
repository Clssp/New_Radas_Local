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

# Em auth_utils.py, dentro da função get_google_auth_url
def get_google_auth_url(redirect_url: str):
    """Gera a URL de autenticação do Google usando o fluxo PKCE (padrão e seguro)."""
    try:
        data = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_url,

            }
        })
        return data.url
    except Exception as e:
        st.error(f"Não foi possível gerar a URL de login: {e}")
        return Nonee

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