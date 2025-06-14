# main.py - v8.1 (Seguro com Supabase API e Auth Refatorado)
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

# Importa as funções de autenticação do módulo de utils
# Isso mantém o código de autenticação separado e limpo
from auth_utils import sign_up, sign_in, sign_out, supabase, get_google_auth_url

# Carrega as chaves de API de forma segura a partir do st.secrets
try:
    API_KEY_GOOGLE = st.secrets["google"]["api_key"]
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
except (KeyError, FileNotFoundError):
    st.error("As chaves de API (Google, OpenAI) não foram encontradas. Verifique seu arquivo `.streamlit/secrets.toml`.")
    st.stop()


# --- DEFINIÇÃO DE TODAS AS FUNÇÕES AUXILIARES ---

def url_para_base64(url):
    """Converte uma imagem de uma URL para uma string base64."""
    if not url:
        return ""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode("utf-8")
        return ""
    except requests.RequestException:
        return ""

# ---- FUNÇÕES DE BANCO DE DADOS (AGORA SEGURAS USANDO SUPABASE API) ----

def salvar_historico(nome, prof, loc, titulo, slogan, nivel, alerta):
    """Salva o histórico da consulta no Supabase de forma segura."""
    try:
        if 'user_session' in st.session_state and st.session_state.user_session:
            user_id = st.session_state.user_session.user.id
            
            dados_para_inserir = {
                "nome_usuario": nome,
                "tipo_negocio_pesquisado": prof,
                "localizacao_pesquisada": loc,
                "nivel_concorrencia_ia": nivel,
                "titulo_gerado_ia": titulo,
                "slogan_gerado_ia": slogan,
                "alerta_oportunidade_ia": alerta,
                "data_consulta": datetime.now().isoformat(),
                "user_id": user_id
            }
            supabase.table("consultas").insert(dados_para_inserir).execute()
        else:
            st.warning("Usuário não logado. Histórico não foi salvo.")
    except APIError as e:
        st.warning(f"Não foi possível salvar o histórico da consulta: {e.message}")
    except Exception as e:
        st.warning(f"Ocorreu um erro inesperado ao salvar o histórico: {e}")

def carregar_historico_db():
    """Carrega o histórico de consultas do usuário logado de forma segura."""
    try:
        if 'user_session' in st.session_state and st.session_state.user_session:
            user_id = st.session_state.user_session.user.id
            # Busca dados SOMENTE do usuário logado e ordena pelos mais recentes
            # O Row Level Security no Supabase garante a privacidade.
            response = supabase.table("consultas").select("*").eq("user_id", user_id).order("data_consulta", desc=True).execute()
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except APIError as e:
        st.error(f"Erro ao carregar histórico: {e.message}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao carregar o histórico: {e}")
        return pd.DataFrame()

# ---- FUNÇÕES DE UTILIDADE E API ----

def carregar_logo_base64(caminho_logo):
    """Carrega uma imagem local (logo) e a converte para base64."""
    try:
        with open(caminho_logo, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        return ""

def check_password():
    """Verifica a senha do admin no sidebar."""
    # TODO: Refatorar para usar roles de usuário no futuro.
    if st.session_state.get("admin_autenticado", False):
        return True
    with st.sidebar.form("admin_form"):
        st.markdown("### Acesso Restrito Admin")
        pwd = st.text_input("Senha", type="password", key="admin_pwd")
        if st.form_submit_button("Acessar"):
            if pwd == st.secrets["admin"]["password"]:
                st.session_state.admin_autenticado = True
                st.rerun()
            else:
                st.sidebar.error("Senha incorreta.")
    return False

# --- FUNÇÕES DE API EXTERNAS (GOOGLE & OPENAI) COM CACHE ---

@st.cache_data(ttl=3600, show_spinner="Buscando concorrentes...")
def buscar_concorrentes(profissao, localizacao):
    """Busca concorrentes usando a API do Google Places."""
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={profissao} em {localizacao}&key={API_KEY_GOOGLE}&language=pt-BR"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("results", [])
    st.error(f"Erro na API do Google: {response.status_code}. Verifique sua chave.")
    return []

@st.cache_data(ttl=3600, show_spinner="Obtendo detalhes do local...")
def buscar_detalhes_lugar(place_id):
    """Busca detalhes de um local específico."""
    fields = "name,formatted_address,review,formatted_phone_number,website,opening_hours,rating,user_ratings_total,photos,price_level"
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields={fields}&key={API_KEY_GOOGLE}&language=pt-BR"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("result", {})
    return {}

@st.cache_data(ttl=3600)
def analisar_sentimentos_por_topico_ia(comentarios):
    """Analisa sentimentos usando a API da OpenAI."""
    prompt = f"""Analise os comentários de clientes: "{comentarios}". Atribua uma nota de 0 a 10 para: Atendimento, Preço, Qualidade, Ambiente, Tempo de Espera. Responda em JSON."""
    try:
        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        dados = json.loads(resposta.choices[0].message.content)
        base = {"Atendimento": 5, "Preço": 5, "Qualidade": 5, "Ambiente": 5, "Tempo de Espera": 5}
        base.update(dados)
        return base
    except Exception as e:
        st.warning(f"IA de sentimentos falhou: {e}.")
        return {}

# ... (outras funções de IA e geração de relatório permanecem as mesmas)
# ... gerar_grafico_radar_base64, gerar_html_relatorio, gerar_pdf, etc...

def gerar_grafico_radar_base64(sentimentos):
    if not sentimentos: return ""
    labels, stats = list(sentimentos.keys()), list(sentimentos.values())
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    stats += stats[:1]; angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='#007bff', alpha=0.25)
    ax.plot(angles, stats, color='#007bff', linewidth=2)
    ax.set_ylim(0, 10); ax.set_yticklabels([])
    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=12)
    ax.set_title("Diagnóstico de Sentimentos por Tópico", fontsize=16, y=1.1)
    buf = BytesIO(); plt.savefig(buf, format="png", bbox_inches='tight')
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def gerar_html_relatorio(**kwargs):
    # Esta função é longa, então a omiti para brevidade, mas ela permanece igual à sua versão original.
    # Certifique-se de copiar a sua função gerar_html_relatorio completa para cá.
    # O conteúdo da sua função original está correto.
    css = """<style>... a sua string CSS completa ...</style>"""
    matriz_html = "..."
    # ... todo o resto da sua função
    body = f"""<html>... o seu corpo de HTML completo ...</html>"""
    return body

