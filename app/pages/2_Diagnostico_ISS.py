"""
FiscoSmart — Página 2: Diagnóstico ISS
Gap por setor, omissões, sazonalidade, radar de inconsistências
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
st.set_page_config(page_title="Diagnóstico ISS | FiscoSmart", layout="wide")

DATA_RAW = os.path.join(ROOT, "data", "raw")

@st.cache_data(ttl=300)
def load():
    return (pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv"),
            pd.read_csv(f"{DATA_RAW}/contribuintes.csv"))

_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")
decl, contribs = load()

st.markdown("## 🔍 Diagnóstico Fiscal — ISS")
st.info(
    "**O que é esta página?** "
    "O ISS (Imposto Sobre Serviços) é regulado pela LC 116/2003. "
    "Sua alíquota varia entre **2% e 5%** da receita bruta declarada pelo prestador. "
    "O problema central do ISS é a **subnotificação**: empresas declaram receitas menores "
    "do que as reais para pagar menos imposto. Esta página identifica quem está fazendo isso, "
    "usando como referência a média do próprio setor (benchmark por CNAE)."
)

col1,col2,col3 = st.columns(3)
with col1:
    ano_sel = st.selectbox("Ano", sorted(decl["ano"].unique(), reverse=True))
with col2:
    cnaes = ["Todos"] + sorted(decl["cnae"].unique().tolist())
    cnae_sel = st.selectbox("Setor (CNAE)", cnaes)
with col3:
    portes = ["Todos"] + sorted(contribs["porte"].unique().tolist())
    porte_sel = st.selectbox("Porte", portes)

df = decl[decl["ano"]==ano_sel].copy()
if cnae_sel != "Todos": df = df[df["cnae"]==cnae_sel]
if porte_sel != "Todos":
    cids = contribs[contribs["porte"]==porte_sel]["id_contribuinte"].tolist()
    df = df[df["id_contribuinte"].isin(cids)]

# KPIs
c1,c2,c3,c4 = st.columns(4)
c1.metric("Gap Total ISS",  _fmt(df["gap_absoluto"].sum()),
    help="Soma de todo o ISS que deveria ter sido recolhido mas não foi, estimado pela diferença entre receita esperada (benchmark) e receita declarada.")
c2.metric("Gap Médio / Contribuinte", _fmt(df.groupby("id_contribuinte")["gap_absoluto"].sum().mean()),
    help="Valor médio de ISS não recolhido por contribuinte. Quanto maior, mais concentrado é o problema em poucos contribuintes.")
c3.metric("Omissões de Declaração", f'{df["omitiu_declaracao"].sum():,}',
    f'{df["omitiu_declaracao"].mean()*100:.1f}% do total',
    help="Número de meses em que contribuintes não entregaram nenhuma declaração. Omissão é infração prevista no CTN art. 113.")
c4.metric("Contribuintes c/ Gap > 30%", f'{(df.groupby("id_contribuinte")["gap_percentual"].mean() > 30).sum():,}',
    help="Número de contribuintes que sistematicamente declaram mais de 30% abaixo do benchmark do seu setor — principal indício de subnotificação.")

st.markdown("---")

# Gap por setor
st.markdown("#### 📊 Gap de Arrecadação por Setor (CNAE)")
st.caption(
    "**O que é CNAE?** É o Código Nacional de Atividade Econômica — identifica o setor de "
    "cada empresa (ex: 6201-5 = desenvolvimento de software, 5611-2 = restaurantes). "
    "**Como ler este gráfico:** barras mais longas = mais ISS não recolhido naquele setor. "
    "A cor indica o gap percentual médio — vermelho escuro significa que as empresas do setor "
    "declaram muito abaixo da média esperada, o que é forte indício de sonegação sistemática."
)

gap_cnae = (df.groupby("cnae").agg(
    gap_medio=("gap_percentual","mean"), gap_total=("gap_absoluto","sum"),
    n_contrib=("id_contribuinte","nunique"), n_omissoes=("omitiu_declaracao","sum"))
    .reset_index().sort_values("gap_total", ascending=False))

col_g1, col_g2 = st.columns(2)
with col_g1:
    fig = px.bar(gap_cnae.head(15), x="gap_total", y="cnae", orientation="h",
        title="Top 15 setores por valor absoluto de gap",
        labels={"gap_total":"Gap R$","cnae":"CNAE"},
        color="gap_medio", color_continuous_scale=["#d4eddf","#fef3c7","#fde8e8"])
    fig.update_layout(height=400, plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)

with col_g2:
    fig2 = px.scatter(gap_cnae, x="n_contrib", y="gap_medio", size="gap_total",
        title="Nº contribuintes × gap médio (tamanho = impacto total)",
        labels={"n_contrib":"Nº Contribuintes","gap_medio":"Gap Médio %"},
        color="gap_medio", color_continuous_scale="RdYlGn_r", hover_data=["cnae"])
    fig2.update_layout(height=400, plot_bgcolor="white")
    st.plotly_chart(fig2, use_container_width=True)

st.caption(
    "💡 **Interpretação:** setores no canto superior direito do segundo gráfico têm muitos "
    "contribuintes E gap médio alto — são os mais prioritários para fiscalização porque o "
    "impacto potencial de recuperação é maior."
)

# Heatmap omissões
st.markdown("---")
st.markdown("#### 🗓️ Mapa de Omissões — Quem Não Declarou e Quando")
st.caption(
    "**Como ler:** cada linha é um contribuinte. Cada coluna é um mês. "
    "**Verde = declarou** no prazo. **Vermelho = não entregou** declaração. "
    "Padrões de vermelho em blocos (vários meses seguidos) indicam abandono fiscal — "
    "a empresa pode estar operando informalmente ou se preparando para encerrar irregularmente. "
    "Mostrado aqui os 30 contribuintes com mais omissões."
)
top_om = (df.groupby("id_contribuinte")["omitiu_declaracao"]
    .sum().sort_values(ascending=False).head(30).index.tolist())
hm_df = df[df["id_contribuinte"].isin(top_om)].pivot_table(
    index="id_contribuinte", columns="competencia",
    values="omitiu_declaracao", aggfunc="max").fillna(0)
fig_hm = px.imshow(hm_df, aspect="auto",
    color_continuous_scale=[[0,"#d4eddf"],[0.5,"#fef3c7"],[1,"#fde8e8"]],
    title="Top 30 contribuintes com mais omissões — verde=declarou, vermelho=omitiu",
    labels={"x":"Mês","y":"ID Contribuinte","color":"Omitiu"})
fig_hm.update_layout(height=420, coloraxis_showscale=False)
st.plotly_chart(fig_hm, use_container_width=True)

# Sazonalidade + Radar
st.markdown("---")
col_s1, col_s2 = st.columns(2)
with col_s1:
    st.markdown("#### 📅 Sazonalidade — Declarado vs. Esperado por Mês")
    st.caption(
        "**O que é sazonalidade?** É a variação natural de um setor ao longo do ano. "
        "Restaurantes faturam mais em dezembro (festas), construtoras faturam menos em janeiro "
        "(chuvas). Esta análise separa queda *normal* de queda *suspeita*. "
        "**Como ler:** a barra azul é o que foi declarado. A linha laranja é o que era esperado "
        "baseado no benchmark do setor. Barras muito abaixo da linha em meses de alta "
        "são o principal alvo de fiscalização."
    )
    cnae_saz = st.selectbox("CNAE para análise", sorted(decl["cnae"].unique()), key="csaz")
    saz = decl[decl["cnae"]==cnae_saz].groupby("mes")["receita_declarada"].mean().reset_index()
    ben = decl[decl["cnae"]==cnae_saz].groupby("mes")["receita_real_estimada"].mean().reset_index()
    fig_s = go.Figure()
    fig_s.add_bar(x=saz["mes"], y=saz["receita_declarada"],
                  name="Declarado", marker_color="#1a4f82")
    fig_s.add_scatter(x=ben["mes"], y=ben["receita_real_estimada"],
                      name="Esperado (benchmark)",
                      line=dict(color="#c8860a", dash="dash", width=2))
    fig_s.update_layout(plot_bgcolor="white", height=320,
                        xaxis_title="Mês", yaxis_title="Receita média (R$)")
    st.plotly_chart(fig_s, use_container_width=True)

with col_s2:
    st.markdown("#### 🕸️ Radar de Inconsistências — Por Contribuinte")
    st.caption(
        "**O que é este gráfico?** Um radar mostra 6 indicadores de risco para um contribuinte "
        "específico. Quanto maior a área colorida, maior o risco fiscal daquele contribuinte. "
        "**Indicadores:** Gap vs. benchmark (declara muito abaixo do setor?), "
        "Taxa de omissão (não entrega declarações?), Variabilidade de receita (oscila demais?), "
        "Taxa de retificação (corrige declarações com frequência?), "
        "Meses sem dados (sumiu do sistema?). "
        "Um radar com área grande em vermelho é candidato prioritário à fiscalização."
    )
    cid_sel = st.number_input("ID do Contribuinte", min_value=1, max_value=2000, value=1)
    cd_c = df[df["id_contribuinte"]==cid_sel]
    if len(cd_c) > 0:
        metrics = {
            "Gap vs. Benchmark": min(100, cd_c["gap_percentual"].mean()),
            "Taxa de Omissão (%)": cd_c["omitiu_declaracao"].mean()*100,
            "Variab. Receita": min(100, cd_c["receita_declarada"].std()/(cd_c["receita_declarada"].mean()+1)*100),
            "Taxa Retificação (%)": cd_c["retificou"].mean()*100,
            "Meses sem Dados (%)": (cd_c["receita_declarada"]==0).mean()*100,
            "Score Global": min(100, cd_c["gap_percentual"].mean() * 0.8),
        }
        cats = list(metrics.keys()); vals = list(metrics.values())
        fig_r = go.Figure(go.Scatterpolar(
            r=vals+[vals[0]], theta=cats+[cats[0]],
            fill="toself", fillcolor="rgba(155,28,28,0.2)",
            line=dict(color="#9b1c1c", width=2)))
        fig_r.update_layout(polar=dict(radialaxis=dict(range=[0,100])), height=320)
        st.plotly_chart(fig_r, use_container_width=True)
        info = contribs[contribs["id_contribuinte"]==cid_sel]
        if len(info) > 0:
            r = info.iloc[0]
            st.caption(f"**{r['razao_social']}** · CNAE: {r['cnae']} · {r['porte']} · {r['regime_tributario']}")
    else:
        st.info("Nenhum dado para este contribuinte no período selecionado.")

# Tabela
st.markdown("---")
st.markdown("#### 📋 Contribuintes com Maior Gap — Lista de Investigação")
st.caption(
    "Ordenados pelo valor absoluto de ISS não recolhido no período. "
    "Esta lista é o ponto de partida para o auditor selecionar os próximos a fiscalizar. "
    "Para a priorização completa (considerando custo da fiscalização e probabilidade de "
    "irregularidade), acesse a página **Priorização Fiscal**."
)
top_gap = (df.groupby("id_contribuinte").agg(
    gap=("gap_absoluto","sum"), omissoes=("omitiu_declaracao","sum"),
    gap_pct=("gap_percentual","mean")).reset_index()
    .merge(contribs[["id_contribuinte","razao_social","cnae","porte","bairro"]], on="id_contribuinte")
    .sort_values("gap", ascending=False).head(20))
top_gap["Gap R$"] = top_gap["gap"].apply(_fmt)
top_gap["Gap %"]  = top_gap["gap_pct"].apply(lambda x: f"{x:.1f}%")
st.dataframe(
    top_gap[["id_contribuinte","razao_social","cnae","porte","bairro","Gap R$","Gap %","omissoes"]]
    .rename(columns={"omissoes":"Omissões"}),
    use_container_width=True, height=350)
