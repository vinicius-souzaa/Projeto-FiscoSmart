"""
FiscoSmart — Motor de Insights Automáticos v2
Combina regras determinísticas + Isolation Forest

FIX v2:
  - __main__ agora salva insights_latest.json em data/processed/ (fix setup.py)
  - Adicionado try/except robusto no carregamento de scores
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
import os, json
from sklearn.ensemble import IsolationForest

DATA_RAW  = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
DATA_PROC = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')


def _fmt(v: float) -> str:
    return f"R$ {v:,.0f}".replace(",","X").replace(".",",").replace("X",".")


class InsightsEngine:
    def __init__(self):
        self.decl     = pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv")
        self.contribs = pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
        self.imoveis  = pd.read_csv(f"{DATA_RAW}/imoveis.csv")
        self.itbi     = pd.read_csv(f"{DATA_RAW}/itbi.csv")
        self.da       = pd.read_csv(f"{DATA_RAW}/divida_ativa.csv")
        self.acoes    = pd.read_csv(f"{DATA_RAW}/acoes_fiscais.csv")
        self.transf   = pd.read_csv(f"{DATA_RAW}/transferencias.csv")
        try:
            self.scores = pd.read_csv(f"{DATA_PROC}/scores_risco.csv")
        except FileNotFoundError:
            self.scores = None

    def insight_gap_setor(self) -> list[dict]:
        ultimos_3m = sorted(self.decl["competencia"].unique())[-3:]
        d3 = self.decl[self.decl["competencia"].isin(ultimos_3m)]
        gap_cnae = (d3.groupby("cnae")
            .agg(gap_medio=("gap_percentual","mean"), valor_gap=("gap_absoluto","sum"), n=("id_contribuinte","count"))
            .reset_index())
        out = []
        for _, r in gap_cnae[gap_cnae["gap_medio"] > 35].iterrows():
            out.append({
                "tipo": "gap_setor",
                "severidade": "alta" if r["gap_medio"] > 50 else "media",
                "cnae": r["cnae"],
                "titulo": f"Gap elevado no setor {r['cnae']}",
                "texto": (f"O setor {r['cnae']} apresentou gap médio de {r['gap_medio']:.1f}% "
                          f"nos últimos 3 meses. Potencial não recolhido: {_fmt(r['valor_gap'])}. "
                          f"Recomenda-se revisão das declarações do setor."),
                "valor_impacto": round(r["valor_gap"], 2),
            })
        return out

    def insight_omissoes_consecutivas(self) -> list[dict]:
        ultimos_6m = sorted(self.decl["competencia"].unique())[-6:]
        d6 = self.decl[self.decl["competencia"].isin(ultimos_6m)]
        omissoes = (d6.groupby("id_contribuinte")["omitiu_declaracao"]
            .sum().reset_index().rename(columns={"omitiu_declaracao":"total_omissoes"}))
        criticos = omissoes[omissoes["total_omissoes"] >= 2]
        if len(criticos) == 0:
            return []
        merged = (criticos
            .merge(self.contribs[["id_contribuinte","cnae","porte"]], on="id_contribuinte")
            .merge(d6.groupby("id_contribuinte")["iss_devido_estimado"].mean().reset_index(), on="id_contribuinte"))
        valor_risco = merged["iss_devido_estimado"].sum() * merged["total_omissoes"].mean()
        return [{
            "tipo": "omissoes_consecutivas", "severidade": "alta",
            "titulo": f"{len(criticos)} contribuintes com omissão recorrente",
            "texto": (f"{len(criticos)} contribuintes omitiram em 2+ dos últimos 6 meses. "
                      f"Valor em risco: {_fmt(valor_risco)}. Ação: notificação prévia imediata."),
            "valor_impacto": round(valor_risco, 2),
        }]

    def insight_queda_arrecadacao_anomala(self) -> list[dict]:
        mensal = (self.decl.groupby(["competencia","mes"])["iss_recolhido"]
            .sum().reset_index().sort_values("competencia"))
        if len(mensal) < 13:
            return []
        mensal["media_mesmo_mes"] = mensal.groupby("mes")["iss_recolhido"].transform("mean")
        mensal["desvio_sazonal"]  = (mensal["iss_recolhido"] - mensal["media_mesmo_mes"]) / mensal["media_mesmo_mes"] * 100
        ultimo = mensal.iloc[-1]
        if ultimo["desvio_sazonal"] < -15:
            return [{
                "tipo": "queda_anomala", "severidade": "alta",
                "titulo": f"Queda anômala de ISS em {ultimo['competencia']}",
                "texto": (f"Arrecadação {abs(ultimo['desvio_sazonal']):.1f}% abaixo da média histórica "
                          f"para o mesmo mês. Queda não explicada por sazonalidade. Investigação recomendada."),
                "valor_impacto": round(abs(ultimo["iss_recolhido"] - ultimo["media_mesmo_mes"]), 2),
            }]
        return []

    def insight_inadimplencia_bairro(self) -> list[dict]:
        inad = (self.imoveis.groupby("bairro")
            .agg(total=("id_imovel","count"), inadimplentes=("inadimplente","sum"),
                 valor_em_atraso=("iptu_lancado","sum"))
            .reset_index())
        inad["taxa_inad"] = inad["inadimplentes"] / inad["total"] * 100
        out = []
        for _, r in inad[inad["taxa_inad"] > 30].sort_values("taxa_inad", ascending=False).iterrows():
            out.append({
                "tipo": "inadimplencia_iptu", "severidade": "media",
                "titulo": f"Alta inadimplência IPTU — {r['bairro']}",
                "texto": (f"{r['bairro']}: {r['taxa_inad']:.1f}% inadimplência "
                          f"({r['inadimplentes']:.0f}/{r['total']:.0f} imóveis). "
                          f"Valor em atraso: {_fmt(r['valor_em_atraso'] * r['taxa_inad']/100)}."),
                "valor_impacto": round(r["valor_em_atraso"] * r["taxa_inad"] / 100, 2),
            })
        return out

    def insight_subavaliacao_itbi(self) -> list[dict]:
        sub = self.itbi[self.itbi["subavaliacao_detectada"] == 1]
        if len(sub) == 0:
            return []
        gap_total = sub["gap_itbi"].sum()
        pct = len(sub) / len(self.itbi) * 100
        return [{
            "tipo": "subavaliacao_itbi", "severidade": "media",
            "titulo": f"Subavaliação em {len(sub)} transações ITBI",
            "texto": (f"{pct:.1f}% das escrituras ({len(sub)}) com valor abaixo do venal IPTU. "
                      f"Gap ITBI estimado: {_fmt(gap_total)}. "
                      f"Recomenda-se arbitramento da base de cálculo."),
            "valor_impacto": round(gap_total, 2),
        }]

    def insight_divida_ativa(self) -> list[dict]:
        total = self.da["valor_total"].sum()
        rec   = self.da["valor_recuperado"].sum()
        tx    = rec / total * 100 if total > 0 else 0
        aberto = self.da[self.da["situacao"] == "Em aberto"]["valor_total"].sum()
        return [{
            "tipo": "divida_ativa",
            "severidade": "alta" if tx < 20 else "media",
            "titulo": f"Taxa de recuperação da dívida ativa: {tx:.1f}%",
            "texto": (f"Estoque total: {_fmt(total)}. Em aberto: {_fmt(aberto)}. "
                      f"Taxa de recuperação: {tx:.1f}%."
                      + (" Abaixo da média nacional (25%) — recomenda-se REFIS municipal." if tx < 25 else "")),
            "valor_impacto": round(aberto, 2),
        }]

    def insight_anomalias_isolation_forest(self) -> list[dict]:
        if self.scores is None:
            return []
        feats = ["gap_medio_pct","taxa_omissao","gap_vs_bench_pct","meses_sem_fiscalizacao"]
        df = self.scores.dropna(subset=feats).copy()
        df["anomalia"] = IsolationForest(contamination=0.05, random_state=42).fit_predict(df[feats])
        anomalos = df[df["anomalia"] == -1]
        if len(anomalos) == 0:
            return []
        valor_pot = anomalos["receita_media_12m"].sum() * 0.03 * 0.40
        return [{
            "tipo": "anomalia_isolation_forest", "severidade": "alta",
            "titulo": f"{len(anomalos)} contribuintes com comportamento atípico",
            "texto": (f"Isolation Forest identificou {len(anomalos)} contribuintes com padrão fiscal "
                      f"incomum — não capturados pelas regras tradicionais. "
                      f"Valor potencial estimado: {_fmt(valor_pot)}."),
            "valor_impacto": round(valor_pot, 2),
            "contribuintes_anomalos": anomalos["id_contribuinte"].tolist(),
        }]


    def insight_prazo_da(self) -> list[dict]:
        """
        Contribuintes com competência vencida entre 60 e 89 dias sem pagamento:
        a menos de 30 dias de serem inscritos em dívida ativa automaticamente.
        Alerta o auditor para agir antes do processo judicial.
        """
        pag_path = os.path.join(DATA_RAW, 'pagamentos_iss.csv')
        if not os.path.exists(pag_path):
            return []

        try:
            pag = pd.read_csv(pag_path, usecols=['id_contribuinte','competencia','status'])
        except Exception:
            return []

        ja_pagou = set(
            zip(pag[pag['status'].isin(['pago','pago_atraso'])]['id_contribuinte'].astype(int),
                pag['competencia'])
        )

        # Chaves já em DA para não duplicar alerta
        da_chaves = set()
        if len(self.da) > 0:
            da_iss = self.da[(self.da['tipo_tributo']=='ISS') & self.da['id_contribuinte'].notna()]
            da_chaves = set(zip(da_iss['id_contribuinte'].astype(int), da_iss['competencia_origem']))

        hoje = date.today()
        alertas = []

        for comp in self.decl['competencia'].unique():
            ano, mes = int(comp[:4]), int(comp[5:7])
            mes_v = mes + 1; ano_v = ano + (mes_v > 12); mes_v = mes_v % 12 or 12
            try:
                venc = date(ano_v, mes_v, 15)
            except ValueError:
                continue

            dias_vencido = (hoje - venc).days
            if not (60 <= dias_vencido <= 89):
                continue

            dias_para_da = 90 - dias_vencido
            decl_comp = self.decl[self.decl['competencia'] == comp]

            pendentes = decl_comp[
                ~decl_comp['id_contribuinte'].isin(
                    [c for c, cp in ja_pagou if cp == comp]
                ) &
                ~decl_comp['id_contribuinte'].isin(
                    [c for c, cp in da_chaves if cp == comp]
                )
            ]

            if len(pendentes) == 0:
                continue

            valor_em_risco = pendentes['iss_devido_estimado'].sum()
            alertas.append({
                'tipo': 'prazo_da',
                'severidade': 'alta' if dias_para_da <= 10 else 'media',
                'titulo': f"Competência {comp} entra em DA em {dias_para_da} dia(s)",
                'texto': (
                    f"{len(pendentes)} contribuintes da competência {comp} ainda não pagaram. "
                    f"O prazo de tolerância vence em {dias_para_da} dia(s) (dia {venc + timedelta(days=90)}). "
                    f"Valor em risco de inscrição em dívida ativa: {_fmt(valor_em_risco)}. "
                    f"Ação: notificação extrajudicial imediata para evitar execução fiscal."
                ),
                'valor_impacto': round(valor_em_risco, 2),
                'competencia': comp,
                'dias_para_da': dias_para_da,
                'n_contribuintes': len(pendentes),
            })

        # Ordenar por urgência (menos dias primeiro)
        alertas.sort(key=lambda x: x['dias_para_da'])
        return alertas

    def todos_insights(self) -> list[dict]:
        insights = (
            self.insight_prazo_da()
            + self.insight_gap_setor()
            + self.insight_omissoes_consecutivas()
            + self.insight_queda_arrecadacao_anomala()
            + self.insight_inadimplencia_bairro()
            + self.insight_subavaliacao_itbi()
            + self.insight_divida_ativa()
            + self.insight_anomalias_isolation_forest()
        )
        sev_ord = {"alta": 0, "media": 1, "baixa": 2}
        insights.sort(key=lambda x: (sev_ord.get(x["severidade"], 2), -x.get("valor_impacto", 0)))
        return insights


# FIX: __main__ agora salva o JSON (setup.py chama este script via subprocess)
if __name__ == "__main__":
    import os as _os
    eng      = InsightsEngine()
    insights = eng.todos_insights()

    out_path = _os.path.join(_os.path.dirname(__file__), '..', 'data', 'processed', 'insights_latest.json')
    _os.makedirs(_os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2, default=str)

    print(f"  {len(insights)} insights gerados → {out_path}")
    for ins in insights:
        print(f"  [{ins['severidade'].upper():5}] {ins['titulo']}")
