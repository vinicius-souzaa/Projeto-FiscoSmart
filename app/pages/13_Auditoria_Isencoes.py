"""
FiscoSmart — Página 13: Auditoria de Isenções IPTU
Identifica imóveis com isenção que precisam de reavaliação:
  - Isenções sem atualização cadastral há mais de 2 anos
  - Isenções em imóveis de alto valor venal
  - Análise do impacto financeiro da revisão
Base legal: Lei Orgânica Municipal, CTN art. 176 (isenção por prazo e condição).
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys, os, io
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
st.set_page_config(page_title="Auditoria de Isenções | FiscoSmart", layout="wide")

DATA_RAW = os.path.join(ROOT, "data", "raw")
_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")


@st.cache_data(ttl=300)
def load():
    imoveis = pd.read_csv(f"{DATA_RAW}/imoveis.csv")
    imoveis["ultima_atualizacao_cadastral"] = pd.to_datetime(
        imoveis["ultima_atualizacao_cadastral"], errors="coerce"
    )
    return imoveis


imoveis = load()

st.markdown("## 🔍 Auditoria de Isenções IPTU")
st.info(
    "**O que é esta página?** "
    "O município pode conceder isenção de IPTU para certas categorias (idosos, deficientes, "
    "entidades sem fins lucrativos, imóveis de baixo valor). Mas as isenções precisam ser "
    "periodicamente reavaliadas: a situação do contribuinte muda, imóveis mudam de uso, "
    "e isenções irregulares representam renúncia fiscal indevida. "
    "\n\n"
    "Esta página identifica imóveis isentos que estão há mais de 2 anos sem atualização "
    "cadastral, ou que têm características suspeitas (alto valor venal, tipo comercial, etc.)."
    "\n\n"
    "**Base legal:** CTN art. 176 — isenções concedidas por prazo certo e sob condição não "
    "são revogadas por alteração legislativa, mas devem ser revisadas se a condição não mais "
    "se verifica."
)

# ── BASE DE ISENÇÕES ──────────────────────────────────────────────────────────
isen = imoveis[imoveis["isencao"] == 1].copy()

if len(isen) == 0:
    st.success("Nenhum imóvel com isenção encontrado na base cadastral.")
    st.stop()

hoje = pd.Timestamp(date.today())
isen["anos_sem_atualizacao"] = ((hoje - isen["ultima_atualizacao_cadastral"]).dt.days / 365).round(1)

# Critérios de suspeição
isen["suspeito_tempo"]  = isen["anos_sem_atualizacao"] > 2
isen["suspeito_valor"]  = isen["valor_venal"] > 200_000
isen["suspeito_tipo"]   = isen["tipo"].isin(["Comercial", "Industrial"])
isen["n_flags"]         = isen["suspeito_tempo"].astype(int) + isen["suspeito_valor"].astype(int) + isen["suspeito_tipo"].astype(int)
isen["prioridade"]      = isen["n_flags"].map({0: "Baixa", 1: "Média", 2: "Alta", 3: "Alta"}).fillna("Alta")

# IPTU que seria cobrado se isenção fosse revogada (alíquota padrão residencial)
aliq_tipo = {"Residencial": 0.008, "Comercial": 0.012, "Industrial": 0.012, "Terreno": 0.020}
isen["iptu_potencial"] = isen.apply(
    lambda r: round(r["valor_venal"] * aliq_tipo.get(r["tipo"], 0.008), 2), axis=1
)
isen["iptu_potencial_ajustado"] = isen["iptu_potencial"] * isen["n_flags"] / 3   # ponderado por suspeição

# ── KPIs ──────────────────────────────────────────────────────────────────────
total_isen = len(isen)
suspeitos  = isen[isen["n_flags"] > 0]
alta_prio  = isen[isen["prioridade"] == "Alta"]
iptu_risco = isen["iptu_potencial"].sum()
iptu_alta  = alta_prio["iptu_potencial"].sum()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total de isenções",         f"{total_isen:,}")
c2.metric("Com alguma irregularidade", f"{len(suspeitos):,}", f"{len(suspeitos)/total_isen*100:.1f}% do total")
c3.metric("Prioridade Alta",           f"{len(alta_prio):,}", "Revisão imediata")
c4.metric("IPTU potencial total",      _fmt(iptu_risco), "Se 100% revogadas")
c5.metric("IPTU prioridade alta",      _fmt(iptu_alta), "Revisão prioritária")

if len(alta_prio) > 0:
    st.error(
        f"⚠️ {len(alta_prio)} imóveis com isenção de alta prioridade para revisão. "
        f"Potencial de receita adicional: {_fmt(iptu_alta)}/ano."
    )

st.markdown("---")

# ── ANÁLISE POR CRITÉRIO ──────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Isenções por Tempo sem Atualização")
    st.caption("Isenções mais antigas são mais propensas a irregularidades")
    bins_tempo = [0, 1, 2, 3, 5, 100]
    labels_tempo = ["< 1 ano", "1-2 anos", "2-3 anos", "3-5 anos", "> 5 anos"]
    isen["faixa_tempo"] = pd.cut(isen["anos_sem_atualizacao"].fillna(10), bins=bins_tempo, labels=labels_tempo)
    tempo_g = isen.groupby("faixa_tempo", observed=True).agg(
        n=("id_imovel", "count"),
        iptu_pot=("iptu_potencial", "sum")
    ).reset_index()
    fig_t = px.bar(
        tempo_g,
        x="faixa_tempo", y="n",
        color="iptu_pot",
        color_continuous_scale=["#1b6b3a", "#c8860a", "#9b1c1c"],
        labels={"faixa_tempo": "Tempo s/ atualização", "n": "Nº imóveis", "iptu_pot": "IPTU potencial"},
        text="n",
    )
    fig_t.update_layout(plot_bgcolor="white", height=300, coloraxis_showscale=False)
    st.plotly_chart(fig_t, use_container_width=True)

with col2:
    st.markdown("#### Composição por Tipo de Imóvel")
    st.caption("Isenções em imóveis comerciais/industriais têm maior suspeição")
    tipo_g = isen.groupby("tipo").agg(
        n=("id_imovel", "count"),
        n_suspeitos=("n_flags", lambda x: (x > 0).sum()),
        iptu_pot=("iptu_potencial", "sum")
    ).reset_index()
    tipo_g["pct_suspeito"] = tipo_g["n_suspeitos"] / tipo_g["n"] * 100

    fig_tipo = go.Figure()
    fig_tipo.add_bar(x=tipo_g["tipo"], y=tipo_g["n"], name="Total", marker_color="#94a3b8")
    fig_tipo.add_bar(x=tipo_g["tipo"], y=tipo_g["n_suspeitos"], name="Suspeitos", marker_color="#9b1c1c")
    fig_tipo.update_layout(
        barmode="overlay", plot_bgcolor="white", height=300,
        xaxis_title="Tipo de imóvel", yaxis_title="Nº de imóveis",
    )
    st.plotly_chart(fig_tipo, use_container_width=True)

# ── DISTRIBUIÇÃO POR VALOR VENAL ──────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Distribuição do Valor Venal dos Imóveis Isentos")
st.caption(
    "Imóveis com valor venal elevado têm maior chance de terem perdido o direito à isenção. "
    "Isenções para imóveis residenciais de baixo valor (< R$80k) são as mais legítimas."
)
fig_vv = px.histogram(
    isen,
    x="valor_venal",
    nbins=30,
    color="tipo",
    color_discrete_map={"Residencial": "#1a4f82", "Comercial": "#c8860a", "Industrial": "#9b1c1c", "Terreno": "#1b6b3a"},
    labels={"valor_venal": "Valor Venal (R$)", "count": "Nº imóveis"},
)
fig_vv.add_vline(x=200_000, line_dash="dash", line_color="#9b1c1c",
                 annotation_text="R$200k (limite de suspeição)")
fig_vv.add_vline(x=80_000, line_dash="dot", line_color="#1b6b3a",
                 annotation_text="R$80k (tipicamente legítimo)")
fig_vv.update_layout(plot_bgcolor="white", height=320)
st.plotly_chart(fig_vv, use_container_width=True)

# ── FILTROS E LISTA DE TRABALHO ───────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Lista de Imóveis para Revisão")

with st.expander("⚙️ Filtros", expanded=True):
    f1, f2, f3 = st.columns(3)
    with f1:
        prio_sel = st.multiselect("Prioridade", ["Alta", "Média", "Baixa"], default=["Alta"])
    with f2:
        tipo_sel = st.multiselect("Tipo", list(isen["tipo"].unique()), default=list(isen["tipo"].unique()))
    with f3:
        anos_min = st.slider("Mínimo de anos sem atualização", 0.0, 10.0, 2.0, step=0.5)

filt = isen[
    isen["prioridade"].isin(prio_sel) &
    isen["tipo"].isin(tipo_sel) &
    (isen["anos_sem_atualizacao"].fillna(0) >= anos_min)
].sort_values(["n_flags", "iptu_potencial"], ascending=[False, False])

st.metric("Imóveis na lista de revisão", f"{len(filt):,}", f"IPTU potencial: {_fmt(filt['iptu_potencial'].sum())}")

filt_show = filt[[
    "id_imovel", "inscricao_imobiliaria", "tipo", "bairro",
    "valor_venal", "iptu_potencial", "anos_sem_atualizacao", "prioridade",
    "suspeito_tempo", "suspeito_valor", "suspeito_tipo",
]].head(100).copy()

filt_show.columns = [
    "ID", "Inscrição", "Tipo", "Bairro",
    "Valor Venal", "IPTU Potencial", "Anos s/ Atualiz.", "Prioridade",
    "Flag: Tempo", "Flag: Valor", "Flag: Tipo",
]
filt_show["Valor Venal"]     = filt_show["Valor Venal"].apply(_fmt)
filt_show["IPTU Potencial"]  = filt_show["IPTU Potencial"].apply(_fmt)
filt_show["Anos s/ Atualiz."] = filt_show["Anos s/ Atualiz."].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/D")

st.dataframe(filt_show, use_container_width=True, height=400, hide_index=True)

# Export
buf = io.StringIO()
filt.to_csv(buf, index=False)
st.download_button(
    "⬇️ Baixar lista completa (CSV)",
    buf.getvalue(),
    f"auditoria_isencoes_{date.today().isoformat()}.csv",
    "text/csv",
)

# ── SIMULADOR ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Simulador de Impacto da Revisão")
st.caption("Estime a receita adicional com diferentes cenários de revogação de isenções.")

c_s1, c_s2 = st.columns(2)
with c_s1:
    pct_rev = st.slider("% das isenções com prioridade Alta que seriam revogadas", 10, 100, 40)
with c_s2:
    tx_adimplencia = st.slider("% de adimplência esperada após revogação", 50, 100, 75)

receita_adicional = alta_prio["iptu_potencial"].sum() * pct_rev / 100 * tx_adimplencia / 100
custo_rev = len(alta_prio) * pct_rev / 100 * 120   # R$120 custo médio de revisão administrativa

sr1, sr2, sr3 = st.columns(3)
sr1.metric("Isenções revogadas", f"{int(len(alta_prio) * pct_rev / 100):,}")
sr2.metric("Receita adicional estimada", _fmt(receita_adicional), "por ano")
sr3.metric("ROI da revisão", f"{receita_adicional/max(custo_rev,1):.0f}x", f"Custo adm. {_fmt(custo_rev)}")
