# Pipeline de Engenharia de Dados — FiscoSmart

Esta pasta contém a infraestrutura completa de engenharia de dados do projeto.
É a "cozinha" do sistema — processa os dados brutos e entrega os resultados para o dashboard.

---

## O que é cada ferramenta e por que foi escolhida

### Apache Airflow
**O que é:** Um orquestrador de workflows — pensa nele como um "gerente de tarefas" que garante que cada etapa do pipeline roda na ordem certa, no horário certo, e que trata erros automaticamente.

**Por que usar:** Sem o Airflow, o pipeline seria um script Python que roda manualmente. O problema: se um passo falhar no meio, você não sabe onde parou, não tem histórico de execuções, e precisa rodar tudo do zero. O Airflow resolve isso — cada "task" tem estado (sucesso, falha, em execução) e pode ser reiniciada individualmente.

**Analogia:** é como um chef de cozinha que garante que os ingredientes chegam antes do cozinheiro, que o cozinheiro termine antes do garçom servir, e que se a geladeira travar, alguém receba um alerta.

**No projeto:** a DAG `dag_pipeline_mensal.py` roda todo dia 1 do mês às 06h e executa as 6 etapas em sequência. Acesse em `http://localhost:8080` após subir o Docker.

---

### dbt (data build tool)
**O que é:** Uma ferramenta que organiza as transformações SQL em camadas, com versionamento e testes automáticos de qualidade dos dados.

**Por que usar:** Sem o dbt, as transformações ficam num arquivo SQL gigante ou espalhadas em pandas. Com dbt, cada transformação é um arquivo `.sql` separado, versionado no Git, com testes que validam os dados antes de chegarem no dashboard.

**Analogia:** é como uma linha de montagem numa fábrica. A matéria-prima entra crua, passa por três estações de transformação, e sai como produto acabado pronto para o cliente usar.

**As três camadas:**

| Camada | Pasta | O que faz |
|--------|-------|-----------|
| Staging | `models/staging/` | Limpa e padroniza os dados brutos (padroniza CNPJ, converte datas, valida alíquotas) |
| Intermediate | `models/intermediate/` | Combina fontes diferentes (junta ISS, IPTU e ITBI numa tabela única) |
| Marts | `models/marts/` | Calcula os KPIs finais que o dashboard vai mostrar (variação mês a mês, eficiência, etc.) |

**Por que três camadas?** Se algo der errado, você sabe exatamente em qual camada o problema está. Se o teste de alíquota falhar no staging, a pipeline para ali — o erro não contamina as camadas seguintes.

---

### PostgreSQL
**O que é:** O banco de dados relacional que armazena os dados processados.

**Por que usar:** Os dados gerados pelo pipeline precisam ser armazenados em algum lugar estruturado. O PostgreSQL é o banco padrão em ambientes de produção de dados — suporta SQL completo, tem ótima performance, e se integra nativamente com dbt e Airflow.

**No projeto:** armazena os dados brutos (raw), os intermediários e os marts finais. O Airflow também usa o mesmo banco para guardar o histórico das execuções (tabelas de metadados separadas).

---

### Docker Compose
**O que é:** Uma ferramenta que sobe vários serviços ao mesmo tempo com um único comando, garantindo que todos se "enxergam" em rede.

**Por que usar:** O Airflow depende do PostgreSQL. O dbt depende do PostgreSQL. Para rodar tudo junto localmente sem conflito de versões ou configurações manuais, o Docker Compose cria um ambiente isolado e reproduzível.

**Analogia:** é como montar um escritório completo com todos os móveis, computadores e conexões de rede já configuradas — qualquer pessoa que clonar este repositório tem exatamente o mesmo ambiente em qualquer máquina.

---

## Como rodar localmente

**Pré-requisito:** ter o [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado.

```bash
# Entrar na pasta pipeline
cd pipeline

# Subir toda a stack (PostgreSQL + Airflow)
docker-compose up -d

# Verificar se está tudo rodando
docker-compose ps
```

Após alguns minutos:
- **Airflow:** http://localhost:8080 (usuário: `admin`, senha: `admin`)
- **PostgreSQL:** porta 5432 (usuário: `airflow`, senha: `airflow`)

Para parar:
```bash
docker-compose down
```

---

## Como o pipeline se conecta ao dashboard

```
pipeline/src/        →  gera os arquivos em  →  dashboard/data/
pipeline/dbt/        →  transforma os dados  →  dashboard/data/processed/
pipeline/airflow/    →  orquestra tudo isso  →  automaticamente todo dia 1
                                                        ↓
                                              dashboard/app/  (Streamlit Cloud)
                                              lê os arquivos e exibe os gráficos
```

Os dois são independentes: o pipeline roda localmente (ou no GitHub Actions como substituto do Airflow na nuvem), e o dashboard lê os resultados. Você pode rodar só o dashboard sem o Docker — ele usa o `setup.py` que reproduz o pipeline em Python puro.

---

## Estrutura de arquivos

```
pipeline/
├── src/                        # Scripts Python do pipeline
│   ├── generate_data.py        # Simula sistema tributário municipal
│   ├── feature_engineering.py  # Calcula 13 indicadores de risco por contribuinte
│   ├── model_risk.py           # Treina o modelo XGBoost e gera scores SHAP
│   ├── forecasting.py          # Previsão de arrecadação com Prophet
│   └── insights_engine.py      # Detecta anomalias e gera alertas automáticos
│
├── dbt/                        # Transformações SQL organizadas em camadas
│   ├── dbt_project.yml         # Configuração do projeto dbt
│   ├── profiles.yml            # Conexão com o PostgreSQL
│   └── models/
│       ├── staging/            # Camada 1: limpeza e padronização
│       ├── intermediate/       # Camada 2: consolidação de fontes
│       └── marts/              # Camada 3: KPIs prontos para consumo
│
├── airflow/
│   └── dags/
│       └── dag_pipeline_mensal.py  # Orquestração mensal automatizada
│
└── docker-compose.yml          # Sobe PostgreSQL + Airflow com um comando
```
