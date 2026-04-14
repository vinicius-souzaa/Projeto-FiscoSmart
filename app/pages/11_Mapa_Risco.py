"""
FiscoSmart — Página 11: Mapa de Risco Fiscal por Bairro
Heatmap geoespacial com concentração de contribuintes de alto risco,
inadimplência IPTU e potencial de recuperação por território.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
st.set_page_config(page_title="Mapa de Risco | FiscoSmart", layout="wide")

DATA_RAW  = os.path.join(ROOT, "data", "raw")
DATA_PROC = os.path.join(ROOT, "data", "processed")
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

# Coordenadas aproximadas dos bairros de São Vicente — SP
# (centro da cidade: -23.9635, -46.3922)
BAIRROS_COORDS = {
    "Centro":                  (-23.9582, -46.3919),
    "Vila Margarida":          (-23.9645, -46.3815),
    "Japuí":                   (-23.9823, -46.4012),
    "Catiapoa":                (-23.9756, -46.3945),
    "Cidade Nautica":          (-23.9612, -46.4145),
    "Vila São Jorge":          (-23.9534, -46.3856),
    "Vila Bocaina":            (-23.9678, -46.3723),
    "Parque Bitaru":           (-23.9523, -46.4067),
    "Esplanada dos Barreiros": (-23.9789, -46.3812),
    "Alto da Boa Vista":       (-23.9712, -46.3634),
    "Vila Nova":               (-23.9623, -46.3978),
    "Jardim Rio Branco":       (-23.9845, -46.3756),
    "Glória":                  (-23.9567, -46.4089),
    "Ilha Porchat":            (-23.9478, -46.4023),
    "Porto Grande":            (-23.9901, -46.3923),
}


@st.cache_data(ttl=300)
def load():
    scores   = pd.read_csv(f"{DATA_PROC}/scores_risco.csv")
    imoveis  = pd.read_csv(f"{DATA_RAW}/imoveis.csv")
    contribs = pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
    da       = pd.read_csv(f"{DATA_RAW}/divida_ativa.csv")
    return scores, imoveis, contribs, da

try:
    scores, imoveis, contribs, da = load()
except FileNotFoundError:
    st.error("Execute `setup.py` primeiro.")
    st.stop()

st.markdown("## 🗺️ Mapa de Risco Fiscal — São Vicente")
st.info(
    "**O que é esta página?** "
    "Visualização territorial do risco fiscal: onde estão concentrados os contribuintes "
    "de alto risco, qual bairro tem mais inadimplência de IPTU, e onde o potencial de "
    "recuperação tributária é maior. Permite ao gestor alocar auditores por região e "
    "planejar campanhas de cobrança geograficamente direcionadas."
)

# ── PREPARAR DADOS POR BAIRRO ─────────────────────────────────────────────────
# ISS: scores por bairro
iss_bairro = (scores
    .groupby("bairro")
    .agg(
        n_total=("id_contribuinte", "count"),
        n_alto=("faixa_risco", lambda x: (x == "Alto").sum()),
        n_medio=("faixa_risco", lambda x: (x == "Médio").sum()),
        score_medio=("score_risco", "mean"),
        potencial_iss=("receita_media_12m", lambda x: x[scores.loc[x.index, "faixa_risco"] == "Alto"].sum() * 0.03 * 0.4),
    )
    .reset_index()
)
iss_bairro["pct_alto"] = (iss_bairro["n_alto"] / iss_bairro["n_total"] * 100).round(1)

# IPTU: inadimplência por bairro
iptu_bairro = (imoveis
    .groupby("bairro")
    .agg(
        n_imoveis=("id_imovel", "count"),
        n_inad=("inadimplente", "sum"),
        valor_inad=("iptu_lancado", lambda x: x[imoveis.loc[x.index, "inadimplente"] == 1].sum()),
    )
    .reset_index()
)
iptu_bairro["pct_inad_iptu"] = (iptu_bairro["n_inad"] / iptu_bairro["n_imoveis"] * 100).round(1)

# Merge e adicionar coordenadas
df_bairro = iss_bairro.merge(iptu_bairro, on="bairro", how="outer").fillna(0)
df_bairro["lat"] = df_bairro["bairro"].map(lambda b: BAIRROS_COORDS.get(b, (-23.96, -46.39))[0])
df_bairro["lon"] = df_bairro["bairro"].map(lambda b: BAIRROS_COORDS.get(b, (-23.96, -46.39))[1])
df_bairro["potencial_total"] = df_bairro["potencial_iss"] + df_bairro["valor_inad"] * 0.3
df_bairro["score_territorio"] = (
    df_bairro["pct_alto"] * 0.4 +
    df_bairro["pct_inad_iptu"] * 0.3 +
    (df_bairro["potencial_total"] / df_bairro["potencial_total"].max() * 100) * 0.3
).clip(0, 100).round(1)

# ── FILTROS ───────────────────────────────────────────────────────────────────
camadas = st.multiselect(
    "Camada de visualização",
    ["Score de Risco ISS", "Inadimplência IPTU", "Score de Território Consolidado"],
    default=["Score de Território Consolidado"],
)

# ── KPIs POR BAIRRO ───────────────────────────────────────────────────────────
st.markdown("---")
top3 = df_bairro.sort_values("score_territorio", ascending=False).head(3)
cols_top = st.columns(3)
for i, (_, row) in enumerate(top3.iterrows()):
    cols_top[i].metric(
        f"#{i+1} {row['bairro']}",
        f"Score {row['score_territorio']:.0f}/100",
        f"{row['n_alto']:.0f} alto risco · IPTU {row['pct_inad_iptu']:.0f}% inad.",
    )

st.markdown("---")

# ── MAPA PRINCIPAL ────────────────────────────────────────────────────────────
st.markdown("#### Mapa de Calor — Risco Fiscal por Território")
st.caption(
    "Cada bolha representa um bairro. Tamanho = número de contribuintes ISS de alto risco. "
    "Cor = score de território consolidado (ISS + IPTU + potencial). "
    "Clique em uma bolha para ver o detalhe do bairro."
)

if "Score de Território Consolidado" in camadas:
    cor_col = "score_territorio"
    cor_titulo = "Score Território"
elif "Score de Risco ISS" in camadas:
    cor_col = "pct_alto"
    cor_titulo = "% Alto Risco ISS"
else:
    cor_col = "pct_inad_iptu"
    cor_titulo = "% Inad. IPTU"

fig_map = px.scatter_mapbox(
    df_bairro,
    lat="lat",
    lon="lon",
    size="n_alto",
    color=cor_col,
    color_continuous_scale=["#1b6b3a", "#fef3c7", "#c8860a", "#9b1c1c"],
    range_color=[0, df_bairro[cor_col].max()],
    hover_name="bairro",
    hover_data={
        "n_alto": True,
        "pct_alto": True,
        "pct_inad_iptu": True,
        "score_territorio": True,
        "potencial_total": True,
        "lat": False,
        "lon": False,
    },
    labels={
        "n_alto": "Contribuintes Alto Risco",
        "pct_alto": "% Alto Risco ISS",
        "pct_inad_iptu": "% Inad. IPTU",
        "score_territorio": "Score Território",
        "potencial_total": "Potencial (R$)",
    },
    mapbox_style="open-street-map",
    center={"lat": -23.965, "lon": -46.392},
    zoom=12,
    size_max=50,
    height=520,
)
fig_map.update_layout(
    coloraxis_colorbar_title=cor_titulo,
    margin={"r": 0, "t": 0, "l": 0, "b": 0},
)
st.plotly_chart(fig_map, use_container_width=True)

# ── PAINEL DE DETALHES ────────────────────────────────────────────────────────
st.markdown("---")
col_l, col_r = st.columns(2)

with col_l:
    st.markdown("#### Ranking de Bairros por Score de Território")
    st.caption("Score consolidado = 40% risco ISS + 30% inadimplência IPTU + 30% potencial financeiro")
    rank = df_bairro.sort_values("score_territorio", ascending=False).copy()
    rank["Score"] = rank["score_territorio"].apply(lambda x: f"{x:.0f}")
    rank["Alto Risco"] = rank["n_alto"].apply(lambda x: f"{int(x):,}")
    rank["IPTU Inad."] = rank["pct_inad_iptu"].apply(lambda x: f"{x:.1f}%")
    rank["Potencial"] = rank["potencial_total"].apply(_fmt)
    st.dataframe(
        rank[["bairro", "Score", "Alto Risco", "IPTU Inad.", "Potencial"]]
        .rename(columns={"bairro": "Bairro"}),
        use_container_width=True,
        height=380,
        hide_index=True,
    )

with col_r:
    st.markdown("#### Potencial de Recuperação por Bairro")
    st.caption("Soma estimada: ISS de alto risco × 40% recuperação + IPTU inadimplente × 30% recuperação")
    fig_pot = px.bar(
        df_bairro.sort_values("potencial_total", ascending=True).tail(12),
        x="potencial_total",
        y="bairro",
        orientation="h",
        color="score_territorio",
        color_continuous_scale=["#1b6b3a", "#c8860a", "#9b1c1c"],
        labels={"potencial_total": "Potencial (R$)", "bairro": "Bairro", "score_territorio": "Score"},
    )
    fig_pot.update_layout(
        plot_bgcolor="white",
        height=380,
        coloraxis_showscale=False,
        xaxis_title="Potencial de Recuperação (R$)",
    )
    st.plotly_chart(fig_pot, use_container_width=True)

# ── DETALHAMENTO POR BAIRRO ───────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Detalhamento por Bairro Selecionado")
bairro_sel = st.selectbox(
    "Selecione um bairro",
    df_bairro.sort_values("score_territorio", ascending=False)["bairro"].tolist(),
)

row = df_bairro[df_bairro["bairro"] == bairro_sel].iloc[0]

dc1, dc2, dc3, dc4, dc5 = st.columns(5)
dc1.metric("Score de Território",    f"{row['score_territorio']:.0f}/100")
dc2.metric("Contribuintes ISS",       f"{int(row['n_total']):,}")
dc3.metric("Alto Risco ISS",          f"{int(row['n_alto']):,} ({row['pct_alto']:.1f}%)")
dc4.metric("Imóveis IPTU Inadimpl.", f"{int(row['n_inad']):,} ({row['pct_inad_iptu']:.1f}%)")
dc5.metric("Potencial Estimado",      _fmt(row["potencial_total"]))

# Contribuintes do bairro
contrib_bairro = scores[scores["bairro"] == bairro_sel].sort_values("score_risco", ascending=False)
if len(contrib_bairro) > 0:
    st.markdown(f"**Top contribuintes de alto risco em {bairro_sel}:**")
    cb = contrib_bairro.head(10).copy()
    cb["Score"] = cb["score_risco"].apply(lambda x: f"{x:.0f}")
    cb["Receita Média"] = cb["receita_media_12m"].apply(_fmt)
    st.dataframe(
        cb[["id_contribuinte", "cnae", "porte", "Score", "faixa_risco", "gap_medio_pct", "Receita Média"]]
        .rename(columns={"faixa_risco": "Faixa", "gap_medio_pct": "Gap %"}),
        use_container_width=True,
        height=260,
        hide_index=True,
    )
