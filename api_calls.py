import streamlit as st
import json
import googlemaps
from pytrends.request import TrendReq
from openai import OpenAI, RateLimitError

# Importamos a função correta do tenacity para a sintaxe moderna
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import db_utils

# --- Clientes de API ---
gmaps_client = googlemaps.Client(key=st.secrets["google"]["api_key"])
openai_client = OpenAI(api_key=st.secrets["openai"]["api_key"])
pytrends = TrendReq(hl='pt-BR', tz=360)


# --- DECORADOR DE RETENTATIVA (COM A SINTAXE CORRETA E MODERNA) ---
# Usamos 'retry' e a função 'retry_if_exception_type'.
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RateLimitError)  # <<-- SINTAXE CORRETA
)
def call_openai_with_retry(prompt):
    """Função separada para a chamada da API, para que possamos aplicar o decorador de retentativa."""
    print("Tentando chamar a API da OpenAI (com a lógica de retentativa)...")
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    print("Chamada à API bem-sucedida!")
    return json.loads(response.choices[0].message.content)


def run_full_analysis(termo: str, localizacao: str, user_id: str, market_id: int):
    """Orquestra a coleta de dados, agora com chamada resiliente e prompt super otimizado."""
    snapshot_data = {}
    
    # Passo 1: Google Maps
    query = f"{termo} em {localizacao}"
    places_result = gmaps_client.places(query=query)['results']
    
    competidores = []
    for place in places_result[:5]:
        try:
            place_details = gmaps_client.place(place_id=place['place_id'], fields=['name', 'rating', 'geometry'])['result']
            competidores.append({
                "name": place_details.get('name'), "rating": place_details.get('rating'),
                "latitude": place_details.get('geometry', {}).get('location', {}).get('lat'),
                "longitude": place_details.get('geometry', {}).get('location', {}).get('lng'),
            })
        except Exception as e:
            print(f"Não foi possível obter detalhes para o place_id {place.get('place_id')}: {e}")
    snapshot_data['competidores'] = competidores

    # Super Otimização do Prompt para evitar Rate Limits de Tokens
    competidores_texto = "\n".join([f"- {c.get('name')} (Nota: {c.get('rating', 'N/A')})" for c in competidores])
    prompt_super_otimizado = f"""
    Analise o mercado de '{termo}' em '{localizacao}' com base nesta lista de concorrentes e suas notas:
    {competidores_texto}

    Gere um relatório JSON conciso com as chaves: "sumario_executivo", "analise_sentimentos", "plano_de_acao", "analise_demografica", "dossies_concorrentes".
    Seja breve e direto em todas as análises.
    """
    
    try:
        # Agora chamamos a API com a função de retentativa correta
        ai_analysis = call_openai_with_retry(prompt_super_otimizado)
    except Exception as e:
        st.error(f"Erro ao chamar a API da OpenAI após várias tentativas: {e}")
        ai_analysis = {"sumario_executivo": "Erro ao gerar análise.", "analise_sentimentos": {}, "plano_de_acao": [], "analise_demografica": "Erro ao gerar análise.", "dossies_concorrentes": []}
    
    snapshot_data.update(ai_analysis)

    # Passo 3: Google Trends
    try:
        pytrends.build_payload(kw_list=[termo], timeframe='today 12-m', geo='BR')
        trends_df = pytrends.interest_over_time()
        if not trends_df.empty:
            trends_data = trends_df[termo].to_dict()
            snapshot_data['google_trends_data'] = {str(k.isoformat()): v for k, v in trends_data.items()}
    except Exception as e:
        print(f"Erro ao buscar dados do Google Trends: {e}")
        snapshot_data['google_trends_data'] = {}

    # Passo 4: Salvar no DB
    final_json_string = json.dumps(snapshot_data, default=str)
    db_utils.add_snapshot(market_id=market_id, user_id=user_id, dados_json=final_json_string)
    
    return