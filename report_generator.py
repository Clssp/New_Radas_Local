# report_generator.py
import base64
import json
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from xhtml2pdf import pisa
from datetime import datetime

def prepare_data_for_pdf(snapshot_data):
    try:
        insights = json.loads(s) if (s := snapshot_data.get('insights_ia')) else {}
        sentimentos = json.loads(s) if (s := snapshot_data.get('sentimentos_gerais')) else {}
        concorrentes_raw = json.loads(s) if (s := snapshot_data.get('dados_concorrentes')) else []
        pdf_data = {
            "base64_logo": carregar_logo_base64("logo_radar_local.png"),
            "titulo": insights.get("titulo", "Análise Estratégica"),
            "slogan": insights.get("slogan", "Insights para o seu sucesso."),
            "concorrentes": concorrentes_raw,
            "sugestoes_estrategicas": insights.get("sugestoes", []),
            "alerta_nicho": insights.get("alerta", ""),
            "grafico_radar_b64": gerar_grafico_radar_base64(sentimentos),
            "matriz_posicionamento": classificar_concorrentes_matriz(concorrentes_raw),
            "horario_pico_inferido": insights.get("horario_pico", "Não foi possível inferir.")
        }
        return pdf_data
    except Exception as e:
        print(f"Erro ao preparar dados para PDF: {e}")
        return None

def sanitize_value(value):
    if isinstance(value, list): return ', '.join(map(str, value))
    if isinstance(value, dict): return json.dumps(value, ensure_ascii=False)
    if value is None: return ""
    return str(value)

def classificar_concorrentes_matriz(concorrentes):
    matriz = {"lideres_premium": [], "custo_beneficio": [], "armadilhas_valor": [], "economicos": []}
    for c in concorrentes:
        nota, preco = c.get("nota"), c.get("nivel_preco")
        if nota is None or preco is None: continue
        if nota >= 4.0:
            matriz["lideres_premium" if preco >= 3 else "custo_beneficio"].append(c.get("nome"))
        else:
            matriz["armadilhas_valor" if preco >= 3 else "economicos"].append(c.get("nome"))
    return matriz

