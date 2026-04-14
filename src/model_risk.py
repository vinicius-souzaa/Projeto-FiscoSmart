"""
FiscoSmart — Modelo de Risco Fiscal v2
XGBoost + SHAP para score e explicabilidade por contribuinte

FIXES v2:
  - Bins de faixa_risco calibrados por percentil (p80/p93) em vez de thresholds fixos
  - Evita que 91% dos contribuintes fiquem em "Baixo" por thresholds arbitrários
  - Salva bins usados em metricas_modelo.pkl para uso consistente no dashboard
"""
import pandas as pd
import numpy as np
import joblib, os, json
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
import xgboost as xgb
import shap

DATA_PROC  = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
os.makedirs(MODELS_DIR, exist_ok=True)

FEATURE_COLS = [
    "porte_num", "regime_num", "gap_medio_pct", "gap_std",
    "taxa_omissao", "taxa_retificacao", "cv_receita",
    "slope_receita_norm", "razao_ultimo_media",
    "meses_sem_fiscalizacao", "nunca_fiscalizado",   # nova feature
    "n_acoes_historicas", "gap_vs_bench_pct", "n_meses_com_dados",
]


def treinar_modelo():
    print("Treinando modelo de risco fiscal XGBoost...")
    df = pd.read_csv(f"{DATA_PROC}/features_risco.csv")
    df = df.dropna(subset=FEATURE_COLS + ["irregularidade_confirmada"])

    X = df[FEATURE_COLS].values
    y = df["irregularidade_confirmada"].values

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=(y == 0).sum() / (y == 1).sum(),
        eval_metric="auc",
        random_state=42,
        verbosity=0,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)

    y_pred_prob = model.predict_proba(X_te)[:, 1]
    y_pred      = (y_pred_prob >= 0.40).astype(int)

    metricas = {
        "auc_roc":   round(roc_auc_score(y_te, y_pred_prob), 4),
        "precision": round(precision_score(y_te, y_pred, zero_division=0), 4),
        "recall":    round(recall_score(y_te, y_pred, zero_division=0), 4),
        "f1":        round(f1_score(y_te, y_pred, zero_division=0), 4),
    }
    print(f"  AUC-ROC: {metricas['auc_roc']} | Precision: {metricas['precision']} "
          f"| Recall: {metricas['recall']} | F1: {metricas['f1']}")

    # Scores para toda a base
    all_scores = model.predict_proba(df[FEATURE_COLS].values)[:, 1] * 100

    # FIX: bins calibrados por percentil da distribuição real de scores
    # p80 → Baixo/Médio, p93 → Médio/Alto — ~7% alto (alinha com prevalência de irregulares)
    bin_medio = float(np.percentile(all_scores, 80))
    bin_alto  = float(np.percentile(all_scores, 93))
    metricas["bin_medio"] = round(bin_medio, 2)
    metricas["bin_alto"]  = round(bin_alto, 2)

    df["score_risco"] = all_scores.round(1)
    df["faixa_risco"] = pd.cut(
        df["score_risco"],
        bins=[0, bin_medio, bin_alto, 100.01],
        labels=["Baixo", "Médio", "Alto"],
        include_lowest=True,
    )

    # SHAP values
    explainer  = shap.TreeExplainer(model)
    shap_vals  = explainer.shap_values(df[FEATURE_COLS].values)
    df_shap    = pd.DataFrame(shap_vals, columns=[f"shap_{c}" for c in FEATURE_COLS])
    df_shap["id_contribuinte"] = df["id_contribuinte"].values
    df_shap.to_csv(f"{DATA_PROC}/shap_values.csv", index=False)

    # Persistir artefatos
    joblib.dump(model,     f"{MODELS_DIR}/modelo_risco.pkl")
    joblib.dump(explainer, f"{MODELS_DIR}/shap_explainer.pkl")
    joblib.dump(metricas,  f"{MODELS_DIR}/metricas_modelo.pkl")

    # FIX: salva bins também em JSON para acesso sem depender do pickle
    meta = {
        "bin_medio": round(bin_medio, 2),
        "bin_alto":  round(bin_alto, 2),
        "auc_roc":   metricas["auc_roc"],
        "recall":    metricas["recall"],
        "precision": metricas["precision"],
        "f1":        metricas["f1"],
        "features":  FEATURE_COLS,
        "gerado_em": str(pd.Timestamp.now()),
    }
    with open(f"{DATA_PROC}/model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    cols_saida = [
        "id_contribuinte", "cnae", "desc_cnae", "porte", "regime_tributario", "bairro",
        "gap_medio_pct", "taxa_omissao", "meses_sem_fiscalizacao", "nunca_fiscalizado",
        "gap_vs_bench_pct", "score_risco", "faixa_risco",
        "irregularidade_confirmada", "receita_media_12m",
    ]
    # FIX: inclui bins como colunas no CSV para evitar dependência exclusiva do pickle
    df["bin_medio"] = round(bin_medio, 2)
    df["bin_alto"]  = round(bin_alto, 2)
    cols_saida += ["bin_medio", "bin_alto"]
    df[cols_saida].to_csv(f"{DATA_PROC}/scores_risco.csv", index=False)

    dist = df["faixa_risco"].value_counts().to_dict()
    print(f"  {len(df)} contribuintes | Baixo: {dist.get('Baixo',0)} "
          f"| Médio: {dist.get('Médio',0)} | Alto: {dist.get('Alto',0)}")
    print(f"  Bins: Médio≥{bin_medio:.1f} | Alto≥{bin_alto:.1f}")
    return model, metricas, df


if __name__ == "__main__":
    from feature_engineering import build_features
    build_features()
    treinar_modelo()
