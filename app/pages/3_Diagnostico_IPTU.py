"""
FiscoSmart — Página 3: Diagnóstico IPTU
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
st.set_page_config(page_title="IPTU | FiscoSmart", layout="wide")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_RAW = os.path.join(ROOT, 'data', 'raw')
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

@st.cache_data(ttl=300)
def load():
    imoveis = pd.read_csv(f"{DATA_RAW}/imoveis.csv")
    parcelas = pd.read_csv(f"{DATA_RAW}/iptu_parcelas.csv")
    return imoveis, parcelas

imoveis, parcelas = load()

st.markdown("## 🏠 Diagnóstico — IPTU")

c1,c2,c3,c4 = st.columns(4)
c1.metric("Total Lançado",    _fmt(imoveis["iptu_lancado"].sum()),  "Todos os imóveis")
c2.metric("Total Pago",       _fmt(imoveis["iptu_pago"].sum()),     f'{imoveis["iptu_pago"].sum()/imoveis["iptu_lancado"].sum()*100:.1f}% de eficiência')
c3.metric("Imóveis Inadimpl.",f'{imoveis["inadimplente"].sum():,}', f'{imoveis["inadimplente"].mean()*100:.1f}% do cadastro')
c4.metric("Imóveis Isentos",  f'{imoveis["isencao"].sum():,}',      "Requer verificação periódica")

st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Inadimplência por Bairro")
    inad = imoveis.groupby("bairro").agg(
        total=("id_imovel","count"), inad=("inadimplente","sum"),
        lancado=("iptu_lancado","sum"), pago=("iptu_pago","sum")
    ).reset_index()
    inad["tx_inad"] = inad["inad"]/inad["total"]*100
    inad["perda"] = inad["lancado"] - inad["pago"]
    fig = px.bar(inad.sort_values("tx_inad", ascending=False),
        x="bairro", y="tx_inad", color="perda",
        title="Taxa de inadimplência e perda por bairro",
        labels={"tx_inad":"Inadimplência %","perda":"Perda R$","bairro":"Bairro"},
        color_continuous_scale="Reds",
    )
    fig.update_layout(plot_bgcolor="white", height=350)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("#### Distribuição por Tipo de Imóvel")
    tipo_inad = imoveis.groupby("tipo").agg(
        total=("id_imovel","count"), inad=("inadimplente","sum"),
        lancado=("iptu_lancado","sum")
    ).reset_index()
    tipo_inad["tx_inad"] = tipo_inad["inad"]/tipo_inad["total"]*100
    fig2 = px.bar(tipo_inad, x="tipo", y=["lancado","tx_inad"],
        title="Arrecadação e inadimplência por tipo",
        barmode="group",
        labels={"value":"Valor","tipo":"Tipo","variable":"Métrica"},
    )
    fig2.update_layout(plot_bgcolor="white", height=350)
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")
st.markdown("#### Imóveis com Possível Isenção Irregular")
st.caption("Imóveis com isenção e alto valor venal (potencial irregularidade cadastral)")
isentos_suspeitos = imoveis[
    (imoveis["isencao"]==1) & (imoveis["valor_venal"] > imoveis["valor_venal"].quantile(0.75))
].sort_values("valor_venal", ascending=False).head(20)
st.dataframe(
    isentos_suspeitos[["id_imovel","inscricao_imobiliaria","tipo","bairro","area_m2","valor_venal","ultima_atualizacao_cadastral"]]
    .rename(columns={"valor_venal":"Valor Venal R$","ultima_atualizacao_cadastral":"Últ. Atualiz."}),
    use_container_width=True, height=300,
)

st.markdown("#### Pareto da Arrecadação — IPTU")
imoveis_sorted = imoveis[imoveis["iptu_pago"]>0].sort_values("iptu_pago", ascending=False)
imoveis_sorted["pct_acum"] = imoveis_sorted["iptu_pago"].cumsum() / imoveis_sorted["iptu_pago"].sum() * 100
imoveis_sorted["pct_imoveis"] = range(1, len(imoveis_sorted)+1)
imoveis_sorted["pct_imoveis"] = imoveis_sorted["pct_imoveis"] / len(imoveis_sorted) * 100
fig_pareto = go.Figure()
fig_pareto.add_scatter(x=imoveis_sorted["pct_imoveis"].values[::50],
    y=imoveis_sorted["pct_acum"].values[::50],
    fill="tozeroy", fillcolor="rgba(26,79,130,0.15)",
    line=dict(color="#1a4f82", width=2), name="% Arrecadação Acumulada")
fig_pareto.add_vline(x=20, line_dash="dash", line_color="#c8860a",
    annotation_text="20% dos imóveis", annotation_position="top right")
fig_pareto.update_layout(plot_bgcolor="white", height=300,
    xaxis_title="% dos Imóveis", yaxis_title="% Arrecadação Acumulada")
st.plotly_chart(fig_pareto, use_container_width=True)
