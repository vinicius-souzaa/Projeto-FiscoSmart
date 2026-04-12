"""
FiscoSmart — Página 7: Score de Risco Fiscal
XGBoost + SHAP — explicabilidade global e individual
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import joblib, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
st.set_page_config(page_title="Score de Risco | FiscoSmart", layout="wide")

DATA_PROC  = os.path.join(ROOT, "data", "processed")
MODELS_DIR = os.path.join(ROOT, "models")
DATA_RAW   = os.path.join(ROOT, "data", "raw")
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

@st.cache_data(ttl=300)
def load():
    scores   = pd.read_csv(f"{DATA_PROC}/scores_risco.csv")
    shap_v   = pd.read_csv(f"{DATA_PROC}/shap_values.csv")
    feats    = pd.read_csv(f"{DATA_PROC}/features_risco.csv")
    metricas = joblib.load(f"{MODELS_DIR}/metricas_modelo.pkl")
    return scores, shap_v, feats, metricas

try:
    scores, shap_v, feats, metricas = load()
except FileNotFoundError:
    st.error("Execute `setup.py` primeiro para gerar os scores.")
    st.stop()

st.markdown("## 🤖 Score de Risco Fiscal — Modelo de Machine Learning")
st.info(
    "**O que é esta página?** "
    "Um modelo de inteligência artificial analisa o comportamento fiscal de cada contribuinte "
    "e atribui uma pontuação de 0 a 100 — onde 100 significa máxima probabilidade de "
    "irregularidade. O modelo foi treinado com o histórico de fiscalizações anteriores: "
    "aprendeu quais padrões de comportamento geralmente precedem uma autuação. "
    "**Por que isso é útil?** Um município tem centenas de auditores-fiscais mas milhares "
    "de contribuintes. O score permite focar o esforço de fiscalização onde a probabilidade "
    "de encontrar irregularidade é maior."
)

# ── MÉTRICAS DO MODELO ────────────────────────────────────────────────────────
st.markdown("#### ⚙️ Qualidade do Modelo")
st.caption(
    "Estas métricas mostram o quão bem o modelo consegue identificar contribuintes irregulares. "
    "Foram calculadas testando o modelo em dados que ele nunca viu durante o treinamento."
)
c1,c2,c3,c4 = st.columns(4)
c1.metric("AUC-ROC", f'{metricas["auc_roc"]:.4f}',
    help="Mede a capacidade de separar irregulares de regulares. Valor entre 0 e 1 — acima de 0.85 é considerado excelente. "
         "Significa: se sortearmos um contribuinte irregular e um regular, o modelo coloca o irregular com score maior "
         f"{metricas['auc_roc']*100:.1f}% das vezes.")
c2.metric("Precision", f'{metricas["precision"]:.4f}',
    help="De todos os contribuintes que o modelo classificou como 'alto risco', quantos % realmente têm irregularidade? "
         "Precision alta = menos fiscalizações desnecessárias.")
c3.metric("Recall", f'{metricas["recall"]:.4f}',
    help="De todos os contribuintes que REALMENTE têm irregularidade, quantos % o modelo identificou? "
         "Recall alto = o modelo não deixa muitos sonegadores passarem despercebidos.")
c4.metric("F1-Score", f'{metricas["f1"]:.4f}',
    help="Média harmônica entre Precision e Recall. Resume o desempenho geral do modelo em um único número.")

with st.expander("📖 Como interpretar AUC-ROC, Precision e Recall?"):
    st.markdown("""
    Imagine 100 contribuintes sendo analisados pelo modelo: 30 são irregulares e 70 são regulares.

    **AUC-ROC 0,96** significa que em 96% das vezes, quando o modelo compara um irregular com um regular,
    ele dá ao irregular um score mais alto. É como se o modelo tivesse 96% de "faro" para achar o problema.

    **Precision 0,47** significa que de cada 10 contribuintes que o modelo alerta como "alto risco",
    cerca de 5 realmente têm irregularidade. Os outros 5 serão fiscalizados e encontrados regulares.
    Isso é aceitável — o custo de fiscalizar um regular é menor que o custo de deixar um irregular passar.

    **Recall 0,83** significa que o modelo captura 83% de todos os irregulares.
    Apenas 17% passam despercebidos. Para fins de arrecadação, Recall alto é mais importante que Precision alta.
    """)

st.markdown("---")

# ── DISTRIBUIÇÃO DOS SCORES ───────────────────────────────────────────────────
col1, col2 = st.columns([2,1])
with col1:
    st.markdown("#### 📊 Distribuição dos Scores")
    st.caption(
        "**Como ler:** o histograma mostra quantos contribuintes têm cada nível de score. "
        "**Verde (0–40) = baixo risco** — contribuintes com comportamento fiscal regular. "
        "**Amarelo (40–70) = médio risco** — merecem atenção mas não são prioridade imediata. "
        "**Vermelho (70–100) = alto risco** — principais candidatos à fiscalização. "
        "A maioria das empresas honesta fica concentrada na faixa verde."
    )
    fig_h = px.histogram(scores, x="score_risco", nbins=40, color="faixa_risco",
        color_discrete_map={"Baixo":"#1b6b3a","Médio":"#c8860a","Alto":"#9b1c1c"},
        labels={"score_risco":"Score (0–100)","count":"Nº Contribuintes"})
    fig_h.update_layout(plot_bgcolor="white", height=320)
    st.plotly_chart(fig_h, use_container_width=True)

with col2:
    st.markdown("#### Por Faixa")
    faixas = scores["faixa_risco"].value_counts().reset_index()
    faixas.columns = ["Faixa","Nº"]
    fig_p = px.pie(faixas, names="Faixa", values="Nº", hole=0.4,
        color="Faixa",
        color_discrete_map={"Baixo":"#1b6b3a","Médio":"#c8860a","Alto":"#9b1c1c"})
    fig_p.update_layout(height=320)
    st.plotly_chart(fig_p, use_container_width=True)

# ── SHAP GLOBAL ───────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 🔬 O Que Mais Influencia o Score? (SHAP Global)")
st.info(
    "**O que é SHAP?** É uma técnica matemática (baseada em teoria dos jogos) que explica "
    "por que o modelo deu determinado score a cada contribuinte. "
    "O gráfico abaixo mostra quais informações sobre o contribuinte mais importam para o modelo "
    "na hora de calcular o risco. **Barras maiores = mais influência no score.** "
    "Isso transforma o modelo de uma 'caixa preta' em algo transparente e auditável — "
    "fundamental no contexto fiscal, onde o auditor precisa justificar cada autuação."
)

FEAT_LABELS = {
    "shap_porte_num": "Porte da empresa",
    "shap_regime_num": "Regime tributário",
    "shap_gap_medio_pct": "Gap médio declarado (%)",
    "shap_gap_std": "Instabilidade do gap",
    "shap_taxa_omissao": "Taxa de omissão de declarações",
    "shap_taxa_retificacao": "Frequência de retificações",
    "shap_cv_receita": "Variabilidade da receita",
    "shap_slope_receita_norm": "Tendência da receita (crescimento/queda)",
    "shap_razao_ultimo_media": "Último mês vs. média histórica",
    "shap_meses_sem_fiscalizacao": "Tempo sem ser fiscalizado",
    "shap_n_acoes_historicas": "Histórico de ações fiscais",
    "shap_gap_vs_bench_pct": "Gap vs. benchmark do setor",
    "shap_n_meses_com_dados": "Regularidade de entregas",
}

shap_cols = [c for c in shap_v.columns if c.startswith("shap_")]
imp = shap_v[shap_cols].abs().mean().reset_index()
imp.columns = ["feature","importancia"]
imp["label"] = imp["feature"].map(FEAT_LABELS)
imp = imp.sort_values("importancia", ascending=True)

fig_s = px.bar(imp, x="importancia", y="label", orientation="h",
    color="importancia", color_continuous_scale="Blues",
    labels={"importancia":"Importância média (|SHAP|)","label":"Fator de risco"})
fig_s.update_layout(height=400, plot_bgcolor="white", coloraxis_showscale=False)
st.plotly_chart(fig_s, use_container_width=True)

st.caption(
    "💡 **Interpretação:** 'Gap vs. benchmark do setor' e 'Taxa de omissão' são os fatores "
    "que mais separam contribuintes regulares de irregulares. Faz sentido: quem declara muito "
    "abaixo da média do setor E não entrega declarações com frequência é o perfil clássico "
    "de sonegação detectado pela auditoria fiscal."
)

# ── SHAP INDIVIDUAL ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 🔍 Explicação Individual — Por que este contribuinte tem este score?")
st.info(
    "**Como usar:** selecione um contribuinte pelo ID. O gráfico mostra exatamente quais "
    "fatores aumentaram ou reduziram o score dele. "
    "**Barras vermelhas** = fatores que aumentam o risco (sinal de alerta). "
    "**Barras verdes** = fatores que reduzem o risco (comportamento positivo). "
    "Esta explicação pode ser usada pelo auditor para fundamentar a seleção do contribuinte "
    "para fiscalização — substituindo o critério subjetivo por evidência objetiva."
)

col_a, col_b = st.columns([1,2])
with col_a:
    cid = st.number_input("ID Contribuinte", min_value=int(scores["id_contribuinte"].min()),
                           max_value=int(scores["id_contribuinte"].max()), value=1)

sc_row = scores[scores["id_contribuinte"]==cid]
sh_row = shap_v[shap_v["id_contribuinte"]==cid]
fe_row = feats[feats["id_contribuinte"]==cid]

if len(sc_row) > 0 and len(sh_row) > 0:
    score_val = sc_row.iloc[0]["score_risco"]
    faixa = str(sc_row.iloc[0]["faixa_risco"])
    cor = {"Baixo":"#1b6b3a","Médio":"#c8860a","Alto":"#9b1c1c"}.get(faixa,"#666")

    with col_b:
        st.markdown(
            f"**Score:** <span style='color:{cor};font-size:1.6rem;font-weight:700'>"
            f"{score_val:.0f}/100</span> — Faixa: **{faixa}**",
            unsafe_allow_html=True)
        st.markdown(
            f"CNAE: `{sc_row.iloc[0]['cnae']}` · "
            f"Porte: {sc_row.iloc[0]['porte']} · "
            f"Bairro: {sc_row.iloc[0]['bairro']}")

    shap_ind = sh_row[shap_cols].iloc[0]
    shap_df = pd.DataFrame({"feature":shap_ind.index,"shap":shap_ind.values})
    shap_df["label"] = shap_df["feature"].map(FEAT_LABELS)
    shap_df = shap_df.sort_values("shap")
    colors = ["#9b1c1c" if v > 0 else "#1b6b3a" for v in shap_df["shap"]]

    fig_w = go.Figure(go.Bar(
        x=shap_df["shap"], y=shap_df["label"], orientation="h",
        marker_color=colors,
        text=[f"{v:+.3f}" for v in shap_df["shap"]], textposition="outside"))
    fig_w.add_vline(x=0, line_width=1.5, line_color="#333")
    fig_w.update_layout(
        title=f"Contribuinte #{cid} — Fatores que aumentam (vermelho) e reduzem (verde) o risco",
        plot_bgcolor="white", height=420,
        xaxis_title="Contribuição SHAP para o score (positivo = aumenta risco)")
    st.plotly_chart(fig_w, use_container_width=True)

    if len(fe_row) > 0:
        fr = fe_row.iloc[0]
        st.markdown("**Dados do contribuinte:**")
        fc1,fc2,fc3,fc4 = st.columns(4)
        fc1.metric("Gap vs. Benchmark",   f'{fr["gap_vs_bench_pct"]:.1f}%',
            help="Quanto este contribuinte declara abaixo da média do seu setor. Acima de 30% é suspeito.")
        fc2.metric("Taxa de Omissão",     f'{fr["taxa_omissao"]*100:.1f}%',
            help="% de meses em que não entregou declaração.")
        fc3.metric("Meses sem Fisc.",     f'{fr["meses_sem_fiscalizacao"]:.0f}',
            help="Há quantos meses este contribuinte não é fiscalizado.")
        fc4.metric("Receita Média 12m",   _fmt(fr["receita_media_12m"]),
            help="Média da receita declarada nos últimos 12 meses.")
else:
    st.info("Contribuinte não encontrado.")

# Top riscos
st.markdown("---")
st.markdown("#### 📋 Top 30 Contribuintes por Score de Risco")
st.caption(
    "Lista dos 30 contribuintes com maior score. Para a lista completa com "
    "cálculo de retorno esperado por fiscalização, acesse a página **Priorização Fiscal**."
)
top = scores.sort_values("score_risco", ascending=False).head(30).copy()
top["Score"] = top["score_risco"].apply(lambda x: f"{x:.0f}")
top["Receita Média"] = top["receita_media_12m"].apply(_fmt)
st.dataframe(
    top[["id_contribuinte","cnae","porte","bairro","Score","faixa_risco","gap_medio_pct","Receita Média"]]
    .rename(columns={"faixa_risco":"Faixa","gap_medio_pct":"Gap %"}),
    use_container_width=True, height=380)
