# main.py - v6.5 (Final com Login Google Funcional)
# ========================================================================

import streamlit as st
import requests
from openai import OpenAI
from datetime import datetime
import base64
import pandas as pd
from io import BytesIO
import unicodedata
import re
import json
from xhtml2pdf import pisa
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import psycopg2
import time

# --- CONFIGURAÇÕES E INICIALIZAÇÃO ---
st.set_page_config(page_title="Radar Local", page_icon="📡", layout="wide")

try:
    API_KEY_GOOGLE = st.secrets["google"]["api_key"]
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
except (KeyError, FileNotFoundError):
    st.error("As chaves de API não foram encontradas. Verifique a localização e o conteúdo do seu arquivo `.streamlit/secrets.toml`.")
    st.stop()

# ATUALIZAÇÃO: Importa a nova função 'get_google_auth_url'
from auth_utils import sign_up, sign_in, sign_out, supabase, get_google_auth_url

# ==============================================================================
# --- DEFINIÇÃO DE TODAS AS FUNÇÕES AUXILIARES ---
# ==============================================================================

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

def main_app():
    st.sidebar.write(f"Logado como: **{st.session_state.user_session.user.email}**"); st.sidebar.button("Logout", on_click=sign_out, use_container_width=True); st.sidebar.markdown("---")
    base64_logo = carregar_logo_base64("logo_radar_local.png")
    st.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{base64_logo}' width='120'><h1>Radar Local</h1><p>Inteligência de Mercado para Autônomos e Pequenos Negócios</p></div>", unsafe_allow_html=True); st.markdown("---")
    placeholder_formulario = st.empty()
    with placeholder_formulario.container():
        with st.form("formulario_principal"):
            st.subheader("🚀 Comece sua Análise Premium"); c1, c2, c3 = st.columns(3)
            with c1: profissao = st.text_input("Profissão/Negócio", placeholder="Barbearia")
            with c2: localizacao = st.text_input("Cidade/Bairro", placeholder="Mooca, SP")
            with c3: nome_usuario = st.text_input("Seu Nome (p/ relatório)", value=st.session_state.user_session.user.email.split('@')[0])
            enviar = st.form_submit_button("🔍 Gerar Análise Completa")

    if enviar:
        placeholder_formulario.empty()
        if not all([profissao, localizacao, nome_usuario]): 
            st.warning("⚠️ Preencha todos os campos."); st.stop()
        col1, col2 = st.columns([0.1, 0.9], gap="small")
        progress_bar = col2.progress(0, text="Conectando aos nossos sistemas...")
        with col1:
            st.spinner("")
            time.sleep(1)
            progress_bar.progress(0.01, text="Mapeando o cenário competitivo na sua região...")
            resultados_google = buscar_concorrentes(profissao, localizacao)
            if not resultados_google: 
                col1.empty(); col2.empty()
                st.error("Nenhum concorrente encontrado. Tente uma busca mais específica."); st.stop()
            progress_bar.progress(0.15, text="Mapa competitivo criado! ✅"); time.sleep(1.5)
            concorrentes, comentarios, dados_ia = [], [], []
            locais_a_processar = resultados_google[:5]
            etapa2_inicio, etapa2_peso = 0.15, 0.35
            for i, lugar in enumerate(locais_a_processar):
                if not (pid := lugar.get("place_id")): continue
                detalhes = buscar_detalhes_lugar(pid)
                progresso_atual = etapa2_inicio + (((i + 1) / len(locais_a_processar)) * etapa2_peso)
                progress_bar.progress(progresso_atual, text=f"Coletando inteligência de '{detalhes.get('name', 'um concorrente')}'...")
                foto_ref = detalhes.get('photos', [{}])[0].get('photo_reference')
                foto_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={foto_ref}&key={API_KEY_GOOGLE}" if foto_ref else ""
                foto_base64 = url_para_base64(foto_url)
                niveis_preco = {1: "$ (Barato)", 2: "$$ (Moderado)", 3: "$$$ (Caro)", 4: "$$$$ (Muito Caro)"}
                nivel_preco_int = detalhes.get("price_level")
                nivel_preco_str = niveis_preco.get(nivel_preco_int, "N/A")
                horarios = detalhes.get('opening_hours', {}).get('weekday_text', ['Horário não informado'])
                reviews = [r.get("text", "") for r in detalhes.get("reviews", []) if r.get("text")]
                comentarios.extend(reviews)
                concorrentes.append({"nome": detalhes.get("name"), "nota": detalhes.get("rating"), "total_avaliacoes": detalhes.get("user_ratings_total"), "site": detalhes.get("website"), "foto_base64": foto_base64, "nivel_preco": nivel_preco_int, "nivel_preco_str": nivel_preco_str, "horarios": horarios, "dossie_ia": {}})
                dados_ia.append({"nome_concorrente": detalhes.get("name"), "comentarios": " ".join(reviews[:5])})
                time.sleep(0.3)
            progress_bar.progress(0.55, text="Nossa IA está decodificando a voz dos seus clientes...")
            sentimentos = analisar_sentimentos_por_topico_ia("\n".join(comentarios[:20]))
            progress_bar.progress(0.70, text="A IA Radar Local está gerando insights estratégicos...")
            insights_ia = enriquecer_com_ia(sentimentos, "\n".join(comentarios[:50]))
            progress_bar.progress(0.85, text="Cruzando dados para encontrar oportunidades únicas...")
            dossies = gerar_dossies_em_lote_ia(dados_ia)
            matriz = classificar_concorrentes_matriz(concorrentes)
            progress_bar.progress(0.90, text="Análise estratégica concluída! ✅"); time.sleep(1.5)
            progress_bar.progress(0.95, text="Compilando seu Dossiê de Inteligência Estratégica...")
            dossies_map = {d.get('nome_concorrente'): d for d in dossies}
            for c in concorrentes: c['dossie_ia'] = dossies_map.get(c['nome'], {})
            grafico_radar = gerar_grafico_radar_base64(sentimentos)
            dados_html = {"base64_logo": base64_logo, "titulo": insights_ia["titulo"], "slogan": insights_ia["slogan"], "concorrentes": concorrentes, "sugestoes_estrategicas": insights_ia["sugestoes"], "alerta_nicho": insights_ia["alerta"], "grafico_radar_b64": grafico_radar, "matriz_posicionamento": matriz, "horario_pico_inferido": insights_ia["horario_pico"]}
            html_relatorio = gerar_html_relatorio(**dados_html)
            pdf_bytes = gerar_pdf(html_relatorio)
            salvar_historico(nome_usuario, profissao, localizacao, insights_ia["titulo"], insights_ia["slogan"], insights_ia["nivel"], insights_ia["alerta"])
            progress_bar.progress(1.0, text="Seu Radar Local está pronto! 🚀"); time.sleep(2)
        col1.empty(); col2.empty()
        st.success("✅ Análise concluída!")
        st.subheader(f"📄 Relatório Estratégico para {profissao}")
        st.components.v1.html(html_relatorio, height=600, scrolling=True)
        if pdf_bytes: st.download_button("⬇️ Baixar Relatório", pdf_bytes, f"relatorio_{profissao}.pdf", "application/pdf")

    st.markdown("---")
    if check_password():
        st.sidebar.success("✅ Acesso admin concedido!")
        st.subheader("📊 Painel de Administrador")
        df = carregar_historico_db()
        if not df.empty:
            st.markdown("#### Análise Rápida"); c1, c2 = st.columns(2)
            with c1: st.write("**Negócios + Pesquisados:**"); st.bar_chart(df['tipo_negocio_pesquisado'].value_counts())
            with c2: st.write("**Localizações + Pesquisadas:**"); st.bar_chart(df['localizacao_pesquisada'].value_counts())
            with st.expander("Ver Histórico Completo"): st.dataframe(df)
        else: st.info("Histórico de consultas vazio.")

    # --- ATUALIZAÇÃO FINAL: TELA DE LOGIN/CADASTRO ---

