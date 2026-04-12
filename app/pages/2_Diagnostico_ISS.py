"""
FiscoSmart — Página 2: Diagnóstico ISS
Gap por setor, omissões, radar de inconsistências, sazonalidade
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

st.set_page_config(page_title="Diagnóstico ISS | FiscoSmart", layout="wide")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_RAW = os.path.join(ROOT, 'data', 'raw')

@st.cache_data(ttl=300)
def load():
    decl     = pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv")
    contribs = pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
    return decl, contribs

decl, contribs = load()
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

st.markdown("## 🔍 Diagnóstico Fiscal — ISS")

# Filtros
col1,col2,col3 = st.columns(3)
with col1:
    ano_sel = st.selectbox("Ano", sorted(decl["ano"].unique(), reverse=True))
with col2:
    cnaes = ["Todos"] + sorted(decl["cnae"].unique().tolist())
    cnae_sel = st.selectbox("Setor (CNAE)", cnaes)
with col3:
    portes = ["Todos"] + sorted(contribs["porte"].unique().tolist())
    porte_sel = st.selectbox("Porte", portes)

df = decl[decl["ano"] == ano_sel].copy()
if cnae_sel != "Todos":
    df = df[df["cnae"] == cnae_sel]
if porte_sel != "Todos":
    cids = contribs[contribs["porte"]==porte_sel]["id_contribuinte"].tolist()
    df = df[df["id_contribuinte"].isin(cids)]

# KPIs do diagnóstico
c1,c2,c3,c4 = st.columns(4)
c1.metric("Gap Total",          _fmt(df["gap_absoluto"].sum()),   "ISS não recolhido estimado")
c2.metric("Gap Médio / Contribuinte", _fmt(df.groupby("id_contribuinte")["gap_absoluto"].sum().mean()), "")
c3.metric("Omissões de Declaração", f'{df["omitiu_declaracao"].sum():,}', f'{df["omitiu_declaracao"].mean()*100:.1f}% do total')
c4.metric("Contribuintes Irregulares", f'{(df.groupby("id_contribuinte")["gap_percentual"].mean() > 30).sum():,}', "Gap > 30%")

st.markdown("---")

# ── GAP POR SETOR ─────────────────────────────────────────────────────────────
st.markdown("#### Gap de Arrecadação por Setor (CNAE)")
gap_cnae = (
    df.groupby("cnae")
    .agg(
        gap_medio=("gap_percentual","mean"),
        gap_total=("gap_absoluto","sum"),
        n_contrib=("id_contribuinte","nunique"),
        n_omissoes=("omitiu_declaracao","sum"),
    )
    .reset_index()
    .sort_values("gap_total", ascending=False)
)
gap_cnae["cor"] = gap_cnae["gap_medio"].apply(lambda x: "#9b1c1c" if x>50 else ("#c8860a" if x>30 else "#1b6b3a"))

col_g1, col_g2 = st.columns(2)
with col_g1:
    fig = px.bar(
        gap_cnae.head(15), x="gap_total", y="cnae", orientation="h",
        title="Top 15 setores por valor de gap (R$)",
        labels={"gap_total":"Gap R$","cnae":"CNAE"},
        color="gap_medio", color_continuous_scale=["#d4eddf","#fef3c7","#fde8e8"],
    )
    fig.update_layout(height=400, plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
with col_g2:
    fig2 = px.scatter(
        gap_cnae, x="n_contrib", y="gap_medio", size="gap_total",
        title="Setores: nº contribuintes × gap médio (tamanho = gap total)",
        labels={"n_contrib":"Contribuintes","gap_medio":"Gap Médio %","gap_total":"Gap Total"},
        color="gap_medio", color_continuous_scale="RdYlGn_r",
        hover_data=["cnae"],
    )
    fig2.update_layout(height=400, plot_bgcolor="white")
    st.plotly_chart(fig2, use_container_width=True)

# ── HEATMAP DE OMISSÕES ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Mapa de Omissões por Contribuinte × Mês")
st.caption("Verde = declarou | Vermelho = omitiu | Use o filtro para investigar contribuintes específicos")

top_omissores = (
    df.groupby("id_contribuinte")["omitiu_declaracao"].sum()
    .sort_values(ascending=False).head(30).index.tolist()
)
hm_df = df[df["id_contribuinte"].isin(top_omissores)].pivot_table(
    index="id_contribuinte", columns="competencia", values="omitiu_declaracao", aggfunc="max"
).fillna(0)

fig_hm = px.imshow(
    hm_df, aspect="auto",
    color_continuous_scale=[[0,"#d4eddf"],[0.5,"#fef3c7"],[1,"#fde8e8"]],
    title="Top 30 contribuintes com mais omissões",
    labels={"x":"Mês","y":"ID Contribuinte","color":"Omitiu"},
)
fig_hm.update_layout(height=420, coloraxis_showscale=False)
st.plotly_chart(fig_hm, use_container_width=True)

# ── SAZONALIDADE ──────────────────────────────────────────────────────────────
st.markdown("---")
col_s1, col_s2 = st.columns(2)
with col_s1:
    st.markdown("#### Sazonalidade por CNAE — Receita Média por Mês")
    cnae_saz = st.selectbox("CNAE para análise", sorted(decl["cnae"].unique()), key="cnae_saz")
    saz_df = decl[decl["cnae"]==cnae_saz].groupby("mes")["receita_declarada"].mean().reset_index()
    bench_df = decl[decl["cnae"]==cnae_saz].groupby("mes")["receita_real_estimada"].mean().reset_index()
    fig_s = go.Figure()
    fig_s.add_bar(x=saz_df["mes"], y=saz_df["receita_declarada"], name="Declarado", marker_color="#1a4f82")
    fig_s.add_scatter(x=bench_df["mes"], y=bench_df["receita_real_estimada"], name="Esperado (benchmark)",
                      line=dict(color="#c8860a", dash="dash", width=2))
    fig_s.update_layout(plot_bgcolor="white", height=320, xaxis_title="Mês", yaxis_title="Receita média (R$)")
    st.plotly_chart(fig_s, use_container_width=True)

with col_s2:
    st.markdown("#### Radar de Inconsistências — Contribuinte")
    cid_sel = st.number_input("ID do Contribuinte", min_value=1, max_value=2000, value=1)
    cd_c = df[df["id_contribuinte"]==cid_sel]
    if len(cd_c) > 0:
        metrics_radar = {
            "Gap vs. Benchmark": min(100, cd_c["gap_percentual"].mean()),
            "Taxa de Omissão (%)": cd_c["omitiu_declaracao"].mean()*100,
            "Variabilidade Receita": min(100, cd_c["receita_declarada"].std() / (cd_c["receita_declarada"].mean()+1) * 100),
            "Taxa de Retificação (%)": cd_c["retificou"].mean()*100,
            "Irregularidade Histórica": 50,  # placeholder
            "Meses sem dados": (cd_c["receita_declarada"]==0).mean()*100,
        }
        cats = list(metrics_radar.keys())
        vals = list(metrics_radar.values())
        fig_r = go.Figure(go.Scatterpolar(
            r=vals + [vals[0]], theta=cats + [cats[0]],
            fill="toself", fillcolor="rgba(155,28,28,0.2)",
            line=dict(color="#9b1c1c", width=2),
        ))
        fig_r.update_layout(
            polar=dict(radialaxis=dict(range=[0,100])),
            height=320, showlegend=False
        )
        st.plotly_chart(fig_r, use_container_width=True)
        info = contribs[contribs["id_contribuinte"]==cid_sel]
        if len(info) > 0:
            st.caption(f"**{info.iloc[0]['razao_social']}** · {info.iloc[0]['cnae']} · {info.iloc[0]['porte']} · {info.iloc[0]['regime_tributario']}")
    else:
        st.info("Nenhum dado para este contribuinte.")

# ── TABELA DETALHADA ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Contribuintes com Maior Gap Acumulado")
top_gap = (
    df.groupby("id_contribuinte")
    .agg(gap=("gap_absoluto","sum"), omissoes=("omitiu_declaracao","sum"), gap_pct=("gap_percentual","mean"))
    .reset_index()
    .merge(contribs[["id_contribuinte","razao_social","cnae","porte","bairro"]], on="id_contribuinte")
    .sort_values("gap", ascending=False).head(20)
)
top_gap["gap_fmt"] = top_gap["gap"].apply(_fmt)
top_gap["gap_pct_fmt"] = top_gap["gap_pct"].apply(lambda x: f"{x:.1f}%")
st.dataframe(
    top_gap[["id_contribuinte","razao_social","cnae","porte","bairro","gap_fmt","gap_pct_fmt","omissoes"]]
    .rename(columns={"gap_fmt":"Gap R$","gap_pct_fmt":"Gap %","omissoes":"Omissões"}),
    use_container_width=True, height=350,
)
