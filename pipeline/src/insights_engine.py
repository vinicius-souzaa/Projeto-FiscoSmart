"""
FiscoSmart — Motor de Insights Automáticos
Combina regras determinísticas + Isolation Forest + linguagem natural
"""
import pandas as pd
import numpy as np
import os
from sklearn.ensemble import IsolationForest
from datetime import date

DATA_RAW  = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
DATA_PROC = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')


def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


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

    # ─── INSIGHTS ISS ────────────────────────────────────────────────────────

    def insight_gap_setor(self) -> list[dict]:
        """Setores com gap de arrecadação sistemático"""
        ultimos_3m = sorted(self.decl["competencia"].unique())[-3:]
        d3 = self.decl[self.decl["competencia"].isin(ultimos_3m)]
        gap_cnae = (
            d3.groupby("cnae")
            .agg(gap_medio=("gap_percentual","mean"), valor_gap=("gap_absoluto","sum"), n=("id_contribuinte","count"))
            .reset_index()
        )
        insights = []
        for _, r in gap_cnae[gap_cnae["gap_medio"] > 35].iterrows():
            desc = self.decl[self.decl["cnae"]==r["cnae"]]["cnae"].count()
            insights.append({
                "tipo": "gap_setor",
                "severidade": "alta" if r["gap_medio"] > 50 else "media",
                "cnae": r["cnae"],
                "titulo": f"Gap elevado no setor {r['cnae']}",
                "texto": (
                    f"O setor {r['cnae']} apresentou gap médio de {r['gap_medio']:.1f}% "
                    f"nos últimos 3 meses. Valor potencial não recolhido: {_fmt_brl(r['valor_gap'])}. "
                    f"Recomenda-se revisão das declarações do setor."
                ),
                "valor_impacto": round(r["valor_gap"], 2),
            })
        return insights

    def insight_omissoes_consecutivas(self) -> list[dict]:
        """Contribuintes com 2+ meses consecutivos sem declaração"""
        ultimos_6m = sorted(self.decl["competencia"].unique())[-6:]
        d6 = self.decl[self.decl["competencia"].isin(ultimos_6m)]
        omissoes = (
            d6.groupby("id_contribuinte")["omitiu_declaracao"]
            .sum()
            .reset_index()
            .rename(columns={"omitiu_declaracao":"total_omissoes"})
        )
        criticos = omissoes[omissoes["total_omissoes"] >= 2]
        if len(criticos) == 0:
            return []
        merged = criticos.merge(self.contribs[["id_contribuinte","cnae","porte"]], on="id_contribuinte")
        merged2 = merged.merge(
            d6.groupby("id_contribuinte")["iss_devido_estimado"].mean().reset_index(),
            on="id_contribuinte"
        )
        valor_risco = merged2["iss_devido_estimado"].sum() * merged2["total_omissoes"].mean()
        return [{
            "tipo": "omissoes_consecutivas",
            "severidade": "alta",
            "titulo": f"{len(criticos)} contribuintes com omissão recorrente",
            "texto": (
                f"{len(criticos)} contribuintes omitiram declaração em 2 ou mais dos últimos 6 meses. "
                f"Valor potencial em risco estimado: {_fmt_brl(valor_risco)}. "
                f"Ação recomendada: notificação prévia imediata."
            ),
            "valor_impacto": round(valor_risco, 2),
        }]

    def insight_queda_arrecadacao_anomala(self) -> list[dict]:
        """Detecta quedas de arrecadação que não são explicadas pela sazonalidade"""
        mensal = (
            self.decl.groupby(["competencia","mes"])["iss_recolhido"]
            .sum()
            .reset_index()
            .sort_values("competencia")
        )
        if len(mensal) < 13:
            return []
        mensal["media_mesmo_mes"] = mensal.groupby("mes")["iss_recolhido"].transform("mean")
        mensal["desvio_sazonal"] = (mensal["iss_recolhido"] - mensal["media_mesmo_mes"]) / mensal["media_mesmo_mes"] * 100
        ultimo = mensal.iloc[-1]
        if ultimo["desvio_sazonal"] < -15:
            return [{
                "tipo": "queda_anomala",
                "severidade": "alta",
                "titulo": f"Queda anômala de ISS em {ultimo['competencia']}",
                "texto": (
                    f"A arrecadação de ISS em {ultimo['competencia']} ficou {abs(ultimo['desvio_sazonal']):.1f}% "
                    f"abaixo da média histórica para o mesmo mês. "
                    f"Essa queda não é explicada pela sazonalidade esperada. "
                    f"Investigação recomendada."
                ),
                "valor_impacto": round(abs(ultimo["iss_recolhido"] - ultimo["media_mesmo_mes"]), 2),
            }]
        return []

    # ─── INSIGHTS IPTU ───────────────────────────────────────────────────────

    def insight_inadimplencia_bairro(self) -> list[dict]:
        inad = self.imoveis.groupby("bairro").agg(
            total=("id_imovel","count"),
            inadimplentes=("inadimplente","sum"),
            valor_em_atraso=("iptu_lancado","sum"),
        ).reset_index()
        inad["taxa_inad"] = inad["inadimplentes"] / inad["total"] * 100
        criticos = inad[inad["taxa_inad"] > 30].sort_values("taxa_inad", ascending=False)
        insights = []
        for _, r in criticos.iterrows():
            insights.append({
                "tipo": "inadimplencia_iptu",
                "severidade": "media",
                "titulo": f"Alta inadimplência de IPTU — {r['bairro']}",
                "texto": (
                    f"O bairro {r['bairro']} tem {r['taxa_inad']:.1f}% de inadimplência no IPTU "
                    f"({r['inadimplentes']:.0f} de {r['total']:.0f} imóveis). "
                    f"Valor em atraso estimado: {_fmt_brl(r['valor_em_atraso'] * r['taxa_inad']/100)}."
                ),
                "valor_impacto": round(r["valor_em_atraso"] * r["taxa_inad"] / 100, 2),
            })
        return insights

    # ─── INSIGHTS ITBI ───────────────────────────────────────────────────────

    def insight_subavaliacao_itbi(self) -> list[dict]:
        sub = self.itbi[self.itbi["subavaliacao_detectada"] == 1]
        if len(sub) == 0:
            return []
        gap_total = sub["gap_itbi"].sum()
        pct = len(sub) / len(self.itbi) * 100
        return [{
            "tipo": "subavaliacao_itbi",
            "severidade": "media",
            "titulo": f"Subavaliação detectada em {len(sub)} transações de ITBI",
            "texto": (
                f"{pct:.1f}% das transações imobiliárias ({len(sub)} escrituras) apresentam "
                f"valor declarado abaixo do valor venal do IPTU. "
                f"Gap de ITBI não recolhido estimado: {_fmt_brl(gap_total)}. "
                f"Recomenda-se arbitramento da base de cálculo nos casos identificados."
            ),
            "valor_impacto": round(gap_total, 2),
        }]

    # ─── INSIGHTS DÍVIDA ATIVA ───────────────────────────────────────────────

    def insight_divida_ativa(self) -> list[dict]:
        total_da = self.da["valor_total"].sum()
        recuperado = self.da["valor_recuperado"].sum()
        tx_recup = recuperado / total_da * 100 if total_da > 0 else 0
        em_aberto = self.da[self.da["situacao"] == "Em aberto"]["valor_total"].sum()
        return [{
            "tipo": "divida_ativa",
            "severidade": "alta" if tx_recup < 20 else "media",
            "titulo": f"Taxa de recuperação de dívida ativa: {tx_recup:.1f}%",
            "texto": (
                f"Estoque total da dívida ativa: {_fmt_brl(total_da)}. "
                f"Valor em aberto (sem parcelamento): {_fmt_brl(em_aberto)}. "
                f"Taxa de recuperação histórica: {tx_recup:.1f}%. "
                + ("Abaixo da média nacional de 25% — recomenda-se campanha de renegociação." if tx_recup < 25 else "")
            ),
            "valor_impacto": round(em_aberto, 2),
        }]

    # ─── INSIGHT ANOMALIAS (Isolation Forest) ────────────────────────────────

    def insight_anomalias_isolation_forest(self) -> list[dict]:
        if self.scores is None:
            return []
        feats = ["gap_medio_pct","taxa_omissao","gap_vs_bench_pct","meses_sem_fiscalizacao"]
        df = self.scores.dropna(subset=feats)
        iso = IsolationForest(contamination=0.05, random_state=42)
        df = df.copy()
        df["anomalia"] = iso.fit_predict(df[feats])
        anomalos = df[df["anomalia"] == -1]
        if len(anomalos) == 0:
            return []
        valor_pot = anomalos["receita_media_12m"].sum() * 0.03 * 0.40  # estimativa conservadora
        return [{
            "tipo": "anomalia_isolation_forest",
            "severidade": "alta",
            "titulo": f"{len(anomalos)} contribuintes com comportamento atípico detectado",
            "texto": (
                f"O modelo de detecção de anomalias identificou {len(anomalos)} contribuintes "
                f"com padrão fiscal estatisticamente incomum em relação ao grupo. "
                f"Esses contribuintes não foram capturados pelos critérios de regra tradicionais. "
                f"Valor potencial estimado: {_fmt_brl(valor_pot)}."
            ),
            "valor_impacto": round(valor_pot, 2),
            "contribuintes_anomalos": anomalos["id_contribuinte"].tolist(),
        }]

    # ─── PRIORIZAÇÃO ─────────────────────────────────────────────────────────

    def gerar_priorizacao(self) -> pd.DataFrame:
        """Combina score de risco + valor potencial para gerar ranking de fiscalização"""
        if self.scores is None:
            return pd.DataFrame()
        df = self.scores.copy()
        df["valor_potencial_mensal"] = df["receita_media_12m"] * df["gap_vs_bench_pct"] / 100 * 0.03
        df["custo_estimado"] = df["porte"].map({"MEI":500,"ME":1200,"EPP":2500,"MD":5000,"GR":12000})
        df["retorno_esperado"] = (
            df["valor_potencial_mensal"] * (df["score_risco"] / 100)
        ) / df["custo_estimado"].clip(lower=100)
        df["ultima_fiscalizacao_categoria"] = pd.cut(
            df["meses_sem_fiscalizacao"], bins=[0,6,12,24,999],
            labels=["<6m","6-12m","12-24m",">24m"]
        )
        return df.sort_values("retorno_esperado", ascending=False).head(100)

    # ─── CONSOLIDAR TODOS OS INSIGHTS ────────────────────────────────────────

    def todos_insights(self) -> list[dict]:
        insights = []
        insights += self.insight_gap_setor()
        insights += self.insight_omissoes_consecutivas()
        insights += self.insight_queda_arrecadacao_anomala()
        insights += self.insight_inadimplencia_bairro()
        insights += self.insight_subavaliacao_itbi()
        insights += self.insight_divida_ativa()
        insights += self.insight_anomalias_isolation_forest()
        # Ordenar por severidade e valor de impacto
        sev_ord = {"alta": 0, "media": 1, "baixa": 2}
        insights.sort(key=lambda x: (sev_ord.get(x["severidade"],2), -x.get("valor_impacto",0)))
        return insights


if __name__ == "__main__":
    eng = InsightsEngine()
    for ins in eng.todos_insights():
        print(f"[{ins['severidade'].upper()}] {ins['titulo']}")
        print(f"  {ins['texto']}\n")
