# main.py - v9.6 (Completo com Correção de Lógica)
# Corrige o NameError movendo a geração de HTML/PDF para depois da definição de dados_html.
# ==============================================================================

import streamlit as st
import requests
import base64
import pandas as pd
import unicodedata
import re
import json
import time
from openai import OpenAI
from datetime import datetime
from io import BytesIO
from xhtml2pdf import pisa
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from gotrue.errors import AuthApiError
from postgrest.exceptions import APIError

# --- FUNÇÃO DE SANITIZAÇÃO ---
def sanitize_value(value):
    if isinstance(value, list): return ', '.join(map(str, value))
    if isinstance(value, dict): return json.dumps(value, ensure_ascii=False)
    if value is None: return ""
    return str(value)

# --- CONFIGURAÇÕES E INICIALIZAÇÃO ---
st.set_page_config(page_title="Radar Local", page_icon="📡", layout="wide")

from auth_utils import sign_up, sign_in, sign_out, supabase

try:
    API_KEY_GOOGLE = st.secrets["google"]["api_key"]
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
except (KeyError, FileNotFoundError):
    st.error("As chaves de API não foram encontradas. Verifique seu arquivo `.streamlit/secrets.toml`."); st.stop()


# --- FUNÇÕES DE BANCO DE DADOS ATUALIZADAS ---
def salvar_historico(user_id, nome, prof, loc, titulo, slogan, nivel, alerta, storage_path):
    try:
        dados_para_inserir = {
            "user_id": user_id, "nome_usuario": nome, "tipo_negocio_pesquisado": prof, 
            "localizacao_pesquisada": loc, "nivel_concorrencia_ia": nivel, 
            "titulo_gerado_ia": titulo, "slogan_gerado_ia": slogan, 
            "alerta_oportunidade_ia": alerta, "data_consulta": datetime.now().isoformat(),
            "pdf_storage_path": storage_path
        }
        supabase.table("consultas").insert(dados_para_inserir).execute()
    except APIError as e: st.warning(f"Não foi possível salvar o histórico: {e.message}")
    except Exception as e: st.warning(f"Ocorreu um erro inesperado ao salvar histórico: {e}")

def carregar_historico_db():
    try:
        if 'user_session' in st.session_state and st.session_state.user_session:
            user_id = st.session_state.user_session.user.id
            response = supabase.table("consultas").select("*").eq("user_id", user_id).order("data_consulta", desc=True).execute()
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except APIError as e: st.error(f"Erro ao carregar histórico: {e.message}"); return pd.DataFrame()
    except Exception as e: st.error(f"Ocorreu um erro inesperado ao carregar histórico: {e}"); return pd.DataFrame()


# --- FUNÇÕES DE API EXTERNAS ---
@st.cache_data(ttl=3600)
def buscar_concorrentes(profissao, localizacao):
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={profissao} em {localizacao}&key={API_KEY_GOOGLE}&language=pt-BR"
    response = requests.get(url)
    if response.status_code == 200: return response.json().get("results", [])
    st.error(f"Erro na API do Google: {response.status_code}. Verifique sua chave.")
    return []

@st.cache_data(ttl=3600)
def buscar_detalhes_lugar(place_id):
    fields = "name,formatted_address,review,formatted_phone_number,website,opening_hours,rating,user_ratings_total,photos,price_level"
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields={fields}&key={API_KEY_GOOGLE}&language=pt-BR"
    response = requests.get(url)
    if response.status_code == 200: return response.json().get("result", {})
    return {}

@st.cache_data(ttl=3600)
def analisar_sentimentos_por_topico_ia(comentarios):
    prompt = f"""Analise os comentários de clientes: "{comentarios}". Atribua uma nota de 0 a 10 para: Atendimento, Preço, Qualidade, Ambiente, Tempo de Espera. Responda em JSON."""
    try:
        resposta = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], temperature=0.1)
        dados = json.loads(resposta.choices[0].message.content)
        base = {"Atendimento": 5, "Preço": 5, "Qualidade": 5, "Ambiente": 5, "Tempo de Espera": 5}
        base.update(dados); return base
    except Exception as e:
        st.warning(f"IA de sentimentos falhou: {e}."); return {}

