# main.py - v9.0 (Arquitetura Sólida com Autenticação Simplificada)
# Foco em login/cadastro por e-mail e senha. Robusto, seguro e limpo.
# ==============================================================================

import streamlit as st
import requests
import base64
import pandas as pd
import unicodedata
import re
import json
import time
from openai import OpenAI
from datetime import datetime
from io import BytesIO
from xhtml2pdf import pisa
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from gotrue.errors import AuthApiError
from postgrest.exceptions import APIError

# --- CONFIGURAÇÕES E INICIALIZAÇÃO ---
st.set_page_config(page_title="Radar Local", page_icon="📡", layout="wide")

# Importa as funções de autenticação do nosso novo e limpo auth_utils
from auth_utils import sign_up, sign_in, sign_out, supabase

# Carrega as chaves de API de forma segura a partir do st.secrets
try:
    API_KEY_GOOGLE = st.secrets["google"]["api_key"]
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
except (KeyError, FileNotFoundError):
    st.error("As chaves de API (Google, OpenAI) não foram encontradas. Verifique seu arquivo `.streamlit/secrets.toml`.")
    st.stop()


# --- FUNÇÕES DE UTILIDADE E GERAÇÃO DE CONTEÚDO ---

def url_para_base64(url: str) -> str:
    """Converte uma imagem de uma URL para uma string base64."""
    if not url: return ""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode("utf-8")
        return ""
    except requests.RequestException:
        return ""

def carregar_logo_base64(caminho_logo: str) -> str:
    """Carrega uma imagem local (logo) e a converte para base64."""
    try:
        with open(caminho_logo, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        return ""

# (Aqui entram suas funções de geração de relatório, IA, etc. Cole-as aqui se não estiverem em outros arquivos)
# Exemplo: gerar_grafico_radar_base64, gerar_html_relatorio, analisar_sentimentos_por_topico_ia, etc.
# Se elas já estão em main.py, elas devem ser coladas nesta seção.


# --- FUNÇÕES DE BANCO DE DADOS (SEGURAS, USANDO SUPABASE API) ---

def salvar_historico(nome, prof, loc, titulo, slogan, nivel, alerta):
    """Salva o histórico da consulta no Supabase de forma segura."""
    try:
        if 'user_session' in st.session_state and st.session_state.user_session:
            user_id = st.session_state.user_session.user.id
            dados_para_inserir = {
                "nome_usuario": nome, "tipo_negocio_pesquisado": prof,
                "localizacao_pesquisada": loc, "nivel_concorrencia_ia": nivel,
                "titulo_gerado_ia": titulo, "slogan_gerado_ia": slogan,
                "alerta_oportunidade_ia": alerta, "data_consulta": datetime.now().isoformat(),
                "user_id": user_id
            }
            supabase.table("consultas").insert(dados_para_inserir).execute()
        else:
            st.warning("Usuário não logado. Histórico não foi salvo.")
    except APIError as e:
        st.warning(f"Não foi possível salvar o histórico: {e.message}")
    except Exception as e:
        st.warning(f"Ocorreu um erro inesperado ao salvar histórico: {e}")

def carregar_historico_db():
    """Carrega o histórico de consultas do usuário logado de forma segura."""
    try:
        if 'user_session' in st.session_state and st.session_state.user_session:
            user_id = st.session_state.user_session.user.id
            response = supabase.table("consultas").select("*").eq("user_id", user_id).order("data_consulta", desc=True).execute()
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except APIError as e:
        st.error(f"Erro ao carregar histórico: {e.message}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao carregar histórico: {e}")
        return pd.DataFrame()


# --- TELA DE AUTENTICAÇÃO (AUTH PAGE) ---
def auth_page():
    """Renderiza a página de login e cadastro."""
    st.title("Bem-vindo ao Radar Local 📡")
    st.write("Faça login para acessar sua plataforma de inteligência de mercado ou crie uma nova conta.")
    
    col1, col2 = st.columns(2)

    with col1:
        with st.form("login_form"):
            st.markdown("#### Já tem uma conta?")
            email = st.text_input("Email")
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                success, message = sign_in(email, pwd)
                if success:
                    st.rerun()
                else:
                    st.error(message)

    with col2:
        with st.form("signup_form"):
            st.markdown("#### Crie sua conta")
            email_signup = st.text_input("Seu melhor e-mail", key="signup_email")
            pwd_signup = st.text_input("Crie uma senha segura", type="password", key="signup_pwd")
            if st.form_submit_button("Registrar", use_container_width=True):
                success, message = sign_up(email_signup, pwd_signup)
                if success:
                    st.success(message)
                    st.info("Enviamos um link de confirmação para o seu e-mail.")
                else:
                    st.error(message)

# --- APLICAÇÃO PRINCIPAL (MAIN APP) ---
def main_app():
    """A aplicação principal que o usuário vê após o login."""
    st.sidebar.write(f"Logado como: **{st.session_state.user_session.user.email}**")
    st.sidebar.button("Sair (Logout)", on_click=sign_out, use_container_width=True)
    st.sidebar.markdown("---")

    base64_logo = carregar_logo_base64("logo_radar_local.png")
    st.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{base64_logo}' width='120'><h1>Radar Local</h1><p>Inteligência de Mercado para Autônomos e Pequenos Negócios</p></div>", unsafe_allow_html=True)
    st.markdown("---")

    # AQUI ENTRA A LÓGICA DO SEU FORMULÁRIO E GERAÇÃO DE RELATÓRIO
    placeholder_formulario = st.empty()
    with placeholder_formulario.container():
        with st.form("formulario_principal"):
            st.subheader("🚀 Comece sua Análise Premium")
            c1, c2, c3 = st.columns(3)
            with c1: profissao = st.text_input("Profissão/Negócio", placeholder="Barbearia")
            with c2: localizacao = st.text_input("Cidade/Bairro", placeholder="Mooca, SP")
            with c3: nome_usuario = st.text_input("Seu Nome (p/ relatório)", value=st.session_state.user_session.user.email.split('@')[0])
            
            enviar = st.form_submit_button("🔍 Gerar Análise Completa")

    if enviar:
        if not all([profissao, localizacao, nome_usuario]):
            st.warning("⚠️ Preencha todos os campos.")
            st.stop()
        
        placeholder_formulario.empty()
        # Aqui começa o processo de geração do relatório (sua lógica original de progresso)
        progress_bar = st.progress(0, text="Iniciando análise...")
        # ... e todo o resto do seu código de geração de relatório ...
        
        # Exemplo de como salvar no final
        # salvar_historico(nome_usuario, profissao, localizacao, ...)

        st.success("✅ Análise concluída!")
        # ... exibir o relatório em HTML, botão de download PDF, etc.
    
    # ... Painel de Admin ...
    # if check_password():
    #     st.subheader("📊 Painel de Administrador")
    #     df_historico = carregar_historico_db()
    #     st.dataframe(df_historico)


# --- ROTEAMENTO E LÓGICA DE EXECUÇÃO ---
def run():
    """Função principal que gerencia o estado da sessão e o roteamento."""
    
    if 'user_session' not in st.session_state:
        st.session_state.user_session = None

    try:
        current_session = supabase.auth.get_session()
        st.session_state.user_session = current_session
    except Exception:
        st.session_state.user_session = None

    if st.session_state.user_session:
        main_app()
    else:
        auth_page()

if __name__ == "__main__":
    run()