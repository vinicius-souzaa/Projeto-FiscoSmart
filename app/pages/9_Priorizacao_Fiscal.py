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

DATA_PROC  = os.path.join(ROOT, "data", "processed")
DATA_RAW   = os.path.join(ROOT, "data", "raw")
MODELS_DIR = os.path.join(ROOT, "models")
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

@st.cache_data(ttl=300)
def load():
    scores   = pd.read_csv(f"{DATA_PROC}/scores_risco.csv")
    feats    = pd.read_csv(f"{DATA_PROC}/features_risco.csv")
    acoes    = pd.read_csv(f"{DATA_RAW}/acoes_fiscais.csv")
    contribs = pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
    return scores, feats, acoes, contribs

try:
    scores, feats, acoes, contribs = load()
except FileNotFoundError:
    st.error("Execute `setup.py` primeiro.")
    st.stop()

st.markdown("## 🎯 Priorização da Fiscalização Tributária")
st.info(
    "**O que é esta página?** "
    "Um problema real de qualquer secretaria de finanças: há dezenas de milhares de "
    "contribuintes mas apenas alguns auditores disponíveis por mês. Para quem fiscalizar primeiro? "
    "\n\n"
    "Esta página responde essa pergunta com uma lógica objetiva: "
    "cada contribuinte recebe um **índice de retorno esperado** que combina três fatores: "
    "o score de risco (probabilidade de encontrar irregularidade), "
    "o valor potencial de recuperação (quanto de ISS pode ser cobrado), e "
    "o custo estimado da fiscalização (empresas maiores custam mais para auditar). "
    "\n\n"
    "**Fórmula:** Retorno = (Valor Potencial × Score de Risco) ÷ Custo Estimado"
)

# Montar ranking
# FIX: scores ja tem taxa_omissao, meses_sem_fiscalizacao e gap_vs_bench_pct
# Merge so com cv_receita que nao existe em scores — evita colunas _x/_y
cols_extras = [c for c in ["cv_receita"] if c not in scores.columns]
if cols_extras:
    df = scores.merge(feats[["id_contribuinte"] + cols_extras],
                      on="id_contribuinte", how="left")
else:
    df = scores.copy()
custo_map = {"MEI":500,"ME":1200,"EPP":2500,"MD":5000,"GR":12000}
aliq_map  = {
    "6201-5":0.03,"6202-3":0.03,"7490-1":0.03,"8599-6":0.02,"5611-2":0.03,
    "5620-1":0.03,"4120-4":0.02,"4330-4":0.02,"8630-5":0.02,"8650-0":0.02,
    "6911-7":0.05,"6920-6":0.03,"7711-0":0.03,"9602-5":0.02,"8511-2":0.02,
    "8512-1":0.02,"4771-7":0.03,"5310-5":0.02,"9311-5":0.03,"4921-3":0.02,
}
df["custo_fisc"]     = df["porte"].map(custo_map).fillna(1500)
df["aliquota_cnae"]  = df["cnae"].map(aliq_map).fillna(0.03)
df["valor_potencial"] = (df["receita_media_12m"]
    * df["gap_vs_bench_pct"].clip(0,100) / 100
    * df["aliquota_cnae"])
df["retorno_esperado"] = (
    df["valor_potencial"] * (df["score_risco"] / 100)
) / df["custo_fisc"].clip(lower=100)

ult_fisc = (acoes.groupby("id_contribuinte")["data_acao"].max()
    .reset_index().rename(columns={"data_acao":"ultima_fiscalizacao"}))
df = df.merge(ult_fisc, on="id_contribuinte", how="left")
df["ultima_fiscalizacao"] = df["ultima_fiscalizacao"].fillna("Nunca fiscalizado")

ranking = df.sort_values("retorno_esperado", ascending=False).reset_index(drop=True)
ranking["posicao"] = ranking.index + 1