# main.py

# ... (outras funções) ...

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
                if s: 
                    st.rerun()
                else: 
                    st.error(m)
    
    with signup_tab:
        with st.form("signup_form", border=False): # <- Garante que só há um deste
            email_signup = st.text_input("Email", key="signup_email")
            pwd_signup = st.text_input("Crie uma senha", type="password", key="signup_pwd")
            if st.form_submit_button("Registrar"):
                s, m = sign_up(email_signup, pwd_signup)
                if s: 
                    st.success(m)
                else: 
                    st.error(m)


# --- ATUALIZAÇÃO: ROTEAMENTO INTELIGENTE ---

# main.py

# ... (todo o código do main.py antes disso) ...

# --- ATUALIZAÇÃO FINAL: ROTEAMENTO ROBUSTO SEM LOOP ---

# 1. Inicializa a sessão se ela não existir.
if 'user_session' not in st.session_state: 
    st.session_state['user_session'] = None

# 2. Verifica se a sessão já existe (útil para usuários que voltam ao site)
if st.session_state.user_session is None:
    try:
        current_session = supabase.auth.get_session()
        if current_session:
            st.session_state.user_session = current_session
    except Exception:
        pass

# 3. Lógica para quando o usuário VOLTA do login com Google
query_params = st.query_params
if query_params.get("code"):
    # Se o 'code' está na URL, significa que o login com Google foi um sucesso.
    # O Supabase.js no navegador já cuidou da sessão.
    # Nós precisamos apenas limpar a URL e recarregar a página.
    
    st.write("Autenticando com o Google, um momento...") # Mensagem para o usuário
    
    # Executa um script JavaScript para recarregar a página na sua URL base.
    js_code = f"""
        <script>
            window.location.href = "{st.secrets.supabase.url.replace('.supabase.co', '.streamlit.app')}";
        </script>
    """
    st.components.v1.html(js_code)
    st.stop() # Interrompe a execução do script para evitar mostrar a página de login

# 4. Verificação final para decidir qual página mostrar
if st.session_state.user_session is None: 
    auth_page()
else: 
    main_app()