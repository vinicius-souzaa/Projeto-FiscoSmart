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

DATA_PROC = os.path.join(ROOT, 'data', 'processed')
MODELS_DIR = os.path.join(ROOT, 'models')
DATA_RAW = os.path.join(ROOT, 'data', 'raw')
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

@st.cache_data(ttl=300)
def load():
    scores = pd.read_csv(f"{DATA_PROC}/scores_risco.csv")
    shap_v = pd.read_csv(f"{DATA_PROC}/shap_values.csv")
    feats  = pd.read_csv(f"{DATA_PROC}/features_risco.csv")
    metricas = joblib.load(f"{MODELS_DIR}/metricas_modelo.pkl")
    return scores, shap_v, feats, metricas

try:
    scores, shap_v, feats, metricas = load()
    model_loaded = True
except FileNotFoundError:
    st.error("Execute `src/model_risk.py` primeiro para gerar os scores.")
    st.stop()

st.markdown("## 🤖 Score de Risco Fiscal — Modelo XGBoost + SHAP")

# ── MÉTRICAS DO MODELO ────────────────────────────────────────────────────────
st.markdown("#### Performance do Modelo")
c1,c2,c3,c4 = st.columns(4)
c1.metric("AUC-ROC",   f'{metricas["auc_roc"]:.4f}',   "Discriminação geral")
c2.metric("Precision", f'{metricas["precision"]:.4f}',  "Precisão nas alertas")
c3.metric("Recall",    f'{metricas["recall"]:.4f}',     "Cobertura de irregulares")
c4.metric("F1-Score",  f'{metricas["f1"]:.4f}',        "Balanço P/R")

st.caption("Threshold de classificação: 0,40 · Modelo treinado em histórico de autuações")

st.markdown("---")

# ── DISTRIBUIÇÃO DOS SCORES ───────────────────────────────────────────────────
col1, col2 = st.columns([2,1])
with col1:
    st.markdown("#### Distribuição dos Scores de Risco")
    fig_hist = px.histogram(
        scores, x="score_risco", nbins=40, color="faixa_risco",
        title="Distribuição de scores por faixa de risco",
        labels={"score_risco":"Score (0–100)","count":"Nº Contribuintes"},
        color_discrete_map={"Baixo":"#1b6b3a","Médio":"#c8860a","Alto":"#9b1c1c"},
    )
    fig_hist.update_layout(plot_bgcolor="white", height=320)
    st.plotly_chart(fig_hist, use_container_width=True)

with col2:
    st.markdown("#### Por Faixa")
    faixas = scores["faixa_risco"].value_counts().reset_index()
    faixas.columns = ["Faixa","Nº"]
    fig_pie = px.pie(faixas, names="Faixa", values="Nº",
        color="Faixa",
        color_discrete_map={"Baixo":"#1b6b3a","Médio":"#c8860a","Alto":"#9b1c1c"},
    )
    fig_pie.update_layout(height=320)
    st.plotly_chart(fig_pie, use_container_width=True)

# ── SCORE POR SETOR ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Score Médio por Setor (CNAE)")
score_cnae = scores.groupby(["cnae","desc_cnae"]).agg(
    score_medio=("score_risco","mean"),
    n_alto_risco=("faixa_risco", lambda x: (x=="Alto").sum()),
    n_total=("id_contribuinte","count"),
).reset_index()
score_cnae["pct_alto"] = score_cnae["n_alto_risco"] / score_cnae["n_total"] * 100
score_cnae = score_cnae.sort_values("score_medio", ascending=False)

fig_bar = px.bar(
    score_cnae, x="score_medio", y="cnae", orientation="h",
    color="pct_alto", color_continuous_scale="RdYlGn_r",
    title="Score médio por setor — cor = % em alto risco",
    labels={"score_medio":"Score Médio","cnae":"CNAE","pct_alto":"% Alto Risco"},
    hover_data=["desc_cnae","n_total","n_alto_risco"],
)
fig_bar.update_layout(height=420, plot_bgcolor="white")
st.plotly_chart(fig_bar, use_container_width=True)

# ── SHAP GLOBAL ───────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Importância Global das Features (SHAP)")
FEAT_NAMES = {
    "shap_porte_num": "Porte da empresa",
    "shap_regime_num": "Regime tributário",
    "shap_gap_medio_pct": "Gap médio vs. declarado (%)",
    "shap_gap_std": "Variabilidade do gap",
    "shap_taxa_omissao": "Taxa de omissão",
    "shap_taxa_retificacao": "Taxa de retificação",
    "shap_cv_receita": "Coef. variação da receita",
    "shap_slope_receita_norm": "Tendência da receita",
    "shap_razao_ultimo_media": "Último mês vs. média",
    "shap_meses_sem_fiscalizacao": "Meses sem fiscalização",
    "shap_n_acoes_historicas": "Ações fiscais anteriores",
    "shap_gap_vs_bench_pct": "Gap vs. benchmark CNAE",
    "shap_n_meses_com_dados": "Meses com dados",
}
shap_cols = [c for c in shap_v.columns if c.startswith("shap_")]
shap_importance = shap_v[shap_cols].abs().mean().reset_index()
shap_importance.columns = ["feature","importancia"]
shap_importance["feature_label"] = shap_importance["feature"].map(FEAT_NAMES)
shap_importance = shap_importance.sort_values("importancia", ascending=True)

