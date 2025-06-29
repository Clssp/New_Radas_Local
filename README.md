# Radar Pro 🚀

### Inteligência de Mercado para Negócios Locais, Automatizada.

Radar Pro é uma aplicação web desenvolvida em Python e Streamlit, projetada para ser uma ferramenta de inteligência de mercado para agências e consultores. A plataforma automatiza a coleta e análise de dados de negócios locais, fornecendo insights estratégicos, análise de concorrência, perfil demográfico e planos de ação gerados por IA.

---

## ✨ Funcionalidades Principais

*   **📊 Dashboard Intuitivo:** Gerencie múltiplos "mercados" (ex: "Padaria" em "Vila Prudente, SP") a partir de um painel de controle central.
*   **🤖 Análise Completa Automatizada:** Com um clique, o sistema busca concorrentes no Google Maps, coleta detalhes (reviews, notas) e usa a IA do **Google Gemini** para gerar relatórios completos.
*   **💡 Insights Gerados por IA:** A análise inclui:
    *   Sumário Executivo e Plano de Ação Estratégico.
    *   Análise de Sentimentos com base nas avaliações dos concorrentes.
    *   Perfil Demográfico detalhado do público-alvo.
    *   Dossiês individuais para cada concorrente.
*   **🗺️ Mapa de Concorrência Interativo:** Visualize a localização geográfica de todos os concorrentes mapeados em um mapa interativo.
*   **📈 Tendências de Mercado:** Gráficos do Google Trends para o termo de busca, mostrando a evolução do interesse ao longo do tempo.
*   **🗂️ Histórico de Análises (Snapshots):** Todas as análises são salvas como "snapshots", permitindo comparar a evolução dos KPIs (Key Performance Indicators) de um mercado ao longo do tempo.

---

## 🛠️ Tecnologias Utilizadas

*   **Frontend:** [Streamlit](https://streamlit.io/)
*   **Backend & Banco de Dados:** [Supabase](https://supabase.com/) (Autenticação, PostgreSQL DB, Storage)
*   **Inteligência Artificial:** [Google Gemini API](https://ai.google.dev/)
*   **Dados de Mercado:**
    *   [Google Maps Platform API](https://developers.google.com/maps)
    *   [Google Trends](https://trends.google.com/) (via `pytrends`)
*   **Linguagem:** Python

---

## 🚀 Como Executar o Projeto Localmente

**1. Clone o Repositório:**
``````bash
git clone https://github.com/Clssp/New_Radas_Local.git
cd New_Radas_Local