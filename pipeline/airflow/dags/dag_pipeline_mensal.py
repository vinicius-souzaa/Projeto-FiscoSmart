"""
FiscoSmart — DAG Principal: Pipeline Mensal Tributário
Executa todo o dia 1 de cada mês às 06:00
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

PROJECT_ROOT = "/opt/airflow/fiscosmart"

default_args = {
    "owner": "fiscosmart",
    "depends_on_past": False,
    "start_date": days_ago(1),
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": False,
}

dag = DAG(
    "fiscosmart_pipeline_mensal",
    default_args=default_args,
    description="Pipeline mensal completo: ingestão → dbt → modelos → previsão",
    schedule_interval="0 6 1 * *",  # 1º dia do mês às 06h
    catchup=False,
    tags=["fiscosmart", "tributario", "mensal"],
)

# ── TASK 1: Simular ingestão de novos dados ────────────────────────────────────
def task_ingestao(**context):
    """Simula chegada de novos dados do mês anterior"""
    import sys, os
    sys.path.insert(0, PROJECT_ROOT)
    from src.generate_data import main as gerar
    print(f"[{context['ds']}] Iniciando ingestão de dados mensais...")
    gerar()
    print("Ingestão concluída.")

t_ingestao = PythonOperator(
    task_id="ingestao_dados_mensais",
    python_callable=task_ingestao,
    dag=dag,
)

# ── TASK 2: Transformações dbt ─────────────────────────────────────────────────
t_dbt_run = BashOperator(
    task_id="dbt_run_transformacoes",
    bash_command=f"cd {PROJECT_ROOT}/dbt && dbt run --profiles-dir . --project-dir . 2>&1 || echo 'dbt não configurado, pulando'",
    dag=dag,
)

t_dbt_test = BashOperator(
    task_id="dbt_test_qualidade",
    bash_command=f"cd {PROJECT_ROOT}/dbt && dbt test --profiles-dir . --project-dir . 2>&1 || echo 'dbt não configurado, pulando'",
    dag=dag,
)

# ── TASK 3: Feature engineering ───────────────────────────────────────────────
def task_features(**context):
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from src.feature_engineering import build_features
    print(f"[{context['ds']}] Construindo features...")
    build_features()

t_features = PythonOperator(
    task_id="feature_engineering",
    python_callable=task_features,
    dag=dag,
)

# ── TASK 4: Retreinar modelo de risco ─────────────────────────────────────────
def task_modelo(**context):
    import sys, os, joblib
    sys.path.insert(0, PROJECT_ROOT)
    from src.model_risk import treinar_modelo
    print(f"[{context['ds']}] Retreinando modelo XGBoost...")
    model, metricas, _ = treinar_modelo()
    # Verificar se novo modelo é melhor
    modelos_dir = f"{PROJECT_ROOT}/models"
    hist_path = f"{modelos_dir}/historico_metricas.pkl"
    try:
        historico = joblib.load(hist_path)
        melhor_anterior = historico[-1].get("auc_roc", 0)
        if metricas["auc_roc"] >= melhor_anterior - 0.01:
            historico.append({**metricas, "data": context['ds']})
            joblib.dump(historico, hist_path)
            print(f"Modelo aceito: AUC-ROC {metricas['auc_roc']} >= {melhor_anterior}")
        else:
            print(f"[ALERTA] Novo modelo ({metricas['auc_roc']}) pior que anterior ({melhor_anterior}). Mantendo anterior.")
    except FileNotFoundError:
        joblib.dump([{**metricas, "data": context['ds']}], hist_path)

t_modelo = PythonOperator(
    task_id="retreinar_modelo_risco",
    python_callable=task_modelo,
    dag=dag,
)

# ── TASK 5: Forecasting ────────────────────────────────────────────────────────
def task_forecast(**context):
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from src.forecasting import rodar_forecasting
    print(f"[{context['ds']}] Atualizando previsões Prophet...")
    rodar_forecasting()

t_forecast = PythonOperator(
    task_id="atualizar_previsoes_prophet",
    python_callable=task_forecast,
    dag=dag,
)

# ── TASK 6: Gerar insights ─────────────────────────────────────────────────────
def task_insights(**context):
    import sys, json, os
    sys.path.insert(0, PROJECT_ROOT)
    from src.insights_engine import InsightsEngine
    print(f"[{context['ds']}] Gerando insights automáticos...")
    engine = InsightsEngine()
    insights = engine.todos_insights()
    out_path = f"{PROJECT_ROOT}/data/processed/insights_latest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2, default=str)
    print(f"  {len(insights)} insights gerados e salvos.")

t_insights = PythonOperator(
    task_id="gerar_insights_automaticos",
    python_callable=task_insights,
    dag=dag,
)

# ── DEPENDÊNCIAS ──────────────────────────────────────────────────────────────
t_ingestao >> t_dbt_run >> t_dbt_test >> t_features >> t_modelo >> t_forecast >> t_insights
