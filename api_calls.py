# Conteúdo completo para o arquivo: api_calls.py

import streamlit as st
import json
import googlemaps
import openai
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from pytrends.request import TrendReq
import pandas as pd
import db_utils

# --- Funções de Inicialização Segura ---

@st.cache_resource
def get_gmaps_client():
    """Cria e retorna um cliente Google Maps de forma segura."""
    try:
        return googlemaps.Client(key=st.secrets.google["maps_api_key"])
    except KeyError:
        st.error("A chave 'maps_api_key' do Google não foi encontrada nos segredos."); st.stop()
    except Exception as e:
        st.error(f"Erro ao inicializar o cliente Google Maps: {e}"); st.stop()

@st.cache_resource
def setup_openai():
    """Configura a chave da API da OpenAI de forma segura."""
    try:
        openai.api_key = st.secrets.openai["api_key"]
    except KeyError:
        st.error("A chave 'api_key' da OpenAI não foi encontrada nos segredos."); st.stop()
    except Exception as e:
        st.error(f"Erro ao configurar a API da OpenAI: {e}"); st.stop()

# --- Função de Chamada à IA ---

@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=4, max=30))
def call_chatgpt_with_retry(prompt: str):
    """Chama a API da OpenAI (ChatGPT) e retorna um objeto JSON."""
    setup_openai()
    try:
        response = openai.chat.completions.create(model="gpt-3.5-turbo-1106", messages=[{"role": "system", "content": "Você é um consultor de negócios especialista. Responda APENAS com um objeto JSON válido, sem texto ou formatação adicional."}, {"role": "user", "content": prompt}], response_format={"type": "json_object"})
        json_string = response.choices[0].message.content
        return json.loads(json_string)
    except Exception as e:
        print(f"ERRO DETALHADO NA CHAMADA DA OPENAI: {e}"); raise e

# --- Lógica de Prompts Customizados ---
def get_prompt_for_business_type(tipo_negocio, termo, localizacao, competidores_texto, avg_rating):
    prompt_base = f"""
    Analise o mercado para '{termo}' em '{localizacao}'.
    Dados coletados:
    - Concorrentes encontrados: {competidores_texto}
    - Nota média da concorrência: {avg_rating:.1f}

    Gere um relatório em formato JSON com as seguintes chaves obrigatórias:
    "sumario_executivo": (string) Um parágrafo conciso com a visão geral do mercado.
    "analise_sentimentos": (objeto) Um objeto com chaves "Positivo", "Negativo", e "Neutro", com valores de 0 a 100.
    "plano_de_acao": (array de 5 a 7 strings) Passos práticos e acionáveis.
    "analise_demografica": (objeto) com as chaves "resumo", "faixa_etaria", e "interesses_principais" (array).
    "dossies_concorrentes": (array de objetos) para os 5 principais concorrentes, cada um com "nome", "posicionamento_mercado", "pontos_fortes", e "pontos_fracos".
    """
    prompts_especificos = {
        "Restaurante, Bar ou Lanchonete": prompt_base + """
        Adicione também as seguintes chaves ao JSON, com insights específicos para alimentação:
        - "analise_cardapio": (string) "Sugestões de pratos, bebidas ou tipos de culinária que estão em alta ou ausentes na região."
        - "estrategia_delivery": (string) "Dicas para otimizar a presença em apps como iFood/Rappi e estratégias de entrega própria."
        """,
        "Loja de Varejo (Roupas, Eletrônicos, etc.)": prompt_base + """
        Adicione também as seguintes chaves ao JSON, com insights específicos para varejo:
        - "analise_mix_produtos": (string) "Análise sobre o mix de produtos ideal para a localidade, sugerindo marcas, estilos ou categorias em alta."
        - "estrategia_visual_merchandising": (string) "Dicas para a vitrine e layout interno da loja para maximizar a atração de clientes e as vendas."
        """,
        "Salão de Beleza ou Barbearia": prompt_base + """
        Adicione também as seguintes chaves ao JSON, com insights específicos para serviços de beleza:
        - "servicos_diferenciados": (string) "Sugestão de 2 a 3 serviços, técnicas ou produtos exclusivos que podem diferenciar o estabelecimento da concorrência local."
        - "estrategia_agendamento": (string) "Análise sobre a melhor forma de gerenciar agendamentos (app próprio, WhatsApp Business, etc.) para fidelizar o público da região."
        """
    }
    return prompts_especificos.get(tipo_negocio, prompt_base)

