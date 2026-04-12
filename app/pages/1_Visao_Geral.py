"""
FiscoSmart — Página 1: Visão Geral
KPIs consolidados de todos os tributos municipais
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

st.set_page_config(page_title="Visão Geral | FiscoSmart", layout="wide")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_RAW = os.path.join(ROOT, 'data', 'raw')
DATA_PROC = os.path.join(ROOT, 'data', 'processed')

@st.cache_data(ttl=300)
def carregar_dados():
    decl    = pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv")
    imoveis = pd.read_csv(f"{DATA_RAW}/imoveis.csv")
    itbi    = pd.read_csv(f"{DATA_RAW}/itbi.csv")
    cosip   = pd.read_csv(f"{DATA_RAW}/cosip.csv")
    alv     = pd.read_csv(f"{DATA_RAW}/taxa_alvara.csv")
    da      = pd.read_csv(f"{DATA_RAW}/divida_ativa.csv")
    transf  = pd.read_csv(f"{DATA_RAW}/transferencias.csv")
    return decl, imoveis, itbi, cosip, alv, da, transf

def _fmt(v): return f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

# ── LOAD ──────────────────────────────────────────────────────────────────────
decl, imoveis, itbi, cosip, alv, da, transf = carregar_dados()

st.markdown("## 📊 Visão Geral — Painel Gerencial")
st.caption("Todos os tributos e transferências constitucionais · Atualizado mensalmente")

# ── FILTROS ───────────────────────────────────────────────────────────────────
anos_disp = sorted(decl["ano"].unique(), reverse=True)
col_f1, col_f2 = st.columns([1,4])
with col_f1:
    ano_sel = st.selectbox("Ano de referência", anos_disp, index=0)

# ── KPIs PRINCIPAIS ───────────────────────────────────────────────────────────
iss_ano    = decl[decl["ano"] == ano_sel]["iss_recolhido"].sum()
iss_ant    = decl[decl["ano"] == ano_sel-1]["iss_recolhido"].sum() if ano_sel > decl["ano"].min() else iss_ano
iptu_ano   = imoveis["iptu_pago"].sum() / 3  # proxy anual
itbi_ano   = itbi[itbi["ano"] == ano_sel]["itbi_recolhido"].sum()
cosip_ano  = cosip[cosip["adimplente"]==1]["valor_pago"].sum() / 3
alv_ano    = alv[alv["ano"] == ano_sel]["valor_pago"].sum()
total_prop = iss_ano + iptu_ano + itbi_ano + cosip_ano + alv_ano
da_estoque = da["valor_total"].sum() - da["valor_recuperado"].sum()
gap_total  = decl[decl["ano"]==ano_sel]["gap_absoluto"].sum()

# KPIs de transferências
transf_ano = transf[transf["ano"]==ano_sel]["valor"].sum()
total_geral = total_prop + transf_ano

var_iss = (iss_ano - iss_ant) / iss_ant * 100 if iss_ant > 0 else 0
tx_entrega = (1 - decl[decl["ano"]==ano_sel]["omitiu_declaracao"].mean()) * 100
tx_inad_iptu = imoveis["inadimplente"].mean() * 100

st.markdown("---")
st.markdown("#### Receita Própria Municipal")
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("ISS",     _fmt(iss_ano),   f"{var_iss:+.1f}% vs ano ant.")
c2.metric("IPTU",    _fmt(iptu_ano),  f"Inadimplência: {tx_inad_iptu:.1f}%")
c3.metric("ITBI",    _fmt(itbi_ano),  "Transmissões imobiliárias")
c4.metric("COSIP",   _fmt(cosip_ano), "Iluminação pública")
c5.metric("Alvarás", _fmt(alv_ano),   "Licença de funcionamento")

st.markdown("#### Indicadores de Risco e Qualidade")
c6,c7,c8,c9 = st.columns(4)
c6.metric("Gap Total ISS",       _fmt(gap_total),   "Potencial não recolhido")
c7.metric("Dívida Ativa",        _fmt(da_estoque),  "Estoque em aberto")
c8.metric("Taxa de Entrega Decl.",f"{tx_entrega:.1f}%", "Declarações ISS entregues")
c9.metric("Receita Total c/ Transf.", _fmt(total_geral), f"Própria: {_fmt(total_prop)}")

# ── GRÁFICO EVOLUÇÃO MENSAL ───────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Evolução Mensal da Arrecadação por Tributo")

iss_mensal = decl.groupby("competencia")["iss_recolhido"].sum().reset_index()
iss_mensal["tipo"] = "ISS"
iss_mensal = iss_mensal.rename(columns={"iss_recolhido":"valor"})

itbi_mensal = itbi.groupby("mes_competencia")["itbi_recolhido"].sum().reset_index()
itbi_mensal = itbi_mensal.rename(columns={"mes_competencia":"competencia","itbi_recolhido":"valor"})
itbi_mensal["tipo"] = "ITBI"

cosip_mensal = cosip[cosip["adimplente"]==1].groupby("competencia")["valor_pago"].sum().reset_index()
cosip_mensal = cosip_mensal.rename(columns={"valor_pago":"valor"})
cosip_mensal["tipo"] = "COSIP"

df_ev = pd.concat([iss_mensal, itbi_mensal, cosip_mensal])
df_ev = df_ev.sort_values("competencia")

fig = px.line(
    df_ev, x="competencia", y="valor", color="tipo",
    title="Arrecadação mensal — ISS, ITBI e COSIP",
    labels={"valor":"R$","competencia":"Competência","tipo":"Tributo"},
    color_discrete_map={"ISS":"#1a4f82","ITBI":"#c8860a","COSIP":"#1b6b3a"},
)
fig.update_traces(line_width=2.5)
fig.update_layout(hovermode="x unified", plot_bgcolor="white", height=380)
st.plotly_chart(fig, use_container_width=True)

# ── COMPARAÇÃO META VS REALIZADO ──────────────────────────────────────────────
st.markdown("#### Meta vs. Realizado — ISS Mensal")
iss_m = decl[decl["ano"]==ano_sel].groupby(["competencia","mes"])["iss_recolhido"].sum().reset_index()
iss_m["meta"] = decl[decl["ano"]==ano_sel-1].groupby("mes")["iss_recolhido"].sum().values[:len(iss_m)] * 1.08 \
    if ano_sel > decl["ano"].min() else iss_m["iss_recolhido"] * 1.05

fig2 = go.Figure()
fig2.add_bar(x=iss_m["competencia"], y=iss_m["iss_recolhido"], name="Realizado", marker_color="#1a4f82")
fig2.add_scatter(x=iss_m["competencia"], y=iss_m["meta"], name="Meta", line=dict(color="#c8860a", dash="dash", width=2))
fig2.update_layout(barmode="overlay", plot_bgcolor="white", height=320, hovermode="x unified")
st.plotly_chart(fig2, use_container_width=True)

# ── COMPOSIÇÃO DA RECEITA ─────────────────────────────────────────────────────
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### Composição da Receita Própria")
    tributos_labels = ["ISS","IPTU","ITBI","COSIP","Alvarás/Taxas"]
    tributos_vals   = [iss_ano, iptu_ano, itbi_ano, cosip_ano, alv_ano]
    fig3 = go.Figure(go.Pie(
        labels=tributos_labels, values=tributos_vals,
        hole=0.45,
        marker_colors=["#1a4f82","#c8860a","#1b6b3a","#7c3aed","#0891b2"],
    ))
    fig3.update_layout(height=300, margin=dict(t=10,b=10))
    st.plotly_chart(fig3, use_container_width=True)

with col_b:
    st.markdown("#### IPTU — Inadimplência por Bairro")
    inad_bairro = imoveis.groupby("bairro").agg(
        total=("id_imovel","count"),
        inad=("inadimplente","sum"),
        valor=("iptu_lancado","sum")
    ).reset_index()
    inad_bairro["tx_inad"] = inad_bairro["inad"]/inad_bairro["total"]*100
    inad_bairro = inad_bairro.sort_values("tx_inad", ascending=True)
    fig4 = px.bar(
        inad_bairro, x="tx_inad", y="bairro", orientation="h",
        labels={"tx_inad":"% Inadimplência","bairro":"Bairro"},
        color="tx_inad", color_continuous_scale=["#d4eddf","#fef3c7","#fde8e8"],
    )
    fig4.update_layout(height=300, plot_bgcolor="white", coloraxis_showscale=False)
    st.plotly_chart(fig4, use_container_width=True)

# ── TRANSFERÊNCIAS CONSTITUCIONAIS ────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Transferências Constitucionais")
t_pivot = transf[transf["ano"]==ano_sel].groupby("tipo_transferencia")["valor"].sum().reset_index()
c_t = st.columns(len(t_pivot))
for i, (_, row) in enumerate(t_pivot.iterrows()):
    c_t[i].metric(row["tipo_transferencia"], _fmt(row["valor"]))
