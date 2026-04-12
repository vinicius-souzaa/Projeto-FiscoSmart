"""
FiscoSmart — Modelo de Risco Fiscal
XGBoost + SHAP para score e explicabilidade por contribuinte
"""
import pandas as pd
import numpy as np
import joblib, os
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import shap

DATA_PROC = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
os.makedirs(MODELS_DIR, exist_ok=True)

FEATURE_COLS = [
    "porte_num", "regime_num", "gap_medio_pct", "gap_std",
    "taxa_omissao", "taxa_retificacao", "cv_receita",
    "slope_receita_norm", "razao_ultimo_media",
    "meses_sem_fiscalizacao", "n_acoes_historicas",
    "gap_vs_bench_pct", "n_meses_com_dados",
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
    y_pred = (y_pred_prob >= 0.40).astype(int)

    metricas = {
        "auc_roc": round(roc_auc_score(y_te, y_pred_prob), 4),
        "precision": round(precision_score(y_te, y_pred), 4),
        "recall": round(recall_score(y_te, y_pred), 4),
        "f1": round(f1_score(y_te, y_pred), 4),
    }
    print(f"  AUC-ROC: {metricas['auc_roc']} | Precision: {metricas['precision']} | Recall: {metricas['recall']} | F1: {metricas['f1']}")

    # Score para todos os contribuintes
    df["score_risco"] = (model.predict_proba(df[FEATURE_COLS].values)[:, 1] * 100).round(1)
    df["faixa_risco"] = pd.cut(
        df["score_risco"],
        bins=[0, 40, 70, 100],
        labels=["Baixo", "Médio", "Alto"],
        include_lowest=True,
    )

    # SHAP values
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(df[FEATURE_COLS].values)
    df_shap = pd.DataFrame(shap_values, columns=[f"shap_{c}" for c in FEATURE_COLS])
    df_shap["id_contribuinte"] = df["id_contribuinte"].values
    df_shap.to_csv(f"{DATA_PROC}/shap_values.csv", index=False)

    # Salvar modelo e resultados
    joblib.dump(model, f"{MODELS_DIR}/modelo_risco.pkl")
    joblib.dump(explainer, f"{MODELS_DIR}/shap_explainer.pkl")
    joblib.dump(metricas, f"{MODELS_DIR}/metricas_modelo.pkl")

    cols_saida = ["id_contribuinte","cnae","desc_cnae","porte","regime_tributario","bairro",
                  "gap_medio_pct","taxa_omissao","meses_sem_fiscalizacao","gap_vs_bench_pct",
                  "score_risco","faixa_risco","irregularidade_confirmada","receita_media_12m"]
    df[cols_saida].to_csv(f"{DATA_PROC}/scores_risco.csv", index=False)
    print(f"  Scores gerados para {len(df)} contribuintes")
    print(f"  Distribuição: {df['faixa_risco'].value_counts().to_dict()}")
    return model, metricas, df


if __name__ == "__main__":
    from feature_engineering import build_features
    build_features()
    treinar_modelo()