@st.cache_data(ttl=3600)
def enriquecer_com_ia(sentimentos, comentarios_gerais):
    prompt = f"""Com base nos seguintes dados: 1. Análise de sentimentos (notas de 0 a 10): {sentimentos}; 2. Comentários de clientes: "{comentarios_gerais}". Gere um relatório JSON com as seguintes chaves: "titulo", "slogan", "nivel_concorrencia", "sugestoes_estrategicas", "alerta_nicho", "horario_pico_inferido"."""
    try:
        resp = client.chat.completions.create(model="gpt-4-turbo-preview", response_format={"type": "json_object"}, messages=[{"role": "user", "content": prompt}])
        dados = json.loads(resp.choices[0].message.content)
        return {"titulo": dados.get("titulo", "Análise Estratégica"), "slogan": dados.get("slogan", "Insights para o seu sucesso."), "nivel": dados.get("nivel_concorrencia", "N/D"), "sugestoes": dados.get("sugestoes_estrategicas", []), "alerta": dados.get("alerta_nicho", ""), "horario_pico": dados.get("horario_pico_inferido", "Não foi possível inferir a partir dos comentários.")}
    except Exception as e:
        st.warning(f"IA de enriquecimento falhou: {e}"); return {"titulo": "Análise", "slogan": "Indisponível", "nivel": "N/D", "sugestoes": [], "alerta": "", "horario_pico": "N/A"}

@st.cache_data(ttl=3600)
def gerar_dossies_em_lote_ia(dados):
    prompt = f"""Para cada concorrente em {json.dumps(dados)}, crie um dossiê JSON: [{{"nome_concorrente": "", "arquétipo": "", "ponto_forte": "", "fraqueza_exploravel": "", "resumo_estrategico": ""}}]"""
    try:
        resp = client.chat.completions.create(model="gpt-4-turbo-preview", response_format={"type": "json_object"}, messages=[{"role": "user", "content": prompt}])
        content = json.loads(resp.choices[0].message.content)
        return next((v for k, v in content.items() if isinstance(v, list)), [])
    except Exception as e:
        st.warning(f"IA de dossiês falhou: {e}"); return []


# --- FUNÇÕES DE PROCESSAMENTO E GERAÇÃO DE RELATÓRIO ---
def classificar_concorrentes_matriz(concorrentes):
    matriz = {"lideres_premium": [], "custo_beneficio": [], "armadilhas_valor": [], "economicos": []}
    for c in concorrentes:
        nota, preco = c.get("nota"), c.get("nivel_preco")
        if nota is None or preco is None: continue
        if nota >= 4.0: matriz["lideres_premium" if preco >= 3 else "custo_beneficio"].append(c.get("nome"))
        else: matriz["armadilhas_valor" if preco >= 3 else "economicos"].append(c.get("nome"))
    return matriz

def gerar_grafico_radar_base64(sentimentos):
    if not sentimentos: return ""
    labels, stats = list(sentimentos.keys()), list(sentimentos.values())
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    stats += stats[:1]; angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='#007bff', alpha=0.25); ax.plot(angles, stats, color='#007bff', linewidth=2)
    ax.set_ylim(0, 10); ax.set_yticklabels([])
    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=12)
    ax.set_title("Diagnóstico de Sentimentos por Tópico", fontsize=16, y=1.1)
    buf = BytesIO(); plt.savefig(buf, format="png", bbox_inches='tight'); plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def url_para_base64(url: str) -> str:
    if not url: return ""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200: return base64.b64encode(response.content).decode("utf-8")
        return ""
    except requests.RequestException: return ""

def carregar_logo_base64(caminho_logo: str) -> str:
    try:
        with open(caminho_logo, "rb") as f: return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError: return ""