def gerar_pdf(html):
    """Gera um PDF a partir de uma string HTML."""
    pdf_bytes = BytesIO()
    pisa.CreatePDF(html.encode('utf-8'), dest=pdf_bytes)
    return pdf_bytes.getvalue()

# --- INTERFACE PRINCIPAL DA APLICAÇÃO (UI) ---

def main_app():
    """Renderiza a aplicação principal para usuários logados."""
    st.sidebar.write(f"Logado como: **{st.session_state.user_session.user.email}**")
    st.sidebar.button("Logout", on_click=sign_out, use_container_width=True)
    st.sidebar.markdown("---")

    base64_logo = carregar_logo_base64("logo_radar_local.png")
    st.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{base64_logo}' width='120'><h1>Radar Local</h1><p>Inteligência de Mercado para Autônomos e Pequenos Negócios</p></div>", unsafe_allow_html=True)
    st.markdown("---")

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
        # Aqui começa o processo de geração do relatório (sua lógica original está boa)
        # ...
        st.success("✅ Análise concluída!")
        # ... exibir relatório, botão de download, etc.

    st.markdown("---")
    if check_password():
        st.sidebar.success("✅ Acesso admin concedido!")
        st.subheader("📊 Painel de Administrador")
        df_historico = carregar_historico_db()
        if not df_historico.empty:
            st.markdown("#### Análise Rápida de Uso")
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Negócios + Pesquisados:**")
                st.bar_chart(df_historico['tipo_negocio_pesquisado'].value_counts())
            with c2:
                st.write("**Localizações + Pesquisadas:**")
                st.bar_chart(df_historico['localizacao_pesquisada'].value_counts())
            with st.expander("Ver Histórico Completo"):
                st.dataframe(df_historico)
        else:
            st.info("Histórico de consultas vazio.")

# --- TELA DE LOGIN/CADASTRO ---

def auth_page():
    """Renderiza a página de login e cadastro."""
    st.title("Bem-vindo ao Radar Local 📡")
    st.write("Faça login ou crie uma conta para acessar sua plataforma de inteligência de mercado.")
    
    # URL do seu app no Streamlit Cloud (deve ser a mesma configurada no Supabase)
    app_url = "https://radarlocalapp.streamlit.app" # Verifique se este nome está correto
    
    google_auth_url = get_google_auth_url(app_url)
    if google_auth_url:
        st.link_button("Entrar com Google", google_auth_url, use_container_width=True, type="primary")
    
    st.markdown("<p style='text-align: center;'>ou</p>", unsafe_allow_html=True)
    
    login_tab, signup_tab = st.tabs(["Login", "Cadastro"])
    with login_tab:
        with st.form("login_form", border=False):
            email = st.text_input("Email")
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                success, message = sign_in(email, pwd)
                if success:
                    st.rerun()
                else:
                    st.error(message)

    with signup_tab:
        with st.form("signup_form", border=False):
            email_signup = st.text_input("Email", key="signup_email")
            pwd_signup = st.text_input("Crie uma senha", type="password", key="signup_pwd")
            if st.form_submit_button("Registrar"):
                success, message = sign_up(email_signup, pwd_signup)
                if success:
                    st.success(message)
                else:
                    st.error(message)

# --- ROTEAMENTO FINAL E ROBUSTO ---

# Inicializa o user_session no st.session_state se não existir
if 'user_session' not in st.session_state:
    st.session_state.user_session = None

try:
    # Tenta obter a sessão atual (caso a página seja recarregada)
    st.session_state.user_session = supabase.auth.get_session()
except Exception:
    # Ignora erros de rede/conexão na inicialização
    pass

query_params = st.query_params

# Lida com o retorno do login OAuth
if "code" in query_params and st.session_state.user_session is None:
    auth_code = query_params.get("code")
    try:
        st.session_state.user_session = supabase.auth.exchange_code_for_session(auth_code)
        st.query_params.clear() # Limpa os parâmetros da URL
        st.rerun()
    except AuthApiError as e:
        st.error(f"Erro na autenticação: {e.message}")
        st.stop()

# Roteamento final: mostra a página principal ou a de autenticação
if st.session_state.user_session:
    main_app()
else:
    auth_page()