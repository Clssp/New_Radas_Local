# main.py

import streamlit as st
import pandas as pd
import json
from datetime import datetime
import time

# Importações dos módulos do projeto
import auth_utils
import db_utils
import api_calls
import supabase_client
import report_generator

# --- Configuração da Página ---
st.set_page_config(page_title="Radar Pro 📡", page_icon="📡", layout="wide", initial_sidebar_state="collapsed")

def run_analysis_with_progress(termo, localizacao, user_id, market_id):
    progress_bar = st.progress(0, text="Iniciando análise... (0%)")
    steps = ["Coletando dados do Google Maps...", "Processando informações locais...", "Consultando IA para insights estratégicos...", "Analisando tendências de busca..."]
    for i, step in enumerate(steps):
        percent_complete = int(((i + 1) / len(steps)) * 100)
        progress_bar.progress(percent_complete, text=f"{step} ({percent_complete}%)")
        time.sleep(1.2)
    with st.spinner("A IA está compilando o relatório final..."):
         api_calls.run_full_analysis(termo, localizacao, user_id, market_id)
    progress_bar.empty()

def login_page():
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
                if user: st.rerun()
                else: st.error(f"Erro no login: {error}")
    with signup_tab:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Senha", type="password", key="signup_password")
            if st.form_submit_button("Cadastrar"):
                user, error = auth_utils.signup_user(email, password)
                if user: st.success("Cadastro realizado! Faça o login para continuar.")
                else: st.error(f"Erro no cadastro: {error}")

def dashboard_page():
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
            if st.form_submit_button("Analisar Mercado"):
                if termo and localizacao:
                    market_id = db_utils.find_market_by_term_and_location(st.session_state.user['id'], termo, localizacao)
                    if not market_id:
                        market_id = db_utils.add_market(st.session_state.user['id'], termo, localizacao)
                    run_analysis_with_progress(termo, localizacao, st.session_state.user['id'], market_id)
                    st.success("Análise concluída e salva com sucesso!")
                    st.rerun()
                else:
                    st.warning("Por favor, preencha o termo e a localização.")
    st.divider()
    
    st.subheader("Meus Mercados Monitorados")
    user_markets = db_utils.get_user_markets(st.session_state.user['id'])
    if not user_markets:
        st.info("Você ainda não adicionou nenhum mercado.")
    else:
        for market in user_markets:
            col1, col2, col3, col4 = st.columns([4, 2, 2, 1])
            with col1:
                st.markdown(f"**{market.get('termo', 'N/A')}** em **{market.get('localizacao', 'N/A')}**")
                last_snapshot_date = db_utils.get_latest_snapshot_date(market['id'])
                if last_snapshot_date:
                    st.caption(f"Última análise: {last_snapshot_date.strftime('%d de %b, %H:%M')}")
                else:
                    st.caption("Nenhuma análise encontrada.")
            with col2:
                if st.button("Ver Detalhes", key=f"details_{market['id']}"):
                    st.session_state.selected_market = market
                    st.rerun()
            with col3:
                if st.button("Reanalisar", key=f"reanalyze_{market['id']}"):
                    run_analysis_with_progress(market['termo'], market['localizacao'], st.session_state.user['id'], market['id'])
                    st.success(f"Mercado '{market['termo']}' reanalisado com sucesso!")
                    st.rerun()
            with col4:
                if st.button("Excluir", key=f"delete_{market['id']}"):
                    db_utils.delete_market(market['id'])
                    st.warning(f"Mercado '{market['termo']}' excluído.")
                    st.rerun()

