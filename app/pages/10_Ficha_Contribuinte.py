"""
FiscoSmart — Página 10: Ficha do Contribuinte
Visão consolidada de um contribuinte: declarações, pagamentos, DA, ações, score.
A página mais usada pelo auditor no dia a dia.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import joblib, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
st.set_page_config(page_title="Ficha do Contribuinte | FiscoSmart", layout="wide")

DATA_RAW  = os.path.join(ROOT, "data", "raw")
DATA_PROC = os.path.join(ROOT, "data", "processed")
MODELS_DIR= os.path.join(ROOT, "models")

_fmt = lambda v: f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")
_pct = lambda v: f"{v:.1f}%"


@st.cache_data(ttl=300)
def load_base():
    contribs = pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
    decl     = pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv")
    acoes    = pd.read_csv(f"{DATA_RAW}/acoes_fiscais.csv")
    da       = pd.read_csv(f"{DATA_RAW}/divida_ativa.csv")
    scores   = pd.read_csv(f"{DATA_PROC}/scores_risco.csv")
    shap_v   = pd.read_csv(f"{DATA_PROC}/shap_values.csv")
    pag_path = f"{DATA_RAW}/pagamentos_iss.csv"
    pag = pd.read_csv(pag_path) if os.path.exists(pag_path) else pd.DataFrame()
    return contribs, decl, acoes, da, scores, shap_v, pag


try:
    contribs, decl, acoes, da, scores, shap_v, pag = load_base()
except FileNotFoundError as e:
    st.error(f"Execute `setup.py` primeiro. Arquivo ausente: {e}")
    st.stop()

st.markdown("## 🗂️ Ficha do Contribuinte")
st.caption("Histórico completo de um contribuinte — declarações, pagamentos, dívida ativa, ações fiscais e score de risco")

# ── BUSCA ─────────────────────────────────────────────────────────────────────
col_busca, col_filtro = st.columns([3, 1])
with col_busca:
    termo = st.text_input(
        "Buscar por razão social, CNPJ ou ID",
        placeholder="Ex: Mendes Ltda   ou   12.345   ou   42",
        help="Mínimo 3 caracteres"
    )
with col_filtro:
    buscar_por = st.selectbox("Campo", ["Razão Social", "CNPJ", "ID"])

if not termo or len(termo) < 2:
    st.info("Digite o nome, CNPJ ou ID do contribuinte para buscar.")

    # Atalho: top 10 alto risco
    st.markdown("#### Sugestão: contribuintes de alto risco")
    top_alto = scores[scores["faixa_risco"]=="Alto"].sort_values("score_risco", ascending=False).head(10)
    top_alto = top_alto.merge(contribs[["id_contribuinte","razao_social","cnpj"]], on="id_contribuinte", how="left")
    top_alto["Score"] = top_alto["score_risco"].apply(lambda x: f"{x:.0f}")
    st.dataframe(
        top_alto[["id_contribuinte","razao_social","cnpj","cnae","porte","Score"]].rename(
            columns={"id_contribuinte":"ID","razao_social":"Razão Social"}),
        use_container_width=True, height=280, hide_index=True
    )
    st.stop()

# Executar busca
if buscar_por == "Razão Social":
    resultados = contribs[contribs["razao_social"].str.contains(termo, case=False, na=False)]
elif buscar_por == "CNPJ":
    resultados = contribs[contribs["cnpj"].str.contains(termo, na=False)]
else:
    try:
        resultados = contribs[contribs["id_contribuinte"] == int(termo)]
    except ValueError:
        resultados = pd.DataFrame()

if len(resultados) == 0:
    st.warning(f"Nenhum contribuinte encontrado para '{termo}'.")
    st.stop()

if len(resultados) > 1:
    opcoes = [f"{r['id_contribuinte']} — {r['razao_social']} ({r['cnpj']})"
              for _, r in resultados.iterrows()]
    sel = st.selectbox(f"{len(resultados)} contribuintes encontrados. Selecione:", opcoes)
    cid = int(sel.split(" — ")[0])
else:
    cid = int(resultados.iloc[0]["id_contribuinte"])

# ── DADOS DO CONTRIBUINTE ─────────────────────────────────────────────────────
c   = contribs[contribs["id_contribuinte"]==cid].iloc[0]
sc  = scores[scores["id_contribuinte"]==cid]
sh  = shap_v[shap_v["id_contribuinte"]==cid]
dc  = decl[decl["id_contribuinte"]==cid].sort_values("competencia")
ac  = acoes[acoes["id_contribuinte"]==cid].sort_values("data_acao", ascending=False)
dac = da[da["id_contribuinte"]==cid].sort_values("data_inscricao", ascending=False)
pgc = pag[pag["id_contribuinte"]==cid].sort_values("data_pagamento", ascending=False) if len(pag) else pd.DataFrame()

# ── CABEÇALHO ─────────────────────────────────────────────────────────────────
st.markdown("---")
hcol1, hcol2, hcol3 = st.columns([2, 1, 1])
with hcol1:
    st.markdown(f"### {c['razao_social']}")
    st.caption(f"CNPJ: **{c['cnpj']}** · {c['desc_cnae']} ({c['cnae']}) · {c['regime_tributario']}")
    st.caption(f"Bairro: {c['bairro']} · Porte: {c['porte']} · Abertura: {c['data_abertura']}")
    st.caption(f"E-mail: {c['email']} · Telefone: {c['telefone']}")

with hcol2:
    if len(sc) > 0:
        score_val = sc.iloc[0]["score_risco"]
        faixa = sc.iloc[0]["faixa_risco"]
        cor = {"Baixo":"#1b6b3a","Médio":"#c8860a","Alto":"#9b1c1c"}.get(str(faixa),"#666")
        st.markdown(
            f"<div style='border-left:4px solid {cor};padding:8px 12px;border-radius:0 8px 8px 0'>"
            f"<div style='font-size:11px;color:#888'>Score de risco</div>"
            f"<div style='font-size:2rem;font-weight:700;color:{cor}'>{score_val:.0f}</div>"
            f"<div style='font-size:13px;font-weight:500;color:{cor}'>{faixa}</div></div>",
            unsafe_allow_html=True
        )

with hcol3:
    da_aberto = dac[dac["situacao"]=="Em aberto"]["valor_total"].sum() if len(dac) else 0
    ult_acao  = ac.iloc[0]["data_acao"] if len(ac) else "Nunca fiscalizado"
    n_omissoes= dc["omitiu_declaracao"].sum() if len(dc) else 0
    st.metric("Dívida ativa em aberto", _fmt(da_aberto))
    st.metric("Última fiscalização",    str(ult_acao))
    st.metric("Omissões de declaração", f"{n_omissoes:.0f}")

# ── ABAS ──────────────────────────────────────────────────────────────────────
st.markdown("---")
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "📊 Declarações ISS",
    "💳 Pagamentos",
    "⚖️ Dívida Ativa",
    "🔍 Ações Fiscais",
    "🤖 Explicação do Score",
])

# ── ABA 1: DECLARAÇÕES ────────────────────────────────────────────────────────
with aba1:
    if len(dc) == 0:
        st.info("Nenhuma declaração encontrada para este contribuinte.")
    else:
        ka, kb, kc, kd = st.columns(4)
        ka.metric("Competências declaradas", len(dc))
        kb.metric("ISS recolhido total",     _fmt(dc["iss_recolhido"].sum()))
        kc.metric("Gap total estimado",      _fmt(dc["gap_absoluto"].sum()))
        kd.metric("Taxa de omissão",         _pct(dc["omitiu_declaracao"].mean()*100))

        fig = go.Figure()
        fig.add_bar(x=dc["competencia"], y=dc["iss_recolhido"],
                    name="ISS recolhido", marker_color="#1a4f82")
        fig.add_scatter(x=dc["competencia"], y=dc["iss_devido_estimado"],
                        name="ISS estimado devido",
                        line=dict(color="#c8860a", dash="dash", width=2))
        fig.add_scatter(x=dc["competencia"], y=dc["gap_absoluto"],
                        name="Gap", line=dict(color="#9b1c1c", width=1.5),
                        yaxis="y2", fill="tozeroy", fillcolor="rgba(155,28,28,0.08)")
        fig.update_layout(
            yaxis2=dict(overlaying="y", side="right", title="Gap (R$)"),
            plot_bgcolor="white", height=320, hovermode="x unified",
            title="Histórico de declarações — recolhido vs estimado"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Tabela detalhada com destaque em omissões
        dc_show = dc[["competencia","receita_declarada","iss_recolhido","iss_devido_estimado",
                       "gap_absoluto","gap_percentual","omitiu_declaracao","retificou"]].copy()
        dc_show = dc_show.sort_values("competencia", ascending=False)
        dc_show.columns = ["Competência","Receita Decl.","ISS Recolhido","ISS Estimado",
                           "Gap R$","Gap %","Omitiu","Retificou"]
        st.dataframe(dc_show, use_container_width=True, height=300, hide_index=True)

# ── ABA 2: PAGAMENTOS ─────────────────────────────────────────────────────────
with aba2:
    if len(pgc) == 0:
        st.info("Nenhum evento de pagamento registrado (batch diário ainda não cobriu este contribuinte ou está adimplente no histórico).")
    else:
        pa, pb, pc = st.columns(3)
        pa.metric("Total de eventos",   len(pgc))
        pb.metric("Valor total pago",   _fmt(pgc["valor_pago"].sum()))
        pc.metric("Pagamentos em atraso", len(pgc[pgc["status"]=="pago_atraso"]))

        fig_pag = px.bar(
            pgc.sort_values("data_pagamento"),
            x="data_pagamento", y="valor_pago", color="status",
            color_discrete_map={"pago":"#1b6b3a","pago_atraso":"#c8860a"},
            title="Eventos de pagamento por data",
            labels={"valor_pago":"R$","data_pagamento":"Data","status":"Status"}
        )
        fig_pag.update_layout(plot_bgcolor="white", height=280)
        st.plotly_chart(fig_pag, use_container_width=True)

        pgc_show = pgc[["competencia","data_vencimento","data_pagamento",
                         "valor_devido","valor_pago","status","dias_atraso"]].copy()
        pgc_show.columns = ["Competência","Vencimento","Pagamento","Valor Devido","Valor Pago","Status","Dias Atraso"]
        st.dataframe(pgc_show, use_container_width=True, height=280, hide_index=True)

# ── ABA 3: DÍVIDA ATIVA ───────────────────────────────────────────────────────
with aba3:
    if len(dac) == 0:
        st.success("Este contribuinte não possui registros em dívida ativa.")
    else:
        da1, da2, da3 = st.columns(3)
        da1.metric("Inscrições em DA",    len(dac))
        da2.metric("Total inscrito",      _fmt(dac["valor_total"].sum()))
        da3.metric("Em aberto",           _fmt(dac[dac["situacao"]=="Em aberto"]["valor_total"].sum()))

        dac_show = dac[["competencia_origem","data_inscricao","tipo_tributo",
                         "valor_principal","juros","multa","valor_total",
                         "valor_recuperado","fase","situacao"]].copy()
        dac_show.columns = ["Competência","Inscrição","Tributo","Principal",
                            "Juros","Multa","Total","Recuperado","Fase","Situação"]
        st.dataframe(dac_show, use_container_width=True, height=280, hide_index=True)

# ── ABA 4: AÇÕES FISCAIS ──────────────────────────────────────────────────────
with aba4:
    if len(ac) == 0:
        st.info("Nenhuma ação fiscal registrada para este contribuinte.")
    else:
        fa1, fa2, fa3 = st.columns(3)
        fa1.metric("Total de ações",        len(ac))
        fa2.metric("Irregularidades conf.", int(ac["irregularidade_confirmada"].sum()))
        fa3.metric("Valor total autuado",   _fmt(ac["valor_autuado"].sum()))

        ac_show = ac[["data_acao","tipo_acao","resultado","irregularidade_confirmada","valor_autuado"]].copy()
        ac_show.columns = ["Data","Tipo","Resultado","Irregularidade Conf.","Valor Autuado"]
        st.dataframe(ac_show, use_container_width=True, height=240, hide_index=True)

# ── ABA 5: EXPLICAÇÃO DO SCORE ────────────────────────────────────────────────
with aba5:
    if len(sc) == 0 or len(sh) == 0:
        st.warning("Score não disponível — rode setup.py para gerar os modelos.")
    else:
        FEAT_LABELS = {
            "shap_porte_num":              "Porte da empresa",
            "shap_regime_num":             "Regime tributário",
            "shap_gap_medio_pct":          "Gap médio declarado (%)",
            "shap_gap_std":                "Instabilidade do gap",
            "shap_taxa_omissao":           "Taxa de omissão de declarações",
            "shap_taxa_retificacao":       "Frequência de retificações",
            "shap_cv_receita":             "Variabilidade da receita",
            "shap_slope_receita_norm":     "Tendência da receita",
            "shap_razao_ultimo_media":     "Último mês vs. média histórica",
            "shap_meses_sem_fiscalizacao": "Tempo sem ser fiscalizado",
            "shap_n_acoes_historicas":     "Histórico de ações fiscais",
            "shap_gap_vs_bench_pct":       "Gap vs. benchmark do setor",
            "shap_n_meses_com_dados":      "Regularidade de entregas",
        }
        shap_cols = [c for c in sh.columns if c.startswith("shap_")]
        shap_ind  = sh[shap_cols].iloc[0]
        shap_df   = pd.DataFrame({"feature":shap_ind.index,"shap":shap_ind.values})
        shap_df["label"]  = shap_df["feature"].map(FEAT_LABELS)
        shap_df = shap_df.sort_values("shap")
        colors   = ["#9b1c1c" if v > 0 else "#1b6b3a" for v in shap_df["shap"]]

        score_val = sc.iloc[0]["score_risco"]
        faixa     = sc.iloc[0]["faixa_risco"]
        cor       = {"Baixo":"#1b6b3a","Médio":"#c8860a","Alto":"#9b1c1c"}.get(str(faixa),"#666")

        st.markdown(
            f"**Score:** <span style='color:{cor};font-size:1.4rem;font-weight:700'>"
            f"{score_val:.0f}/100</span> — Faixa **{faixa}**",
            unsafe_allow_html=True
        )
        st.caption("Barras vermelhas = aumentam o risco · barras verdes = reduzem o risco")

        fig_w = go.Figure(go.Bar(
            x=shap_df["shap"], y=shap_df["label"], orientation="h",
            marker_color=colors,
            text=[f"{v:+.3f}" for v in shap_df["shap"]],
            textposition="outside"
        ))
        fig_w.add_vline(x=0, line_width=1.5, line_color="#333")
        fig_w.update_layout(
            plot_bgcolor="white", height=420,
            xaxis_title="Contribuição SHAP (positivo = aumenta o risco)",
            margin=dict(l=220)
        )
        st.plotly_chart(fig_w, use_container_width=True)

        # Resumo em linguagem natural para o auto de infração
        top3_risco = shap_df[shap_df["shap"]>0].sort_values("shap",ascending=False).head(3)
        if len(top3_risco):
            fatores = " · ".join([
                f"{r['label']} ({r['shap']:+.2f})"
                for _, r in top3_risco.iterrows()
            ])
            st.info(
                f"**Resumo para auto de infração:** Score {score_val:.0f}/100 "
                f"justificado principalmente por: {fatores}."
            )
