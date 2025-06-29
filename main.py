# Conteúdo completo para o arquivo: main.py

import streamlit as st
import pandas as pd
import json
from datetime import datetime
import time
import folium
from streamlit_folium import st_folium

# Módulos do projeto
import auth_utils
import db_utils
import api_calls
import report_generator
import admin_page

# --- Carregamento do CSS ---
@st.cache_data
def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"Arquivo de estilo '{file_name}' não encontrado.")

# --- Funções de Processamento ---
def run_analysis_with_progress(termo: str, localizacao: str, user_id: str, market_id: int, maps_api_key: str, tipo_negocio: str):
    progress_bar = st.progress(0, text="Iniciando análise...")
    try:
        api_calls.run_full_analysis(termo, localizacao, user_id, market_id, progress_bar, maps_api_key, tipo_negocio)
        st.toast("Análise concluída com sucesso!", icon="✅")
        time.sleep(2)
        st.rerun()
    except Exception as e:
        st.error(f"Ocorreu um erro crítico durante a análise: {e}")
    finally:
        progress_bar.empty()

# --- Views (Páginas) da Aplicação ---
def login_page():
    with st.container():
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            st.image("logo.png", width=200)
            st.title("Radar Pro: Inteligência de Mercado")
            st.subheader("Faça login para acessar seu dashboard")
            with st.container(border=True):
                login_tab, signup_tab = st.tabs(["Login", "Cadastro"])
                with login_tab:
                    with st.form("login_form"):
                        st.subheader("Acesse sua conta")
                        email = st.text_input("Email", key="login_email")
                        password = st.text_input("Senha", type="password", key="login_password")
                        if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                            with st.spinner('Verificando...'):
                                user, error = auth_utils.login_user(email, password)
                                if user: st.session_state.page = 'dashboard'; st.rerun()
                                else: st.error(f"Erro no login: {error}")
                with signup_tab:
                    with st.form("signup_form"):
                        st.subheader("Crie sua conta")
                        email = st.text_input("Email", key="signup_email")
                        password = st.text_input("Senha", type="password", key="signup_password")
                        if st.form_submit_button("Cadastrar", use_container_width=True):
                            with st.spinner('Criando conta...'):
                                user, error = auth_utils.signup_user(email, password)
                                if user: st.success("Cadastro realizado! Você já pode fazer o login."); time.sleep(3); st.rerun()
                                else: st.error(f"Erro no cadastro: {error}")

def dashboard_page():
    st.title("Dashboard de Mercados")
    st.divider()
    maps_api_key = st.secrets.google["maps_api_key"]
    with st.expander("➕ Adicionar e Analisar Novo Mercado", expanded=True):
        with st.form("new_market_form"):
            tipos_negocio = ["Genérico / Outros", "Restaurante, Bar ou Lanchonete", "Loja de Varejo (Roupas, Eletrônicos, etc.)", "Serviços Locais (Eletricista, Encanador, etc.)", "Salão de Beleza ou Barbearia", "Academia ou Estúdio Fitness"]
            tipo_negocio_selecionado = st.selectbox("Selecione o Tipo de Negócio:", tipos_negocio)
            termo = st.text_input("Termo de Busca Específico", placeholder="Ex: Barbearia Clássica")
            localizacao = st.text_input("Localização", placeholder="Ex: Copacabana, Rio de Janeiro")
            if st.form_submit_button("Analisar Mercado", use_container_width=True, type="primary"):
                if termo and localizacao:
                    user_id = st.session_state.user['id']
                    if db_utils.check_and_update_daily_limit(user_id):
                        with st.spinner("Iniciando análise completa..."):
                            market_id = db_utils.add_market(user_id, termo, localizacao, tipo_negocio_selecionado)
                            run_analysis_with_progress(termo, localizacao, user_id, market_id, maps_api_key, tipo_negocio_selecionado)
                    else:
                        st.error("Você já atingiu seu limite diário de análises."); time.sleep(3)
                else:
                    st.warning("Preencha o termo e a localização.")
    st.divider()
    st.subheader("Meus Mercados Monitorados")
    user_markets = db_utils.get_user_markets(st.session_state.user['id'])
    if not user_markets:
        st.info("Você ainda não adicionou nenhum mercado.")
    else:
        analysis_info = db_utils.get_user_analysis_info(st.session_state.user['id'])
        limit_reached = analysis_info['limit_reached']
        for market in user_markets:
            with st.container(border=True):
                cols = st.columns([4, 2, 2, 2])
                with cols[0]:
                    st.markdown(f"#### {market.get('termo', 'N/A')}")
                    st.caption(f"Em: {market.get('localizacao', 'N/A')} | Tipo: {market.get('tipo_negocio', 'N/A')}")
                with cols[1]:
                    last_date = db_utils.get_latest_snapshot_date(market['id'])
                    st.caption("Última análise:" if last_date else "Status:")
                    st.markdown(f"**{last_date.strftime('%d/%m/%Y')}**" if last_date else "**Ainda não analisado**")
                if cols[2].button("Ver Detalhes", key=f"details_{market['id']}", use_container_width=True):
                    st.session_state.selected_market = market; st.session_state.page = 'details'; st.rerun()
                disable_button = limit_reached
                tooltip = "Você atingiu seu limite diário de análises." if limit_reached else f"Reanalisar mercado (consome 1 de suas {int(db_utils.get_platform_setting('daily_analysis_limit'))} análises diárias)"
                if cols[3].button("Reanalisar", key=f"reanalyze_{market['id']}", use_container_width=True, disabled=disable_button, help=tooltip, type="primary"):
                    if db_utils.check_and_update_daily_limit(st.session_state.user['id']):
                        run_analysis_with_progress(market['termo'], market['localizacao'], st.session_state.user['id'], market['id'], maps_api_key, market.get('tipo_negocio'))
                    else: st.error("Limite de análises diárias atingido."); time.sleep(2); st.rerun()

