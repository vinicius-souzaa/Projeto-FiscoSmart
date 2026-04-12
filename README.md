# FiscoSmart — Inteligência Tributária Municipal

Dashboard de análise, diagnóstico, previsão e priorização fiscal para municípios brasileiros.

🔗 **[Demo ao vivo no Streamlit Cloud](https://fiscosmart.streamlit.app)**

---

## Tributos cobertos

| Tributo | Tipo | Base Legal |
|--------|------|-----------|
| ISS | Imposto próprio | LC 116/2003 + LC 214/2025 |
| IPTU | Imposto próprio | CTN art. 32 |
| ITBI | Imposto próprio | CTN art. 35 |
| Taxa de Alvará | Taxa | CTN art. 77 |
| Taxa de Coleta de Lixo | Taxa | CTN art. 77 |
| COSIP | Contribuição | CF art. 149-A |
| Contribuição de Melhoria | Contribuição | CTN art. 81 |
| FPM, ICMS, IPVA, ITR | Transferências | CF art. 158/159 |

---

## Arquitetura

```
fiscosmart/
├── src/
│   ├── generate_data.py        # Dados sintéticos — todos os tributos
│   ├── feature_engineering.py  # 13 features de risco por contribuinte
│   ├── model_risk.py           # XGBoost + SHAP (AUC-ROC 0.96)
│   ├── forecasting.py          # Prophet por tributo — 6 meses
│   └── insights_engine.py      # Regras + Isolation Forest + linguagem natural
├── app/
│   ├── main.py                 # Entry point com auto-setup
│   └── pages/
│       ├── 1_Visao_Geral.py
│       ├── 2_Diagnostico_ISS.py
│       ├── 3_Diagnostico_IPTU.py
│       ├── 4_Diagnostico_ITBI.py
│       ├── 5_Taxas_COSIP.py
│       ├── 6_Divida_Ativa.py
│       ├── 7_Score_Risco.py
│       ├── 8_Previsao_Arrecadacao.py
│       └── 9_Priorizacao_Fiscal.py
├── data/
│   ├── raw/                    # Gerado automaticamente
│   └── processed/              # Features, scores, forecasts, insights
├── models/                     # Artefatos ML serializados
├── .github/workflows/
│   ├── ci.yml                  # Valida pipeline a cada push
│   └── atualizacao_mensal.yml  # Regenera dados todo dia 1 do mês
├── setup.py                    # Roda pipeline completa localmente
└── requirements.txt
```

---

## Pipeline

```
setup.py (local) ou GitHub Actions (automático)
    │
    ├── generate_data.py    → data/raw/        (ISS, IPTU, ITBI, Taxas, DA...)
    ├── feature_engineering → data/processed/  (13 features por contribuinte)
    ├── model_risk.py       → models/ + scores (XGBoost + SHAP)
    ├── forecasting.py      → data/processed/  (Prophet × 4 tributos)
    └── insights_engine.py  → data/processed/  (alertas automáticos)
                                    │
                              Streamlit Cloud
                              9 páginas do dashboard
```

**Atualização automática:** GitHub Actions roda toda pipeline no dia 1 de cada mês,
faz commit dos dados novos e o Streamlit Cloud redeployar automaticamente.

---

## Camadas analíticas

| Camada | Páginas | O que entrega |
|--------|---------|---------------|
| Descritiva | 1–6 | KPIs, evolução, inadimplência, aging |
| Diagnóstica | 2–6 | Gap por setor, subavaliação, Pareto, radar |
| Preditiva | 7–8 | Score XGBoost, SHAP individual, Prophet |
| Prescritiva | 9 | Ranking retorno esperado, simulador, CSV |

---

## Como rodar localmente

```bash
# 1. Clonar
git clone https://github.com/SEU_USUARIO/fiscosmart.git
cd fiscosmart

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Gerar dados e modelos (~2 min)
python setup.py

# 4. Iniciar dashboard
streamlit run app/main.py
```

## Deploy no Streamlit Cloud

1. Fork ou push para o GitHub
2. Acesse [share.streamlit.io](https://share.streamlit.io)
3. **Main file path:** `app/main.py`
4. Deploy — o setup roda automaticamente na primeira abertura

---

## Stack

- **Analytics:** pandas, numpy, scikit-learn
- **ML:** xgboost, shap
- **Séries temporais:** prophet
- **Visualização:** plotly
- **Dashboard:** streamlit
- **CI/CD:** GitHub Actions
- **Deploy:** Streamlit Cloud

---

## Referências legais

- CTN — Lei 5.172/1966
- CF/88 — arts. 145, 149-A, 156, 158, 159
- LC 116/2003 — ISS · LC 157/2016 — alíquota mínima ISS
- LC 214/2025 — ISS na transição para IBS
- EC 132/2023 — Reforma Tributária
- Lei 6.830/1980 — Execução Fiscal
- Lei 13.709/2018 — LGPD
- Lei 4.729/1965 — Crimes de sonegação fiscal

---

Desenvolvido como projeto de portfólio — Data Analytics → Data Engineering.
