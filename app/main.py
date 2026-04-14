"""
FiscoSmart — Dashboard Principal
Detecta automaticamente se precisa rodar o setup e executa antes de abrir.
"""
import streamlit as st
import sys, os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

st.set_page_config(
    page_title="FiscoSmart — Inteligência Tributária Municipal",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
div[data-testid="metric-container"] {
    background: rgba(26,79,130,0.06);
    border-radius: 8px;
    padding: 12px 16px;
    border-left: 3px solid #1a4f82;
}
.block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ── AUTO-SETUP ────────────────────────────────────────────────────────────────
SCORES_PATH   = os.path.join(ROOT, "data", "processed", "scores_risco.csv")
FORECAST_PATH = os.path.join(ROOT, "data", "processed", "forecast_arrecadacao.csv")
INSIGHTS_PATH = os.path.join(ROOT, "data", "processed", "insights_latest.json")

def precisa_setup():
    return not all(os.path.exists(p) for p in [SCORES_PATH, FORECAST_PATH, INSIGHTS_PATH])

def rodar_setup():
    from src.generate_data      import main as gerar_dados
    from src.feature_engineering import build_features
    from src.model_risk          import treinar_modelo
    from src.forecasting         import rodar_forecasting
    from src.insights_engine     import InsightsEngine

    os.makedirs(os.path.join(ROOT, "data", "processed"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)

    gerar_dados()
    build_features()
    treinar_modelo()
    rodar_forecasting()

    engine   = InsightsEngine()
    insights = engine.todos_insights()
    with open(INSIGHTS_PATH, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2, default=str)

if precisa_setup():
    st.markdown("## 🏛️ FiscoSmart")
    bar = st.progress(0, text="Iniciando pipeline...")
    etapas = [
        (10, "Gerando dados sintéticos (ISS, IPTU, ITBI, Taxas, DA)..."),
        (35, "Construindo features de risco fiscal..."),
        (55, "Treinando modelo XGBoost + SHAP..."),
        (75, "Gerando previsões Prophet (6 meses)..."),
        (90, "Calculando insights automáticos..."),
        (100, "Concluído!"),
    ]
    try:
        from src.generate_data       import main as gerar_dados
        from src.feature_engineering import build_features
        from src.model_risk           import treinar_modelo
        from src.forecasting          import rodar_forecasting
        from src.insights_engine      import InsightsEngine

        os.makedirs(os.path.join(ROOT, "data", "processed"), exist_ok=True)
        os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)

        bar.progress(10, text=etapas[0][1]); gerar_dados()
        bar.progress(35, text=etapas[1][1]); build_features()
        bar.progress(55, text=etapas[2][1]); treinar_modelo()
        bar.progress(75, text=etapas[3][1]); rodar_forecasting()
        bar.progress(90, text=etapas[4][1])

        engine   = InsightsEngine()
        insights = engine.todos_insights()
        with open(INSIGHTS_PATH, "w", encoding="utf-8") as f:
            json.dump(insights, f, ensure_ascii=False, indent=2, default=str)

        bar.progress(100, text=etapas[5][1])
        st.success("✅ Pipeline concluída! O dashboard está pronto.")
        st.rerun()

    except Exception as e:
        st.error(f"Erro durante o setup: {e}")
        st.exception(e)
        st.stop()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏛️ FiscoSmart")
    st.markdown("**Inteligência Tributária Municipal**")
    st.markdown("---")
    st.markdown("**Município:** São Vicente — SP")
    st.markdown("**Dados:** Sintéticos · 36 meses")
    st.markdown("**Pipeline:** GitHub Actions · mensal")
    st.markdown("---")

    # Métricas rápidas na sidebar
    try:
        import joblib
        m = joblib.load(os.path.join(ROOT, "models", "metricas_modelo.pkl"))
        st.markdown("**Modelo de Risco**")
        st.caption(f"AUC-ROC: `{m['auc_roc']}`")
        st.caption(f"Recall: `{m['recall']}`")
        st.caption(f"F1: `{m['f1']}`")
        st.markdown("---")
    except Exception:
        pass

    # Insights na sidebar
    try:
        with open(INSIGHTS_PATH, encoding="utf-8") as f:
            insights = json.load(f)
        altas = [i for i in insights if i.get("severidade") == "alta"]
        if altas:
            st.markdown(f"**⚠️ {len(altas)} alertas ativos**")
            for ins in altas[:2]:
                st.error(f"**{ins['titulo']}**\n\n{ins['texto'][:120]}...")
    except Exception:
        pass

    st.markdown("---")
    st.caption("Portfólio · Data Analytics\nVinicius · 2026")

# ── HOME ──────────────────────────────────────────────────────────────────────
st.markdown("## 🏛️ FiscoSmart — Inteligência Tributária Municipal")
st.markdown(
    "Dashboard de análise fiscal para municípios brasileiros. "
    "Cobre ISS, IPTU, ITBI, Taxas, COSIP, Contribuição de Melhoria e Dívida Ativa. "
    "Modelo XGBoost com explicabilidade SHAP + previsão Prophet."
)

# KPIs de status
try:
    import pandas as pd
    decl  = pd.read_csv(os.path.join(ROOT, "data", "raw", "declaracoes_iss.csv"))
    imoveis = pd.read_csv(os.path.join(ROOT, "data", "raw", "imoveis.csv"))
    da    = pd.read_csv(os.path.join(ROOT, "data", "raw", "divida_ativa.csv"))
    scores = pd.read_csv(SCORES_PATH)

    _fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("ISS Arrecadado (36m)",  _fmt(decl["iss_recolhido"].sum()))
    c2.metric("IPTU Arrecadado",       _fmt(imoveis["iptu_pago"].sum()))
    c3.metric("Dívida Ativa",          _fmt(da["valor_total"].sum()))
    c4.metric("Contribuintes Alto Risco",
              f'{(scores["faixa_risco"]=="Alto").sum():,}',
              f'de {len(scores):,} analisados')
except Exception:
    st.info("Dados carregando...")

st.markdown("---")

# Cards de navegação
st.markdown("### Módulos do sistema")
modulos = [
    ("📊", "Visão Geral",           "KPIs consolidados de todos os tributos e transferências"),
    ("🔍", "Diagnóstico ISS",       "Gap por setor, omissões, sazonalidade, radar por contribuinte"),
    ("🏠", "Diagnóstico IPTU",      "Inadimplência por bairro, Pareto, isenções irregulares"),
    ("📋", "Diagnóstico ITBI",      "Subavaliação de base de cálculo, transações suspeitas"),
    ("💰", "Taxas e COSIP",         "Alvará, coleta de lixo, iluminação pública, contribuição de melhoria"),
    ("⚖️", "Dívida Ativa",          "Aging, Pareto, taxa de recuperação, simulador REFIS"),
    ("🤖", "Score de Risco",        "XGBoost + SHAP global e waterfall individual por contribuinte"),
    ("📈", "Previsão",              "Prophet por tributo — próximos 6 meses com IC 95% e gap de meta"),
    ("🎯", "Priorização Fiscal",    "Ranking de retorno esperado, simulador top-N, exportação CSV"),
    ("🗂️", "Ficha do Contribuinte", "Histórico completo + score + notificação fiscal (PDF)"),
    ("🗺️", "Mapa de Risco",         "Heatmap geoespacial por bairro — ISS, IPTU, potencial de cobrança"),
    ("📊", "Benchmark Municipal",   "Comparativo de São Vicente vs. municípios pares do litoral paulista"),
    ("🔍", "Auditoria de Isenções", "Revisão periódica de isenções IPTU — priorização por risco"),
    ("🏛️", "Painel Executivo",      "Visão de alto nível para o Secretário de Finanças"),
]
cols = st.columns(3)
for i, (icon, titulo, desc) in enumerate(modulos):
    with cols[i % 3]:
        st.markdown(f"**{icon} {titulo}**")
        st.caption(desc)
        st.markdown("---")
