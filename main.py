# main.py - v7.0 (Arquitetura de Autenticação Final)
# ========================================================================

import streamlit as st
import requests, base64, pandas as pd, unicodedata, re, json, time
from openai import OpenAI
from datetime import datetime
from io import BytesIO
from xhtml2pdf import pisa
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import psycopg2

# --- CONFIGURAÇÕES E INICIALIZAÇÃO ---
st.set_page_config(page_title="Radar Local", page_icon="📡", layout="wide")

try:
    API_KEY_GOOGLE = st.secrets["google"]["api_key"]
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
except (KeyError, FileNotFoundError):
    st.error("As chaves de API não foram encontradas. Verifique `.streamlit/secrets.toml`.")
    st.stop()

from auth_utils import sign_up, sign_in, sign_out, supabase, get_google_auth_url, exchange_code_for_session

# --- DEFINIÇÃO DE TODAS AS FUNÇÕES AUXILIARES ---
# (O código das suas 10+ funções auxiliares permanece aqui, inalterado)
def url_para_base64(url):
    if not url: return ""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode("utf-8")
    except requests.RequestException:
        return ""
    return ""

@st.cache_resource(show_spinner=False)
def init_connection():
    try: return psycopg2.connect(**st.secrets["database"])
    except psycopg2.OperationalError as e: st.error(f"Erro ao conectar ao banco de dados: {e}."); st.stop()
conn = init_connection()

def salvar_historico(nome, prof, loc, titulo, slogan, nivel, alerta):
    user_id = st.session_state.user_session.user.id
    sql = """INSERT INTO public.consultas (nome_usuario, tipo_negocio_pesquisado, localizacao_pesquisada, nivel_concorrencia_ia, titulo_gerado_ia, slogan_gerado_ia, alerta_oportunidade_ia, data_consulta, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);"""
    dados = (nome, prof, loc, nivel, titulo, slogan, alerta, datetime.now(), user_id)
    try:
        with conn.cursor() as cur: cur.execute(sql, dados)
        conn.commit()
    except psycopg2.Error as e: st.error(f"Erro ao salvar histórico: {e}"); conn.rollback()

def carregar_historico_db():
    try: return pd.read_sql("SELECT * FROM public.consultas ORDER BY data_consulta DESC", conn)
    except Exception as e: st.error(f"Erro ao carregar histórico: {e}"); return pd.DataFrame()

def carregar_logo_base64(caminho_logo):
    try:
        with open(caminho_logo, "rb") as f: return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError: return ""

def check_password():
    if st.session_state.get("admin_autenticado", False): return True
    with st.sidebar.form("admin_form"):
        st.markdown("### Acesso Restrito Admin")
        pwd = st.text_input("Senha", type="password", key="admin_pwd")
        if st.form_submit_button("Acessar"):
            if pwd == st.secrets["admin"]["password"]: 
                st.session_state.admin_autenticado = True
                st.rerun()
            else: st.sidebar.error("Senha incorreta.")
    return False

@st.cache_data(ttl=3600, show_spinner=False)
def buscar_concorrentes(p, l):
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={p} em {l}&key={API_KEY_GOOGLE}&language=pt-BR"
    response = requests.get(url)
    if response.status_code == 200: return response.json().get("results", [])
    st.error(f"Erro na API do Google: {response.status_code}. Verifique sua chave."); return []

@st.cache_data(ttl=3600, show_spinner=False)
def buscar_detalhes_lugar(pid):
    fields = "name,formatted_address,review,formatted_phone_number,website,opening_hours,rating,user_ratings_total,photos,price_level"
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={pid}&fields={fields}&key={API_KEY_GOOGLE}&language=pt-BR"
    response = requests.get(url)
    if response.status_code == 200: return response.json().get("result", {})
    return {}

def analisar_sentimentos_por_topico_ia(comentarios):
    prompt = f"""Analise os comentários de clientes: "{comentarios}". Atribua uma nota de 0 a 10 para: Atendimento, Preço, Qualidade, Ambiente, Tempo de Espera. Responda em JSON."""
    try:
        resposta = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], temperature=0.1)
        dados = json.loads(resposta.choices[0].message.content)
        base = {"Atendimento": 5, "Preço": 5, "Qualidade": 5, "Ambiente": 5, "Tempo de Espera": 5}; base.update(dados)
        return base
    except Exception as e: st.warning(f"IA de sentimentos falhou: {e}."); return {}

