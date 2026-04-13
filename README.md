# FiscoSmart — Inteligência Tributária Municipal

Sistema end-to-end de análise fiscal para municípios brasileiros: detecta sonegação, prevê arrecadação e prioriza fiscalizações com machine learning — alimentado por um pipeline de dados incremental com atualização diária automática.

🔗 **[Abrir o dashboard ao vivo](https://fiscosmart.streamlit.app)**
![CI](https://github.com/vinicius-souzaa/Projeto-FiscoSmart/actions/workflows/ci.yml/badge.svg)
![Batch Diário](https://github.com/vinicius-souzaa/Projeto-FiscoSmart/actions/workflows/batch_diario.yml/badge.svg)

---

## O problema que este projeto resolve

Um município de médio porte tem entre 5.000 e 15.000 contribuintes de ISS e, em geral, menos de 10 auditores-fiscais disponíveis por mês. Para quem fiscalizar primeiro? Sem sistema, a resposta é intuição. Com FiscoSmart, é matemática.

O sistema combina três fontes de informação: o histórico de declarações de cada contribuinte, o benchmark médio do seu setor (CNAE), e o histórico de autuações anteriores. Um modelo XGBoost aprende quais padrões precedem irregularidades e gera um score de risco de 0 a 100 para cada contribuinte. A lista de priorização multiplica esse score pelo valor potencial de recuperação e divide pelo custo estimado da fiscalização — o resultado é um ranking por retorno esperado. O auditor vai direto para quem vai render mais.

---

## Pipeline de dados

O que diferencia este projeto de um dashboard estático é o pipeline incremental. Os dados não são regenerados do zero — eles crescem.

```
generate_data.py          →   histórico base (36 meses, roda uma vez)
        ↓
data/raw/*.csv            →   arquivos estáticos commitados no repositório
        ↓
batch_diario.py           →   append diário de eventos de pagamento (D-1)
        ↓
pagamentos_iss.csv        →   fato de pagamento com granularidade diária
        ↓
feature_engineering.py    →   13 indicadores de risco por contribuinte
        ↓
model_risk.py             →   XGBoost retreinado com dados acumulados
        ↓
forecasting.py            →   Prophet atualizado com série crescente
        ↓
insights_engine.py        →   alertas automáticos recalculados
        ↓
GitHub Actions commit     →   Streamlit Cloud faz redeploy automaticamente
```

### Separação entre obrigação e pagamento

O ISS tem vencimento no dia 15 do mês seguinte à competência. O pagamento pode cair em qualquer dia. O sistema modela isso com duas tabelas separadas:

- `declaracoes_iss.csv` — fato de obrigação (mensal, por competência)
- `pagamentos_iss.csv` — fato de pagamento (diário, evento por evento)

A cada execução do batch, o sistema calcula a probabilidade de pagamento de cada contribuinte em aberto naquele dia — baseada na proximidade do vencimento e no perfil de risco — e registra os eventos. Contribuintes vencidos há mais de 90 dias sem pagamento são inscritos automaticamente em dívida ativa.

---

## Automação via GitHub Actions

Três workflows em `.github/workflows/`:

| Workflow | Gatilho | O que faz |
|---|---|---|
| `ci.yml` | Cada push na main | Valida dados, roda pipeline analítica, testa qualidade do modelo |
| `batch_diario.yml` | Todo dia às 04h Brasília | Processa eventos de pagamento de D-1, retreina modelo, atualiza insights |
| `atualizacao_mensal.yml` | Dia 1 de cada mês | Retreino completo com série acumulada, forecasting, commit |

O batch diário é idempotente — rodar duas vezes no mesmo dia não duplica dados.

---

## O que o sistema cobre

| Tributo | O que é | Base legal |
|---|---|---|
| ISS | Imposto sobre serviços prestados no município | LC 116/2003 |
| IPTU | Imposto sobre imóveis urbanos | CTN art. 32 |
| ITBI | Imposto sobre venda de imóveis | CTN art. 35 |
| Taxa de Alvará | Licença de funcionamento | CTN art. 77 |
| Taxa de Lixo | Coleta de resíduos sólidos | CTN art. 77 |
| COSIP | Contribuição para iluminação pública | CF art. 149-A |
| Contribuição de Melhoria | Obras que valorizam imóveis | CTN art. 81 |
| FPM / ICMS / IPVA / ITR | Transferências constitucionais | CF arts. 158-159 |
| Dívida Ativa | Tributos vencidos em cobrança | Lei 6.830/1980 |

---

## As 4 camadas de análise

**1. Descritiva — o que aconteceu?**
KPIs de todos os tributos, evolução mensal, comparação com metas, inadimplência por bairro, composição da receita própria vs. transferências.

**2. Diagnóstica — por que aconteceu?**
Gap de ISS por setor (CNAE), heatmap de omissões, subavaliação de base de cálculo no ITBI, isenções irregulares de IPTU, aging da dívida ativa.

**3. Preditiva — o que vai acontecer?**
Score de risco por contribuinte (XGBoost + SHAP) e previsão de arrecadação para os próximos 6 meses com intervalo de confiança 95% (Prophet).

**4. Prescritiva — o que fazer?**
Ranking por retorno esperado com simulador interativo: "com 5 auditores fazendo 4 fiscalizações cada, qual o potencial de recuperação fiscalizando os top 20?" Exporta lista de trabalho em CSV com os 3 principais fatores de risco de cada contribuinte.

---

## Como o modelo funciona

O XGBoost analisa 13 indicadores comportamentais por contribuinte:

gap médio declarado vs. benchmark do setor · taxa de omissão de declarações · variabilidade da receita declarada · tendência de queda (slope) · razão último mês vs. média histórica · taxa de retificação · meses sem fiscalização · histórico de ações fiscais · porte · regime tributário · gap vs. benchmark CNAE · meses com dados · instabilidade do gap

O modelo é treinado com o histórico de autuações como variável alvo. A cada batch semanal ele é retreinado do zero com toda a série acumulada.

Resultado atual: **AUC-ROC 0,97** — em 97% das comparações, o modelo coloca o contribuinte irregular com score maior que o regular. Recall de 0,84 — captura 84% de todos os irregulares da base.

Além do score, o sistema usa SHAP para explicar cada decisão individualmente:

> "Score 87 porque: declara 58% abaixo do benchmark do setor (+0,42), sem fiscalização há 38 meses (+0,31), omitiu declarações em 4 dos últimos 12 meses (+0,18)."

Isso transforma o modelo de uma caixa preta em evidência auditável — o fiscal consegue justificar a seleção do contribuinte com base em fatores objetivos.

---

## Estrutura do repositório

```
Projeto-FiscoSmart/
├── app/
│   ├── main.py                     # Dashboard principal com auto-setup
│   └── pages/
│       ├── 1_Visao_Geral.py        # KPIs consolidados
│       ├── 2_Diagnostico_ISS.py    # Gap, omissões, radar por contribuinte
│       ├── 3_Diagnostico_IPTU.py   # Inadimplência, Pareto, isenções
│       ├── 4_Diagnostico_ITBI.py   # Subavaliação de base de cálculo
│       ├── 5_Taxas_COSIP.py        # Alvará, lixo, COSIP, contrib. melhoria
│       ├── 6_Divida_Ativa.py       # Aging, Pareto, simulador REFIS
│       ├── 7_Score_Risco.py        # XGBoost + SHAP global e individual
│       ├── 8_Previsao_Arrecadacao.py  # Prophet + gap de meta
│       └── 9_Priorizacao_Fiscal.py # Ranking ROI + exportação CSV
│
├── src/
│   ├── generate_data.py            # Gerador do histórico base (roda uma vez)
│   ├── batch_diario.py             # Append diário de eventos de pagamento
│   ├── feature_engineering.py      # 13 features de risco por contribuinte
│   ├── model_risk.py               # XGBoost + SHAP + bins calibrados
│   ├── forecasting.py              # Prophet por tributo (fallback linear)
│   └── insights_engine.py          # Alertas automáticos + Isolation Forest
│
├── data/
│   ├── raw/                        # CSVs históricos (estáticos, commitados)
│   │   ├── contribuintes.csv       # 2.000 contribuintes ISS
│   │   ├── declaracoes_iss.csv     # Obrigações mensais — cresce com o batch
│   │   ├── pagamentos_iss.csv      # Eventos de pagamento diários (append)
│   │   ├── imoveis.csv             # 15.000 imóveis
│   │   ├── itbi.csv                # Transações imobiliárias
│   │   ├── divida_ativa.csv        # Estoque de DA — cresce com o batch
│   │   ├── cosip_mensal.csv        # COSIP pré-agregado (144 linhas)
│   │   └── ...                     # demais tabelas raw
│   └── processed/                  # Artefatos analíticos (gerados pelo setup)
│       ├── features_risco.csv
│       ├── scores_risco.csv
│       ├── shap_values.csv
│       ├── forecast_arrecadacao.csv
│       └── insights_latest.json
│
├── models/
│   ├── modelo_risco.pkl            # XGBoost treinado
│   ├── shap_explainer.pkl          # TreeExplainer
│   └── metricas_modelo.pkl         # AUC, Recall, F1, bins calibrados
│
├── pipeline/                       # Stack local de engenharia de dados
│   ├── airflow/dags/               # DAG Airflow (orquestração local)
│   ├── dbt/                        # Transformações SQL em 3 camadas
│   ├── docker-compose.yml          # PostgreSQL + Airflow com um comando
│   └── README.md                   # Documentação da stack
│
├── .github/workflows/
│   ├── ci.yml                      # Valida pipeline a cada push
│   ├── batch_diario.yml            # Append diário — 04h Brasília
│   └── atualizacao_mensal.yml      # Retreino completo — dia 1
│
├── setup.py                        # Roda pipeline analítica localmente
└── requirements.txt
```

---

## Como rodar localmente

```bash
git clone https://github.com/vinicius-souzaa/Projeto-FiscoSmart.git
cd Projeto-FiscoSmart
pip install -r requirements.txt

# Os dados históricos já estão no repositório.
# Só precisa rodar a pipeline analítica:
python setup.py

# Abrir o dashboard:
streamlit run app/main.py
```

Para rodar o batch diário manualmente (simular D-1):

```bash
python src/batch_diario.py
```

Para resetar o histórico base do zero (opcional):

```bash
python src/generate_data.py
python setup.py
```

**Stack local de engenharia de dados (Airflow + dbt + PostgreSQL):**

```bash
cd pipeline
docker-compose up -d
# Airflow: http://localhost:8080 (admin/admin)
```

Ver detalhes em [`pipeline/README.md`](pipeline/README.md).

---

## Stack técnica

| Categoria | Ferramenta | Decisão |
|---|---|---|
| Ingestão | pandas, numpy, faker | Simula sistema tributário com benchmarks Simples Nacional |
| Pipeline incremental | batch_diario.py | Append de eventos diários com sentinel de data-corte |
| Transformações | dbt | SQL em 3 camadas (staging → intermediate → marts) |
| Orquestração | Apache Airflow | DAG com retry, dependências e histórico de execuções |
| ML | XGBoost + SHAP | Melhor performance em dados tabulares + explicabilidade auditável |
| Séries temporais | Prophet | Sazonalidade anual automática com fallback linear |
| Anomalias | Isolation Forest | Detecta contribuintes atípicos fora das regras tradicionais |
| Banco | PostgreSQL | Padrão para data warehousing local |
| Infraestrutura | Docker Compose | Ambiente reproduzível com um comando |
| Dashboard | Streamlit | Python puro, 9 páginas, auto-setup na primeira abertura |
| CI/CD | GitHub Actions | 3 workflows: CI por push, batch diário, retreino mensal |
| Deploy | Streamlit Cloud | Redeploy automático após cada commit do batch |

---

## Dados

Os dados são sintéticos, gerados a partir de benchmarks reais do Simples Nacional, SICONFI e Tesouro Nacional. O município simulado é São Vicente — SP (355 mil habitantes), com 2.000 contribuintes ISS e 15.000 imóveis.

O histórico cobre 36 meses (jan/2022 a dez/2024). A partir de jan/2025 o batch diário passa a acumular eventos reais de pagamento — a série cresce a cada execução.

---

## Referências legais

CTN (Lei 5.172/1966) · LC 116/2003 · LC 157/2016 · LC 214/2025 · EC 132/2023 · CF/88 arts. 145, 149-A, 156, 158-159 · Lei 6.830/1980 · Lei 13.709/2018 (LGPD) · Lei 4.729/1965

---

Desenvolvido por Vinicius — portfólio Data Analyst → Data Engineer · 2026