# Filtros
st.markdown("---")
with st.expander("⚙️ Filtros", expanded=True):
    c1,c2,c3,c4 = st.columns(4)
    with c1: faixa_sel = st.multiselect("Faixa de risco", ["Alto","Médio","Baixo"], default=["Alto","Médio"])
    with c2: porte_sel = st.multiselect("Porte", sorted(df["porte"].unique()), default=list(df["porte"].unique()))
    with c3: cnae_f = st.selectbox("CNAE", ["Todos"] + sorted(df["cnae"].unique().tolist()))
    with c4: score_min = st.slider("Score mínimo", 0, 100, 40)

filt = ranking[
    ranking["faixa_risco"].astype(str).isin(faixa_sel) &
    ranking["porte"].isin(porte_sel) &
    (ranking["score_risco"] >= score_min)
].copy()
if cnae_f != "Todos":
    filt = filt[filt["cnae"]==cnae_f]

c1,c2,c3,c4 = st.columns(4)
c1.metric("Contribuintes selecionados", f"{len(filt):,}")
c2.metric("Potencial total de recuperação", _fmt(filt["valor_potencial"].sum()),
    help="Soma do ISS que pode ser recuperado de todos os contribuintes listados, se 100% forem autuados com sucesso.")
c3.metric("Custo total estimado", _fmt(filt["custo_fisc"].sum()),
    help="Estimativa do custo de fiscalizar todos os contribuintes listados (auditor-fiscal × horas × deslocamento).")
roi = filt["valor_potencial"].sum()/filt["custo_fisc"].sum() if filt["custo_fisc"].sum()>0 else 0
c4.metric("ROI esperado", f"{roi:.1f}x",
    help="Retorno sobre o investimento em fiscalização. '5x' significa que para cada R$1 gasto em fiscalização, o município pode recuperar R$5 em tributos.")

# Simulador
st.markdown("---")
st.markdown("#### 📐 Simulador — Quanto posso recuperar?")
st.caption(
    "**Como usar:** ajuste o número de auditores disponíveis e quantas fiscalizações cada um "
    "consegue fazer no mês. O sistema calcula automaticamente o potencial de recuperação "
    "se você fiscalizar os N primeiros do ranking. A curva mostra como o retorno cresce — "
    "os primeiros contribuintes do ranking valem muito mais do que os últimos."
)
col_sim, col_res = st.columns([1,2])
with col_sim:
    n_aud  = st.number_input("Auditores disponíveis", 1, 30, 5)
    fisc_a = st.number_input("Fiscalizações por auditor/mês", 1, 20, 4)
    n_max  = n_aud * fisc_a
    n_sel  = st.slider("Fiscalizar top N contribuintes", 1, min(100,len(filt)), min(n_max,len(filt)))

top_n = filt.head(n_sel)
vp_n  = top_n["valor_potencial"].sum()
ct_n  = top_n["custo_fisc"].sum()
roi_n = vp_n / ct_n if ct_n > 0 else 0
pct_pot = vp_n / filt["valor_potencial"].sum() * 100 if filt["valor_potencial"].sum() > 0 else 0

with col_res:
    cr1,cr2,cr3 = st.columns(3)
    cr1.metric("Potencial (top N)",   _fmt(vp_n))
    cr2.metric("Custo estimado",      _fmt(ct_n))
    cr3.metric("ROI esperado",        f"{roi_n:.1f}x")
    st.progress(min(100,int(pct_pot)),
        text=f"{pct_pot:.1f}% do potencial total com apenas {n_sel} fiscalizações")

# Curva de retorno
st.markdown("#### 📈 Curva de Retorno Acumulado")
st.caption(
    "**Como ler:** o eixo X mostra a posição no ranking. O eixo Y mostra quanto dinheiro "
    "acumulado você recuperaria fiscalizando até aquela posição. A curva sobe rápido no início "
    "(os primeiros contribuintes valem muito) e vai achatando — isso é o princípio de Pareto: "
    "80% do potencial de recuperação está nos 20% melhores contribuintes do ranking."
)
d_curva = filt[["posicao","valor_potencial","custo_fisc"]].copy()
d_curva["val_acum"] = d_curva["valor_potencial"].cumsum()
d_curva["roi_acum"] = d_curva["val_acum"] / d_curva["custo_fisc"].cumsum().clip(lower=1)

