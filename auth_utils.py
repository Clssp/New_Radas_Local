# auth_utils.py

import streamlit as st
from supabase import create_client, Client
from gotrue.errors import AuthApiError

# Inicializa a conexão com o Supabase usando os segredos
@st.cache_resource
def init_supabase_client():
    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]
    return create_client(supabase_url, supabase_key)

supabase: Client = init_supabase_client()

# --- FUNÇÃO DE CADASTRO (SIGN UP) ---
def sign_up(email, password):
    """Realiza o cadastro de um novo usuário no Supabase."""
    try:
        # Envia as credenciais para o Supabase criar o usuário
        res = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
        
        # Se chegou aqui, a chamada foi bem-sucedida
        mensagem = "✅ Cadastro realizado! Verifique seu e-mail para confirmar a conta antes de fazer o login."
        return True, mensagem

    except AuthApiError as e:
        # Captura erros específicos da API de autenticação
        if "User already registered" in e.message:
            mensagem = "⚠️ Este e-mail já está cadastrado. Tente fazer o login."
        else:
            mensagem = f"❌ Erro no cadastro: {e.message}"
        return False, mensagem
    
    except Exception as e:
        # Captura qualquer outro erro inesperado (ex: sem internet)
        mensagem = f"❌ Ocorreu um erro inesperado: {e}"
        return False, mensagem

# --- FUNÇÃO DE LOGIN (SIGN IN) ---
def sign_in(email, password):
    """Realiza o login de um usuário no Supabase."""
    try:
        # Tenta autenticar o usuário
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        # Salva a sessão do usuário no estado do Streamlit
        st.session_state.user_session = res.session
        return True, None

    except AuthApiError as e:
        mensagem = f"❌ Erro de login: {e.message}"
        return False, mensagem
    except Exception as e:
        mensagem = f"❌ Ocorreu um erro inesperado: {e}"
        return False, mensagem

# --- FUNÇÃO DE LOGOUT (SIGN OUT) ---
def sign_out():
    """Realiza o logout do usuário."""
    try:
        supabase.auth.sign_out()
        st.session_state.user_session = None # Limpa a sessão local
    except Exception as e:
        st.error(f"Erro ao fazer logout: {e}")

        # auth_utils.py

def get_google_auth_url(redirect_url: str):
    """Gera a URL de autenticação do Google."""
    try:
        data = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_url
            }
        })
        return data.url
    except Exception as e:
        st.error(f"Não foi possível gerar a URL de login: {e}")
        return None