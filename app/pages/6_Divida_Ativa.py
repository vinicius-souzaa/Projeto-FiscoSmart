"""
FiscoSmart — Página 6: Dívida Ativa
Estoque, aging, taxa de recuperação, Pareto, análise por tributo e fase
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
st.set_page_config(page_title="Dívida Ativa | FiscoSmart", layout="wide")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_RAW = os.path.join(ROOT, 'data', 'raw')
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

@st.cache_data(ttl=300)
def load():
    da     = pd.read_csv(f"{DATA_RAW}/divida_ativa.csv")
    contribs = pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
    return da, contribs

da, contribs = load()
da["data_inscricao"] = pd.to_datetime(da["data_inscricao"])
da["ano_inscricao"] = da["data_inscricao"].dt.year
da["em_aberto"] = da["valor_total"] - da["valor_recuperado"]

st.markdown("## ⚖️ Dívida Ativa Municipal")
st.caption("Todos os tributos · Fase administrativa e judicial · LC 6.830/80")

# ── KPIs ──────────────────────────────────────────────────────────────────────
total_estoque   = da["valor_total"].sum()
total_recuperado= da["valor_recuperado"].sum()
total_aberto    = da["em_aberto"].sum()
tx_recuperacao  = total_recuperado / total_estoque * 100 if total_estoque > 0 else 0
n_inscricoes    = len(da)
n_aberto        = (da["situacao"]=="Em aberto").sum()
media_nacional  = 25.0  # benchmark taxa de recuperação

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Estoque Total",        _fmt(total_estoque),    f"{n_inscricoes:,} inscrições")
c2.metric("Valor Recuperado",     _fmt(total_recuperado), f"{tx_recuperacao:.1f}% do estoque")
c3.metric("Em Aberto",            _fmt(total_aberto),     f"{n_aberto:,} processos")
c4.metric("Taxa de Recuperação",  f"{tx_recuperacao:.1f}%",
          f"{'▲' if tx_recuperacao >= media_nacional else '▼'} Média nacional: {media_nacional:.0f}%")
c5.metric("Fase Judicial",
          f"{(da['fase']=='Judicial').sum():,}",
          f"{(da['fase']=='Judicial').mean()*100:.1f}% do total")

if tx_recuperacao < media_nacional:
    st.error(f"⚠️ Taxa de recuperação ({tx_recuperacao:.1f}%) abaixo da média nacional ({media_nacional:.0f}%). "
             f"Recomenda-se campanha de renegociação (REFIS municipal) e intensificação das execuções fiscais.")

st.markdown("---")

# ── COMPOSIÇÃO DO ESTOQUE ─────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Composição do Estoque por Tributo")
    comp = da.groupby("tipo_tributo").agg(
        total=("valor_total","sum"),
        recuperado=("valor_recuperado","sum"),
        aberto=("em_aberto","sum"),
        n=("id_da","count"),
    ).reset_index()
    comp["tx_recup"] = comp["recuperado"] / comp["total"] * 100
    fig_comp = go.Figure()
    fig_comp.add_bar(x=comp["tipo_tributo"], y=comp["aberto"],
                     name="Em Aberto", marker_color="#9b1c1c")
    fig_comp.add_bar(x=comp["tipo_tributo"], y=comp["recuperado"],
                     name="Recuperado", marker_color="#1b6b3a")
    fig_comp.update_layout(barmode="stack", plot_bgcolor="white", height=340)
    st.plotly_chart(fig_comp, use_container_width=True)

with col2:
    st.markdown("#### Taxa de Recuperação por Tributo")
    fig_tx = px.bar(
        comp.sort_values("tx_recup"), x="tx_recup", y="tipo_tributo",
        orientation="h",
        title="% Recuperado por tipo de tributo",
        labels={"tx_recup":"% Recuperado","tipo_tributo":"Tributo"},
        color="tx_recup", color_continuous_scale=["#fde8e8","#fef3c7","#d4eddf"],
        range_color=[0,50],
        text=comp.sort_values("tx_recup")["tx_recup"].apply(lambda x: f"{x:.1f}%"),
    )
    fig_tx.add_vline(x=media_nacional, line_dash="dash", line_color="#c8860a",
                     annotation_text=f"Média nacional {media_nacional:.0f}%")
    fig_tx.update_layout(plot_bgcolor="white", height=340, coloraxis_showscale=False)
    st.plotly_chart(fig_tx, use_container_width=True)

# ── AGING DA DÍVIDA ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Aging da Dívida Ativa — Por Ano de Inscrição")
st.caption("Dívidas mais antigas têm menor probabilidade de recuperação")
aging = da.groupby("ano_inscricao").agg(
    total=("valor_total","sum"),
    aberto=("em_aberto","sum"),
    recuperado=("valor_recuperado","sum"),
    n=("id_da","count"),
).reset_index()
aging["tx_recup"] = aging["recuperado"] / aging["total"] * 100

fig_aging = go.Figure()
fig_aging.add_bar(x=aging["ano_inscricao"].astype(str), y=aging["aberto"],
                  name="Em Aberto", marker_color="#9b1c1c")
fig_aging.add_bar(x=aging["ano_inscricao"].astype(str), y=aging["recuperado"],
                  name="Recuperado", marker_color="#1b6b3a")
fig_aging.add_scatter(x=aging["ano_inscricao"].astype(str), y=aging["tx_recup"],
                      name="% Recuperado", yaxis="y2",
                      line=dict(color="#c8860a", width=2.5), mode="lines+markers")
fig_aging.update_layout(
    barmode="stack",
    yaxis2=dict(overlaying="y", side="right", range=[0,100], title="% Recuperado"),
    plot_bgcolor="white", height=360, hovermode="x unified",
    title="Composição e taxa de recuperação por vintagem da dívida",
)
st.plotly_chart(fig_aging, use_container_width=True)

# ── CURVA DE PARETO ───────────────────────────────────────────────────────────
st.markdown("---")
col3, col4 = st.columns(2)
with col3:
    st.markdown("#### Curva de Pareto — Concentração da Dívida")
    da_sorted = da.sort_values("em_aberto", ascending=False).copy()
    da_sorted["pct_valor_acum"] = da_sorted["em_aberto"].cumsum() / da_sorted["em_aberto"].sum() * 100
    da_sorted["pct_processos"] = np.arange(1, len(da_sorted)+1) / len(da_sorted) * 100

    fig_pareto = go.Figure()
    fig_pareto.add_scatter(
        x=da_sorted["pct_processos"].values[::5],
        y=da_sorted["pct_valor_acum"].values[::5],
        fill="tozeroy", fillcolor="rgba(26,79,130,0.15)",
        line=dict(color="#1a4f82", width=2), name="Valor Acumulado",
    )
    fig_pareto.add_vline(x=20, line_dash="dash", line_color="#c8860a",
                         annotation_text="20% dos processos")
    fig_pareto.update_layout(
        plot_bgcolor="white", height=340,
        xaxis_title="% dos Processos", yaxis_title="% do Valor Acumulado",
        title="80% do valor da DA está em quantos % dos processos?",
    )
    st.plotly_chart(fig_pareto, use_container_width=True)

with col4:
    st.markdown("#### Por Fase e Situação")
    fase_sit = da.groupby(["fase","situacao"])["em_aberto"].sum().reset_index()
    fig_fs = px.sunburst(
        fase_sit, path=["fase","situacao"], values="em_aberto",
        title="Estoque em aberto: fase × situação",
        color_discrete_sequence=["#1a4f82","#c8860a","#9b1c1c","#1b6b3a"],
    )
    fig_fs.update_layout(height=340)
    st.plotly_chart(fig_fs, use_container_width=True)

# ── SIMULADOR DE REFIS ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 📐 Simulador de Campanha de Renegociação (REFIS Municipal)")
st.caption("Estime o impacto de uma campanha de parcelamento com desconto")
col_r1, col_r2, col_r3 = st.columns(3)
with col_r1:
    pct_adesao = st.slider("% de contribuintes que aderem", 5, 60, 25)
with col_r2:
    desconto_multa = st.slider("% de desconto na multa", 0, 100, 50)
with col_r3:
    desconto_juros = st.slider("% de desconto nos juros", 0, 100, 30)

base_refis = da[da["situacao"]=="Em aberto"].copy()
n_potencial = int(len(base_refis) * pct_adesao / 100)
valor_principal = base_refis["valor_principal"].sum() * pct_adesao / 100
multa_descont = base_refis["multa"].sum() * pct_adesao / 100 * (1 - desconto_multa/100)
juros_descont = base_refis["juros"].sum() * pct_adesao / 100 * (1 - desconto_juros/100)
receita_estimada = valor_principal + multa_descont + juros_descont
renúncia_fiscal = (base_refis["multa"].sum() + base_refis["juros"].sum()) * pct_adesao/100 - (multa_descont + juros_descont)

cr1,cr2,cr3 = st.columns(3)
cr1.metric("Processos que aderem (est.)", f"{n_potencial:,}")
cr2.metric("Receita estimada da campanha", _fmt(receita_estimada))
cr3.metric("Renúncia fiscal (desconto)", _fmt(renúncia_fiscal))

# ── TOP DEVEDORES ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Top 20 Maiores Devedores (ISS)")
top_dev = (
    da[da["tipo_tributo"]=="ISS"]
    .sort_values("em_aberto", ascending=False)
    .head(20)
    .merge(contribs[["id_contribuinte","razao_social","cnae","porte"]], on="id_contribuinte", how="left")
)
top_dev["Em Aberto"] = top_dev["em_aberto"].apply(_fmt)
top_dev["Total"] = top_dev["valor_total"].apply(_fmt)
st.dataframe(
    top_dev[["id_contribuinte","razao_social","cnae","porte","competencia_origem",
             "fase","situacao","Total","Em Aberto"]]
    .rename(columns={"competencia_origem":"Competência","razao_social":"Razão Social"}),
    use_container_width=True, height=360,
)