def details_page():
    if 'selected_market' not in st.session_state or st.session_state.selected_market is None:
        st.warning("Nenhum mercado selecionado. Redirecionando..."); st.session_state.page = 'dashboard'; time.sleep(1); st.rerun(); return
    market = st.session_state.selected_market
    latest_snapshot = db_utils.get_latest_snapshot(market['id'])
    if not latest_snapshot:
        st.error("Dados de análise não encontrados."); 
        if st.button("⬅️ Voltar ao Dashboard"): st.session_state.selected_market = None; st.session_state.page = 'dashboard'; st.rerun()
        return

    data = latest_snapshot.get('dados_json', {})
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"Análise Detalhada: {data.get('termo_busca', 'N/A')}")
        st.subheader(f"Localização: {data.get('localizacao_busca', 'N/A')}")
        st.caption(f"Tipo de Negócio Analisado: {data.get('tipo_negocio', 'Genérico / Outros')}")
    with col2:
        st.write(""); pdf_bytes = report_generator.gerar_relatorio_pdf(data, st.secrets.google["maps_api_key"])
        if pdf_bytes: st.download_button("📄 Baixar Relatório PDF", pdf_bytes, f"Relatorio_{data.get('termo_busca')}.pdf", "application/pdf", use_container_width=True)
        if st.button("⬅️ Voltar ao Dashboard"): st.session_state.selected_market = None; st.session_state.page = 'dashboard'; st.rerun()

    st.divider()
    tabs_list = ["📊 Visão Geral", "📝 Plano de Ação", "💡 Insights", "📈 Tendências", "👥 Demografia", " Dossiês", "🗺️ Mapa", "♟️ SWOT", "📉 Evolução"]
    (tab_geral, tab_plano, tab_extra, tab_tendencias, tab_demografia, 
     tab_dossies, tab_mapa, tab_swot, tab_evolucao) = st.tabs(tabs_list)

    # --- Abas de Detalhes ---
    with tab_geral:
        st.header("Sumário Executivo"); st.write(data.get('sumario_executivo', 'N/A'))
        st.header("Análise de Sentimentos"); sentimentos = data.get('analise_sentimentos', {})
        if sentimentos:
            cols = st.columns(len(sentimentos)); cores = {"Positivo": "normal", "Neutro": "off", "Negativo": "inverse"}
            for i, (s, p) in enumerate(sentimentos.items()):
                with cols[i]: st.metric(label=s, value=f"{p}%", delta_color=cores.get(s, "off"))
        else: st.info("Nenhuma análise de sentimentos foi gerada.")

    with tab_plano:
        st.header("Plano de Ação Sugerido"); plano = data.get('plano_de_acao', [])
        if plano:
            for i, passo in enumerate(plano): st.markdown(f"**{i+1}.** {passo}")
        else: st.info("Nenhum plano de ação foi gerado.")

    with tab_extra:
        st.header("Insights Específicos do Setor"); has_extra_data = False
        insights_map = {"analise_cardapio": "Análise de Cardápio", "estrategia_delivery": "Estratégia de Delivery", "analise_mix_produtos": "Análise de Mix de Produtos", "estrategia_visual_merchandising": "Estratégia de Visual Merchandising", "servicos_diferenciados": "Serviços Diferenciados", "estrategia_agendamento": "Estratégia de Agendamento"}
        for key, title in insights_map.items():
            if key in data: st.subheader(title); st.write(data.get(key)); has_extra_data = True
        if not has_extra_data: st.info("Nenhum insight específico para este setor foi gerado.")

    with tab_tendencias:
        st.header(f"📈 Tendências de Busca para '{data.get('termo_busca')}'"); st.info("Análise do interesse de busca nos últimos 12 meses no Brasil (Fonte: Google Trends).")
        with st.spinner("Buscando dados de tendências..."): trends_df = api_calls.get_interest_over_time(data.get('termo_busca'))
        if not trends_df.empty:
            st.line_chart(trends_df)
            media = trends_df.iloc[:, 0].mean(); ultimo_valor = trends_df.iloc[-1, 0]
            st.write(f"**Análise da Tendência:**")
            if ultimo_valor > media * 1.2: st.success(f"O interesse atual ({ultimo_valor}) está significativamente **acima** da média anual ({media:.1f}).")
            elif ultimo_valor < media * 0.8: st.warning(f"O interesse atual ({ultimo_valor}) está significativamente **abaixo** da média anual ({media:.1f}).")
            else: st.info(f"O interesse atual ({ultimo_valor}) está **estável** em relação à média anual ({media:.1f}).")
        else: st.error("Não foi possível obter os dados de tendências para este termo.")

    with tab_demografia:
        st.header("Análise Demográfica do Público-Alvo"); demografia = data.get('analise_demografica', {});
        if demografia:
            st.subheader("Resumo do Perfil"); st.write(demografia.get('resumo', 'N/A'))
            st.subheader("Faixa Etária Principal"); st.info(f"📊 {demografia.get('faixa_etaria', 'N/A')}")
            st.subheader("Principais Interesses"); [st.markdown(f"- {i}") for i in demografia.get('interesses_principais', [])]
        else: st.info("Nenhuma análise demográfica foi gerada.")

    with tab_dossies:
        st.header("Dossiês dos Principais Concorrentes"); dossies = data.get('dossies_concorrentes', [])
        if dossies:
            for concorrente in dossies:
                with st.container(border=True):
                    st.subheader(concorrente.get('nome', 'N/A')); st.markdown(f"**Posicionamento:** *{concorrente.get('posicionamento_mercado', 'N/A')}*")
                    col1, col2 = st.columns(2)
                    with col1: st.success(f"**Pontos Fortes:**\n{concorrente.get('pontos_fortes', 'N/A')}")
                    with col2: st.warning(f"**Pontos Fracos:**\n{concorrente.get('pontos_fracos', 'N/A')}")
        else: st.info("Nenhum dossiê de concorrente foi gerado.")

    with tab_mapa:
        st.header("Mapa Interativo da Concorrência"); competidores = data.get('competidores', [])
        competidores_com_coords = [c for c in competidores if c.get('latitude') and c.get('longitude')]
        if competidores_com_coords:
            avg_lat = sum(c['latitude'] for c in competidores_com_coords) / len(competidores_com_coords)
            avg_lon = sum(c['longitude'] for c in competidores_com_coords) / len(competidores_com_coords)
            mapa = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)
            for comp in competidores_com_coords: folium.Marker(location=[comp['latitude'], comp['longitude']], popup=f"<b>{comp['name']}</b>", tooltip=comp['name'], icon=folium.Icon(color='red', icon='info-sign')).add_to(mapa)
            st_folium(mapa, use_container_width=True)
        else: st.warning("Nenhum concorrente com dados de localização foi encontrado.")

    with tab_swot:
        st.header("Análise SWOT Estratégica"); st.info(f"Esta análise é gerada sob demanda e consome 1 de suas análises diárias.")
        st.session_state.setdefault('swot_analysis', None)
        if st.button("Gerar Análise SWOT com IA", type="primary"):
            if db_utils.check_and_update_daily_limit(st.session_state.user['id']):
                with st.spinner("A IA está elaborando a matriz estratégica..."):
                    try:
                        st.session_state.swot_analysis = api_calls.generate_swot_analysis(data)
                        st.toast("Análise SWOT gerada!", icon="🧠"); st.rerun()
                    except Exception as e: st.error(f"Erro ao gerar análise SWOT: {e}"); st.session_state.swot_analysis = None
            else: st.error("Limite de análises diárias atingido.")
        if st.session_state.swot_analysis:
            swot = st.session_state.swot_analysis; col1, col2 = st.columns(2)
            with col1:
                st.subheader("👍 Forças"); [st.markdown(f"- {item}") for item in swot.get("strengths", [])]
                st.subheader("👎 Fraquezas"); [st.markdown(f"- {item}") for item in swot.get("weaknesses", [])]
            with col2:
                st.subheader("✨ Oportunidades"); [st.markdown(f"- {item}") for item in swot.get("opportunities", [])]
                st.subheader("❗ Ameaças"); [st.markdown(f"- {item}") for item in swot.get("threats", [])]
    
    with tab_evolucao:
        st.header("Evolução Histórica dos Indicadores (KPIs)")
        history_df = db_utils.get_kpi_history(market['id'])
        if history_df.empty or len(history_df) < 2:
            st.info("É necessário ter pelo menos duas análises para visualizar a evolução dos KPIs.")
        else:
            st.subheader("Concorrentes e Nota Média")
            st.line_chart(history_df[['competitor_count', 'avg_rating']])
            st.subheader("Sentimento do Mercado (%)")
            st.line_chart(history_df[['positive_sentiment', 'neutral_sentiment', 'negative_sentiment']])
            st.subheader("Histórico de Sumários Executivos")
            for index, row in history_df.sort_index(ascending=False).iterrows():
                with st.expander(f"Análise de {index.strftime('%d/%m/%Y')}"):
                    st.write(row['executive_summary'])

