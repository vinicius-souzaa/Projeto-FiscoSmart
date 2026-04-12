"""
FiscoSmart — Página 4: Diagnóstico ITBI
Subavaliação de base de cálculo, transações suspeitas, análise por bairro
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
st.set_page_config(page_title="ITBI | FiscoSmart", layout="wide")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_RAW = os.path.join(ROOT, 'data', 'raw')
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")
_pct = lambda v: f"{v:.1f}%"

@st.cache_data(ttl=300)
def load():
    itbi    = pd.read_csv(f"{DATA_RAW}/itbi.csv")
    imoveis = pd.read_csv(f"{DATA_RAW}/imoveis.csv")
    return itbi, imoveis

itbi, imoveis = load()

st.markdown("## 📋 Diagnóstico — ITBI")
st.caption("Imposto sobre Transmissão de Bens Imóveis · Alíquota municipal: 2%")

# ── KPIs ──────────────────────────────────────────────────────────────────────
total_transacoes  = len(itbi)
total_devido      = itbi["itbi_devido"].sum()
total_recolhido   = itbi["itbi_recolhido"].sum()
total_gap         = itbi["gap_itbi"].sum()
n_subavaliados    = itbi["subavaliacao_detectada"].sum()
pct_subav         = n_subavaliados / total_transacoes * 100
eficiencia        = total_recolhido / total_devido * 100 if total_devido > 0 else 0

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Transações",         f"{total_transacoes:,}",  "Escrituras analisadas")
c2.metric("ITBI Devido",        _fmt(total_devido),        "Valor venal × 2%")
c3.metric("ITBI Recolhido",     _fmt(total_recolhido),     _pct(eficiencia) + " de eficiência")
c4.metric("Gap Total",          _fmt(total_gap),           "Subavaliação estimada")
c5.metric("Transações Susp.",   f"{n_subavaliados:,}",     _pct(pct_subav) + " do total")

st.markdown("---")

# ── SCATTER SUBAVALIAÇÃO ──────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Valor Declarado vs. Valor Venal (IPTU)")
    st.caption("Pontos abaixo da linha diagonal = declaração inferior ao valor venal")
    fig_sc = px.scatter(
        itbi.sample(min(500, len(itbi)), random_state=42),
        x="valor_venal_iptu", y="valor_declarado_escritura",
        color="subavaliacao_detectada",
        color_discrete_map={0:"#1b6b3a", 1:"#9b1c1c"},
        title="Declarado × Venal",
        labels={
            "valor_venal_iptu": "Valor Venal IPTU (R$)",
            "valor_declarado_escritura": "Valor Declarado Escritura (R$)",
            "subavaliacao_detectada": "Subavaliação"
        },
        hover_data=["bairro","tipo_imovel","gap_itbi"],
        opacity=0.6,
    )
    # Linha de referência (x=y)
    max_v = max(itbi["valor_venal_iptu"].max(), itbi["valor_declarado_escritura"].max())
    fig_sc.add_scatter(
        x=[0, max_v], y=[0, max_v],
        mode="lines", line=dict(color="#c8860a", dash="dash", width=1.5),
        name="Valor declarado = Venal",
    )
    fig_sc.update_layout(plot_bgcolor="white", height=380)
    st.plotly_chart(fig_sc, use_container_width=True)

with col2:
    st.markdown("#### Distribuição da Razão Declarado / Venal")
    st.caption("Razão < 0,80 indica possível subavaliação")
    fig_hist = px.histogram(
        itbi, x="razao_decl_venal", nbins=40,
        color="subavaliacao_detectada",
        color_discrete_map={0:"#1b6b3a", 1:"#9b1c1c"},
        title="Razão Valor Declarado / Valor Venal",
        labels={"razao_decl_venal":"Razão Decl./Venal","count":"Transações"},
    )
    fig_hist.add_vline(x=0.80, line_dash="dash", line_color="#c8860a",
                       annotation_text="Piso 0,80", annotation_position="top right")
    fig_hist.update_layout(plot_bgcolor="white", height=380)
    st.plotly_chart(fig_hist, use_container_width=True)

# ── ANÁLISE POR BAIRRO E TIPO ─────────────────────────────────────────────────
st.markdown("---")
col3, col4 = st.columns(2)
with col3:
    st.markdown("#### Gap por Bairro")
    gap_bairro = (
        itbi.groupby("bairro")
        .agg(gap=("gap_itbi","sum"), subav=("subavaliacao_detectada","sum"), n=("id_itbi","count"))
        .reset_index()
        .sort_values("gap", ascending=False)
    )
    gap_bairro["pct_subav"] = gap_bairro["subav"] / gap_bairro["n"] * 100
    fig_b = px.bar(
        gap_bairro, x="bairro", y="gap",
        color="pct_subav", color_continuous_scale="Reds",
        title="Gap de ITBI por bairro — cor = % de subavaliação",
        labels={"gap":"Gap R$","bairro":"Bairro","pct_subav":"% Subavaliadas"},
    )
    fig_b.update_layout(plot_bgcolor="white", height=340)
    st.plotly_chart(fig_b, use_container_width=True)

with col4:
    st.markdown("#### Evolução Mensal — ITBI Devido vs. Recolhido")
    itbi_mensal = (
        itbi.groupby("mes_competencia")
        .agg(devido=("itbi_devido","sum"), recolhido=("itbi_recolhido","sum"))
        .reset_index()
        .sort_values("mes_competencia")
    )
    fig_ev = go.Figure()
    fig_ev.add_bar(x=itbi_mensal["mes_competencia"], y=itbi_mensal["devido"],
                   name="Devido", marker_color="rgba(155,28,28,0.3)")
    fig_ev.add_bar(x=itbi_mensal["mes_competencia"], y=itbi_mensal["recolhido"],
                   name="Recolhido", marker_color="#1a4f82")
    fig_ev.update_layout(barmode="overlay", plot_bgcolor="white", height=340,
                         hovermode="x unified")
    st.plotly_chart(fig_ev, use_container_width=True)

# ── TABELA DE TRANSAÇÕES SUSPEITAS ────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Transações com Maior Indício de Subavaliação")
st.caption("Razão declarado/venal < 0,80 · Ordenado por gap de ITBI")
suspeitas = (
    itbi[itbi["subavaliacao_detectada"]==1]
    .sort_values("gap_itbi", ascending=False)
    .head(25)
)
suspeitas["Valor Venal"] = suspeitas["valor_venal_iptu"].apply(_fmt)
suspeitas["Valor Declarado"] = suspeitas["valor_declarado_escritura"].apply(_fmt)
suspeitas["Gap ITBI"] = suspeitas["gap_itbi"].apply(_fmt)
suspeitas["Razão"] = suspeitas["razao_decl_venal"].apply(lambda x: f"{x:.3f}")

st.dataframe(
    suspeitas[["id_itbi","bairro","tipo_imovel","Valor Venal",
               "Valor Declarado","Razão","Gap ITBI","mes_competencia"]]
    .rename(columns={"mes_competencia":"Competência","tipo_imovel":"Tipo"}),
    use_container_width=True, height=360,
)

# ── INSIGHT AUTOMÁTICO ────────────────────────────────────────────────────────
st.markdown("---")
st.info(
    f"💡 **Insight Automático:** {n_subavaliados} transações ({pct_subav:.1f}%) apresentam "
    f"valor declarado em escritura inferior a 80% do valor venal registrado no IPTU. "
    f"O gap total de ITBI não recolhido é estimado em {_fmt(total_gap)}. "
    f"Recomendação: aplicar arbitramento da base de cálculo conforme previsto na LC 116/2003 "
    f"e legislação municipal, utilizando o valor venal do IPTU como piso de cálculo."
)
