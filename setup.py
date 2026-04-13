"""
FiscoSmart — Setup local v2
Roda a pipeline completa: dados → features → modelo → previsão → insights
FIX: insights_engine agora salva JSON automaticamente ao rodar como __main__
"""
import subprocess, sys, os, time

BASE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(BASE, "src")


def run(script, desc):
    print(f"\n{'='*55}\n  {desc}\n{'='*55}")
    t0 = time.time()
    r  = subprocess.run([sys.executable, os.path.join(SRC, script)], cwd=BASE)
    elapsed = time.time() - t0
    if r.returncode != 0:
        print(f"  [ERRO] {script} falhou (código {r.returncode})")
        sys.exit(1)
    print(f"  [OK] {script} concluído em {elapsed:.1f}s")


if __name__ == "__main__":
    print("\n" + "="*55)
    print("  FiscoSmart — Pipeline de Setup v2")
    print("="*55)
    t_total = time.time()
    run("generate_data.py",       "1/5  Gerando dados sintéticos...")
    run("feature_engineering.py", "2/5  Construindo features de risco...")
    run("model_risk.py",          "3/5  Treinando XGBoost + SHAP...")
    run("forecasting.py",         "4/5  Previsões Prophet (6 meses)...")
    run("insights_engine.py",     "5/5  Insights automáticos + JSON...")
    print("\n" + "="*55)
    print(f"  Setup concluído em {time.time()-t_total:.0f}s")
    print("  Execute: streamlit run app/main.py")
    print("="*55 + "\n")
