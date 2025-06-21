# report_generator.py

import streamlit as st
import base64
from io import BytesIO
from xhtml2pdf import pisa
import matplotlib.pyplot as plt
import pandas as pd
import requests
from datetime import datetime

def get_static_map_url(competidores, api_key):
    if not competidores or not api_key:
        return ""
    
    base_url = "https://maps.googleapis.com/maps/api/staticmap?"
    params = { "size": "600x400", "maptype": "roadmap", "key": api_key }
    
    markers = []
    for comp in competidores[:10]:
        lat = comp.get('latitude')
        lon = comp.get('longitude')
        if lat and lon:
            marker_label = comp.get('name', 'C')[0].upper()
            markers.append(f"color:red|label:{marker_label}|{lat},{lon}")
    
    params["markers"] = markers
    
    try:
        request = requests.Request('GET', base_url, params=params).prepare()
        return request.url
    except Exception as e:
        print(f"Erro ao criar URL do mapa estático: {e}")
        return ""

def generate_sentiment_chart_base64(sentimentos):
    if not sentimentos or not all(isinstance(v, (int, float)) for v in sentimentos.values()):
        return ""
    try:
        dados_grafico = {
            'Positivo': sentimentos.get('Positivo', 0),
            'Negativo': sentimentos.get('Negativo', 0),
            'Neutro': sentimentos.get('Neutro', 0)
        }
        df = pd.DataFrame(list(dados_grafico.items()), columns=['Sentimento', 'Valor'])
        
        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(6, 4))
        
        colors = {'Positivo': '#2ca02c', 'Negativo': '#d62728', 'Neutro': '#ff7f0e'}
        bar_colors = [colors.get(s, '#7f7f7f') for s in df['Sentimento']]
        
        bars = ax.bar(df['Sentimento'], df['Valor'], color=bar_colors)
        
        ax.set_title('Análise de Sentimentos', fontsize=16, weight='bold', color='#333')
        ax.set_ylabel('Pontuação (0-100)', fontsize=12)
        ax.set_xlabel('')
        ax.set_ylim(0, 100)
        ax.tick_params(axis='x', rotation=0, labelsize=12)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2.0, yval, int(yval), va='bottom', ha='center')

        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', transparent=True)
        plt.close(fig)
        buf.seek(0)
        
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Erro ao gerar gráfico de sentimentos: {e}")
        return ""

def gerar_relatorio_pdf(data: dict):
    maps_api_key = st.secrets.google.get("maps_api_key", "")
    
    sumario = data.get('sumario_executivo', 'N/A')
    plano_acao_html = "".join([f"<li>{p}</li>" for p in data.get('plano_de_acao', [])])
    demografia = data.get('analise_demografica', 'N/A')
    dossies = data.get('dossies_concorrentes', [])
    dossies_html = ""
    for d in dossies:
        dossies_html += f"""
        <div class="dossie-card">
            <h4>{d.get('nome', 'N/A')}</h4>
            <p><strong>Pontos Fortes:</strong> {d.get('pontos_fortes', 'N/A')}</p>
            <p><strong>Pontos Fracos:</strong> {d.get('pontos_fracos', 'N/A')}</p>
        </div>
        """
        
    sentiment_chart_b64 = generate_sentiment_chart_base64(data.get('analise_sentimentos', {}))
    static_map_url = get_static_map_url(data.get('competidores', []), maps_api_key)

    html_template = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ margin: 0.75in; }}
            body {{ font-family: 'Helvetica', 'sans-serif'; color: #333; }}
            h1 {{ color: #005f73; font-size: 24pt; border-bottom: 2px solid #005f73; padding-bottom: 10px; margin-bottom: 5px; }}
            h2 {{ color: #0a9396; font-size: 16pt; margin-top: 30px; border-bottom: 1px solid #e0e0e0; padding-bottom: 8px; page-break-after: avoid; }}
            h4 {{ margin-bottom: 5px; font-size: 12pt;}}
            .subtitle {{ font-size: 12pt; color: #555; margin-top: 0; }}
            .section {{ margin-bottom: 25px; page-break-inside: avoid; }}
            .dossie-card {{ border: 1px solid #e0e0e0; padding: 15px; margin-top: 15px; }}
            p, li {{ line-height: 1.5; font-size: 10pt; }}
            ul {{ padding-left: 20px; }}
            .center {{ text-align: center; }}
            .footer {{ position: fixed; bottom: -25px; left: 0; right: 0; text-align: center; font-size: 8pt; color: #888; }}
        </style>
    </head>
    <body>
        <div class="footer">Relatório gerado por Radar Pro | {datetime.now().strftime('%d/%m/%Y')}</div>
        <h1>Análise de Mercado: {data.get('termo_busca', 'N/A')}</h1>
        <p class="subtitle"><strong>Localização:</strong> {data.get('localizacao_busca', 'N/A')}</p>
        <div class="section"><h2>Visão Geral Estratégica</h2><p>{sumario}</p></div>
        <div class="section center"><h2>Análise de Sentimentos</h2><img src="data:image/png;base64,{sentiment_chart_b64}" style="width: 80%; max-width: 500px;"></div>
        <div class="section center" style="page-break-before: always;"><h2>Mapa da Concorrência</h2><img src="{static_map_url}" style="width: 100%; max-width: 600px;"></div>
        <div class="section"><h2>Plano de Ação Sugerido</h2><ul>{plano_acao_html}</ul></div>
        <div class="section"><h2>Análise Demográfica</h2><p>{demografia}</p></div>
        <div class="section" style="page-break-before: always;"><h2>Dossiês dos Concorrentes</h2>{dossies_html}</div>
    </body>
    </html>
    """

    pdf_bytes = BytesIO()
    pisa_status = pisa.CreatePDF(BytesIO(html_template.encode('UTF-8')), dest=pdf_bytes)

    if pisa_status.err:
        st.error("Ocorreu um erro ao gerar o PDF.")
        return None
    
    pdf_bytes.seek(0)
    return pdf_bytes.getvalue()