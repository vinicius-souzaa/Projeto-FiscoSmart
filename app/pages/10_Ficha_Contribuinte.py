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
import joblib, os, sys, io
from datetime import date

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
aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs([
    "📊 Declarações ISS",
    "💳 Pagamentos",
    "⚖️ Dívida Ativa",
    "🔍 Ações Fiscais",
    "🤖 Explicação do Score",
    "📄 Gerar Notificação",
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

# ── ABA 6: GERAR NOTIFICAÇÃO (PDF / TXT) ─────────────────────────────────────
with aba6:
    st.markdown("#### Gerar Notificação Fiscal Preliminar")
    st.caption(
        "Gera um documento de notificação pré-preenchido com os dados do contribuinte, "
        "score de risco, principais fatores de risco e base legal. Pode ser exportado "
        "como arquivo texto para impressão ou envio por e-mail."
    )

    if len(sc) == 0:
        st.warning("Score não disponível — rode setup.py para gerar o modelo.")
    else:
        score_val = sc.iloc[0]["score_risco"]
        faixa     = str(sc.iloc[0]["faixa_risco"])

        # Configurações da notificação
        nc1, nc2 = st.columns(2)
        with nc1:
            tipo_notif = st.selectbox("Tipo de notificação", [
                "Notificação Prévia de Lançamento",
                "Auto de Infração (ISS)",
                "Intimação para Apresentação de Documentos",
                "Aviso de Débito — Dívida Ativa",
            ])
            n_numero = st.text_input("Número do documento", value=f"NF-{cid:05d}-{date.today().year}")
        with nc2:
            prazo_dias = st.number_input("Prazo para resposta (dias)", 5, 30, 15)
            auditor_nome = st.text_input("Nome do auditor responsável", value="Auditor Fiscal")

        # Montar conteúdo
        gap_12m = dc["gap_absoluto"].sum() if len(dc) > 0 else 0
        iss_12m  = dc["iss_recolhido"].sum() if len(dc) > 0 else 0

        # Top 3 fatores de risco
        top3_txt = ""
        if len(sh) > 0:
            FEAT_LABELS_SHORT = {
                "shap_gap_medio_pct":          "gap médio declarado acima do benchmark setorial",
                "shap_taxa_omissao":           "omissões sistemáticas de declaração",
                "shap_gap_vs_bench_pct":       "receita declarada abaixo da média do setor",
                "shap_meses_sem_fiscalizacao": "longo período sem fiscalização",
                "shap_cv_receita":             "alta variabilidade da receita declarada",
                "shap_slope_receita_norm":     "tendência de queda na receita declarada",
                "shap_taxa_retificacao":       "frequência elevada de retificações",
                "shap_n_acoes_historicas":     "histórico de ações fiscais anteriores",
                "shap_porte_num":              "porte da empresa",
                "shap_regime_num":             "regime tributário",
                "shap_razao_ultimo_media":     "último mês com receita muito inferior à média",
                "shap_gap_std":                "instabilidade no padrão de declaração",
                "shap_n_meses_com_dados":      "irregularidade na entrega de declarações",
                "shap_nunca_fiscalizado":      "nunca foi submetido a fiscalização",
            }
            shap_cols = [col for col in sh.columns if col.startswith("shap_")]
            shap_ind  = sh[shap_cols].iloc[0]
            shap_df_n = pd.DataFrame({"feature": shap_ind.index, "shap": shap_ind.values})
            top3_fatores = shap_df_n[shap_df_n["shap"] > 0].sort_values("shap", ascending=False).head(3)
            linhas = []
            for i, (_, row) in enumerate(top3_fatores.iterrows(), 1):
                desc = FEAT_LABELS_SHORT.get(row["feature"], row["feature"])
                linhas.append(f"   {i}. {desc.capitalize()} (contribuição: {row['shap']:+.3f})")
            top3_txt = "\n".join(linhas)

        vencimento_notif = date.today().replace(
            day=min(date.today().day + prazo_dias, 28)
        )

        notificacao = f"""
================================================================================
          PREFEITURA MUNICIPAL DE SÃO VICENTE — ESTADO DE SÃO PAULO
                       SECRETARIA MUNICIPAL DE FINANÇAS
                      DEPARTAMENTO DE FISCALIZAÇÃO TRIBUTÁRIA
================================================================================
                        {tipo_notif.upper()}
================================================================================

Número: {n_numero}          Data: {date.today().strftime('%d/%m/%Y')}
Auditor Fiscal Responsável: {auditor_nome}

CONTRIBUINTE / PESSOA JURÍDICA:
--------------------------------------------------------------------------------
Razão Social:  {c['razao_social']}
CNPJ:          {c['cnpj']}
Atividade:     {c.get('desc_cnae', c['cnae'])} (CNAE {c['cnae']})
Regime:        {c.get('regime_tributario', 'N/D')}
Bairro:        {c.get('bairro', 'N/D')} — São Vicente/SP

ANÁLISE DE RISCO FISCAL (Sistema FiscoSmart — IA):
--------------------------------------------------------------------------------
Score de Risco:    {score_val:.0f}/100 — Faixa: {faixa.upper()}
ISS Recolhido (12m): {_fmt(iss_12m)}
Gap Estimado (12m):  {_fmt(gap_12m)}  (diferença entre estimado e declarado)

Principais indicadores de risco identificados pelo sistema:
{top3_txt if top3_txt else '   (dados de explicabilidade não disponíveis)'}

FUNDAMENTAÇÃO LEGAL:
--------------------------------------------------------------------------------
O lançamento e/ou a presente notificação têm como fundamento:
  - Lei Complementar nº 116/2003 (Lei Geral do ISS — arts. 1º, 7º e 12)
  - Código Tributário Nacional — arts. 142, 148 e 173
  - Decreto Municipal nº ____/_____ (Regulamento do ISSQN)
  - Portaria SMF nº ____/_____ (Procedimento de fiscalização eletrônica)

PROVIDÊNCIAS REQUERIDAS:
--------------------------------------------------------------------------------
O contribuinte acima identificado fica INTIMADO a, no prazo de {prazo_dias} ({"quinze" if prazo_dias == 15 else str(prazo_dias)}) dias
corridos a contar do recebimento desta notificação (até {vencimento_notif.strftime('%d/%m/%Y')}),
apresentar-se junto à Secretaria Municipal de Finanças — Fiscalização Tributária,
munido dos seguintes documentos:

  1. Livros fiscais e declarações PGDAS-D dos últimos 36 meses
  2. Notas fiscais de serviços emitidas e recebidas no período
  3. Extratos bancários das contas utilizadas para movimentação empresarial
  4. Contratos de prestação de serviços vigentes
  5. Demonstrativos contábeis (DRE, Balanço) dos últimos 3 exercícios

A não apresentação no prazo legal implicará em lançamento de ofício, conforme
art. 149, VI, do CTN, com aplicação de multa de 75% (setenta e cinco por cento)
sobre o valor do imposto apurado, acrescida de juros de mora de 1% a.m.

CIÊNCIA DO CONTRIBUINTE:
--------------------------------------------------------------------------------
Recebi em: ____/____/________     Assinatura: ____________________________

                              São Vicente, {date.today().strftime('%d de %B de %Y')}

                              ____________________________
                              {auditor_nome}
                              Auditor Fiscal Municipal
                              Matrícula: _________________
================================================================================
Documento gerado pelo sistema FiscoSmart — uso exclusivo da Secretaria de Finanças
================================================================================
"""

        st.code(notificacao, language=None)

        # Exportar como arquivo de texto (UTF-8, imprimível)
        buf_txt = io.BytesIO(notificacao.encode("utf-8"))
        st.download_button(
            label=f"⬇️ Baixar notificação ({n_numero})",
            data=buf_txt,
            file_name=f"notificacao_{n_numero.replace('/','_').replace('-','_')}.txt",
            mime="text/plain",
        )

        # Opção PDF (requer reportlab)
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT

            def gerar_pdf(texto_notif: str) -> bytes:
                buf_pdf = io.BytesIO()
                doc = SimpleDocTemplate(buf_pdf, pagesize=A4,
                                        leftMargin=2.5*cm, rightMargin=2.5*cm,
                                        topMargin=2*cm, bottomMargin=2*cm)
                styles = getSampleStyleSheet()
                estilo_mono = ParagraphStyle(
                    "mono", parent=styles["Normal"],
                    fontName="Courier", fontSize=8, leading=11,
                    spaceAfter=2,
                )
                estilo_titulo = ParagraphStyle(
                    "titulo", parent=styles["Heading1"],
                    fontSize=11, alignment=TA_CENTER, spaceAfter=8,
                    textColor=colors.HexColor("#1a4f82"),
                )
                story = []
                story.append(Paragraph("PREFEITURA MUNICIPAL DE SÃO VICENTE", estilo_titulo))
                story.append(Paragraph("Secretaria Municipal de Finanças — Fiscalização Tributária", estilo_titulo))
                story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a4f82")))
                story.append(Spacer(1, 8))
                for linha in texto_notif.strip().split("\n"):
                    if linha.strip().startswith("=="):
                        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
                    elif linha.strip().startswith("--"):
                        story.append(HRFlowable(width="100%", thickness=0.3, color=colors.lightgrey))
                    else:
                        story.append(Paragraph(linha.replace(" ", "&nbsp;"), estilo_mono))
                doc.build(story)
                buf_pdf.seek(0)
                return buf_pdf.read()

            pdf_bytes = gerar_pdf(notificacao)
            st.download_button(
                label=f"⬇️ Baixar notificação PDF ({n_numero})",
                data=pdf_bytes,
                file_name=f"notificacao_{n_numero.replace('/','_').replace('-','_')}.pdf",
                mime="application/pdf",
            )
        except ImportError:
            st.caption("Para exportar em PDF, instale: `pip install reportlab`")
