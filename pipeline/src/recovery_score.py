"""
FiscoSmart — Score de Recuperabilidade da Dívida Ativa
Modelo logístico para priorizar esforço de cobrança:
  P(recuperação) para cada inscrição em DA, dada fase, tributo,
  valor e tempo desde a inscrição.

Uso:
  python src/recovery_score.py          # treina e salva scores
  from src.recovery_score import prever_recuperabilidade
"""
import pandas as pd
import numpy as np
import joblib, os, json
from datetime import date
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score
from sklearn.metrics import roc_auc_score

DATA_RAW   = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
DATA_PROC  = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
os.makedirs(DATA_PROC, exist_ok=True)


def _preparar_features(da: pd.DataFrame) -> pd.DataFrame:
    """Constrói feature matrix a partir de divida_ativa.csv."""
    df = da.copy()
    df["data_inscricao"] = pd.to_datetime(df["data_inscricao"], errors="coerce")
    hoje = pd.Timestamp(date.today())
    df["meses_inscrito"] = ((hoje - df["data_inscricao"]).dt.days / 30).clip(0, 120)

    # Encodings
    df["fase_num"]    = df["fase"].map({"Administrativa": 0, "Judicial": 1}).fillna(0)
    df["tributo_num"] = df["tipo_tributo"].map({"ISS": 0, "IPTU": 1}).fillna(2)

    # Features normalizadas
    df["log_principal"] = np.log1p(df["valor_principal"])
    df["log_juros"]     = np.log1p(df["juros"])
    df["log_multa"]     = np.log1p(df["multa"])
    df["razao_juros"]   = df["juros"] / (df["valor_principal"] + 1)   # quanto virou de juros
    df["razao_multa"]   = df["multa"] / (df["valor_principal"] + 1)

    return df


FEATURE_COLS_DA = [
    "fase_num", "tributo_num", "log_principal", "log_juros", "log_multa",
    "razao_juros", "razao_multa", "meses_inscrito",
]


def treinar_recovery_model():
    print("Treinando modelo de recuperabilidade de DA...")
    da = pd.read_csv(f"{DATA_RAW}/divida_ativa.csv")
    df = _preparar_features(da)
    df["recuperado"] = (df["valor_recuperado"] > 0).astype(int)

    df_clean = df.dropna(subset=FEATURE_COLS_DA + ["recuperado"])
    X = df_clean[FEATURE_COLS_DA].values
    y = df_clean["recuperado"].values

    if len(y) < 20 or y.sum() < 5:
        print("  AVISO: poucos dados para treinar recovery model — usando heurística.")
        return None, None

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    LogisticRegression(class_weight="balanced", max_iter=500, random_state=42)),
    ])

    # Cross-validation para AUC
    if len(y) >= 50:
        cv_auc = cross_val_score(model, X, y, cv=5, scoring="roc_auc")
        print(f"  CV AUC-ROC (5-fold): {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")

    model.fit(X, y)

    # Scores para toda a base
    df_clean = df_clean.copy()
    df_clean["prob_recuperacao"] = model.predict_proba(X)[:, 1]
    df_clean["score_recuperacao"] = (df_clean["prob_recuperacao"] * 100).round(1)

    # Faixa de prioridade de cobrança
    df_clean["prioridade_cobranca"] = pd.cut(
        df_clean["score_recuperacao"],
        bins=[0, 30, 60, 100.01],
        labels=["Baixa", "Média", "Alta"],
        include_lowest=True,
    )

    cols_saida = [
        "id_da", "tipo_tributo", "fase", "situacao", "id_contribuinte",
        "competencia_origem", "valor_principal", "juros", "multa", "valor_total",
        "valor_recuperado", "meses_inscrito",
        "prob_recuperacao", "score_recuperacao", "prioridade_cobranca",
    ]
    df_out = df_clean[[c for c in cols_saida if c in df_clean.columns]]
    df_out.to_csv(f"{DATA_PROC}/recovery_scores.csv", index=False)

    joblib.dump(model, f"{MODELS_DIR}/recovery_model.pkl")
    print(f"  {len(df_out)} inscrições com score de recuperação gerado.")

    dist = df_clean["prioridade_cobranca"].value_counts().to_dict()
    print(f"  Alta: {dist.get('Alta',0)} | Média: {dist.get('Média',0)} | Baixa: {dist.get('Baixa',0)}")
    return model, df_out


def prever_recuperabilidade(da_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica o modelo salvo em novos registros de DA.
    Retorna o DataFrame original com colunas adicionadas:
      prob_recuperacao, score_recuperacao, prioridade_cobranca
    """
    model_path = os.path.join(MODELS_DIR, "recovery_model.pkl")
    if not os.path.exists(model_path):
        da_df["score_recuperacao"] = 50.0
        da_df["prioridade_cobranca"] = "Média"
        return da_df

    model = joblib.load(model_path)
    df = _preparar_features(da_df.copy())
    cols_ok = [c for c in FEATURE_COLS_DA if c in df.columns]
    df_feat = df[cols_ok].fillna(0)

    da_df = da_df.copy()
    da_df["prob_recuperacao"] = model.predict_proba(df_feat.values)[:, 1]
    da_df["score_recuperacao"] = (da_df["prob_recuperacao"] * 100).round(1)
    da_df["prioridade_cobranca"] = pd.cut(
        da_df["score_recuperacao"],
        bins=[0, 30, 60, 100.01],
        labels=["Baixa", "Média", "Alta"],
        include_lowest=True,
    )
    return da_df


if __name__ == "__main__":
    treinar_recovery_model()
