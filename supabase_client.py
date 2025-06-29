# Conteúdo para o arquivo: supabase_client.py (VERSÃO CORRIGIDA)

import streamlit as st
from supabase import create_client, Client

# A anotação @st.cache_resource garante que esta função rode apenas uma vez,
# criando um único cliente Supabase e reutilizando-o.
@st.cache_resource
def get_supabase_client() -> Client:
    """
    Cria e retorna um cliente Supabase, configurando a sessão do usuário se existir.
    Usa o cache do Streamlit para evitar recriar a conexão a cada rerun.
    """
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        client = create_client(supabase_url, supabase_key)

        # A lógica de restauração da sessão é movida para dentro da função.
        # Isso garante que seja executada no momento certo.
        if "user_session" in st.session_state and st.session_state.user_session:
            client.auth.set_session(
                st.session_state.user_session.access_token,
                st.session_state.user_session.refresh_token
            )
        
        print("Cliente Supabase inicializado com sucesso.")
        return client

    except Exception as e:
        st.error(f"Erro fatal ao inicializar o cliente Supabase: {e}")
        st.stop()
        return None

# Agora, em vez de exportar uma variável, vamos chamar a função para obter o cliente.
# Fazemos isso para que outros módulos possam importá-lo facilmente.
supabase_client = get_supabase_client()