def enriquecer_com_ia(sentimentos, comentarios_gerais):
    prompt = f"""Com base nos seguintes dados: 1. Análise de sentimentos (notas de 0 a 10): {sentimentos}; 2. Comentários de clientes: "{comentarios_gerais}". Gere um relatório JSON com as seguintes chaves: "titulo", "slogan", "nivel_concorrencia", "sugestoes_estrategicas", "alerta_nicho", "horario_pico_inferido"."""
    try:
        resp = client.chat.completions.create(model="gpt-4-turbo-preview", response_format={"type": "json_object"}, messages=[{"role": "user", "content": prompt}])
        dados = json.loads(resp.choices[0].message.content)
        return {"titulo": dados.get("titulo", "Análise Estratégica"), "slogan": dados.get("slogan", "Insights para o seu sucesso."), "nivel": dados.get("nivel_concorrencia", "N/D"), "sugestoes": dados.get("sugestoes_estrategicas", []), "alerta": dados.get("alerta_nicho", ""), "horario_pico": dados.get("horario_pico_inferido", "Não foi possível inferir a partir dos comentários.")}
    except Exception as e:
        st.warning(f"IA de enriquecimento falhou: {e}"); return {"titulo": "Análise", "slogan": "Indisponível", "nivel": "N/D", "sugestoes": [], "alerta": "", "horario_pico": "N/A"}

def gerar_dossies_em_lote_ia(dados):
    prompt = f"""Para cada concorrente em {json.dumps(dados)}, crie um dossiê JSON: [{{"nome_concorrente": "", "arquétipo": "", "ponto_forte": "", "fraqueza_exploravel": "", "resumo_estrategico": ""}}]"""
    try:
        resp = client.chat.completions.create(model="gpt-4-turbo-preview", response_format={"type": "json_object"}, messages=[{"role": "user", "content": prompt}])
        content = json.loads(resp.choices[0].message.content)
        return next((v for k, v in content.items() if isinstance(v, list)), [])
    except Exception as e: st.warning(f"IA de dossiês falhou: {e}"); return []

def classificar_concorrentes_matriz(concorrentes):
    matriz = {"lideres_premium": [], "custo_beneficio": [], "armadilhas_valor": [], "economicos": []}
    for c in concorrentes:
        nota, preco, nome = c.get("nota"), c.get("nivel_preco"), c.get("nome")
        if nota is None or preco is None: continue
        if nota >= 4.0:
            matriz["lideres_premium" if preco >= 3 else "custo_beneficio"].append(nome)
        else:
            matriz["armadilhas_valor" if preco >= 3 else "economicos"].append(nome)
    return matriz

def gerar_grafico_radar_base64(sentimentos):
    if not sentimentos: return ""
    labels, stats = list(sentimentos.keys()), list(sentimentos.values())
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    stats += stats[:1]; angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='#007bff', alpha=0.25); ax.plot(angles, stats, color='#007bff', linewidth=2)
    ax.set_ylim(0, 10); ax.set_yticklabels([]); ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=12)
    ax.set_title("Diagnóstico de Sentimentos por Tópico", fontsize=16, y=1.1)
    buf = BytesIO(); plt.savefig(buf, format="png", bbox_inches='tight'); plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def gerar_html_relatorio(**kwargs):
    css = """<style> body { font-family: Arial, sans-serif; color: #333; } .center { text-align: center; } .report-header { padding-bottom: 20px; border-bottom: 2px solid #eee; margin-bottom: 40px; } .slogan { font-style: italic; color: #555; } .section { margin-top: 35px; page-break-inside: avoid; } h1 { color: #2c3e50; } h3 { border-bottom: 1px solid #eee; padding-bottom: 5px; color: #34495e; } h4 { color: #34495e; margin-bottom: 5px; } .alert { border: 1px solid #e74c3c; background-color: #fbecec; padding: 15px; margin-top: 20px; border-radius: 5px;} table { border-collapse: collapse; width: 100%; font-size: 12px; } th, td { border: 1px solid #ccc; padding: 8px; text-align: left; } th { background-color: #f2f2f2; } .dossier-card { border: 1px solid #ddd; padding: 15px; margin-top: 20px; page-break-inside: avoid; border-radius: 8px; background-color: #f9f9f9; } .dossier-card h4 { margin-top: 0; } .dossier-card strong { color: #3498db; } .dossier-card img { width: 100%; max-width: 400px; height: auto; border-radius: 8px; margin-bottom: 15px; } .matrix-container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; } .matrix-quadrant { border: 1px solid #eee; padding: 10px; border-radius: 5px; } ul { padding-left: 20px; } li { margin-bottom: 5px; } </style>"""
    matriz = kwargs.get("matriz_posicionamento", {})
    matriz_html = "<div class='matrix-container'>"
    quadrantes = {"lideres_premium": ("🏆 Líderes Premium", "(Qualidade Alta, Preço Alto)"), "custo_beneficio": ("🚀 Custo-Benefício", "(Qualidade Alta, Preço Acessível)"), "armadilhas_valor": ("⚠️ Armadilhas de Valor", "(Qualidade Baixa, Preço Alto)"), "economicos": ("🛒 Opções Econômicas", "(Qualidade Baixa, Preço Acessível)")}
    for chave, (titulo, subtitulo) in quadrantes.items():
        nomes = matriz.get(chave, [])
        lista_nomes = "<ul>" + "".join(f"<li>{nome}</li>" for nome in nomes) + "</ul>" if nomes else "<p>Nenhum concorrente neste quadrante.</p>"
        matriz_html += f"<div class='matrix-quadrant'><h4>{titulo}</h4><p><small>{subtitulo}</small></p>{lista_nomes}</div>"
    matriz_html += "</div>"
    dossie_html = ""
    for c in kwargs.get("concorrentes",[]):
        horarios_lista = "".join(f"<li>{h}</li>" for h in c.get('horarios', []))
        foto_tag = f'<img src="data:image/jpeg;base64,{c.get("foto_base64")}" alt="Foto de {c.get("nome")}">' if c.get("foto_base64") else "<p><small>Foto não disponível.</small></p>"
        dossie_html += f"""<div class='dossier-card'><h4>{c.get('nome')}</h4>{foto_tag}<p><strong>Nível de Preço:</strong> {c.get("nivel_preco_str", "N/A")}</p><p><strong>Arquétipo:</strong> {c.get('dossie_ia',{}).get('arquétipo','N/A')}</p><p><strong>Ponto Forte:</strong> {c.get('dossie_ia',{}).get('ponto_forte','N/A')}</p><p><strong>Fraqueza Explorável:</strong> {c.get('dossie_ia',{}).get('fraqueza_exploravel','N/A')}</p><p><strong>Resumo Estratégico:</strong> {c.get('dossie_ia',{}).get('resumo_estrategico','')}</p><h4>Horário de Funcionamento</h4><ul>{horarios_lista}</ul></div>"""
    body = f"""<html><head><meta charset='utf-8'>{css}</head><body><div class='report-header center'><img src='data:image/png;base64,{kwargs.get("base64_logo","")}' width='120'><h1>{kwargs.get("titulo")}</h1><p class='slogan'>"{kwargs.get("slogan")}"</p></div><div class='section'><h3>Diagnóstico Geral do Mercado</h3>{kwargs.get("horario_pico_inferido", "")}</div><div class='section center'><img src='data:image/png;base64,{kwargs.get("grafico_radar_b64","")}' width='500'></div><div class='section'><h3>Matriz de Posicionamento Competitivo</h3>{matriz_html}</div><div class='section'><h3>Sugestões Estratégicas</h3><ul>{''.join(f"<li>{s}</li>" for s in kwargs.get("sugestoes_estrategicas",[]))}</ul></div>{f"<div class='section alert'><h3>🚨 Alerta de Oportunidade</h3><p>{kwargs.get('alerta_nicho')}</p></div>" if kwargs.get('alerta_nicho') else ""}<div class='section' style='page-break-before: always;'><h3>Apêndice: Dossiês Estratégicos dos Concorrentes</h3>{dossie_html}</div></body></html>"""
    return body