def gerar_html_relatorio(**kwargs):
    CSS = """<style> body { font-family: Arial, sans-serif; color: #333333; } .center { text-align: center; } .report-header { padding-bottom: 20px; border-bottom: 2px solid #eeeeee; margin-bottom: 40px; } .slogan { font-style: italic; color: #555555; } .section { margin-top: 35px; page-break-inside: avoid; } h1 { color: #2c3e50; } h3 { border-bottom: 1px solid #eeeeee; padding-bottom: 5px; color: #34495e; } h4 { color: #34495e; margin-bottom: 5px; } .alert { border: 1px solid #e74c3c; background-color: #fbecec; padding: 15px; margin-top: 20px; border-radius: 5px; } table { border-collapse: collapse; width: 100%; font-size: 12px; } th, td { border: 1px solid #cccccc; padding: 8px; text-align: left; } th { background-color: #f2f2f2; } .dossier-card { border: 1px solid #dddddd; padding: 15px; margin-top: 20px; page-break-inside: avoid; border-radius: 8px; background-color: #f9f9f9; } .dossier-card h4 { margin-top: 0; } .dossier-card strong { color: #3498db; font-weight: bold; } .dossier-card img { width: 100%; max-width: 400px; height: auto; border-radius: 8px; margin-bottom: 15px; } .matrix-container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; } .matrix-quadrant { border: 1px solid #eeeeee; padding: 10px; border-radius: 5px; } ul { padding-left: 20px; } li { margin-bottom: 5px; } </style>"""
    matriz = kwargs.get("matriz_posicionamento", {})
    matriz_html = "<div class='matrix-container'>"
    quadrantes = {"lideres_premium": ("🏆 Líderes Premium", "(Qualidade Alta, Preço Alto)"), "custo_beneficio": ("👍 Custo-Benefício", "(Qualidade Alta, Preço Acessível)"), "armadilhas_valor": ("💀 Armadilhas de Valor", "(Qualidade Baixa, Preço Alto)"), "economicos": ("💰 Opções Econômicas", "(Qualidade Baixa, Preço Acessível)")}
    for chave, (titulo, subtitulo) in quadrantes.items():
        nomes = matriz.get(chave, [])
        lista_nomes = "<ul>" + "".join(f"<li>{sanitize_value(nome)}</li>" for nome in nomes) + "</ul>" if nomes else "<p>Nenhum concorrente neste quadrante.</p>"
        matriz_html += f"<div class='matrix-quadrant'><h4>{titulo}</h4><p><small>{subtitulo}</small></p>{lista_nomes}</div>"
    matriz_html += "</div>"
    dossie_html = ""
    for c in kwargs.get("concorrentes",[]):
        horarios_lista = "".join(f"<li>{sanitize_value(h)}</li>" for h in c.get('horarios', []))
        foto_tag = f'<img src="data:image/jpeg;base64,{c.get("foto_base64")}" alt="Foto de {sanitize_value(c.get("nome"))}">' if c.get("foto_base64") else "<p><small>Foto não disponível.</small></p>"
        dossie_html += f"""<div class='dossier-card'><h4>{sanitize_value(c.get('nome'))}</h4>{foto_tag}<p><strong>Nível de Preço:</strong> {sanitize_value(c.get("nivel_preco_str", "N/A"))}</p><p><strong>Arquétipo:</strong> {sanitize_value(c.get('dossie_ia',{}).get('arquétipo', 'N/A'))}</p><p><strong>Ponto Forte:</strong> {sanitize_value(c.get('dossie_ia',{}).get('ponto_forte','N/A'))}</p><p><strong>Fraqueza Explorável:</strong> {sanitize_value(c.get('dossie_ia', {}).get('fraqueza_exploravel','N/A'))}</p><p><strong>Resumo Estratégico:</strong> {sanitize_value(c.get('dossie_ia',{}).get('resumo_estrategico',''))}</p><h4>Horário de Funcionamento</h4><ul>{horarios_lista}</ul></div>"""
    sugestoes_html = "".join([f"<li>{sanitize_value(s)}</li>" for s in kwargs.get("sugestoes_estrategicas", [])])
    alerta_nicho = kwargs.get('alerta_nicho')
    alerta_html = f"<div class='section alert'><h3>🚨 Alerta de Oportunidade</h3><p>{sanitize_value(alerta_nicho)}</p></div>" if alerta_nicho else ""
    body = f"""<html><head><meta charset='utf-8'>{CSS}</head><body><div class='report-header center'><img src='data:image/png;base64,{kwargs.get("base64_logo","")}' width='120'><h1>{sanitize_value(kwargs.get("titulo"))}</h1><p class='slogan'>"{sanitize_value(kwargs.get("slogan"))}"</p></div><div class='section'><h3>Diagnóstico Geral do Mercado</h3>{sanitize_value(kwargs.get("horario_pico_inferido", ""))}</div><div class='section center'><img src='data:image/png;base64,{kwargs.get("grafico_radar_b64","")}' width='500'></div><div class='section'><h3>Matriz de Posicionamento Competitivo</h3>{matriz_html}</div><div class='section'><h3>Sugestões Estratégicas</h3><ul>{sugestoes_html}</ul></div>{alerta_html}<div class='section' style='page-break-before: always;'><h3>Apêndice: Dossiês Estratégicos dos Concorrentes</h3>{dossie_html}</div></body></html>"""
    return body

def gerar_pdf(html):
    pdf_bytes = BytesIO()
    pisa.CreatePDF(html.encode('utf-8'), dest=pdf_bytes)
    return pdf_bytes.getvalue()

