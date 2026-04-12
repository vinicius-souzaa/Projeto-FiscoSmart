"""
FiscoSmart — Página 8: Previsão de Arrecadação
Prophet por tributo — próximos 6 meses com intervalo de confiança
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
st.set_page_config(page_title="Previsão | FiscoSmart", layout="wide")

DATA_PROC = os.path.join(ROOT, 'data', 'processed')
DATA_RAW  = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'raw')
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")

@st.cache_data(ttl=300)
def load():
    try:
        fc = pd.read_csv(f"{DATA_PROC}/forecast_arrecadacao.csv")
        fc["ds"] = pd.to_datetime(fc["ds"])
        return fc, True
    except FileNotFoundError:
        return pd.DataFrame(), False

fc, ok = load()

st.markdown("## 📈 Previsão de Arrecadação — Prophet")
st.caption("Modelo de séries temporais com sazonalidade anual · Horizonte: 6 meses")

if not ok or len(fc) == 0:
    st.warning("Execute `src/forecasting.py` para gerar as previsões.")
    st.stop()

tributos_disp = fc["tipo"].unique().tolist()
tributo_sel   = st.selectbox("Selecione o tributo", tributos_disp, index=0)

df_t = fc[fc["tipo"] == tributo_sel].sort_values("ds")
historico = df_t[~df_t["is_forecast"]].copy()
previsao  = df_t[df_t["is_forecast"]].copy()

# ── GRÁFICO PRINCIPAL ─────────────────────────────────────────────────────────
st.markdown(f"#### {tributo_sel} — Histórico + Previsão (6 meses)")

fig = go.Figure()

# Intervalo de confiança
fig.add_scatter(
    x=pd.concat([previsao["ds"], previsao["ds"].iloc[::-1]]),
    y=pd.concat([previsao["yhat_upper"], previsao["yhat_lower"].iloc[::-1]]),
    fill="toself", fillcolor="rgba(26,79,130,0.12)",
    line=dict(color="rgba(255,255,255,0)"),
    name="IC 95%", showlegend=True,
)

# Histórico
fig.add_scatter(
    x=historico["ds"], y=historico["yhat"],
    mode="lines", line=dict(color="#1a4f82", width=2.5),
    name="Histórico",
)

# Previsão
fig.add_scatter(
    x=previsao["ds"], y=previsao["yhat"],
    mode="lines+markers",
    line=dict(color="#c8860a", width=2.5, dash="dash"),
    marker=dict(size=8, color="#c8860a"),
    name="Previsão",
)

# Linha divisória histórico/previsão
if len(historico) > 0:
    fig.add_vline(
        x=historico["ds"].max(),
        line_dash="dot", line_color="#888",
        annotation_text="Hoje", annotation_position="top",
    )

fig.update_layout(
    plot_bgcolor="white", height=420,
    hovermode="x unified",
    xaxis_title="Mês", yaxis_title="Arrecadação (R$)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig, use_container_width=True)

# ── TABELA DE PREVISÕES ───────────────────────────────────────────────────────
st.markdown("#### Valores Previstos por Mês")
prev_tab = previsao[["ds","yhat","yhat_lower","yhat_upper"]].copy()
prev_tab["Mês"]     = prev_tab["ds"].dt.strftime("%b/%Y")
prev_tab["Previsto"]= prev_tab["yhat"].apply(_fmt)
prev_tab["IC Inf."] = prev_tab["yhat_lower"].apply(_fmt)
prev_tab["IC Sup."] = prev_tab["yhat_upper"].apply(_fmt)
prev_tab["Variação vs. Últ. Mês"] = prev_tab["yhat"].pct_change().fillna(0).apply(lambda x: f"{x*100:+.1f}%")
st.dataframe(
    prev_tab[["Mês","Previsto","IC Inf.","IC Sup.","Variação vs. Últ. Mês"]],
    use_container_width=True, hide_index=True,
)

# ── COMPARAÇÃO COM META ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 🎯 Comparação com Meta Municipal")
meta_mensal_input = st.number_input(
    f"Meta mensal de {tributo_sel} (R$)",
    min_value=0,
    value=int(historico["yhat"].mean() * 1.08) if len(historico) > 0 else 1_000_000,
    step=50_000,
    format="%d",
)

if len(previsao) > 0:
    previsao = previsao.copy()
    previsao["meta"] = meta_mensal_input
    previsao["gap_meta"] = previsao["yhat"] - previsao["meta"]
    previsao["atingiu"] = previsao["gap_meta"] >= 0
    n_acima = previsao["atingiu"].sum()
    gap_total = previsao["gap_meta"].sum()

    cm1, cm2, cm3 = st.columns(3)
    cm1.metric("Meses acima da meta", f"{n_acima}/{len(previsao)}")
    cm2.metric("Gap acumulado vs. meta", _fmt(abs(gap_total)),
               "Acima da meta" if gap_total >= 0 else "Abaixo da meta")
    cm3.metric("Média prevista", _fmt(previsao["yhat"].mean()),
               f"Meta: {_fmt(meta_mensal_input)}")

    fig_meta = go.Figure()
    colors = ["#1b6b3a" if a else "#9b1c1c" for a in previsao["atingiu"]]
    fig_meta.add_bar(
        x=previsao["ds"].dt.strftime("%b/%Y"),
        y=previsao["yhat"],
        marker_color=colors,
        name="Previsto",
        text=previsao["yhat"].apply(_fmt),
        textposition="outside",
    )
    fig_meta.add_scatter(
        x=previsao["ds"].dt.strftime("%b/%Y"),
        y=previsao["meta"],
        mode="lines", line=dict(color="#c8860a", dash="dash", width=2),
        name="Meta",
    )
    fig_meta.update_layout(
        plot_bgcolor="white", height=360,
        title="Previsão vs. Meta — verde = acima, vermelho = abaixo",
        hovermode="x unified",
    )
    st.plotly_chart(fig_meta, use_container_width=True)

    if gap_total < 0:
        st.error(
            f"⚠️ O modelo prevê que {tributo_sel} ficará {_fmt(abs(gap_total))} abaixo da meta "
            f"nos próximos {len(previsao)} meses. Para compensar, seria necessário recuperar em média "
            f"{_fmt(abs(gap_total)/len(previsao))} adicionais por mês via fiscalização ou renegociação."
        )

# ── COMPARAÇÃO ENTRE TRIBUTOS ─────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Comparação de Crescimento — Todos os Tributos")
prev_todos = fc[fc["is_forecast"]].groupby("tipo")["yhat"].mean().reset_index()
hist_todos = fc[~fc["is_forecast"]].groupby("tipo")["yhat"].mean().reset_index()
comp = prev_todos.merge(hist_todos, on="tipo", suffixes=("_prev","_hist"))
comp["variacao"] = (comp["yhat_prev"] - comp["yhat_hist"]) / comp["yhat_hist"] * 100

fig_comp = px.bar(
    comp.sort_values("variacao"), x="variacao", y="tipo", orientation="h",
    title="Variação esperada: média prevista vs. média histórica (%)",
    labels={"variacao":"Variação %","tipo":"Tributo"},
    color="variacao",
    color_discrete_sequence=["#9b1c1c" if v < 0 else "#1b6b3a" for v in comp.sort_values("variacao")["variacao"]],
    color_continuous_scale=["#fde8e8","#fef3c7","#d4eddf"],
    text=comp.sort_values("variacao")["variacao"].apply(lambda x: f"{x:+.1f}%"),
)
fig_comp.update_layout(plot_bgcolor="white", height=300, coloraxis_showscale=False)
st.plotly_chart(fig_comp, use_container_width=True)
