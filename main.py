import streamlit as st
import pandas as pd
import json
from datetime import datetime

# Importações dos módulos do projeto
import auth_utils
import db_utils
import api_calls
import supabase_client # Importamos para garantir que a conexão seja inicializada

# --- Configuração da Página ---
st.set_page_config(page_title="Radar Pro 📡", page_icon="📡", layout="wide", initial_sidebar_state="collapsed")

# --- Funções das Páginas ---

def login_page():
    # ... (código da função login_page sem alterações)
    st.image("logo.png", width=200) 
    st.title("Radar Pro: Inteligência de Mercado")
    st.subheader("Faça login para acessar seu dashboard")
    login_tab, signup_tab = st.tabs(["Login", "Cadastro"])
    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Senha", type="password", key="login_password")
            if st.form_submit_button("Entrar"):
                user, error = auth_utils.login_user(email, password)
                if user:
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error(f"Erro no login: {error}")
    with signup_tab:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Senha", type="password", key="signup_password")
            if st.form_submit_button("Cadastrar"):
                user, error = auth_utils.signup_user(email, password)
                if user:
                    st.success("Cadastro realizado! Faça o login para continuar.")
                else:
                    st.error(f"Erro no cadastro: {error}")

def dashboard_page():
    # ... (cabeçalho da página sem alterações)
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.title("Dashboard de Mercados")
        st.caption(f"Logado como: {st.session_state.user['email']}")
    with col2:
        if st.button("Sair"):
            auth_utils.logout_user()
            st.rerun()
    st.divider()

    with st.expander("➕ Adicionar e Analisar Novo Mercado"):
        with st.form("new_market_form"):
            termo = st.text_input("Termo de Busca (Ex: Padaria, Barbearia)", placeholder="Padaria")
            localizacao = st.text_input("Localização (Ex: Vila Prudente, SP)", placeholder="Vila Prudente, São Paulo")
            
            # --- LÓGICA DE CACHE IMPLEMENTADA AQUI ---
            if st.form_submit_button("Analisar Mercado"):
                if termo and localizacao:
                    # Passo 1: Verifica se o mercado já existe no DB para este usuário
                    market_id = db_utils.find_market_by_term_and_location(st.session_state.user['id'], termo, localizacao)
                    
                    # Passo 2: Se o mercado existe, verifica se há um snapshot recente (CACHE)
                    if market_id and db_utils.check_for_recent_snapshot(market_id, max_age_days=7):
                        st.info(f"CACHE HIT: Já existe uma análise recente para '{termo}' em '{localizacao}'. Os dados foram carregados sem custo.")
                        st.rerun()
                    else:
                        # CACHE MISS: Se não há análise recente, executa a análise completa
                        with st.spinner(f"Analisando '{termo}' em '{localizacao}'... Isso pode levar alguns minutos."):
                            try:
                                # Se o mercado não existia, cria um novo
                                if not market_id:
                                    market_id = db_utils.add_market(st.session_state.user['id'], termo, localizacao)
                                
                                api_calls.run_full_analysis(termo, localizacao, st.session_state.user['id'], market_id)
                                st.success("Análise concluída e salva com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Ocorreu um erro durante a análise: {e}")
                else:
                    st.warning("Por favor, preencha o termo e a localização.")

    st.divider()
    
    # ... (Restante do código do dashboard e da details_page sem alterações) ...
    st.subheader("Meus Mercados Monitorados")
    user_markets = db_utils.get_user_markets(st.session_state.user['id'])
    if not user_markets:
        st.info("Você ainda não adicionou nenhum mercado. Use o formulário acima para começar.")
    else:
        for market in user_markets:
            col1, col2, col3, col4 = st.columns([4, 2, 2, 1])
            with col1:
                st.markdown(f"**{market.get('termo', 'N/A')}** em **{market.get('localizacao', 'N/A')}**")
                last_snapshot_date = db_utils.get_latest_snapshot_date(market['id'])
                if last_snapshot_date:
                    st.caption(f"Última análise: {last_snapshot_date.strftime('%d/%m/%Y %H:%M')}")
                else:
                    st.caption("Nenhuma análise encontrada.")
            with col2:
                if st.button("Ver Detalhes", key=f"details_{market['id']}"):
                    st.session_state.selected_market = market
                    st.rerun()
            with col3:
                # O botão Reanalisar agora ignora o cache de propósito
                if st.button("Reanalisar", key=f"reanalyze_{market['id']}"):
                    with st.spinner(f"Reanalisando '{market['termo']}'..."):
                        api_calls.run_full_analysis(market['termo'], market['localizacao'], st.session_state.user['id'], market['id'])
                        st.success(f"Mercado '{market['termo']}' reanalisado com sucesso!")
                        st.rerun()
            with col4:
                if st.button("Excluir", key=f"delete_{market['id']}"):
                    db_utils.delete_market(market['id'])
                    st.warning(f"Mercado '{market['termo']}' excluído.")
                    st.rerun()

def details_page():
    # ... (A função details_page continua exatamente a mesma)
    market = st.session_state.selected_market
    if st.button("⬅️ Voltar ao Dashboard"):
        st.session_state.selected_market = None
        st.rerun()
    st.title(f"Análise Detalhada: {market.get('termo', 'N/A')}")
    st.subheader(f"Localização: {market.get('localizacao', 'N/A')}")
    st.divider()
    snapshot = db_utils.get_latest_snapshot(market['id'])
    if not snapshot:
        st.error("Nenhum dado de análise (snapshot) foi encontrado para este mercado. Tente reanalisar.")
        return
    try:
        data = json.loads(snapshot['dados_json'])
    except (json.JSONDecodeError, TypeError, KeyError):
        st.error("Erro ao ler os dados da análise. O formato do snapshot pode estar corrompido.")
        return
    tabs = ["Visão Geral", "Plano de Ação", "📍 Mapa da Concorrência", "Tendências de Mercado", "Demografia", "Dossiês dos Concorrentes", "Evolução (KPIs)"]
    tab_geral, tab_plano, tab_mapa, tab_trends, tab_demo, tab_dossie, tab_evolucao = st.tabs(tabs)
    with tab_geral:
        st.header("Visão Geral do Mercado")
        st.markdown(data.get('sumario_executivo', "Sumário executivo não disponível."))
        st.subheader("Análise de Sentimentos (Reviews)")
        sentimentos = data.get('analise_sentimentos', {})
        if sentimentos:
            df_sentimentos = pd.DataFrame(list(sentimentos.items()), columns=['Sentimento', 'Contagem'])
            st.bar_chart(df_sentimentos.set_index('Sentimento'))
        else:
            st.info("Dados de sentimento não disponíveis.")
    # ... etc ...

def main():
    if 'user' not in st.session_state: st.session_state.user = None
    if 'selected_market' not in st.session_state: st.session_state.selected_market = None
    if not st.session_state.user:
        login_page()
    elif st.session_state.selected_market:
        details_page()
    else:
        dashboard_page()

if __name__ == "__main__":
    main()