# --- FUNÇÃO DE ADMIN ---
def check_password():
    if st.session_state.get("admin_autenticado", False): return True
    with st.sidebar.expander("🔑 Acesso Restrito Admin"):
        with st.form("admin_form"):
            pwd = st.text_input("Senha", type="password", key="admin_pwd")
            if st.form_submit_button("Acessar"):
                if pwd == st.secrets["admin"]["password"]:
                    st.session_state.admin_autenticado = True; st.rerun()
                else: st.error("Senha incorreta.")
    return False

# --- TELA DE AUTENTICAÇÃO ---
def auth_page():
    st.title("Bem-vindo ao Radar Local 📡")
    st.write("Faça login para acessar sua plataforma de inteligência de mercado ou crie uma nova conta.")
    col1, col2 = st.columns(2, gap="large")
    with col1:
        with st.form("login_form"):
            st.markdown("#### Já tem uma conta?")
            email = st.text_input("Email", key="login_email")
            pwd = st.text_input("Senha", type="password", key="login_pwd")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                with st.spinner("Verificando credenciais..."):
                    success, message = sign_in(email, pwd)
                if success: st.rerun()
                else: st.error(message)
    with col2:
        with st.form("signup_form"):
            st.markdown("#### Crie sua conta")
            email_signup = st.text_input("Seu melhor e-mail", key="signup_email")
            pwd_signup = st.text_input("Crie uma senha segura", type="password", key="signup_pwd")
            if st.form_submit_button("Registrar", use_container_width=True):
                success, message = sign_up(email_signup, pwd_signup)
                if success:
                    st.success(message)
                    st.info("📧 Enviamos um link de confirmação para o seu e-mail. Não se esqueça de verificar a caixa de spam!")
                    st.balloons()
                else: st.error(message)

