"""
FiscoSmart — Setup v3
Assume que os dados históricos (data/raw/) já existem no repositório.
Só roda: features → modelo → forecasting → insights.

Para gerar o histórico do zero (primeira vez ou reset):
    python src/generate_data.py
"""
import subprocess, sys, os, time

BASE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(BASE, "src")

DATA_RAW_OBRIGATORIOS = [
    "data/raw/contribuintes.csv",
    "data/raw/declaracoes_iss.csv",
    "data/raw/imoveis.csv",
    "data/raw/itbi.csv",
    "data/raw/divida_ativa.csv",
    "data/raw/acoes_fiscais.csv",
    "data/raw/cosip_mensal.csv",
    "data/raw/transferencias.csv",
]


def verificar_dados():
    faltando = [f for f in DATA_RAW_OBRIGATORIOS if not os.path.exists(os.path.join(BASE, f))]
    if faltando:
        print("\n[ERRO] Dados históricos ausentes:")
        for f in faltando:
            print(f"  {f}")
        print("\nGere os dados históricos primeiro:")
        print("  python src/generate_data.py")
        sys.exit(1)


def run(script, desc):
    print(f"\n{'='*52}\n  {desc}\n{'='*52}")
    t0 = time.time()
    r  = subprocess.run([sys.executable, os.path.join(SRC, script)], cwd=BASE)
    if r.returncode != 0:
        print(f"  [ERRO] {script} falhou (código {r.returncode})")
        sys.exit(1)
    print(f"  [OK] concluído em {time.time()-t0:.1f}s")


if __name__ == "__main__":
    print("\n" + "="*52)
    print("  FiscoSmart — Setup v3")
    print("="*52)

    verificar_dados()

    t_total = time.time()
    run("feature_engineering.py", "1/4  Features de risco...")
    run("model_risk.py",          "2/4  XGBoost + SHAP...")
    run("forecasting.py",         "3/4  Prophet (6 meses)...")
    run("insights_engine.py",     "4/4  Insights + JSON...")

    print("\n" + "="*52)
    print(f"  Pronto em {time.time()-t_total:.0f}s")
    print("  streamlit run app/main.py")
    print("="*52 + "\n")