def details_page():
    market = st.session_state.selected_market
    
    header_cols = st.columns([0.3, 0.4, 0.3])
    with header_cols[0]:
        if st.button("⬅️ Voltar ao Dashboard"):
            if 'swot_analysis' in st.session_state:
                del st.session_state.swot_analysis
            st.session_state.selected_market = None
            st.rerun()
    
    snapshot = db_utils.get_latest_snapshot(market['id'])
    if snapshot:
        try:
            data = json.loads(snapshot['dados_json'])
            data['termo_busca'] = market.get('termo', 'N/A')
            data['localizacao_busca'] = market.get('localizacao', 'N/A')
            with header_cols[2]:
                pdf_bytes = report_generator.gerar_relatorio_pdf(data)
                if pdf_bytes:
                    st.download_button(
                        label="📄 Baixar Relatório em PDF",
                        data=pdf_bytes,
                        file_name=f"Relatorio_RadarPro_{market.get('termo', '').replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        except (json.JSONDecodeError, TypeError): data = None
    else: data = None

    st.title(f"Análise Detalhada: {market.get('termo', 'N/A')}")
    st.subheader(f"Localização: {market.get('localizacao', 'N/A')}")
    st.divider()
    
    if not data:
        st.error("Dados de análise não encontrados ou corrompidos. Tente reanalisar o mercado.")
        return

    tabs_list = ["Visão Geral", "Plano de Ação", "📍 Mapa", "Tendências", "Demografia", "Dossiês", "📈 Evolução", "♟️ Análise SWOT"]
    tabs = st.tabs(tabs_list)

    with tabs[0]:
        st.header("Visão Geral do Mercado")
        st.markdown(data.get('sumario_executivo', "N/A"))
        st.subheader("Análise de Sentimentos")
        sentimentos = data.get('analise_sentimentos', {})
        if sentimentos and all(isinstance(v, (int, float)) for v in sentimentos.values()):
            df_sentimentos = pd.DataFrame(list(sentimentos.items()), columns=['Sentimento', 'Contagem'])
            st.bar_chart(df_sentimentos.set_index('Sentimento'))
        else:
            st.info("Dados de sentimento não disponíveis.")

    with tabs[1]:
        st.header("Plano de Ação Sugerido")
        plano_acao = data.get('plano_de_acao', [])
        if plano_acao:
            for i, step in enumerate(plano_acao, 1): st.markdown(f"**{i}.** {step}")
        else: st.info("Nenhum plano de ação foi gerado.")

    with tabs[2]:
        st.header("Mapa da Concorrência")
        competidores = data.get('competidores', [])
        col1, col2 = st.columns([0.6, 0.4])
        with col1:
            if competidores:
                df_mapa = pd.DataFrame(competidores).dropna(subset=['latitude', 'longitude'])
                if not df_mapa.empty: st.map(df_mapa, zoom=13)
                else: st.info("Nenhum concorrente com dados de localização válidos.")
            else: st.info("Nenhum concorrente encontrado.")
        with col2:
            st.subheader("Lista de Concorrentes")
            if competidores:
                for comp in competidores: st.markdown(f"**{comp.get('name')}** - Nota: {comp.get('rating', 'N/A')} ⭐")
            else: st.write("N/A")
            
    with tabs[3]:
        st.header("Tendências de Busca (Google Trends)")
        trends_data = data.get('google_trends_data', {})
        if trends_data:
            df_trends = pd.DataFrame(list(trends_data.items()), columns=['Data', 'Interesse'])
            df_trends['Data'] = pd.to_datetime(df_trends['Data'])
            st.line_chart(df_trends.set_index('Data'))
        
        related_queries = data.get('related_queries')
        if related_queries:
            st.subheader("Principais Buscas Relacionadas")
            df_related = pd.DataFrame(related_queries)
            st.dataframe(df_related, use_container_width=True)
        
        if not trends_data and not related_queries:
            st.info("Não foi possível carregar dados de tendências.")

    with tabs[4]:
        st.header("Análise Demográfica")
        col1, col2 = st.columns(2)
        with col1: st.markdown(data.get('analise_demografica', "N/A"))
        with col2:
            location_geocode = data.get('location_geocode')
            if location_geocode: st.map(pd.DataFrame([location_geocode]), zoom=12)
            else: st.write("Mapa da região indisponível.")

    with tabs[5]:
        st.header("Dossiês dos Concorrentes")
        dossies = data.get('competidores', [])
        if dossies:
            for d in dossies:
                with st.container(border=True):
                    st.subheader(d.get('name', 'N/A'))
                    col1, col2 = st.columns(2)
                    
                    rating = d.get('rating')
                    total_ratings = d.get('total_ratings')
                    display_rating = f"{rating:.1f} ⭐" if rating is not None else "Sem nota"
                    display_delta = f"{total_ratings} avaliações" if total_ratings is not None else ""
                    
                    col1.metric("Nota Média", value=display_rating, delta=display_delta)
                    
                    if d.get('address'): st.markdown(f"📍 **Endereço:** {d['address']}")
                    if d.get('phone'): st.markdown(f"📞 **Telefone:** {d['phone']}")
                    if d.get('website'): st.markdown(f"🌐 **Site:** [{d['website']}]({d['website']})")
        else:
            st.info("Nenhum dado sobre concorrentes foi encontrado.")

    with tabs[6]:
        st.header("Evolução Histórica dos Indicadores (KPIs)")
        all_snapshots = db_utils.get_all_snapshots(market['id'])
        if not all_snapshots or len(all_snapshots) < 2:
            st.info("É necessário ter pelo menos duas análises para comparar a evolução.")
        else:
            def format_date_for_display(date_str):
                return datetime.fromisoformat(date_str).strftime("%d de %b, %H:%M")
            date_map = {format_date_for_display(s['data_snapshot']): s['data_snapshot'] for s in all_snapshots}
            display_dates = list(date_map.keys())
            snapshots_dict = {s['data_snapshot']: json.loads(s['dados_json']) for s in all_snapshots}
            
            st.markdown("Selecione os períodos para comparar:")
            col1, col2 = st.columns(2)
            selected_display_date_from = col1.selectbox("De (data antiga):", options=display_dates, index=len(display_dates)-1)
            selected_display_date_to = col2.selectbox("Para (data recente):", options=display_dates, index=0)
            date_from_str = date_map[selected_display_date_from]
            date_to_str = date_map[selected_display_date_to]

            if date_from_str != date_to_str:
                data_from = snapshots_dict[date_from_str]
                data_to = snapshots_dict[date_to_str]
                st.divider()
                st.subheader(f"Comparativo de {selected_display_date_from} para {selected_display_date_to}")

                competidores_from = len(data_from.get('competidores', [])); competidores_to = len(data_to.get('competidores', []))
                ratings_from = [c.get('rating') for c in data_from.get('competidores', []) if c.get('rating') is not None]
                avg_rating_from = sum(ratings_from) / len(ratings_from) if ratings_from else 0
                ratings_to = [c.get('rating') for c in data_to.get('competidores', []) if c.get('rating') is not None]
                avg_rating_to = sum(ratings_to) / len(ratings_to) if ratings_to else 0
                sentimento_pos_from = data_from.get('analise_sentimentos', {}).get('Positivo', 0)
                sentimento_pos_to = data_to.get('analise_sentimentos', {}).get('Positivo', 0)
                
                kpi_cols = st.columns(3)
                kpi_cols[0].metric(label="Nº de Concorrentes", value=competidores_to, delta=competidores_to - competidores_from)
                kpi_cols[1].metric(label="Nota Média Concorrência", value=f"{avg_rating_to:.2f}", delta=f"{(avg_rating_to - avg_rating_from):.2f}")
                kpi_cols[2].metric(label="Sentimento Positivo", value=f"{sentimento_pos_to}", delta=f"{sentimento_pos_to - sentimento_pos_from}")

    with tabs[7]:
        st.header("Análise SWOT para um Novo Entrante")
        st.info("Esta análise é gerada sob demanda pela IA.")
        if 'swot_analysis' not in st.session_state: st.session_state.swot_analysis = None
        if st.button("🧠 Gerar Análise SWOT com IA"):
            progress_bar = st.progress(0, text="A IA está se preparando...")
            for i in range(100):
                time.sleep(0.03); progress_bar.progress(i + 1, text=f"Consultando o especialista... {i+1}%")
            with st.spinner("Elaborando a matriz estratégica..."):
                try: st.session_state.swot_analysis = api_calls.generate_swot_analysis(data)
                except Exception as e: st.error(f"Erro ao gerar a análise SWOT: {e}"); st.session_state.swot_analysis = None
            progress_bar.empty()
        
        if st.session_state.swot_analysis:
            swot = st.session_state.swot_analysis
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("👍 Forças (Strengths)"); [st.markdown(f"- {item}") for item in swot.get("strengths", ["N/A"])]
                st.subheader("👎 Fraquezas (Weaknesses)"); [st.markdown(f"- {item}") for item in swot.get("weaknesses", ["N/A"])]
            with col2:
                st.subheader("✨ Oportunidades (Opportunities)"); [st.markdown(f"- {item}") for item in swot.get("opportunities", ["N/A"])]
                st.subheader("⚠️ Ameaças (Threats)"); [st.markdown(f"- {item}") for item in swot.get("threats", ["N/A"])]

def main():
    if 'user' not in st.session_state: st.session_state.user = None
    if 'selected_market' not in st.session_state: st.session_state.selected_market = None
    if not st.session_state.user: login_page()
    elif st.session_state.selected_market: details_page()
    else: dashboard_page()

if __name__ == "__main__":
    main()