def gerar_grafico_radar_base64(sentimentos):
    if not sentimentos: return ""
    plt.style.use('seaborn-v0_8-whitegrid')
    for key, value in sentimentos.items():
        if not isinstance(value, (int, float)): sentimentos[key] = 0.0
    labels, stats = list(sentimentos.keys()), list(sentimentos.values())
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    stats += stats[:1]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='#005f73', alpha=0.25)
    ax.plot(angles, stats, color='#005f73', linewidth=2)
    ax.set_ylim(0, 10)
    ax.set_yticklabels([])
    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=12, color="#34495e")
    ax.set_title("Diagnóstico de Sentimentos por Tópico", fontsize=16, y=1.1, color="#0a9396")
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', transparent=True)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def carregar_logo_base64(caminho_logo: str) -> str:
    try:
        with open(caminho_logo, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        return ""

def gerar_html_relatorio(**kwargs):
    CSS = """@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap'); body { font-family: 'Roboto', sans-serif; color: #34495e; margin: 1.5cm; } h1, h2, h3, h4 { color: #005f73; font-weight: 700; } h1 { font-size: 24pt; margin-bottom: 0; } h2 { font-size: 18pt; border-bottom: 2px solid #0a9396; padding-bottom: 5px; margin-top: 40px; } h3 { font-size: 14pt; border-bottom: 1px solid #e5e7eb; padding-bottom: 3px; margin-top: 25px; color: #0a9396; } .slogan { font-style: italic; color: #6b7280; font-weight: 300; font-size: 14pt; margin-top: 5px; } .section { page-break-inside: avoid; margin-bottom: 30px; } .alert { border: 1px solid #ae2012; background-color: #ffddd2; padding: 15px; margin-top: 20px; border-radius: 5px; color: #ae2012; } .matrix-table { border-collapse: collapse; width: 100%; margin-top: 20px; } .matrix-table th, .matrix-table td { border: 1px solid #e5e7eb; padding: 12px; text-align: left; vertical-align: top; } .matrix-table th { background-color: #f9fafb; font-weight: 700; } .matrix-table ul { padding-left: 20px; margin: 0; } .dossier-card { border: 1px solid #e5e7eb; padding: 15px; margin-top: 20px; page-break-inside: avoid; border-radius: 8px; background-color: #f9fafb; } .dossier-card strong { color: #005f73; font-weight: bold; } .dossier-card p { line-height: 1.6; }"""
    
    client_name = kwargs.get("client_name")
    titulo_principal = sanitize_value(kwargs.get("titulo"))
    if client_name:
        titulo_principal = f"Análise de Mercado para {sanitize_value(client_name)}"
    logo_para_usar = kwargs.get("custom_logo_b64") or kwargs.get("base64_logo", "")
    
    matriz = kwargs.get("matriz_posicionamento", {});
    matriz_html = f"""<table class="matrix-table"><tr><th>🏆 Líderes Premium<br><small>(Qualidade Alta, Preço Alto)</small></th><th>👍 Custo-Benefício<br><small>(Qualidade Alta, Preço Acessível)</small></th></tr><tr><td><ul>{"".join(f"<li>{sanitize_value(n)}</li>" for n in matriz.get("lideres_premium", []))}</ul></td><td><ul>{"".join(f"<li>{sanitize_value(n)}</li>" for n in matriz.get("custo_beneficio", []))}</ul></td></tr><tr><th>💀 Armadilhas de Valor<br><small>(Qualidade Baixa, Preço Alto)</small></th><th>💰 Opções Econômicas<br><small>(Qualidade Baixa, Preço Acessível)</small></th></tr><tr><td><ul>{"".join(f"<li>{sanitize_value(n)}</li>" for n in matriz.get("armadilhas_valor", []))}</ul></td><td><ul>{"".join(f"<li>{sanitize_value(n)}</li>" for n in matriz.get("economicos", []))}</ul></td></tr></table>"""
    dossie_html = "".join([f"""<div class='dossier-card'><h3>{sanitize_value(c.get('nome'))}</h3><p><strong>Arquétipo:</strong> {sanitize_value(c.get('dossie_ia',{}).get('arquétipo', 'N/A'))}</p><p><strong>Ponto Forte:</strong> {sanitize_value(c.get('dossie_ia',{}).get('ponto_forte','N/A'))}</p><p><strong>Fraqueza Explorável:</strong> {sanitize_value(c.get('dossie_ia', {}).get('fraqueza_exploravel','N/A'))}</p><p><strong>Resumo Estratégico:</strong> {sanitize_value(c.get('dossie_ia',{}).get('resumo_estrategico',''))}</p></div>""" for c in kwargs.get("concorrentes",[])])
    sugestoes_html = "".join([f"<li>{sanitize_value(s)}</li>" for s in kwargs.get("sugestoes_estrategicas", [])]);
    alerta_html = f"<div class='section alert'><h3>Alerta de Oportunidade</h3><p>{sanitize_value(kwargs.get('alerta_nicho'))}</p></div>" if kwargs.get('alerta_nicho') else ""
    
    body = f"""<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><table width="100%" style="border-bottom: 2px solid #005f73; margin-bottom: 20px;"><tr><td style="vertical-align: middle;"><h1>{titulo_principal}</h1><p class='slogan'>"{sanitize_value(kwargs.get("slogan"))}"</p></td><td style="text-align: right;"><img src='data:image/png;base64,{logo_para_usar}' width='100'></td></tr></table><div class='section'><h2>Diagnóstico Geral do Mercado</h2><div style="text-align:center;"><img src='data:image/png;base64,{kwargs.get("grafico_radar_b64","")}' style="width: 80%; max-width: 500px;"></div>{alerta_html}</div><div class='section'><h2>Matriz de Posicionamento Competitivo</h2>{matriz_html}</div><div class='section'><h2>Sugestões Estratégicas</h2><ul>{sugestoes_html}</ul></div><div class='section' style='page-break-before: always;'><h2>Apêndice: Dossiês dos Concorrentes</h2>{dossie_html}</div><hr style="margin-top: 40px; color: #e5e7eb;"><p style="text-align: center; font-size: 9pt; color: #9ca3af;">Relatório gerado por Radar Pro em {datetime.now().strftime('%d/%m/%Y')}</p></body></html>"""
    return body

def gerar_pdf(html):
    pdf_bytes = BytesIO()
    pisa_status = pisa.CreatePDF(html.encode('utf-8'), dest=pdf_bytes)
    return pdf_bytes.getvalue() if not pisa_status.err else None