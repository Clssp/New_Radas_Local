# auth_utils.py (v9.1 - Comunicação Humanizada)

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

# --- FUNÇÕES DE AUTENTICAÇÃO COM FEEDBACK MELHORADO ---

def sign_up(email, password):
    """Realiza o cadastro de um novo usuário com mensagens de feedback claras."""
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        mensagem = "✅ Cadastro realizado! Verifique seu e-mail para confirmar a conta."
        return True, mensagem
    except AuthApiError as e:
        if "User already registered" in str(e):
            mensagem = "⚠️ Este e-mail já está cadastrado. Por favor, tente fazer o login."
        else:
            mensagem = f"❌ Erro no cadastro. Tente novamente."
        return False, mensagem
    except Exception:
        mensagem = f"❌ Não foi possível conectar aos nossos servidores. Tente novamente mais tarde."
        return False, mensagem

def sign_in(email, password):
    """Realiza o login de um usuário com mensagens de erro humanizadas."""
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user_session = res.session
        return True, None
    except AuthApiError as e:
        if "Invalid login credentials" in str(e):
            return False, "❌ E-mail ou senha incorretos. Por favor, verifique seus dados."
        else:
            return False, "❌ Ocorreu um problema ao tentar fazer login. Tente novamente."
    except Exception:
        return False, "❌ Não foi possível conectar ao servidor. Verifique sua conexão com a internet."

def sign_out():
    """Realiza o logout do usuário e limpa a sessão."""
    try:
        supabase.auth.sign_out()
        st.session_state.user_session = None
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao fazer logout: {e}")