# --- Roteador Principal ---
def main():
    st.set_page_config(page_title="Radar Pro", page_icon="logo.png", layout="wide")
    load_css("style.css")

    st.session_state.setdefault('user', None); st.session_state.setdefault('is_admin', False); st.session_state.setdefault('page', 'login') 
    
    if not st.session_state.user:
        login_page(); return 

    if st.session_state.user:
        with st.sidebar:
            st.image("logo.png")
            st.write(f"Bem-vindo, **{st.session_state.user.get('email')}**")
            
            analysis_info = db_utils.get_user_analysis_info(st.session_state.user['id'])
            limit = int(db_utils.get_platform_setting('daily_analysis_limit'))
            analyses_left = limit - analysis_info['count']
            
            st.write("Análises gratuitas hoje:")
            st.progress(analyses_left / limit if analyses_left >= 0 and limit > 0 else 0)
            st.caption(f"{analyses_left if analyses_left >= 0 else 0} de {limit} restantes")
            
            st.divider()
            if st.button("Meu Dashboard", use_container_width=True): st.session_state.page = 'dashboard'; st.session_state.pop('selected_market', None); st.session_state.pop('swot_analysis', None); st.rerun()
            if st.session_state.is_admin:
                if st.button("Painel de Administração", use_container_width=True, type="secondary"): st.session_state.page = 'admin'; st.rerun()
            st.divider()
            if st.button("Sair", use_container_width=True): auth_utils.logout_user(); st.rerun()

        page_map = {'dashboard': dashboard_page, 'details': details_page, 'admin': admin_page.render}
        page_function = page_map.get(st.session_state.page, dashboard_page)
        
        if st.session_state.page == 'admin' and not st.session_state.is_admin:
            dashboard_page()
        else:
            page_function()

if __name__ == "__main__":
    main()