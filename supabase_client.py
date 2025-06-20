import streamlit as st
from supabase import create_client, Client

# Inicializa o cliente como None para lidar com possíveis erros de inicialização
supabase_client: Client = None

try:
    # Cria a única instância do cliente Supabase para toda a aplicação
    supabase_client = create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"]
    )

    # Lógica de restauração da sessão: Fica aqui, no único lugar onde o cliente é criado.
    # Se uma sessão de usuário já existir no estado do Streamlit, restaura ela.
    if 'user_session' in st.session_state and st.session_state.user_session:
        supabase_client.auth.set_session(
            st.session_state.user_session.access_token,
            st.session_state.user_session.refresh_token
        )

except (KeyError, FileNotFoundError):
    st.error("As credenciais do Supabase (URL e Key) não foram encontradas. Verifique seu arquivo .streamlit/secrets.toml.")
    st.stop()

except Exception as e:
    st.warning(f"Não foi possível restaurar a sessão: {e}. Por favor, faça login novamente.")
    # Limpa o estado da sessão se a restauração falhar para forçar um novo login.
    for key in list(st.session_state.keys()):
        del st.session_state[key]