fig_shap = px.bar(
    shap_importance, x="importancia", y="feature_label", orientation="h",
    title="Importância média (|SHAP|) — quanto cada feature contribui para o score",
    labels={"importancia":"Importância média","feature_label":"Feature"},
    color="importancia", color_continuous_scale="Blues",
)
fig_shap.update_layout(height=400, plot_bgcolor="white", coloraxis_showscale=False)
st.plotly_chart(fig_shap, use_container_width=True)

# ── SHAP INDIVIDUAL ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Explicabilidade Individual — SHAP Waterfall")
st.caption("Selecione um contribuinte para ver por que ele recebeu aquele score")

col_a, col_b = st.columns([1,2])
with col_a:
    cid_sel = st.number_input("ID Contribuinte", min_value=int(scores["id_contribuinte"].min()),
                               max_value=int(scores["id_contribuinte"].max()), value=1)

sc_row = scores[scores["id_contribuinte"]==cid_sel]
sh_row = shap_v[shap_v["id_contribuinte"]==cid_sel]
fe_row = feats[feats["id_contribuinte"]==cid_sel]

if len(sc_row) > 0 and len(sh_row) > 0:
    score_val = sc_row.iloc[0]["score_risco"]
    faixa = sc_row.iloc[0]["faixa_risco"]
    cor_faixa = {"Baixo":"#1b6b3a","Médio":"#c8860a","Alto":"#9b1c1c"}.get(str(faixa),"#666")

    with col_b:
        st.markdown(f"**Score:** <span style='color:{cor_faixa};font-size:1.6rem;font-weight:700'>{score_val:.0f}/100</span> — Faixa: **{faixa}**", unsafe_allow_html=True)
        st.markdown(f"CNAE: `{sc_row.iloc[0]['cnae']}` · Porte: {sc_row.iloc[0]['porte']} · Bairro: {sc_row.iloc[0]['bairro']}")

    shap_ind = sh_row[shap_cols].iloc[0]
    shap_df = pd.DataFrame({
        "feature": shap_ind.index,
        "shap": shap_ind.values,
    })
    shap_df["label"] = shap_df["feature"].map(FEAT_NAMES)
    shap_df = shap_df.sort_values("shap")

    colors = ["#9b1c1c" if v > 0 else "#1b6b3a" for v in shap_df["shap"]]
    fig_wf = go.Figure(go.Bar(
        x=shap_df["shap"], y=shap_df["label"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.3f}" for v in shap_df["shap"]],
        textposition="outside",
    ))
    fig_wf.add_vline(x=0, line_width=1.5, line_color="#333")
    fig_wf.update_layout(
        title=f"Contribuinte #{cid_sel} — Fatores que aumentam (vermelho) ou reduzem (verde) o risco",
        plot_bgcolor="white", height=420,
        xaxis_title="Contribuição SHAP para o score",
    )
    st.plotly_chart(fig_wf, use_container_width=True)

    if len(fe_row) > 0:
        fr = fe_row.iloc[0]
        st.markdown("**Dados do contribuinte:**")
        fc1,fc2,fc3,fc4 = st.columns(4)
        fc1.metric("Gap vs. Benchmark",  f'{fr["gap_vs_bench_pct"]:.1f}%')
        fc2.metric("Taxa de Omissão",    f'{fr["taxa_omissao"]*100:.1f}%')
        fc3.metric("Meses sem Fisc.",    f'{fr["meses_sem_fiscalizacao"]:.0f}')
        fc4.metric("Receita Média 12m",  _fmt(fr["receita_media_12m"]))
else:
    st.info("Nenhum dado encontrado para este contribuinte.")

# ── TABELA TOP RISCO ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Top 30 Contribuintes por Score de Risco")
top = scores.sort_values("score_risco", ascending=False).head(30)
top["Receita Média"] = top["receita_media_12m"].apply(_fmt)
top["Score"] = top["score_risco"].apply(lambda x: f"{x:.0f}")
st.dataframe(
    top[["id_contribuinte","cnae","porte","bairro","Score","faixa_risco","gap_medio_pct","Receita Média"]]
    .rename(columns={"faixa_risco":"Faixa","gap_medio_pct":"Gap %"}),
    use_container_width=True, height=380,
)
