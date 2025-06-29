# Conteúdo completo para o arquivo: admin_page.py

import streamlit as st
import pandas as pd
import db_utils
import time

def render():
    """Renderiza a página completa do painel de administração com tabela melhorada."""
    st.title("Painel de Administração do Radar Pro")
    st.markdown("---")

    # Seção 1: Métricas da Plataforma
    st.subheader("Métricas Gerais")
    stats = db_utils.get_platform_stats_admin()
    if stats:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Usuários", stats.get('total_users', 0))
        col2.metric("Total de Análises", stats.get('total_snapshots', 0))
        col3.metric("Total de Mercados", stats.get('total_markets', 0))
    else:
        st.warning("Não foi possível carregar as estatísticas.")

    st.markdown("---")

    # Seção 2: Configurações da Plataforma
    st.subheader("Configurações da Plataforma")
    with st.container(border=True):
        st.write("**Controle de Limites de Análise**")
        current_limit = db_utils.get_platform_setting('daily_analysis_limit')
        new_limit = st.number_input(
            label="Limite diário de análises gratuitas por usuário",
            min_value=0, max_value=100, value=int(current_limit), step=1,
            help="Defina quantas análises um usuário pode fazer gratuitamente por dia."
        )
        if st.button("Salvar Novo Limite", type="primary"):
            with st.spinner("Salvando..."):
                if db_utils.update_platform_setting_admin('daily_analysis_limit', str(new_limit)):
                    st.toast("Limite atualizado com sucesso!", icon="🎉"); time.sleep(1); st.rerun()
                else:
                    st.error("Não foi possível salvar a alteração.")
    
    st.markdown("---")

    # Seção 3: Gerenciamento de Usuários com Melhor Estilo
    st.subheader("Gerenciamento de Usuários")
    st.info("Clique na caixa de seleção 'Ativo?' para ativar/desativar um usuário e salve as alterações.")

    users = db_utils.get_all_users_admin()
    if not users:
        st.warning("Nenhum usuário encontrado.")
    else:
        df_users = pd.DataFrame(users)
        
        # Tratamento de dados para exibição correta
        df_users['last_sign_in_at'] = pd.to_datetime(df_users['last_sign_in_at']).dt.tz_localize(None) if 'last_sign_in_at' in df_users else None
        df_users.fillna(0, inplace=True)
        df_users['is_active'] = df_users['is_active'].astype(bool)

        if 'original_df_users' not in st.session_state:
            st.session_state.original_df_users = df_users.copy()
        
        with st.container(border=True):
            edited_df = st.data_editor(
                df_users,
                column_config={
                    "id": None,  # Oculta a coluna de ID
                    "email": st.column_config.TextColumn("Email", width="large", disabled=True),
                    "last_sign_in_at": st.column_config.DatetimeColumn("Último Login", format="DD/MM/YYYY HH:mm", disabled=True),
                    "is_active": st.column_config.CheckboxColumn("Ativo?", width="small"),
                    "snapshot_count": st.column_config.NumberColumn("Análises", width="small", disabled=True),
                    "market_count": st.column_config.NumberColumn("Mercados", width="small", disabled=True),
                    "analysis_credits": None,  # Oculta a coluna de créditos legada
                },
                use_container_width=True,
                hide_index=True,
                key="user_admin_editor_styled"
            )
        
        if st.button("Salvar Alterações na Tabela de Usuários", type="secondary", use_container_width=True):
            diff = edited_df.compare(st.session_state.original_df_users)
            if diff.empty:
                st.toast("Nenhuma alteração detectada.", icon="🤷")
            else:
                with st.spinner("Salvando alterações..."):
                    updates_made = 0
                    for user_id_str in diff.index:
                        update_data = {}
                        changed_cols = diff.loc[user_id_str].dropna().index.get_level_values(0).unique()
                        for col in changed_cols:
                            update_data[col] = edited_df.loc[user_id_str, col]
                        if update_data:
                            if db_utils.update_user_profile_admin(str(user_id_str), update_data):
                                updates_made += 1
                    if updates_made > 0:
                        st.success(f"{updates_made} usuário(s) atualizado(s) com sucesso!")
                        del st.session_state.original_df_users
                        time.sleep(1); st.rerun()
                    else:
                        st.error("Falha ao salvar as alterações.")