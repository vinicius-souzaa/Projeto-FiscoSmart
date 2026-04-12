"""
FiscoSmart — Página 9: Priorização Fiscal
Ranking de retorno esperado + simulador + exportação
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys, os, io
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
st.set_page_config(page_title="Priorização Fiscal | FiscoSmart", layout="wide")

DATA_PROC = os.path.join(ROOT, 'data', 'processed')
DATA_RAW = os.path.join(ROOT, 'data', 'raw')
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

@st.cache_data(ttl=300)
def load():
    scores  = pd.read_csv(f"{DATA_PROC}/scores_risco.csv")
    feats   = pd.read_csv(f"{DATA_PROC}/features_risco.csv")
    acoes   = pd.read_csv(f"{DATA_RAW}/acoes_fiscais.csv")
    contribs= pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
    return scores, feats, acoes, contribs

try:
    scores, feats, acoes, contribs = load()
except FileNotFoundError:
    st.error("Execute `src/model_risk.py` antes de usar esta página.")
    st.stop()

# ── CALCULAR RANKING ──────────────────────────────────────────────────────────
df = scores.merge(feats[["id_contribuinte","taxa_omissao","cv_receita","slope_receita_norm",
                          "meses_sem_fiscalizacao","gap_vs_bench_pct"]], on="id_contribuinte", how="left")

# Custo estimado de fiscalização por porte
custo_mapa = {"MEI":500,"ME":1200,"EPP":2500,"MD":5000,"GR":12000}
df["custo_fisc"] = df["porte"].map(custo_mapa).fillna(1500)

# Valor potencial de recuperação mensal
df["valor_potencial"] = (
    df["receita_media_12m"] * df["gap_vs_bench_pct"].clip(0,100) / 100 * df["aliquota"]
    if "aliquota" in df.columns else
    df["receita_media_12m"] * df["gap_vs_bench_pct"].clip(0,100) / 100 * 0.03
)
# Usar ISS alíquotas do mapeamento
aliq_map = {
    "6201-5":0.03,"6202-3":0.03,"7490-1":0.03,"8599-6":0.02,
    "5611-2":0.03,"5620-1":0.03,"4120-4":0.02,"4330-4":0.02,
    "8630-5":0.02,"8650-0":0.02,"6911-7":0.05,"6920-6":0.03,
    "7711-0":0.03,"9602-5":0.02,"8511-2":0.02,"8512-1":0.02,
    "4771-7":0.03,"5310-5":0.02,"9311-5":0.03,"4921-3":0.02,
}
df["aliquota_cnae"] = df["cnae"].map(aliq_map).fillna(0.03)
df["valor_potencial"] = df["receita_media_12m"] * df["gap_vs_bench_pct"].clip(0,100) / 100 * df["aliquota_cnae"]

# Índice de retorno esperado
df["retorno_esperado"] = (
    df["valor_potencial"] * (df["score_risco"] / 100)
) / df["custo_fisc"].clip(lower=100)

# Última fiscalização
ult_fisc = acoes.groupby("id_contribuinte")["data_acao"].max().reset_index().rename(columns={"data_acao":"ultima_fiscalizacao"})
df = df.merge(ult_fisc, on="id_contribuinte", how="left")
df["ultima_fiscalizacao"] = df["ultima_fiscalizacao"].fillna("Nunca")

# Ranking final
ranking = df.sort_values("retorno_esperado", ascending=False).reset_index(drop=True)
ranking["posicao"] = ranking.index + 1

# ── INTERFACE ─────────────────────────────────────────────────────────────────
st.markdown("## 🎯 Priorização da Fiscalização Tributária")
st.caption(
    "O índice de retorno esperado combina: Score de Risco (probabilidade de irregularidade) × "
    "Valor Potencial de Recuperação ÷ Custo Estimado da Ação Fiscal"
)

# ── FILTROS ───────────────────────────────────────────────────────────────────
with st.expander("⚙️ Filtros e parâmetros", expanded=True):
    col1,col2,col3,col4 = st.columns(4)
    with col1:
        faixa_sel = st.multiselect("Faixa de risco", ["Alto","Médio","Baixo"], default=["Alto","Médio"])
    with col2:
        porte_sel = st.multiselect("Porte", sorted(df["porte"].unique()), default=list(df["porte"].unique()))
    with col3:
        cnae_opts = ["Todos"] + sorted(df["cnae"].unique().tolist())
        cnae_f = st.selectbox("CNAE", cnae_opts)
    with col4:
        score_min = st.slider("Score mínimo", 0, 100, 40)

df_filt = ranking[
    ranking["faixa_risco"].astype(str).isin(faixa_sel) &
    ranking["porte"].isin(porte_sel) &
    (ranking["score_risco"] >= score_min)
].copy()
if cnae_f != "Todos":
    df_filt = df_filt[df_filt["cnae"]==cnae_f]

# ── KPIs DA SELEÇÃO ───────────────────────────────────────────────────────────
c1,c2,c3,c4 = st.columns(4)
c1.metric("Contribuintes selecionados", f"{len(df_filt):,}")
c2.metric("Valor potencial total",      _fmt(df_filt["valor_potencial"].sum()))
c3.metric("Custo estimado total",       _fmt(df_filt["custo_fisc"].sum()))
c4.metric("ROI esperado",
          f"{df_filt['valor_potencial'].sum()/df_filt['custo_fisc'].sum():.1f}x"
          if df_filt["custo_fisc"].sum() > 0 else "—",
          "Potencial / Custo")

st.markdown("---")

# ── SIMULADOR DE RETORNO ──────────────────────────────────────────────────────
st.markdown("#### 📐 Simulador — Se eu fiscalizar os top N contribuintes...")
col_sim, col_res = st.columns([1,2])
with col_sim:
    n_auditores = st.number_input("Auditores disponíveis no mês", 1, 30, 5)
    fiscalizacoes_por_auditor = st.number_input("Fiscalizações por auditor/mês", 1, 20, 4)
    n_max = n_auditores * fiscalizacoes_por_auditor
    n_sel = st.slider("Quantos contribuintes fiscalizar?", 1, min(100, len(df_filt)), min(n_max, len(df_filt)))

top_n = df_filt.head(n_sel)
valor_potencial_n = top_n["valor_potencial"].sum()
custo_n = top_n["custo_fisc"].sum()
roi_n = valor_potencial_n / custo_n if custo_n > 0 else 0
pct_do_total = valor_potencial_n / df_filt["valor_potencial"].sum() * 100 if df_filt["valor_potencial"].sum() > 0 else 0

with col_res:
    cr1,cr2,cr3 = st.columns(3)
    cr1.metric("Valor potencial (top N)",  _fmt(valor_potencial_n))
    cr2.metric("Custo estimado (top N)",   _fmt(custo_n))
    cr3.metric("ROI esperado",             f"{roi_n:.1f}x")
    st.progress(min(100, int(pct_do_total)), text=f"{pct_do_total:.1f}% do potencial total com {n_sel} fiscalizações")

# Curva de retorno acumulado
st.markdown("#### Curva de Retorno Acumulado")
df_curva = df_filt[["posicao","valor_potencial","custo_fisc","score_risco"]].copy()
df_curva["valor_acum"] = df_curva["valor_potencial"].cumsum()
df_curva["custo_acum"] = df_curva["custo_fisc"].cumsum()
df_curva["roi_acum"]   = df_curva["valor_acum"] / df_curva["custo_acum"].clip(lower=1)

fig_curva = go.Figure()
fig_curva.add_scatter(
    x=df_curva["posicao"].values[:100],
    y=df_curva["valor_acum"].values[:100],
    fill="tozeroy", fillcolor="rgba(26,79,130,0.12)",
    line=dict(color="#1a4f82", width=2.5),
    name="Valor Potencial Acumulado",
    yaxis="y",
)
fig_curva.add_scatter(
    x=df_curva["posicao"].values[:100],
    y=df_curva["roi_acum"].values[:100],
    line=dict(color="#c8860a", width=2, dash="dash"),
    name="ROI Acumulado",
    yaxis="y2",
)
fig_curva.add_vline(x=n_sel, line_dash="dot", line_color="#9b1c1c",
                    annotation_text=f"Top {n_sel}", annotation_position="top")
fig_curva.update_layout(
    yaxis2=dict(overlaying="y", side="right", title="ROI (x)"),
    plot_bgcolor="white", height=360,
    hovermode="x unified",
    xaxis_title="Posição no Ranking",
    yaxis_title="Valor Potencial Acumulado (R$)",
    title="Quanto se recupera fiscalizando os N primeiros do ranking?",
)
st.plotly_chart(fig_curva, use_container_width=True)

# ── TABELA DE PRIORIZAÇÃO ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Lista de Trabalho — Contribuintes Priorizados")
st.caption("Top 3 fatores de risco exibidos para cada contribuinte (baseado em SHAP)")

# Carregar SHAP para top 3 fatores
try:
    shap_v = pd.read_csv(f"{DATA_PROC}/shap_values.csv")
    FEAT_LABELS = {
        "shap_gap_medio_pct":"Gap declarado",
        "shap_taxa_omissao":"Omissão",
        "shap_gap_vs_bench_pct":"Gap vs. benchmark",
        "shap_meses_sem_fiscalizacao":"Sem fiscalização",
        "shap_taxa_retificacao":"Retificações",
        "shap_cv_receita":"Instabilidade receita",
    }
    shap_cols = list(FEAT_LABELS.keys())
    shap_top3 = {}
    for _, row in shap_v[shap_v["id_contribuinte"].isin(top_n["id_contribuinte"])].iterrows():
        cid = row["id_contribuinte"]
        vals = {FEAT_LABELS[c]: row[c] for c in shap_cols if c in row.index}
        top3 = sorted(vals.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        shap_top3[cid] = " · ".join([f"{k} ({v:+.2f})" for k,v in top3])
    top_n = top_n.copy()
    top_n["Top 3 Fatores de Risco"] = top_n["id_contribuinte"].map(shap_top3).fillna("—")
    shap_ok = True
except FileNotFoundError:
    shap_ok = False

top_n_show = top_n.head(50).copy()
top_n_show["Score"] = top_n_show["score_risco"].apply(lambda x: f"{x:.0f}")
top_n_show["Potencial"] = top_n_show["valor_potencial"].apply(_fmt)
top_n_show["Custo Est."] = top_n_show["custo_fisc"].apply(_fmt)
top_n_show["Gap %"] = top_n_show["gap_vs_bench_pct"].apply(lambda x: f"{x:.1f}%") if "gap_vs_bench_pct" in top_n_show else "—"

cols_exib = ["posicao","id_contribuinte","cnae","porte","bairro","Score","faixa_risco",
             "Gap %","Potencial","Custo Est.","ultima_fiscalizacao"]
if shap_ok:
    cols_exib.append("Top 3 Fatores de Risco")

st.dataframe(
    top_n_show[cols_exib].rename(columns={
        "posicao":"#","faixa_risco":"Faixa","ultima_fiscalizacao":"Últ. Fisc."
    }),
    use_container_width=True, height=400,
)

# ── EXPORTAÇÃO ────────────────────────────────────────────────────────────────
st.markdown("---")
col_exp1, col_exp2 = st.columns(2)
with col_exp1:
    csv_buf = io.StringIO()
    top_n_show.to_csv(csv_buf, index=False)
    st.download_button(
        label=f"⬇️ Exportar lista de trabalho (top {n_sel}) — CSV",
        data=csv_buf.getvalue(),
        file_name=f"priorizacao_fiscal_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
with col_exp2:
    st.info(
        f"**Resumo da lista:** {n_sel} contribuintes selecionados · "
        f"Potencial de recuperação: {_fmt(valor_potencial_n)} · "
        f"ROI esperado: {roi_n:.1f}x o custo de fiscalização"
    )

# ── ANÁLISE DA DISTRIBUIÇÃO ───────────────────────────────────────────────────
st.markdown("---")
col_d1, col_d2 = st.columns(2)
with col_d1:
    st.markdown("#### Score de Risco × Valor Potencial")
    fig_sc = px.scatter(
        df_filt.head(200),
        x="score_risco", y="valor_potencial",
        color="faixa_risco", size="custo_fisc",
        color_discrete_map={"Baixo":"#1b6b3a","Médio":"#c8860a","Alto":"#9b1c1c"},
        title="Score × Potencial — tamanho = custo de fiscalização",
        labels={"score_risco":"Score Risco","valor_potencial":"Valor Potencial R$"},
        hover_data=["cnae","porte","bairro"],
        opacity=0.7,
    )
    fig_sc.update_layout(plot_bgcolor="white", height=340)
    st.plotly_chart(fig_sc, use_container_width=True)

with col_d2:
    st.markdown("#### Top Setores Priorizados")
    setor_rank = (
        df_filt.groupby("cnae")
        .agg(n=("id_contribuinte","count"),
             potencial=("valor_potencial","sum"),
             score_medio=("score_risco","mean"))
        .reset_index()
        .sort_values("potencial", ascending=False)
        .head(10)
    )
    fig_setor = px.bar(
        setor_rank, x="potencial", y="cnae", orientation="h",
        color="score_medio", color_continuous_scale="RdYlGn_r",
        title="Top 10 setores por potencial de recuperação",
        labels={"potencial":"Potencial R$","cnae":"CNAE","score_medio":"Score Médio"},
        text=setor_rank["n"].apply(lambda x: f"{x} contrib."),
    )
    fig_setor.update_layout(plot_bgcolor="white", height=340, coloraxis_showscale=False)
    st.plotly_chart(fig_setor, use_container_width=True)