def gerar_pdf(html):
    pdf_bytes = BytesIO(); pisa.CreatePDF(html.encode('utf-8'), dest=pdf_bytes); return pdf_bytes.getvalue()

# ... (main_app e seu conteúdo permanecem os mesmos)
def main_app():
    # ...
    
# --- TELA DE LOGIN/CADASTRO ---
def auth_page():
    st.title("Bem-vindo ao Radar Local 📡"); st.write("Faça login ou crie uma conta.")
    app_url = "https://radarlocalapp.streamlit.app"
    google_auth_url = get_google_auth_url(app_url)
    if google_auth_url:
        st.link_button("Entrar com Google", google_auth_url, use_container_width=True, type="primary")
    st.markdown("<p style='text-align: center;'>ou</p>", unsafe_allow_html=True)
    login_tab, signup_tab = st.tabs(["Login", "Cadastro"])
    with login_tab:
        with st.form("login_form", border=False):
            email = st.text_input("Email")
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                s, m = sign_in(email, pwd)
                if s: st.rerun()
                else: st.error(m)
    with signup_tab:
        with st.form("signup_form", border=False):
            email_signup = st.text_input("Email", key="signup_email")
            pwd_signup = st.text_input("Crie uma senha", type="password", key="signup_pwd")
            if st.form_submit_button("Registrar"):
                s, m = sign_up(email_signup, pwd_signup)
                if s: st.success(m)
                else: st.error(m)


# --- ROTEAMENTO FINAL E ROBUSTO ---

if 'user_session' not in st.session_state: 
    st.session_state.user_session = None

query_params = st.query_params
auth_code = query_params.get("code")

# Se houver um código de autorização na URL, processe-o
if auth_code and st.session_state.user_session is None:
    exchange_code_for_session(auth_code)
    # Limpa a URL e recarrega a página de forma segura
    st.components.v1.html(
        f"""
        <script>
            window.location.href = "{st.secrets.supabase.url.replace('.supabase.co', '.streamlit.app') if 'supabase' in st.secrets else 'https://radarlocalapp.streamlit.app'}";
        </script>
        """
    )
    st.stop()

# Verificação final para decidir qual página mostrar
if st.session_state.user_session is None:
    # Tenta obter a sessão novamente caso a página tenha sido apenas recarregada
    try:
        st.session_state.user_session = supabase.auth.get_session()
    except Exception:
        pass # Ignora erros se a API ainda não estiver pronta

# Roteamento final
if st.session_state.user_session is None:
    auth_page()
else:
    main_app()