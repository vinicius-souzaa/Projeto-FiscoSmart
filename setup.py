"""
FiscoSmart — Setup local
Roda a pipeline completa: dados → features → modelo → previsão → insights
Use este script para rodar localmente antes de subir no GitHub.
"""
import subprocess, sys, os

BASE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(BASE, "src")

def run(script, desc):
    print(f"\n{'='*55}\n  {desc}\n{'='*55}")
    r = subprocess.run([sys.executable, os.path.join(SRC, script)], cwd=BASE)
    if r.returncode != 0:
        print(f"  [ERRO] {script} falhou.")
        sys.exit(1)
    print(f"  [OK] {script} concluído.")

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  FiscoSmart — Pipeline de Setup")
    print("="*55)
    run("generate_data.py",       "1/5  Gerando dados sintéticos...")
    run("feature_engineering.py", "2/5  Construindo features...")
    run("model_risk.py",          "3/5  Treinando XGBoost + SHAP...")
    run("forecasting.py",         "4/5  Previsões Prophet...")
    run("insights_engine.py",     "5/5  Insights automáticos...")
    print("\n" + "="*55)
    print("  Setup concluído!")
    print("  streamlit run app/main.py")
    print("="*55 + "\n")