# --- APLICAÇÃO PRINCIPAL ---
def main_app():
    st.sidebar.write(f"Logado como: **{st.session_state.user_session.user.email}**")
    st.sidebar.button("Sair (Logout)", on_click=sign_out, use_container_width=True)
    st.sidebar.markdown("---")
    
    st.sidebar.header("Seus Relatórios")
    df_historico = carregar_historico_db()
    if not df_historico.empty and 'pdf_storage_path' in df_historico.columns:
        for index, row in df_historico.head(10).iterrows():
            path = row['pdf_storage_path']
            if path and pd.notna(path):
                try:
                    res = supabase.storage.from_("relatorios").create_signed_url(path, 3600)
                    url_assinada = res['signedURL']
                    nome_relatorio = f"{row['tipo_negocio_pesquisado']} em {row['localizacao_pesquisada']}"
                    data_consulta = pd.to_datetime(row['data_consulta']).strftime('%d/%m/%y')
                    st.sidebar.link_button(label=f"📄 {nome_relatorio} ({data_consulta})", url=url_assinada, use_container_width=True, key=f"link_{index}")
                except Exception as e:
                    st.sidebar.caption(f"⚠️ Erro ao gerar link para '{row['tipo_negocio_pesquisado']}'")
    else:
        st.sidebar.info("Você ainda não gerou nenhum relatório.")
    st.sidebar.markdown("---")

    if check_password():
        st.sidebar.success("✅ Acesso admin concedido!")
        st.sidebar.subheader("Painel de Administrador")
    
    base64_logo = carregar_logo_base64("logo_radar_local.png")
    st.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{base64_logo}' width='120'><h1>Radar Local</h1><p>Inteligência de Mercado para Autônomos e Pequenos Negócios</p></div>", unsafe_allow_html=True)
    st.markdown("---")
    
    placeholder_formulario = st.empty()
    with placeholder_formulario.container():
        with st.form("formulario_principal"):
            st.subheader("🚀 Comece sua Análise Premium")
            c1, c2, c3 = st.columns(3)
            with c1: profissao = st.text_input("Profissão/Negócio", placeholder="Barbearia")
            with c2: localizacao = st.text_input("Cidade/Bairro", placeholder="Mooca, SP")
            with c3: nome_usuario = st.text_input("Seu Nome (p/ relatório)", value=st.session_state.user_session.user.email.split('@')[0])
            form_col1, form_col2, form_col3 = st.columns([2, 3, 2])
            with form_col2:
                enviar = st.form_submit_button("🔍 Gerar Análise Completa", use_container_width=True)

    if enviar:
        if not all([profissao, localizacao, nome_usuario]):
            st.warning("⚠️ Preencha todos os campos."); st.stop()
        
        placeholder_formulario.empty()
        
        progress_bar = st.progress(0, text="Mapeando o cenário...")
        resultados_google = buscar_concorrentes(profissao, localizacao)
        if not resultados_google:
            st.error("Nenhum concorrente encontrado. Tente uma busca mais específica."); st.stop()
        
        progress_bar.progress(0.15, text="Mapa competitivo criado! ✅"); time.sleep(1)

        concorrentes, comentarios, dados_ia = [], [], []
        locais_a_processar = resultados_google[:5]
        
        for i, lugar in enumerate(locais_a_processar):
            if not (pid := lugar.get("place_id")): continue
            progresso_atual = 0.15 + (((i + 1) / len(locais_a_processar)) * 0.40)
            progress_bar.progress(progresso_atual, text=f"Coletando inteligência de '{lugar.get('name', 'um concorrente')}'...")
            detalhes = buscar_detalhes_lugar(pid)
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

        progress_bar.progress(0.55, text="Nossa IA está decodificando a voz dos seus clientes...")
        sentimentos = analisar_sentimentos_por_topico_ia("\n".join(comentarios[:20]))
        progress_bar.progress(0.70, text="A IA Radar Local está gerando insights estratégicos...")
        insights_ia = enriquecer_com_ia(sentimentos, "\n".join(comentarios[:50]))
        progress_bar.progress(0.85, text="Cruzando dados para encontrar oportunidades únicas...")
        dossies = gerar_dossies_em_lote_ia(dados_ia)
        matriz = classificar_concorrentes_matriz(concorrentes)
        progress_bar.progress(0.90, text="Análise estratégica concluída! ✅"); time.sleep(1)
        progress_bar.progress(0.95, text="Compilando seu Dossiê de Inteligência Estratégica...")
        
        dossies_map = {d.get('nome_concorrente'): d for d in dossies}
        for c in concorrentes: c['dossie_ia'] = dossies_map.get(c['nome'], {})
        
        grafico_radar = gerar_grafico_radar_base64(sentimentos)
        
        # O dicionário dados_html é criado aqui, antes de ser usado.
        dados_html = {"base64_logo": base64_logo, "titulo": insights_ia["titulo"], "slogan": insights_ia["slogan"], "concorrentes": concorrentes, "sugestoes_estrategicas": insights_ia["sugestoes"], "alerta_nicho": insights_ia["alerta"], "grafico_radar_b64": grafico_radar, "matriz_posicionamento": matriz, "horario_pico_inferido": insights_ia["horario_pico"]}
        
        # Agora as chamadas são feitas na ordem correta.
        html_relatorio = gerar_html_relatorio(**dados_html)
        pdf_bytes = gerar_pdf(html_relatorio)
        
        if html_relatorio and pdf_bytes:
            progress_bar.progress(0.98, text="Salvando seu relatório na nuvem...")
            user_id = st.session_state.user_session.user.id
            timestamp = int(time.time())
            file_name = f"relatorio_{profissao.replace(' ', '_')}_{timestamp}.pdf"
            storage_path = f"{user_id}/{file_name}"
            
            try:
                supabase.storage.from_("relatorios").upload(path=storage_path, file=pdf_bytes, file_options={"content-type": "application/pdf"})
                salvar_historico(user_id, nome_usuario, profissao, localizacao, insights_ia["titulo"], insights_ia["slogan"], insights_ia["nivel"], insights_ia["alerta"], storage_path)
            except Exception as e:
                st.error(f"Ocorreu um erro ao salvar seu relatório: {e}"); st.stop()
            
            progress_bar.progress(1.0, text="Seu Radar Local está pronto! 🚀"); time.sleep(2)
            progress_bar.empty()
            
            st.success("✅ Análise concluída e salva com sucesso!")
            st.subheader(f"Relatório Estratégico para {profissao}")
            st.components.v1.html(html_relatorio, height=600, scrolling=True)
            st.download_button("📥 Baixar o Relatório Gerado", pdf_bytes, f"relatorio_{profissao}.pdf", "application/pdf", use_container_width=True)
        else:
            progress_bar.empty()
            st.error("❌ Desculpe, não foi possível gerar a análise. Tente usar termos mais específicos.")

# --- ROTEAMENTO E EXECUÇÃO ---
def run():
    if 'user_session' not in st.session_state: st.session_state.user_session = None
    try: st.session_state.user_session = supabase.auth.get_session()
    except Exception: st.session_state.user_session = None

    if st.session_state.user_session: main_app()
    else: auth_page()

if __name__ == "__main__":
    run()