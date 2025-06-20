import streamlit as st
# Removemos a importação do create_client
# Importamos a nossa instância única e compartilhada
from supabase_client import supabase_client

def login_user(email, password):
    """Realiza o login e salva a SESSÃO no st.session_state."""
    try:
        # Usa o cliente compartilhado
        response = supabase_client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        st.session_state.user = response.user.dict()
        st.session_state.user_session = response.session
        return st.session_state.user, None
    except Exception as e:
        return None, str(e)

def signup_user(email, password):
    """Cadastra um novo usuário."""
    try:
        # Usa o cliente compartilhado
        response = supabase_client.auth.sign_up({
            "email": email,
            "password": password,
        })
        return response.user.dict(), None
    except Exception as e:
        return None, str(e)

def logout_user():
    """Realiza o logout e limpa TODAS as chaves do session_state."""
    try:
        # Usa o cliente compartilhado
        supabase_client.auth.sign_out()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Logout realizado com sucesso.")
    except Exception as e:
        st.error(f"Erro ao fazer logout: {e}")