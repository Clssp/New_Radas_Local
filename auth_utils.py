# Conteúdo para o arquivo: auth_utils.py

import streamlit as st
from supabase_client import supabase_client
import db_utils

def login_user(email, password):
    """
    Realiza o login do usuário, verifica se a conta está ativa, se é um
    administrador, e carrega os dados da sessão.
    """
    try:
        # Autentica o usuário com email e senha
        response = supabase_client.auth.sign_in_with_password({"email": email, "password": password})
        user_id = response.user.id

        # Etapa crucial: Busca o perfil do usuário para verificar status e carregar dados
        profile = db_utils.get_user_profile(user_id)

        # Verifica se o perfil existe e se a conta está ativa
        if not profile or not profile.get('is_active', False):
            supabase_client.auth.sign_out()  # Garante o logout se a conta estiver inativa
            return None, "Usuário desativado ou não encontrado. Contate o suporte."

        # Se tudo estiver OK, armazena os dados na sessão do Streamlit
        st.session_state.user = response.user.dict()
        st.session_state.user_session = response.session
        st.session_state.is_admin = db_utils.is_user_admin(user_id)
        # st.session_state.credits = profile.get('analysis_credits', 0) # Lógica de créditos foi removida

        return st.session_state.user, None

    except Exception as e:
        # Trata erros comuns de login
        if "invalid login credentials" in str(e).lower():
            return None, "Email ou senha inválidos."
        
        # Para outros erros, retorna a mensagem genérica
        return None, f"Ocorreu um erro: {e}"

def signup_user(email, password):
    """Realiza o cadastro de um novo usuário."""
    try:
        response = supabase_client.auth.sign_up({"email": email, "password": password})
        # O perfil do usuário (com créditos) é criado automaticamente por um Trigger no Supabase.
        # É importante verificar se esse Trigger está ativo e funcionando.
        if response.user:
            return response.user.dict(), None
        else:
            return None, "Não foi possível criar o usuário. Tente novamente."
            
    except Exception as e:
        if 'User already registered' in str(e):
            return None, "Este email já está cadastrado."
        return None, f"Erro no cadastro: {e}"

def logout_user():
    """Realiza o logout e limpa completamente o estado da sessão."""
    if 'user' in st.session_state and st.session_state.user:
        supabase_client.auth.sign_out()

    # Limpa todas as chaves da sessão para garantir um estado limpo
    keys_to_clear = list(st.session_state.keys())
    for key in keys_to_clear:
        del st.session_state[key]