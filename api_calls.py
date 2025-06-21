# api_calls.py

import streamlit as st
import json
import googlemaps
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from pytrends.request import TrendReq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import db_utils

# --- VERIFICAÇÃO E CONFIGURAÇÃO DOS CLIENTES DE API ---
if "google" not in st.secrets:
    st.error("🚨 Seção [google] não encontrada no arquivo secrets.toml!")
    st.stop()

try:
    gmaps_client = googlemaps.Client(key=st.secrets.google["maps_api_key"])
except KeyError:
    st.error("🚨 Chave 'maps_api_key' não encontrada na seção [google] do seu secrets.toml!")
    st.stop()

pytrends = TrendReq(hl='pt-BR', tz=360)

try:
    GEMINI_API_KEY = st.secrets.google["gemini_api_key"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("🚨 Chave 'gemini_api_key' não encontrada na seção [google] do seu secrets.toml!")
    st.stop()

# --- Configurações do Modelo ---
generation_config = {"temperature": 0.3, "top_p": 1, "top_k": 1, "max_output_tokens": 8192}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]
gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash",
                                     generation_config=generation_config,
                                     safety_settings=safety_settings)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(ResourceExhausted)
)
def call_gemini_with_retry(prompt: str):
    prompt_com_instrucao_json = f"""
    {prompt}
    Sua resposta DEVE ser um objeto JSON bem formado. Não inclua a palavra 'json' ou os marcadores ``` no início ou no fim. Apenas o JSON puro.
    """
    try:
        response = gemini_model.generate_content(prompt_com_instrucao_json)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"🚨 ERRO DETALHADO NA CHAMADA GEMINI: {e}")
        raise e

def run_full_analysis(termo: str, localizacao: str, user_id: str, market_id: int):
    snapshot_data = {}
    
    query = f"{termo} em {localizacao}"
    try:
        places_result = gmaps_client.places(query=query).get('results', [])
    except Exception as e:
        st.error(f"🚨 Erro na chamada do Google Maps: {e}")
        return

    competidores = []
    fields_to_request = ['name', 'rating', 'geometry', 'formatted_address', 'formatted_phone_number', 'website', 'user_ratings_total']
    for place in places_result[:10]:
        try:
            place_details = gmaps_client.place(place_id=place['place_id'], fields=fields_to_request)['result']
            competidores.append({
                "name": place_details.get('name'), "rating": place_details.get('rating'),
                "total_ratings": place_details.get('user_ratings_total'), "address": place_details.get('formatted_address'),
                "phone": place_details.get('formatted_phone_number'), "website": place_details.get('website'),
                "latitude": place_details.get('geometry', {}).get('location', {}).get('lat'),
                "longitude": place_details.get('geometry', {}).get('location', {}).get('lng'),
            })
        except Exception as e:
            print(f"⚠️ Não foi possível obter detalhes para o place_id {place.get('place_id')}: {e}")
    snapshot_data['competidores'] = competidores
    
    try:
        geocode_result = gmaps_client.geocode(localizacao)
        if geocode_result:
            snapshot_data['location_geocode'] = geocode_result[0]['geometry']['location']
    except Exception as e:
        print(f"⚠️ Não foi possível obter o geocode da localização: {e}")

    competidores_texto = "\n".join([f"- {c.get('name')} (Nota: {c.get('rating', 'N/A')})" for c in competidores])
    prompt_analise_gemini = f"""
    Como um especialista em inteligência de mercado, analise o mercado de '{termo}' na região de '{localizacao}' com base nesta lista de concorrentes:
    {competidores_texto}
    Gere um relatório JSON conciso contendo EXATAMENTE as seguintes chaves: "sumario_executivo", "analise_sentimentos", "plano_de_acao", "analise_demografica", "dossies_concorrentes".
    - "sumario_executivo": (string) Um parágrafo com a visão geral do mercado.
    - "analise_sentimentos": (objeto) Um objeto com chaves "Positivo", "Negativo", "Neutro" e valores numéricos (0 a 100).
    - "plano_de_acao": (array de strings) Uma lista com 5 a 7 passos práticos.
    - "analise_demografica": (string) Um texto curto sobre o perfil do público-alvo.
    - "dossies_concorrentes": (array de objetos) Uma lista de dossiês para 2-3 concorrentes. Cada dossiê deve ter as chaves "nome", "pontos_fortes" e "pontos_fracos".
    """
    try:
        ai_analysis = call_gemini_with_retry(prompt_analise_gemini)
    except Exception as e:
        st.error(f"🚨 Erro final ao chamar a API da Gemini: {e}")
        ai_analysis = {}
    snapshot_data.update(ai_analysis)

    try:
        pytrends.build_payload(kw_list=[termo], timeframe='today 12-m', geo='BR')
        interest_df = pytrends.interest_over_time()
        if not interest_df.empty and termo in interest_df.columns:
            trends_data = interest_df[termo].to_dict()
            snapshot_data['google_trends_data'] = {str(k.isoformat()): v for k, v in trends_data.items()}
        
        related_queries = pytrends.related_queries()
        if termo in related_queries and related_queries[termo] is not None:
            top_queries = related_queries[termo].get('top')
            if top_queries is not None:
                snapshot_data['related_queries'] = top_queries.to_dict('records')
    except Exception as e:
        print(f"⚠️ Aviso ao buscar dados do Google Trends (pode ser normal para termos de baixo volume): {e}")

    final_json_string = json.dumps(snapshot_data, default=str)
    db_utils.add_snapshot(market_id=market_id, user_id=user_id, dados_json=final_json_string)
    return

def generate_swot_analysis(market_data: dict):
    termo = market_data.get('termo_busca', 'este mercado')
    localizacao = market_data.get('localizacao_busca', 'esta localização')
    sumario = market_data.get('sumario_executivo', 'N/A')
    plano = market_data.get('plano_de_acao', [])
    
    prompt_swot = f"""
    Com base na seguinte análise de mercado para '{termo}' em '{localizacao}':
    - Sumário Executivo: {sumario}
    - Sugestões de Plano de Ação: {", ".join(plano)}
    Atue como um consultor de negócios sênior. Crie uma análise SWOT para um NOVO EMPREENDEDOR.
    Sua resposta DEVE ser um objeto JSON com as chaves: "strengths", "weaknesses", "opportunities", "threats".
    Cada chave deve conter um array de 2 a 3 strings concisas.
    """
    swot_analysis = call_gemini_with_retry(prompt_swot)
    return swot_analysis