# --- Função de Análise de Tendências ---
@st.cache_data(ttl=3600) # Cache de 1 hora para os dados do Trends
def get_interest_over_time(keyword: str, location: str = 'BR') -> pd.DataFrame:
    """Busca o interesse por uma palavra-chave no Google Trends nos últimos 12 meses."""
    try:
        pytrends = TrendReq(hl='pt-BR', tz=360)
        pytrends.build_payload([keyword], cat=0, timeframe='today 12-m', geo=location, gprop='')
        df = pytrends.interest_over_time()
        if not df.empty and keyword in df.columns:
            return df[[keyword]]
        return pd.DataFrame()
    except Exception as e:
        print(f"Erro ao buscar dados do Google Trends: {e}"); return pd.DataFrame()

# --- Função Principal de Orquestração ---
def run_full_analysis(termo: str, localizacao: str, user_id: str, market_id: int, progress_bar, maps_api_key: str, tipo_negocio: str):
    gmaps = get_gmaps_client()
    snapshot_data = {"termo_busca": termo, "localizacao_busca": localizacao, "tipo_negocio": tipo_negocio}

    progress_bar.progress(10, text="Buscando concorrentes no Google Maps...")
    query = f"{termo} em {localizacao}"
    places_result = gmaps.places(query=query).get('results', [])
    competidores = [{'name': p.get('name'), 'address': p.get('formatted_address'), 'rating': p.get('rating', 0), 'user_ratings_total': p.get('user_ratings_total', 0), 'latitude': p.get('geometry', {}).get('location', {}).get('lat'), 'longitude': p.get('geometry', {}).get('location', {}).get('lng')} for p in places_result[:10]]
    snapshot_data['competidores'] = competidores

    geocode_result = gmaps.geocode(localizacao)
    if geocode_result:
        snapshot_data['location_geocode'] = geocode_result[0]['geometry']['location']

    progress_bar.progress(40, text=f"Consultando IA para análise de '{tipo_negocio}'...")
    competidores_texto = "\n".join([f"- {c.get('name')} (Nota: {c.get('rating')})" for c in competidores])
    avg_rating_list = [c['rating'] for c in competidores if c.get('rating')]
    avg_rating = sum(avg_rating_list) / len(avg_rating_list) if avg_rating_list else 0

    prompt_final = get_prompt_for_business_type(tipo_negocio, termo, localizacao, competidores_texto, avg_rating)
    ai_analysis = call_chatgpt_with_retry(prompt_final)
    snapshot_data.update(ai_analysis)

    progress_bar.progress(90, text="Salvando análise no banco de dados...")
    final_json_string = json.dumps(snapshot_data, default=str)
    
    new_snapshot_id = db_utils.add_snapshot(market_id=market_id, user_id=user_id, dados_json=final_json_string)

    if new_snapshot_id:
        progress_bar.progress(95, text="Registrando KPIs para análise histórica...")
        db_utils.add_kpi_entry(snapshot_id=new_snapshot_id, market_id=market_id, user_id=user_id, analysis_data=snapshot_data)

    progress_bar.progress(100, text="Análise concluída com sucesso!")
    time.sleep(1)

# --- Função para SWOT ---
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def generate_swot_analysis(data: dict):
    termo = data.get('termo_busca', 'N/A')
    localizacao = data.get('localizacao_busca', 'N/A')
    sumario = data.get('sumario_executivo', 'Sem sumário.')
    prompt_swot = f"""Baseado na seguinte análise de mercado para '{termo}' em '{localizacao}': "{sumario}". Crie uma Análise SWOT. Sua resposta deve ser um objeto JSON com quatro chaves: "strengths", "weaknesses", "opportunities", e "threats". Cada chave deve conter um array de 2 a 3 strings."""
    swot_analysis = call_chatgpt_with_retry(prompt_swot)
    return swot_analysis