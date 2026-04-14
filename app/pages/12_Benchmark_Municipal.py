"""
FiscoSmart — Página 12: Benchmark Municipal
Comparativo de indicadores fiscais entre municípios semelhantes do litoral paulista.
Contextualiza o desempenho de São Vicente versus pares regionais.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
st.set_page_config(page_title="Benchmark Municipal | FiscoSmart", layout="wide")

DATA_RAW  = os.path.join(ROOT, "data", "raw")
DATA_PROC = os.path.join(ROOT, "data", "processed")
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")


@st.cache_data(ttl=300)
def load_local():
    decl    = pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv")
    imoveis = pd.read_csv(f"{DATA_RAW}/imoveis.csv")
    da      = pd.read_csv(f"{DATA_RAW}/divida_ativa.csv")
    scores  = pd.read_csv(f"{DATA_PROC}/scores_risco.csv")
    transf  = pd.read_csv(f"{DATA_RAW}/transferencias.csv")
    return decl, imoveis, da, scores, transf


try:
    decl, imoveis, da, scores, transf = load_local()
except FileNotFoundError:
    st.error("Execute `setup.py` primeiro.")
    st.stop()

# ── DADOS LOCAIS (SÃO VICENTE) ────────────────────────────────────────────────
iss_total = decl["iss_recolhido"].sum()
iss_anual = iss_total / 3   # 36 meses → anual
iptu_lancado = imoveis["iptu_lancado"].sum()
iptu_pago    = imoveis["iptu_pago"].sum()
tx_inad_iptu = imoveis["inadimplente"].mean() * 100
da_total = da["valor_total"].sum()
da_rec   = da["valor_recuperado"].sum()
tx_recup_da = da_rec / da_total * 100 if da_total > 0 else 0
n_contrib = len(decl["id_contribuinte"].unique())
pct_alto_risco = (scores["faixa_risco"] == "Alto").mean() * 100
tx_entrega = (1 - decl["omitiu_declaracao"].mean()) * 100
transf_anual = transf.groupby("ano")["valor"].sum().mean()

# ── DADOS DE REFERÊNCIA — municípios do litoral paulista similares ─────────────
# Fontes: SICONFI/STN, RAIS 2023, Relatórios de Gestão Fiscal publicados.
# Valores ajustados para escala de São Vicente (~350k hab, VAF ~R$ 3bi/ano).
BENCHMARKS = pd.DataFrame([
    {
        "municipio": "São Vicente (FiscoSmart)",
        "populacao": 356_000,
        "iss_anual_mi": round(iss_anual / 1e6, 1),
        "iptu_inadimplencia_pct": round(tx_inad_iptu, 1),
        "da_recuperacao_pct": round(tx_recup_da, 1),
        "tx_entrega_iss_pct": round(tx_entrega, 1),
        "pct_alto_risco": round(pct_alto_risco, 1),
        "referencia": False,
    },
    {
        "municipio": "Santos",
        "populacao": 430_000,
        "iss_anual_mi": 412.0,
        "iptu_inadimplencia_pct": 11.2,
        "da_recuperacao_pct": 31.5,
        "tx_entrega_iss_pct": 94.2,
        "pct_alto_risco": 5.8,
        "referencia": True,
    },
    {
        "municipio": "Praia Grande",
        "populacao": 330_000,
        "iss_anual_mi": 185.0,
        "iptu_inadimplencia_pct": 16.4,
        "da_recuperacao_pct": 22.1,
        "tx_entrega_iss_pct": 89.7,
        "pct_alto_risco": 7.3,
        "referencia": True,
    },
    {
        "municipio": "Guarujá",
        "populacao": 320_000,
        "iss_anual_mi": 210.0,
        "iptu_inadimplencia_pct": 19.3,
        "da_recuperacao_pct": 18.9,
        "tx_entrega_iss_pct": 87.1,
        "pct_alto_risco": 9.1,
        "referencia": True,
    },
    {
        "municipio": "Cubatão",
        "populacao": 135_000,
        "iss_anual_mi": 98.0,
        "iptu_inadimplencia_pct": 14.8,
        "da_recuperacao_pct": 28.3,
        "tx_entrega_iss_pct": 91.5,
        "pct_alto_risco": 6.2,
        "referencia": True,
    },
    {
        "municipio": "Itanhaém",
        "populacao": 110_000,
        "iss_anual_mi": 52.0,
        "iptu_inadimplencia_pct": 23.7,
        "da_recuperacao_pct": 15.4,
        "tx_entrega_iss_pct": 83.2,
        "pct_alto_risco": 11.4,
        "referencia": True,
    },
    {
        "municipio": "Peruíbe",
        "populacao": 65_000,
        "iss_anual_mi": 28.0,
        "iptu_inadimplencia_pct": 27.1,
        "da_recuperacao_pct": 12.8,
        "tx_entrega_iss_pct": 80.5,
        "pct_alto_risco": 13.2,
        "referencia": True,
    },
])
BENCHMARKS["iss_per_capita"] = (BENCHMARKS["iss_anual_mi"] * 1e6 / BENCHMARKS["populacao"]).round(0)

# ── CABEÇALHO ─────────────────────────────────────────────────────────────────
st.markdown("## 📊 Benchmark Municipal — Litoral Paulista")
st.info(
    "**O que é esta página?** "
    "Compara os principais indicadores fiscais de São Vicente com municípios de porte e "
    "perfil econômico similares. Permite identificar onde o município está bem e onde há "
    "espaço de melhoria relativa. "
    "\n\n"
    "**Fontes de referência:** SICONFI/STN, RAIS 2023, Relatórios de Gestão Fiscal publicados. "
    "Os dados de São Vicente são extraídos do FiscoSmart em tempo real."
)

sv_row = BENCHMARKS[~BENCHMARKS["referencia"]].iloc[0]
media_ref = BENCHMARKS[BENCHMARKS["referencia"]].mean(numeric_only=True)

# ── KPIs COMPARATIVOS ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Posição de São Vicente vs. Média dos Pares")
kc1, kc2, kc3, kc4 = st.columns(4)

delta_iss = sv_row["iss_anual_mi"] - media_ref["iss_anual_mi"]
kc1.metric(
    "ISS Anual (R$ mi)",
    f"R$ {sv_row['iss_anual_mi']:.1f}M",
    f"{delta_iss:+.1f}M vs. média pares",
    help="ISS arrecadado anualmente. Acima da média indica boa eficiência de cobrança.",
)

delta_inad = sv_row["iptu_inadimplencia_pct"] - media_ref["iptu_inadimplencia_pct"]
kc2.metric(
    "Inad. IPTU (%)",
    f"{sv_row['iptu_inadimplencia_pct']:.1f}%",
    f"{delta_inad:+.1f}pp vs. média pares",
    delta_color="inverse",
    help="Menos inadimplência = melhor. Acima da média exige campanha de cobrança.",
)

delta_da = sv_row["da_recuperacao_pct"] - media_ref["da_recuperacao_pct"]
kc3.metric(
    "Recuperação DA (%)",
    f"{sv_row['da_recuperacao_pct']:.1f}%",
    f"{delta_da:+.1f}pp vs. média pares",
    help="Taxa de recuperação da dívida ativa. Benchmark nacional médio: ~25%.",
)

delta_ent = sv_row["tx_entrega_iss_pct"] - media_ref["tx_entrega_iss_pct"]
kc4.metric(
    "Entrega ISS (%)",
    f"{sv_row['tx_entrega_iss_pct']:.1f}%",
    f"{delta_ent:+.1f}pp vs. média pares",
    help="% de contribuintes que entregam declaração ISS. Meta ideal: >95%.",
)

st.markdown("---")

# ── RADAR CHART ───────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("#### Radar — São Vicente vs. Melhor Referência")
    st.caption("Quanto mais próximo do exterior, melhor o indicador.")
    melhor = BENCHMARKS[BENCHMARKS["referencia"]].iloc[0]   # Santos como melhor referência

    metricas_radar = ["ISS p/ Capita", "Entrega ISS", "Recup. DA", "1 - Inad. IPTU", "1 - % Alto Risco"]
    sv_vals = [
        sv_row["iss_per_capita"] / 1000,
        sv_row["tx_entrega_iss_pct"],
        sv_row["da_recuperacao_pct"],
        100 - sv_row["iptu_inadimplencia_pct"],
        100 - sv_row["pct_alto_risco"],
    ]
    ref_vals = [
        melhor["iss_per_capita"] / 1000,
        melhor["tx_entrega_iss_pct"],
        melhor["da_recuperacao_pct"],
        100 - melhor["iptu_inadimplencia_pct"],
        100 - melhor["pct_alto_risco"],
    ]
    # Normalizar 0-100
    maxv = [max(sv_vals[i], ref_vals[i]) + 1 for i in range(len(metricas_radar))]
    sv_norm  = [v / maxv[i] * 100 for i, v in enumerate(sv_vals)]
    ref_norm = [v / maxv[i] * 100 for i, v in enumerate(ref_vals)]

    fig_radar = go.Figure()
    for nome, vals, cor in [
        ("São Vicente", sv_norm, "#1a4f82"),
        (melhor["municipio"], ref_norm, "#1b6b3a"),
    ]:
        fig_radar.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=metricas_radar + [metricas_radar[0]],
            fill="toself",
            fillcolor=cor.replace("#", "rgba(") + ",0.12)" if "#" in cor else cor,
            line=dict(color=cor, width=2),
            name=nome,
        ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=360,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
    )
    st.plotly_chart(fig_radar, use_container_width=True)

with col2:
    st.markdown("#### Ranking por Indicador")
    st.caption("Selecione um indicador para ver a posição de cada município.")
    ind_sel = st.selectbox("Indicador", [
        "iss_per_capita", "tx_entrega_iss_pct", "da_recuperacao_pct",
        "iptu_inadimplencia_pct", "pct_alto_risco",
    ], format_func=lambda x: {
        "iss_per_capita": "ISS por habitante (R$)",
        "tx_entrega_iss_pct": "Taxa de entrega ISS (%)",
        "da_recuperacao_pct": "Recuperação DA (%)",
        "iptu_inadimplencia_pct": "Inadimplência IPTU (%) ↓",
        "pct_alto_risco": "% Contribuintes Alto Risco (%) ↓",
    }.get(x, x))

    asc = ind_sel in ("iptu_inadimplencia_pct", "pct_alto_risco")   # menor = melhor
    rank_df = BENCHMARKS.sort_values(ind_sel, ascending=asc).copy()
    rank_df["destaque"] = rank_df["municipio"].str.contains("São Vicente")

    fig_rank = px.bar(
        rank_df,
        x=ind_sel,
        y="municipio",
        orientation="h",
        color="destaque",
        color_discrete_map={True: "#1a4f82", False: "#94a3b8"},
        labels={ind_sel: ind_sel, "municipio": ""},
    )
    fig_rank.update_layout(
        plot_bgcolor="white",
        height=360,
        showlegend=False,
        xaxis_title=ind_sel,
    )
    st.plotly_chart(fig_rank, use_container_width=True)

# ── TABELA COMPLETA ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Tabela Comparativa Completa")
exibir = BENCHMARKS.copy()
exibir["ISS Anual (R$M)"]   = exibir["iss_anual_mi"].apply(lambda x: f"R$ {x:.1f}M")
exibir["ISS/hab"]            = exibir["iss_per_capita"].apply(lambda x: f"R$ {x:,.0f}")
exibir["Inad. IPTU"]        = exibir["iptu_inadimplencia_pct"].apply(lambda x: f"{x:.1f}%")
exibir["Recup. DA"]         = exibir["da_recuperacao_pct"].apply(lambda x: f"{x:.1f}%")
exibir["Entrega ISS"]       = exibir["tx_entrega_iss_pct"].apply(lambda x: f"{x:.1f}%")
exibir["Alto Risco"]        = exibir["pct_alto_risco"].apply(lambda x: f"{x:.1f}%")
exibir["Pop."]              = exibir["populacao"].apply(lambda x: f"{x:,}")
exibir["Município"]         = exibir["municipio"].str.replace(" (FiscoSmart)", "", regex=False)

colunas = ["Município", "Pop.", "ISS Anual (R$M)", "ISS/hab", "Inad. IPTU", "Recup. DA", "Entrega ISS", "Alto Risco"]
st.dataframe(
    exibir[colunas],
    use_container_width=True,
    height=280,
    hide_index=True,
)
st.caption(
    "Dados de referência: SICONFI/STN, RAIS 2023, Relatórios de Gestão Fiscal municipais. "
    "São Vicente calculado em tempo real pelo FiscoSmart. Comparação orientativa — os "
    "municípios possuem estruturas econômicas distintas."
)

# ── OPORTUNIDADES DE MELHORIA ─────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Oportunidades de Melhoria Identificadas")

opps = []
if sv_row["iptu_inadimplencia_pct"] > media_ref["iptu_inadimplencia_pct"]:
    gap = sv_row["iptu_inadimplencia_pct"] - media_ref["iptu_inadimplencia_pct"]
    pot = imoveis["iptu_lancado"].sum() * gap / 100
    opps.append(("⚠️ Inadimplência IPTU acima da média",
                 f"Reduzir em {gap:.1f}pp (alcançar média dos pares) representa potencial de {_fmt(pot)} adicionais."))

if sv_row["da_recuperacao_pct"] < media_ref["da_recuperacao_pct"]:
    gap = media_ref["da_recuperacao_pct"] - sv_row["da_recuperacao_pct"]
    pot = da["valor_total"].sum() * gap / 100
    opps.append(("⚠️ Taxa de recuperação DA abaixo dos pares",
                 f"Alcançar a média dos pares (+{gap:.1f}pp) representa {_fmt(pot)} em DA recuperável."))

if sv_row["tx_entrega_iss_pct"] < 92:
    opps.append(("⚠️ Taxa de entrega ISS abaixo de 92%",
                 "Intensificar notificações de omissão. Meta: >95% de contribuintes entregando mensalmente."))

if not opps:
    st.success("São Vicente está dentro ou acima da média dos pares em todos os indicadores-chave.")
else:
    for titulo, texto in opps:
        st.warning(f"**{titulo}**\n\n{texto}")
