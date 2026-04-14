"""
FiscoSmart — Feature Engineering
Constrói features para o modelo XGBoost de risco fiscal
"""
import pandas as pd
import numpy as np
import os

DATA_RAW = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
DATA_PROC = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
os.makedirs(DATA_PROC, exist_ok=True)


def build_features():
    print("Construindo features de risco fiscal...")
    decl = pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv")
    contribs = pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
    acoes = pd.read_csv(f"{DATA_RAW}/acoes_fiscais.csv")
    acoes["data_acao"] = pd.to_datetime(acoes["data_acao"])

    # Só últimos 12 meses para features preditivas
    ultimos_12 = sorted(decl["competencia"].unique())[-12:]
    d12 = decl[decl["competencia"].isin(ultimos_12)]

    # FIX VIÉS TEMPORAL: limite temporal para o target
    # Só conta ações fiscais anteriores ao fim da janela de features,
    # evitando que o modelo "veja o futuro" durante o treinamento.
    fim_janela = pd.Timestamp(ultimos_12[-1] + "-01") + pd.offsets.MonthEnd(0)

    feats = []
    for cid in contribs["id_contribuinte"].unique():
        c = contribs[contribs["id_contribuinte"] == cid].iloc[0]
        cd = d12[d12["id_contribuinte"] == cid]
        if len(cd) == 0:
            continue

        # Features de declaração
        gap_medio = cd["gap_percentual"].mean()
        gap_std = cd["gap_percentual"].std() if len(cd) > 1 else 0
        taxa_omissao = cd["omitiu_declaracao"].mean()
        taxa_retificacao = cd["retificou"].mean()
        receita_media = cd["receita_declarada"].mean()
        receita_std = cd["receita_declarada"].std() if len(cd) > 1 else 0
        cv_receita = receita_std / receita_media if receita_media > 0 else 0

        # Tendência (slope da receita declarada)
        if len(cd) > 3:
            x = np.arange(len(cd))
            y = cd["receita_declarada"].values
            slope = np.polyfit(x, y, 1)[0] if y.std() > 0 else 0
            slope_norm = slope / receita_media if receita_media > 0 else 0
        else:
            slope_norm = 0

        # Último mês vs. média histórica
        ultimo_mes_receita = cd.iloc[-1]["receita_declarada"]
        razao_ultimo_media = ultimo_mes_receita / receita_media if receita_media > 0 else 1

        # Meses sem fiscalização
        acoes_c = acoes[acoes["id_contribuinte"] == cid]

        # FIX VIÉS TEMPORAL: usa apenas ações ANTES do fim da janela de features
        acoes_c_hist = acoes_c[acoes_c["data_acao"] <= fim_janela]

        nunca_fiscalizado = int(len(acoes_c_hist) == 0)   # flag binária nova
        if len(acoes_c_hist) > 0:
            ultima_acao = acoes_c_hist["data_acao"].max()
            meses_sem_fisc = max(0, (fim_janela - ultima_acao).days // 30)
        else:
            # Nunca fiscalizado: valor alto mas separado do flag para o modelo diferenciar
            meses_sem_fisc = 48

        # Porte e regime (encoded)
        porte_map = {"MEI": 1, "ME": 2, "EPP": 3, "MD": 4, "GR": 5}
        regime_map = {"MEI": 1, "Simples Nacional": 2, "Lucro Presumido": 3, "Lucro Real": 4}

        # FIX VIÉS TEMPORAL: target usa apenas ações dentro da janela histórica
        irr = acoes_c_hist["irregularidade_confirmada"].max() if len(acoes_c_hist) > 0 else 0

        feats.append({
            "id_contribuinte": cid,
            "cnae": c["cnae"],
            "desc_cnae": c["desc_cnae"],
            "porte": c["porte"],
            "porte_num": porte_map.get(c["porte"], 2),
            "regime_tributario": c["regime_tributario"],
            "regime_num": regime_map.get(c["regime_tributario"], 2),
            "bairro": c["bairro"],
            "risco_latente": c["risco_latente"],
            # Situação cadastral (se disponível)
            "situacao_cnpj": c.get("situacao_cnpj", "Ativo"),
            # Features preditivas
            "gap_medio_pct": round(gap_medio, 2),
            "gap_std": round(gap_std, 2),
            "taxa_omissao": round(taxa_omissao, 4),
            "taxa_retificacao": round(taxa_retificacao, 4),
            "receita_media_12m": round(receita_media, 2),
            "cv_receita": round(cv_receita, 4),
            "slope_receita_norm": round(slope_norm, 6),
            "razao_ultimo_media": round(razao_ultimo_media, 4),
            "meses_sem_fiscalizacao": meses_sem_fisc,
            "nunca_fiscalizado": nunca_fiscalizado,          # nova feature
            "n_acoes_historicas": len(acoes_c_hist),
            "n_meses_com_dados": len(cd),
            # Target (sem lookahead)
            "irregularidade_confirmada": int(irr),
        })

    df = pd.DataFrame(feats)

    # Adicionar benchmark gap
    bench_cnae = (
        decl.groupby("cnae")
        .agg(bench_receita_media=("receita_real_estimada", "mean"))
        .reset_index()
    )
    df = df.merge(bench_cnae, on="cnae", how="left")
    df["gap_vs_bench_pct"] = (
        (df["bench_receita_media"] - df["receita_media_12m"]) / df["bench_receita_media"] * 100
    ).clip(0, 100).round(2)

    df.to_csv(f"{DATA_PROC}/features_risco.csv", index=False)
    print(f"  {len(df)} contribuintes com features geradas")
    return df


if __name__ == "__main__":
    build_features()
