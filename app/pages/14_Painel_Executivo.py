"""
FiscoSmart — Página 14: Painel Executivo
Visão simplificada para o Secretário de Finanças e gestores:
  - Semáforo de situação fiscal
  - KPIs estratégicos sem jargão técnico
  - Tendências e metas
  - Alertas de alto nível

Não exige conhecimento de ML ou análise de dados.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys, os, json
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
st.set_page_config(
    page_title="Painel Executivo | FiscoSmart",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_RAW  = os.path.join(ROOT, "data", "raw")
DATA_PROC = os.path.join(ROOT, "data", "processed")
MODELS_DIR= os.path.join(ROOT, "models")

_fmt  = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")
_fmtM = lambda v: f"R$ {v/1e6:.1f}M"


@st.cache_data(ttl=300)
def load():
    decl    = pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv")
    imoveis = pd.read_csv(f"{DATA_RAW}/imoveis.csv")
    da      = pd.read_csv(f"{DATA_RAW}/divida_ativa.csv")
    transf  = pd.read_csv(f"{DATA_RAW}/transferencias.csv")
    scores  = pd.read_csv(f"{DATA_PROC}/scores_risco.csv")
    fc      = pd.read_csv(f"{DATA_PROC}/forecast_arrecadacao.csv")
    try:
        insights_raw = json.loads(open(f"{DATA_PROC}/insights_latest.json", encoding="utf-8").read())
    except Exception:
        insights_raw = []
    return decl, imoveis, da, transf, scores, fc, insights_raw


try:
    decl, imoveis, da, transf, scores, fc, insights_raw = load()
except FileNotFoundError:
    st.error("Execute `setup.py` primeiro.")
    st.stop()

# ── CALCULAR KPIs ─────────────────────────────────────────────────────────────
ano_recente = decl["ano"].max()
ano_ant     = ano_recente - 1

iss_atual = decl[decl["ano"] == ano_recente]["iss_recolhido"].sum()
iss_ant   = decl[decl["ano"] == ano_ant]["iss_recolhido"].sum() if ano_ant in decl["ano"].values else iss_atual
var_iss   = (iss_atual - iss_ant) / iss_ant * 100 if iss_ant > 0 else 0

iptu_pago     = imoveis["iptu_pago"].sum()
iptu_lancado  = imoveis["iptu_lancado"].sum()
tx_inad_iptu  = imoveis["inadimplente"].mean() * 100

da_total = da["valor_total"].sum()
da_rec   = da["valor_recuperado"].sum()
da_aberto= da_total - da_rec
tx_recup  = da_rec / da_total * 100 if da_total > 0 else 0

n_alto_risco = (scores["faixa_risco"] == "Alto").sum()
n_contrib    = len(scores)
tx_omissao   = decl[decl["ano"] == ano_recente]["omitiu_declaracao"].mean() * 100

transf_anual = transf[transf["ano"] == ano_recente]["valor"].sum()
receita_total = iss_atual + iptu_pago + transf_anual

# Previsão 6 meses
fc_fut = fc[fc["is_forecast"] == True]
prev_iss  = fc_fut[fc_fut["tipo"] == "ISS"]["yhat"].sum() if "tipo" in fc.columns else 0
prev_iptu = fc_fut[fc_fut["tipo"] == "IPTU"]["yhat"].sum() if "tipo" in fc.columns else 0

# Alertas de alta severidade
alertas_altos = [i for i in insights_raw if i.get("severidade") == "alta"]

# ── CABEÇALHO EXECUTIVO ───────────────────────────────────────────────────────
st.markdown(
    f"<div style='background:#1a4f82;padding:20px 28px;border-radius:12px;margin-bottom:16px'>"
    f"<h2 style='color:white;margin:0'>🏛️ Painel Executivo — São Vicente</h2>"
    f"<p style='color:#b8d4f0;margin:4px 0 0'>Atualizado em {date.today().strftime('%d/%m/%Y')} "
    f"· Dados de {ano_recente} · Uso restrito à Secretaria de Finanças</p>"
    f"</div>",
    unsafe_allow_html=True,
)

# ── SEMÁFORO DE SITUAÇÃO FISCAL ───────────────────────────────────────────────
st.markdown("### Situação Fiscal Geral")

def semaforo(valor, bom, alerta, pior_melhor="maior"):
    if pior_melhor == "maior":
        if valor >= bom:   return "🟢", "Boa"
        if valor >= alerta: return "🟡", "Atenção"
        return "🔴", "Crítica"
    else:  # menor é melhor
        if valor <= bom:    return "🟢", "Boa"
        if valor <= alerta: return "🟡", "Atenção"
        return "🔴", "Crítica"

sem_iss,  sit_iss   = semaforo(var_iss, 5, 0)
sem_iptu, sit_iptu  = semaforo(tx_inad_iptu, 15, 25, pior_melhor="menor")
sem_da,   sit_da    = semaforo(tx_recup, 25, 15)
sem_iss2, sit_iss2  = semaforo(100 - tx_omissao, 90, 80)

sc1, sc2, sc3, sc4 = st.columns(4)
for col, sem, sit, titulo, detalhe in [
    (sc1, sem_iss,  sit_iss,  "ISS",              f"Crescimento {var_iss:+.1f}% a/a"),
    (sc2, sem_iptu, sit_iptu, "IPTU",             f"Inadimplência: {tx_inad_iptu:.1f}%"),
    (sc3, sem_da,   sit_da,   "Dívida Ativa",     f"Recuperação: {tx_recup:.1f}%"),
    (sc4, sem_iss2, sit_iss2, "Cumprimento ISS",  f"Entrega declarações: {100-tx_omissao:.1f}%"),
]:
    with col:
        st.markdown(
            f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;"
            f"padding:16px;text-align:center'>"
            f"<div style='font-size:2.5rem'>{sem}</div>"
            f"<div style='font-weight:700;font-size:1.1rem'>{titulo}</div>"
            f"<div style='color:#64748b;font-size:0.85rem'>{sit} · {detalhe}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── FINANCEIRO RESUMIDO ───────────────────────────────────────────────────────
st.markdown("### Resumo Financeiro")
f1, f2, f3, f4 = st.columns(4)
f1.metric("Receita total (ISS + IPTU + Transf.)", _fmtM(receita_total), f"Ano {ano_recente}")
f2.metric("ISS arrecadado",                        _fmtM(iss_atual),    f"{var_iss:+.1f}% vs {ano_ant}")
f3.metric("Dívida ativa em aberto",                _fmtM(da_aberto),    f"{tx_recup:.1f}% recuperado")
f4.metric("Previsão ISS (próx. 6 meses)",          _fmtM(prev_iss),     "Modelo Prophet")

st.markdown("---")

# ── GRÁFICO DE TENDÊNCIA ───────────────────────────────────────────────────────
st.markdown("### Tendência de Arrecadação ISS")

iss_m = (decl.groupby(["competencia", "ano"])["iss_recolhido"]
    .sum().reset_index().sort_values("competencia"))

# Adicionar previsão
fc_iss = fc[fc["tipo"] == "ISS"].copy() if "tipo" in fc.columns else pd.DataFrame()

fig_trend = go.Figure()
fig_trend.add_bar(
    x=iss_m["competencia"], y=iss_m["iss_recolhido"],
    name="Realizado", marker_color="#1a4f82", opacity=0.85,
)
if len(fc_iss) > 0:
    fc_fut_iss = fc_iss[fc_iss["is_forecast"] == True]
    fig_trend.add_scatter(
        x=fc_fut_iss["ds"].astype(str).str[:7],
        y=fc_fut_iss["yhat"],
        name="Previsão (6m)",
        line=dict(color="#c8860a", dash="dash", width=2.5),
        mode="lines+markers",
    )
    fig_trend.add_traces([
        go.Scatter(
            x=list(fc_fut_iss["ds"].astype(str).str[:7]) + list(fc_fut_iss["ds"].astype(str).str[:7])[::-1],
            y=list(fc_fut_iss["yhat_upper"]) + list(fc_fut_iss["yhat_lower"])[::-1],
            fill="toself",
            fillcolor="rgba(200,134,10,0.12)",
            line=dict(width=0),
            name="IC 95%",
            showlegend=False,
        )
    ])
fig_trend.update_layout(
    plot_bgcolor="white",
    height=340,
    hovermode="x unified",
    xaxis_title="",
    yaxis_title="R$",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    bargap=0.15,
)
st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")

# ── ALERTAS ───────────────────────────────────────────────────────────────────
st.markdown("### Alertas Ativos")

if not alertas_altos:
    st.success("Nenhum alerta de alta severidade no momento.")
else:
    st.markdown(f"**{len(alertas_altos)} alertas requerem atenção da gestão:**")
    for alerta in alertas_altos[:6]:
        impacto = alerta.get("valor_impacto", 0)
        with st.container():
            st.markdown(
                f"<div style='border-left:4px solid #9b1c1c;padding:10px 16px;"
                f"border-radius:0 8px 8px 0;background:#fff5f5;margin-bottom:8px'>"
                f"<strong>{alerta['titulo']}</strong><br>"
                f"<span style='font-size:0.85rem;color:#374151'>{alerta['texto'][:200]}{'...' if len(alerta['texto'])>200 else ''}</span>"
                + (f"<br><span style='color:#9b1c1c;font-weight:600'>Impacto: {_fmt(impacto)}</span>"
                   if impacto > 0 else "")
                + "</div>",
                unsafe_allow_html=True,
            )

st.markdown("---")

# ── INDICADORES DE DESEMPENHO DA SECRETARIA ───────────────────────────────────
st.markdown("### Indicadores de Desempenho da Fiscalização")

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("**Contribuintes por faixa de risco**")
    faixas = scores["faixa_risco"].value_counts().reset_index()
    faixas.columns = ["Faixa", "N"]
    fig_faixa = px.pie(
        faixas, names="Faixa", values="N", hole=0.45,
        color="Faixa",
        color_discrete_map={"Baixo": "#1b6b3a", "Médio": "#c8860a", "Alto": "#9b1c1c"},
    )
    fig_faixa.update_layout(height=260, margin=dict(t=10, b=10))
    fig_faixa.update_traces(textinfo="percent+label")
    st.plotly_chart(fig_faixa, use_container_width=True)

with col_b:
    st.markdown("**Composição da Dívida Ativa por fase**")
    fase_g = da.groupby("fase")["em_aberto" if "em_aberto" in da.columns else "valor_total"].sum()
    da_copy = da.copy()
    da_copy["em_aberto_calc"] = da_copy["valor_total"] - da_copy["valor_recuperado"]
    fase_g = da_copy.groupby("fase")["em_aberto_calc"].sum().reset_index()
    fase_g.columns = ["Fase", "Em Aberto"]
    fig_fase = px.bar(
        fase_g,
        x="Fase", y="Em Aberto",
        color="Fase",
        color_discrete_map={"Administrativa": "#1a4f82", "Judicial": "#9b1c1c"},
        labels={"Em Aberto": "R$"},
        text=fase_g["Em Aberto"].apply(_fmt),
    )
    fig_fase.update_traces(textposition="outside")
    fig_fase.update_layout(
        plot_bgcolor="white",
        height=260,
        showlegend=False,
        yaxis_title="R$",
    )
    st.plotly_chart(fig_fase, use_container_width=True)

# ── RODAPÉ ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"FiscoSmart · Painel Executivo · São Vicente — SP · Gerado em {date.today().strftime('%d/%m/%Y')} · "
    "Uso exclusivo da Secretaria Municipal de Finanças"
)
