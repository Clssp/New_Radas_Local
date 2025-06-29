# report_generator.py

import streamlit as st
import base64
from io import BytesIO
from xhtml2pdf import pisa
import matplotlib.pyplot as plt
import pandas as pd
import requests
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

def image_to_base64(path):
    """Converte uma imagem local para uma string Base64 para embutir no HTML."""
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Arquivo de imagem não encontrado em: {path}")
        return None

def get_static_map_url(competidores, api_key):
    """Gera a URL para um mapa estático com marcadores para os concorrentes."""
    if not api_key or not competidores:
        return ""

    base_url = "https://maps.googleapis.com/maps/api/staticmap?"
    params = {"size": "600x400", "maptype": "roadmap", "key": api_key}
    
    markers = []
    # Limita o número de marcadores para não exceder o limite de URL da API
    for i, comp in enumerate(competidores[:18]):
        lat = comp.get('latitude')
        lon = comp.get('longitude')
        if lat and lon:
            # Usando números para os labels para economizar espaço
            markers.append(f"color:red|label:{i+1}|{lat},{lon}")

    if markers:
        params["markers"] = markers

    try:
        request = requests.Request('GET', base_url, params=params).prepare()
        # Retorna a URL pronta para ser usada na tag <img>
        return request.url
    except Exception as e:
        print(f"Erro ao criar URL do mapa estático: {e}")
        return ""

def generate_sentiment_chart_base64(sentimentos):
    # ... (código desta função permanece o mesmo)
    if not sentimentos or not isinstance(sentimentos, dict): return ""
    try:
        df = pd.DataFrame(list(sentimentos.items()), columns=['Sentimento', 'Pontuação'])
        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(6, 4))
        colors = {'Positivo': '#2ca02c', 'Negativo': '#d62728', 'Neutro': '#ffaa00'}
        bar_colors = [colors.get(s, '#7f7f7f') for s in df['Sentimento']]
        bars = ax.bar(df['Sentimento'], df['Pontuação'], color=bar_colors)
        ax.set_title('Análise de Sentimentos', fontsize=16, weight='bold', color='#333')
        ax.set_ylabel('Pontuação (0-100)', fontsize=12); ax.set_ylim(0, 105)
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2.0, yval + 1, int(yval), va='bottom', ha='center')
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', transparent=True); plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Erro ao gerar gráfico de sentimentos: {e}")
        return ""

def gerar_relatorio_pdf(data: dict, maps_api_key: str):
    """Gera o relatório PDF completo, agora incluindo o logo e o mapa estático."""
    try:
        env = Environment(loader=FileSystemLoader('.'))
        template = env.get_template("template.html")
        
        # Prepara o contexto com todos os dados necessários para o template
        context = {
            'logo_base64': image_to_base64("logo.png"), # Converte o logo
            'termo_busca': data.get('termo_busca', 'N/A'),
            'localizacao_busca': data.get('localizacao_busca', 'N/A'),
            'sumario': data.get('sumario_executivo', 'N/A'),
            'plano_acao': data.get('plano_de_acao', []),
            'demografia': data.get('analise_demografica', {}),
            'dossies': data.get('dossies_concorrentes', []),
            'data_geracao': datetime.now().strftime('%d/%m/%Y'),
            'sentiment_chart_b64': generate_sentiment_chart_base64(data.get('analise_sentimentos', {})),
            'static_map_url': get_static_map_url(data.get('competidores', []), maps_api_key),
            'competidores_lista': data.get('competidores', []) # Lista para a legenda do mapa
        }

        html_out = template.render(context)
        
        pdf_bytes = BytesIO()
        pisa_status = pisa.CreatePDF(BytesIO(html_out.encode('UTF-8')), dest=pdf_bytes)

        if pisa_status.err:
            st.error("Ocorreu um erro ao renderizar o PDF.")
            print(f"Erro PDF: {pisa_status.err}")
            return None

        pdf_bytes.seek(0)
        return pdf_bytes.getvalue()
    except Exception as e:
        st.error(f"Erro ao preparar o relatório PDF: {e}")
        return None