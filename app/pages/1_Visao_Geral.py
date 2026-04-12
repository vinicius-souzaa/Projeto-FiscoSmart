"""
FiscoSmart — Página 1: Visão Geral
KPIs consolidados de todos os tributos municipais
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
st.set_page_config(page_title="Visão Geral | FiscoSmart", layout="wide")

DATA_RAW = os.path.join(ROOT, "data", "raw")

@st.cache_data(ttl=300)
def load():
    return (
        pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv"),
        pd.read_csv(f"{DATA_RAW}/imoveis.csv"),
        pd.read_csv(f"{DATA_RAW}/itbi.csv"),
        pd.read_csv(f"{DATA_RAW}/cosip.csv"),
        pd.read_csv(f"{DATA_RAW}/taxa_alvara.csv"),
        pd.read_csv(f"{DATA_RAW}/divida_ativa.csv"),
        pd.read_csv(f"{DATA_RAW}/transferencias.csv"),
    )

_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")
decl, imoveis, itbi, cosip, alv, da, transf = load()

st.markdown("## 📊 Visão Geral — Painel Gerencial")
st.info(
    "**O que é esta página?** "
    "Resume toda a arrecadação tributária do município em uma tela. "
    "Municípios arrecadam de três formas: impostos próprios (ISS, IPTU, ITBI), "
    "taxas por serviços (alvará, lixo, iluminação) e transferências da União e do Estado "
    "(FPM, ICMS, IPVA). Tudo consolidado aqui para o gestor ter a visão completa."
)

ano_sel = st.selectbox("Ano", sorted(decl["ano"].unique(), reverse=True))

iss_ano   = decl[decl["ano"]==ano_sel]["iss_recolhido"].sum()
iss_ant   = decl[decl["ano"]==ano_sel-1]["iss_recolhido"].sum() if ano_sel > decl["ano"].min() else iss_ano
iptu_ano  = imoveis["iptu_pago"].sum() / 3
itbi_ano  = itbi[itbi["ano"]==ano_sel]["itbi_recolhido"].sum()
cosip_ano = cosip[cosip["adimplente"]==1]["valor_pago"].sum() / 3
alv_ano   = alv[alv["ano"]==ano_sel]["valor_pago"].sum()
da_aberto = da["valor_total"].sum() - da["valor_recuperado"].sum()
gap_total = decl[decl["ano"]==ano_sel]["gap_absoluto"].sum()
transf_ano= transf[transf["ano"]==ano_sel]["valor"].sum()
var_iss   = (iss_ano - iss_ant) / iss_ant * 100 if iss_ant > 0 else 0
tx_inad   = imoveis["inadimplente"].mean() * 100
tx_entrega= (1 - decl[decl["ano"]==ano_sel]["omitiu_declaracao"].mean()) * 100

# ── KPIs RECEITA PRÓPRIA ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 💰 Receita Própria Municipal")
st.caption(
    "Tributos arrecadados diretamente pelo município. Quanto maior, mais independente "
    "financeiramente é a prefeitura. O ISS é o principal imposto próprio municipal — "
    "incide sobre toda prestação de serviços realizada no território do município."
)
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("ISS",     _fmt(iss_ano),   f"{var_iss:+.1f}% vs ano anterior",
    help="Imposto Sobre Serviços — pago por empresas e autônomos. Ex: clínicas, escritórios, construtoras, academias.")
c2.metric("IPTU",    _fmt(iptu_ano),  f"Inadimplência: {tx_inad:.1f}%",
    help="Imposto Predial e Territorial Urbano — pago pelos donos de imóveis. Calculado sobre o valor venal registrado no cadastro da prefeitura.")
c3.metric("ITBI",    _fmt(itbi_ano),  "Vendas de imóveis",
    help="Imposto sobre Transmissão de Bens Imóveis — cobrado a cada venda de imóvel. Alíquota de 2% sobre o valor da escritura.")
c4.metric("COSIP",   _fmt(cosip_ano), "Iluminação pública",
    help="Contribuição para custeio da iluminação pública — cobrada junto com a conta de luz de todos os imóveis.")
c5.metric("Alvarás", _fmt(alv_ano),   "Licença de funcionamento",
    help="Taxa cobrada anualmente de toda empresa para funcionar legalmente no município.")

# ── KPIs RISCO ────────────────────────────────────────────────────────────────
st.markdown("#### ⚠️ Indicadores de Risco Fiscal")
st.caption(
    "Estes números mostram dinheiro que deveria ter entrado mas não entrou. "
    "O **Gap** é a diferença entre o que as empresas deveriam declarar "
    "(baseado na média do seu setor) e o que efetivamente declararam. "
    "A **Dívida Ativa** são tributos vencidos e não pagos, já inscritos para cobrança judicial."
)
c6,c7,c8,c9 = st.columns(4)
c6.metric("Gap de ISS",         _fmt(gap_total),    "Estimativa de não recolhido",
    help="Calculado comparando a receita declarada de cada empresa com a média do seu setor e porte. Indica o potencial de recuperação via fiscalização.")
c7.metric("Dívida Ativa",       _fmt(da_aberto),    "Em aberto",
    help="Tributos inscritos em dívida ativa ainda não pagos. Cobrança feita via execução fiscal — processo judicial regido pela Lei 6.830/80.")
c8.metric("Entrega de Declarações", f"{tx_entrega:.1f}%", "Contribuintes ISS",
    help="Porcentagem de contribuintes que entregaram a declaração mensal. Abaixo de 90% é sinal de alerta — omissão de declaração é infração prevista no CTN.")
c9.metric("Receita Total",      _fmt(iss_ano+iptu_ano+itbi_ano+cosip_ano+alv_ano+transf_ano), "Própria + transferências",
    help="Receita tributária própria somada às transferências constitucionais. É o orçamento total disponível para a prefeitura.")

# ── EVOLUÇÃO MENSAL ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 📈 Evolução Mensal por Tributo")
st.caption(
    "**Como ler:** cada linha é um tributo diferente ao longo dos 36 meses analisados. "
    "Quedas bruscas fora do padrão sazonal esperado podem indicar sonegação ou omissão. "
    "O ISS oscila conforme a atividade econômica — queda em dezembro é normal "
    "(menos serviços prestados no fim do ano). O ITBI oscila com o mercado imobiliário."
)

iss_m  = decl.groupby("competencia")["iss_recolhido"].sum().reset_index()
iss_m["tipo"]  = "ISS"; iss_m = iss_m.rename(columns={"iss_recolhido":"valor"})
itbi_m = itbi.groupby("mes_competencia")["itbi_recolhido"].sum().reset_index()
itbi_m = itbi_m.rename(columns={"mes_competencia":"competencia","itbi_recolhido":"valor"})
itbi_m["tipo"] = "ITBI"
cosip_m = cosip[cosip["adimplente"]==1].groupby("competencia")["valor_pago"].sum().reset_index()
cosip_m = cosip_m.rename(columns={"valor_pago":"valor"}); cosip_m["tipo"] = "COSIP"

df_ev = pd.concat([iss_m, itbi_m, cosip_m]).sort_values("competencia")
fig = px.line(df_ev, x="competencia", y="valor", color="tipo",
    color_discrete_map={"ISS":"#1a4f82","ITBI":"#c8860a","COSIP":"#1b6b3a"},
    labels={"valor":"R$","competencia":"Mês","tipo":"Tributo"})
fig.update_traces(line_width=2.5)
fig.update_layout(hovermode="x unified", plot_bgcolor="white", height=360)
st.plotly_chart(fig, use_container_width=True)

# ── META VS REALIZADO ─────────────────────────────────────────────────────────
st.markdown("#### 🎯 Meta vs. Realizado — ISS")
st.caption(
    "**Como ler:** barras azuis = arrecadação real de cada mês. "
    "Linha laranja = meta (8% acima do mesmo mês do ano anterior, crescimento esperado). "
    "Barra abaixo da linha = mês abaixo da meta. "
    "Vários meses consecutivos abaixo indicam necessidade de intensificar a fiscalização."
)

iss_mv = decl[decl["ano"]==ano_sel].groupby(["competencia","mes"])["iss_recolhido"].sum().reset_index()
if ano_sel > decl["ano"].min():
    iss_ant_m = decl[decl["ano"]==ano_sel-1].groupby("mes")["iss_recolhido"].sum()
    iss_mv["meta"] = iss_mv["mes"].map(iss_ant_m) * 1.08
else:
    iss_mv["meta"] = iss_mv["iss_recolhido"] * 1.05

fig2 = go.Figure()
fig2.add_bar(x=iss_mv["competencia"], y=iss_mv["iss_recolhido"],
             name="Realizado", marker_color="#1a4f82")
fig2.add_scatter(x=iss_mv["competencia"], y=iss_mv["meta"],
                 name="Meta (+8% a.a.)", line=dict(color="#c8860a", dash="dash", width=2))
fig2.update_layout(barmode="overlay", plot_bgcolor="white", height=300, hovermode="x unified")
st.plotly_chart(fig2, use_container_width=True)

# ── COMPOSIÇÃO + INADIMPLÊNCIA ────────────────────────────────────────────────
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### 🥧 Composição da Receita Própria")
    st.caption(
        "**Como ler:** cada fatia mostra quanto cada tributo representa do total. "
        "O ISS costuma ser o maior porque incide sobre serviços — a atividade econômica "
        "dominante nas cidades. Municípios com IPTU muito pequeno têm cadastro imobiliário "
        "desatualizado ou muitas isenções irregulares."
    )
    fig3 = go.Figure(go.Pie(
        labels=["ISS","IPTU","ITBI","COSIP","Alvarás"],
        values=[iss_ano,iptu_ano,itbi_ano,cosip_ano,alv_ano], hole=0.45,
        marker_colors=["#1a4f82","#c8860a","#1b6b3a","#7c3aed","#0891b2"]))
    fig3.update_layout(height=300, margin=dict(t=10,b=10))
    st.plotly_chart(fig3, use_container_width=True)

with col_b:
    st.markdown("#### 🏘️ Inadimplência de IPTU por Bairro")
    st.caption(
        "**Como ler:** barras mais longas e mais vermelhas = mais imóveis sem pagar IPTU. "
        "Inadimplência acima de 30% num bairro é sinal de alerta — pode indicar dificuldade "
        "econômica da região ou problemas no sistema de cobrança municipal."
    )
    inad = imoveis.groupby("bairro").agg(
        total=("id_imovel","count"), inad=("inadimplente","sum")).reset_index()
    inad["tx"] = inad["inad"] / inad["total"] * 100
    fig4 = px.bar(inad.sort_values("tx", ascending=True), x="tx", y="bairro",
        orientation="h", color="tx",
        color_continuous_scale=["#d4eddf","#fef3c7","#fde8e8"],
        labels={"tx":"% Inadimplência","bairro":"Bairro"})
    fig4.update_layout(height=300, plot_bgcolor="white", coloraxis_showscale=False)
    st.plotly_chart(fig4, use_container_width=True)

# ── TRANSFERÊNCIAS ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 🏛️ Transferências Constitucionais")
st.info(
    "**O que são?** São valores que a União e os Estados são obrigados por lei a repassar "
    "aos municípios (CF arts. 158 e 159). Não dependem de fiscalização local, mas precisam "
    "ser monitorados porque oscilam com a economia. "
    "**FPM** = 25% do IR+IPI federal. "
    "**ICMS** = 25% do ICMS estadual. "
    "**IPVA** = 50% do IPVA estadual. "
    "**FUNDEB** = vinculado à educação."
)
t_pivot = transf[transf["ano"]==ano_sel].groupby("tipo_transferencia")["valor"].sum().reset_index()
cols_t = st.columns(len(t_pivot))
for i, (_, row) in enumerate(t_pivot.iterrows()):
    cols_t[i].metric(row["tipo_transferencia"], _fmt(row["valor"]))
