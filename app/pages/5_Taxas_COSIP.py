"""
FiscoSmart — Página 5: Taxas Municipais e COSIP
Alvará, coleta de lixo, iluminação pública, contribuição de melhoria
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
st.set_page_config(page_title="Taxas e COSIP | FiscoSmart", layout="wide")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_RAW = os.path.join(ROOT, 'data', 'raw')
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

@st.cache_data(ttl=300)
def load():
    alv   = pd.read_csv(f"{DATA_RAW}/taxa_alvara.csv")
    cosip = pd.read_csv(f"{DATA_RAW}/cosip.csv")
    lixo  = pd.read_csv(f"{DATA_RAW}/taxa_lixo.csv")
    cm    = pd.read_csv(f"{DATA_RAW}/contrib_melhoria.csv")
    contr = pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
    return alv, cosip, lixo, cm, contr

alv, cosip, lixo, cm, contribs = load()

st.markdown("## 💰 Taxas Municipais, COSIP e Contribuição de Melhoria")
st.caption("Receitas tributárias acessórias — complementam a arrecadação própria municipal")

# ── KPIs ──────────────────────────────────────────────────────────────────────
alv_rec   = alv["valor_pago"].sum()
alv_lanc  = alv["valor_lancado"].sum()
cosip_rec = cosip["valor_pago"].sum()
cosip_lanc = cosip["valor_lancado"].sum()
lixo_rec  = lixo["valor_pago"].sum()
lixo_lanc = lixo["valor_lancado"].sum()
cm_rec    = cm["valor_pago"].sum()
cm_lanc   = cm["valor_lancado"].sum()

c1,c2,c3,c4 = st.columns(4)
c1.metric("Alvará/Licença",    _fmt(alv_rec),   f"{alv_rec/alv_lanc*100:.1f}% de adimplência")
c2.metric("COSIP",             _fmt(cosip_rec), f"{cosip_rec/cosip_lanc*100:.1f}% de adimplência")
c3.metric("Taxa Lixo",         _fmt(lixo_rec),  f"{lixo_rec/lixo_lanc*100:.1f}% de adimplência")
c4.metric("Contrib. Melhoria", _fmt(cm_rec),    f"{cm_rec/cm_lanc*100:.1f}% de adimplência")

st.markdown("---")

# ── ALVARÁ POR PORTE ──────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Taxa de Alvará — Inadimplência por Porte")
    alv_porte = (
        alv.merge(contribs[["id_contribuinte","porte"]], on="id_contribuinte", how="left")
        .groupby(["porte","ano"])
        .agg(lanc=("valor_lancado","sum"), pago=("valor_pago","sum"), n_inad=("adimplente", lambda x: (~x.astype(bool)).sum()), n=("id_contribuinte","count"))
        .reset_index()
    )
    alv_porte["tx_inad"] = (1 - alv_porte["pago"] / alv_porte["lanc"].clip(lower=1)) * 100
    fig_alv = px.bar(
        alv_porte, x="porte", y="tx_inad", color="ano",
        barmode="group",
        title="Inadimplência de alvará por porte (%)",
        labels={"porte":"Porte","tx_inad":"Inadimplência %","ano":"Ano"},
        color_discrete_sequence=["#1a4f82","#c8860a","#1b6b3a"],
    )
    fig_alv.update_layout(plot_bgcolor="white", height=340)
    st.plotly_chart(fig_alv, use_container_width=True)

with col2:
    st.markdown("#### COSIP — Distribuição por Faixa de Consumo")
    cosip_faixa = cosip.groupby("faixa_consumo").agg(
        arrecadado=("valor_pago","sum"),
        lançado=("valor_lancado","sum"),
        n=("id_economia","count"),
    ).reset_index()
    cosip_faixa["tx_adim"] = cosip_faixa["arrecadado"] / cosip_faixa["lançado"] * 100
    cosip_faixa["faixa_label"] = cosip_faixa["faixa_consumo"].map({
        1:"Faixa 1\n(R$8,50)", 2:"Faixa 2\n(R$15,00)",
        3:"Faixa 3\n(R$28,00)", 4:"Faixa 4\n(R$55,00)"
    })
    fig_cos = go.Figure()
    fig_cos.add_bar(x=cosip_faixa["faixa_label"], y=cosip_faixa["arrecadado"],
                    name="Arrecadado", marker_color="#1a4f82")
    fig_cos.add_scatter(x=cosip_faixa["faixa_label"], y=cosip_faixa["tx_adim"],
                        name="Adimplência %", yaxis="y2",
                        line=dict(color="#c8860a", width=2), mode="lines+markers")
    fig_cos.update_layout(
        yaxis2=dict(overlaying="y", side="right", range=[80,105]),
        plot_bgcolor="white", height=340, hovermode="x unified",
    )
    st.plotly_chart(fig_cos, use_container_width=True)

# ── EVOLUÇÃO COSIP MENSAL ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### COSIP — Evolução Mensal de Arrecadação")
cosip_mensal = (
    cosip.groupby("competencia")
    .agg(lancado=("valor_lancado","sum"), arrecadado=("valor_pago","sum"))
    .reset_index()
    .sort_values("competencia")
)
cosip_mensal["gap"] = cosip_mensal["lancado"] - cosip_mensal["arrecadado"]
fig_cm = go.Figure()
fig_cm.add_scatter(x=cosip_mensal["competencia"], y=cosip_mensal["lancado"],
                   name="Lançado", line=dict(color="#c8860a", dash="dash"))
fig_cm.add_scatter(x=cosip_mensal["competencia"], y=cosip_mensal["arrecadado"],
                   name="Arrecadado", fill="tonexty",
                   fillcolor="rgba(26,79,130,0.1)", line=dict(color="#1a4f82"))
fig_cm.update_layout(plot_bgcolor="white", height=300, hovermode="x unified")
st.plotly_chart(fig_cm, use_container_width=True)

# ── CONTRIBUIÇÃO DE MELHORIA ──────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Contribuição de Melhoria — por Obra")
for obra_id in cm["id_obra"].unique():
    obra = cm[cm["id_obra"]==obra_id]
    desc = obra.iloc[0]["desc_obra"]
    lanc = obra["valor_lancado"].sum()
    pago = obra["valor_pago"].sum()
    pct  = pago / lanc * 100 if lanc > 0 else 0
    n_adim = (obra["adimplente"]==0).sum()

    with st.expander(f"🏗️ Obra {obra_id}: {desc}"):
        ca,cb,cc,cd = st.columns(4)
        ca.metric("Valor Lançado",   _fmt(lanc))
        cb.metric("Valor Recuperado",_fmt(pago),  f"{pct:.1f}% de adesão")
        cc.metric("Imóveis Beneficiados", f"{len(obra):,}")
        cd.metric("Inadimplentes",   f"{n_adim:,}")

        # Distribuição por bairro
        bairro_cm = obra.groupby("bairro").agg(lanc=("valor_lancado","sum"), pago=("valor_pago","sum")).reset_index()
        bairro_cm["tx"] = bairro_cm["pago"] / bairro_cm["lanc"] * 100
        fig_o = px.bar(bairro_cm, x="bairro", y="tx",
                       title=f"% de adimplência por bairro — {desc}",
                       labels={"tx":"Adimplência %","bairro":"Bairro"},
                       color="tx", color_continuous_scale=["#fde8e8","#fef3c7","#d4eddf"],
                       range_color=[0,100])
        fig_o.update_layout(plot_bgcolor="white", height=280, coloraxis_showscale=False)
        st.plotly_chart(fig_o, use_container_width=True)

# ── TAXA DE LIXO ──────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Taxa de Coleta de Lixo — Comparativo por Semestre")
lixo_sem = lixo.groupby(["ano","semestre"]).agg(
    lanc=("valor_lancado","sum"), pago=("valor_pago","sum")
).reset_index()
lixo_sem["periodo"] = lixo_sem["ano"].astype(str) + " S" + lixo_sem["semestre"].astype(str)
lixo_sem["tx_inad"] = (1 - lixo_sem["pago"]/lixo_sem["lanc"].clip(lower=1))*100
fig_lx = go.Figure()
fig_lx.add_bar(x=lixo_sem["periodo"], y=lixo_sem["pago"], name="Arrecadado", marker_color="#1a4f82")
fig_lx.add_scatter(x=lixo_sem["periodo"], y=lixo_sem["tx_inad"],
                   name="Inadimplência %", yaxis="y2",
                   line=dict(color="#9b1c1c", width=2.5), mode="lines+markers")
fig_lx.update_layout(
    yaxis2=dict(overlaying="y", side="right", range=[0,40], title="Inadimplência %"),
    plot_bgcolor="white", height=320, hovermode="x unified",
)
st.plotly_chart(fig_lx, use_container_width=True)

st.info(
    f"💡 **Insight Automático:** A arrecadação de COSIP representa "
    f"{cosip_rec/(cosip_rec+alv_rec+lixo_rec+cm_rec)*100:.1f}% do total das taxas municipais. "
    f"O gap acumulado de taxas (lancado − arrecadado) é de "
    f"{_fmt((alv_lanc-alv_rec)+(cosip_lanc-cosip_rec)+(lixo_lanc-lixo_rec))}. "
    f"Recomenda-se cruzar os inadimplentes de alvará com o cadastro do ISS para "
    f"identificar estabelecimentos operando sem licença."
)