fig_c = go.Figure()
fig_c.add_scatter(x=d_curva["posicao"].values[:100], y=d_curva["val_acum"].values[:100],
    fill="tozeroy", fillcolor="rgba(26,79,130,0.12)",
    line=dict(color="#1a4f82",width=2.5), name="Potencial Acumulado (R$)")
fig_c.add_scatter(x=d_curva["posicao"].values[:100], y=d_curva["roi_acum"].values[:100],
    line=dict(color="#c8860a",width=2,dash="dash"), name="ROI Acumulado (x)", yaxis="y2")
fig_c.add_vline(x=n_sel, line_dash="dot", line_color="#9b1c1c",
    annotation_text=f"Top {n_sel}")
fig_c.update_layout(
    yaxis2=dict(overlaying="y",side="right",title="ROI (x)"),
    plot_bgcolor="white", height=360, hovermode="x unified",
    xaxis_title="Posição no Ranking", yaxis_title="Potencial Acumulado (R$)")
st.plotly_chart(fig_c, use_container_width=True)

# Tabela
st.markdown("---")
st.markdown("#### 📋 Lista de Trabalho — Contribuintes Priorizados")
st.caption(
    "Lista ordenada pelo índice de retorno esperado. O auditor deve começar pelo topo. "
    "A coluna 'Última Fisc.' mostra há quanto tempo o contribuinte não é visitado — "
    "contribuintes nunca fiscalizados têm prioridade extra independentemente do score."
)

try:
    shap_v = pd.read_csv(f"{DATA_PROC}/shap_values.csv")
    SLABELS = {
        "shap_gap_medio_pct":"Gap declarado",
        "shap_taxa_omissao":"Omissão",
        "shap_gap_vs_bench_pct":"Gap vs. benchmark",
        "shap_meses_sem_fiscalizacao":"Sem fiscalização",
    }
    scols = list(SLABELS.keys())
    top3 = {}
    for _, row in shap_v[shap_v["id_contribuinte"].isin(top_n["id_contribuinte"])].iterrows():
        cid = row["id_contribuinte"]
        vals = {SLABELS[c]: row[c] for c in scols if c in row.index}
        t3 = sorted(vals.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        top3[cid] = " · ".join([f"{k} ({v:+.2f})" for k,v in t3])
    top_n = top_n.copy()
    top_n["Top 3 Fatores"] = top_n["id_contribuinte"].map(top3).fillna("—")
    cols_ex = ["posicao","id_contribuinte","cnae","porte","bairro",
               "score_risco","faixa_risco","valor_potencial","custo_fisc",
               "ultima_fiscalizacao","Top 3 Fatores"]
except Exception:
    cols_ex = ["posicao","id_contribuinte","cnae","porte","bairro",
               "score_risco","faixa_risco","valor_potencial","custo_fisc","ultima_fiscalizacao"]

t_show = top_n[cols_ex].head(50).copy()
t_show["score_risco"]    = t_show["score_risco"].apply(lambda x: f"{x:.0f}")
t_show["valor_potencial"] = t_show["valor_potencial"].apply(_fmt)
t_show["custo_fisc"]     = t_show["custo_fisc"].apply(_fmt)
st.dataframe(t_show.rename(columns={
    "posicao":"#","faixa_risco":"Faixa","score_risco":"Score",
    "valor_potencial":"Potencial","custo_fisc":"Custo Est.",
    "ultima_fiscalizacao":"Última Fisc."}),
    use_container_width=True, height=380)

# Download
st.markdown("---")
col_e1, col_e2 = st.columns(2)
with col_e1:
    buf = io.StringIO()
    top_n.to_csv(buf, index=False)
    st.download_button(
        f"⬇️ Baixar lista de trabalho (top {n_sel}) — CSV",
        buf.getvalue(),
        f"priorizacao_fiscal_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
        "text/csv")
with col_e2:
    st.info(
        f"**Resumo:** {n_sel} contribuintes · "
        f"Potencial: {_fmt(vp_n)} · ROI: {roi_n:.1f}x"
    )
