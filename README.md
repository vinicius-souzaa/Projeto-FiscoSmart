# FiscoSmart — Inteligência Tributária Municipal

Sistema completo de análise fiscal para municípios brasileiros: detecta sonegação, prevê arrecadação e prioriza fiscalizações usando machine learning.

🔗 **[Abrir o dashboard ao vivo](https://fiscosmart.streamlit.app)**
![CI](https://github.com/vinicius-souzaa/Projeto-FiscoSmart/actions/workflows/ci.yml/badge.svg)

---

## O problema que este projeto resolve

Imagine que você é o Secretário de Finanças de um município com 8.000 contribuintes de ISS e apenas 6 auditores-fiscais disponíveis. Para quem você manda fiscalizar primeiro? Sem sistema, a resposta é baseada em intuição ou sorte.

Com o FiscoSmart, a resposta é objetiva: um modelo de machine learning analisa o histórico de declarações de cada contribuinte, compara com a média do setor, e gera uma lista ordenada por probabilidade de irregularidade multiplicada pelo valor potencial de recuperação. O auditor vai direto para quem vai render mais.

---

## O que o sistema cobre

| Tributo | O que é | Base legal |
|---|---|---|
| ISS | Imposto sobre serviços prestados no município | LC 116/2003 |
| IPTU | Imposto sobre imóveis urbanos | CTN art. 32 |
| ITBI | Imposto sobre venda de imóveis | CTN art. 35 |
| Taxa de Alvará | Taxa para funcionar legalmente | CTN art. 77 |
| Taxa de Lixo | Taxa de coleta de resíduos | CTN art. 77 |
| COSIP | Contribuição para iluminação pública | CF art. 149-A |
| Contribuição de Melhoria | Cobrança por obras que valorizam imóveis | CTN art. 81 |
| FPM / ICMS / IPVA / ITR | Transferências da União e dos Estados | CF arts. 158-159 |
| Dívida Ativa | Tributos vencidos em cobrança judicial | Lei 6.830/1980 |

---

## As 4 camadas de análise

**1. Descritiva — O que aconteceu?**
KPIs de todos os tributos, evolução mensal, comparação com metas, inadimplência por bairro. Painel para o Secretário de Finanças.

**2. Diagnóstica — Por que aconteceu?**
Identifica onde está o problema: qual setor está subnotificando, quais imóveis têm isenção suspeita, quais escrituras declararam valor abaixo do venal.

**3. Preditiva — O que vai acontecer?**
Score de risco por contribuinte (XGBoost + SHAP) e previsão de arrecadação para os próximos 6 meses (Prophet).

**4. Prescritiva — O que fazer?**
Ranking de priorização com simulador: "se eu fiscalizar os top 20, qual o potencial de recuperação?" Exporta lista de trabalho em CSV.

---

## Como o modelo de risco funciona

O modelo analisa 13 indicadores de comportamento de cada contribuinte e aprende, a partir do histórico de autuações, quais padrões precedem irregularidades.

Resultado validado: **AUC-ROC 0,96** — em 96% das comparações, o modelo coloca o contribuinte irregular com score maior que o regular.

Além do score, o sistema usa **SHAP** para explicar cada decisão em linguagem do auditor:

> "Score 87 porque: declara 58% abaixo do benchmark (+0,42), sem fiscalização há 38 meses (+0,31), omitiu declarações em 4 dos últimos 12 meses (+0,18)."

---

## Estrutura do repositório

```
fiscosmart/
├── app/                        # Dashboard Streamlit (9 páginas)
├── src/                        # Pipeline analítica em Python
├── data/                       # Dados gerados automaticamente
├── models/                     # Artefatos ML (XGBoost + SHAP + Prophet)
├── pipeline/                   # Engenharia de dados (roda local via Docker)
│   ├── src/                    # Mesmos scripts src/ adaptados para o pipeline
│   ├── dbt/                    # Transformações SQL em 3 camadas
│   ├── airflow/dags/           # Orquestração mensal automatizada
│   ├── docker-compose.yml      # Sobe PostgreSQL + Airflow
│   └── README.md               # Explicação detalhada de cada ferramenta
├── .github/workflows/
│   ├── ci.yml                  # Valida pipeline a cada push
│   └── atualizacao_mensal.yml  # Roda pipeline todo dia 1 do mês
├── setup.py                    # Roda pipeline completa localmente
└── requirements.txt
```

---

## Como rodar

**Só o dashboard:**
```bash
git clone https://github.com/vinicius-souzaa/Projeto-FiscoSmart.git
cd Projeto-FiscoSmart
pip install -r requirements.txt
python setup.py
streamlit run app/main.py
```

**Pipeline completa com Docker (Airflow + dbt + PostgreSQL):**
```bash
cd pipeline
docker-compose up -d
# Acesse: http://localhost:8080 (admin/admin)
```

Ver detalhes em [`pipeline/README.md`](pipeline/README.md).

---

## Atualização automática

O GitHub Actions roda toda a pipeline no dia 1 de cada mês, commita os dados atualizados, e o Streamlit Cloud redeployar automaticamente. Nenhuma ação manual necessária.

---

## Stack técnica

| Categoria | Ferramenta | Por que |
|---|---|---|
| Dados | pandas, numpy, faker | Simula sistema tributário com benchmarks reais |
| Transformações | dbt | SQL organizado em camadas testáveis |
| Orquestração | Apache Airflow | Retry automático, histórico de execuções, dependências entre tasks |
| ML | XGBoost + SHAP | Melhor performance em dados tabulares + explicabilidade |
| Séries temporais | Prophet | Sazonalidade automática sem tuning manual |
| Banco | PostgreSQL | Padrão para data warehousing |
| Infraestrutura | Docker Compose | Ambiente reproduzível com um comando |
| Dashboard | Streamlit | Python puro, sem separar frontend e backend |
| CI/CD | GitHub Actions | Validação e atualização automática |
| Deploy | Streamlit Cloud | Hospedagem gratuita para projetos públicos |

---

## Referências legais

CTN (Lei 5.172/1966) · LC 116/2003 · LC 157/2016 · LC 214/2025 · EC 132/2023 · CF/88 arts. 145, 149-A, 156, 158-159 · Lei 6.830/1980 · Lei 13.709/2018 (LGPD) · Lei 4.729/1965

---

Desenvolvido por Vinicius — portfólio Data Analyst → Data Engineer · 2026
