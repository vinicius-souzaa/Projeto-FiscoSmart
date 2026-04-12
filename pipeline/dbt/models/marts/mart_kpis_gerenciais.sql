-- models/marts/mart_kpis_gerenciais.sql
-- KPIs consolidados para o dashboard gerencial

{{ config(materialized='table') }}

WITH arrecadacao AS (
    SELECT
        competencia,
        ano,
        mes,
        tributo,
        arrecadado,
        potencial,
        gap_total,
        gap_medio_pct
    FROM {{ ref('int_arrecadacao_mensal') }}
),
totais_mes AS (
    SELECT
        competencia,
        ano,
        mes,
        SUM(arrecadado)   AS arrecadacao_total,
        SUM(potencial)    AS potencial_total,
        SUM(gap_total)    AS gap_total,
        SUM(arrecadado) * 100.0 / NULLIF(SUM(potencial), 0) AS eficiencia_pct
    FROM arrecadacao
    GROUP BY competencia, ano, mes
),
com_variacao AS (
    SELECT
        t.*,
        LAG(arrecadacao_total, 1) OVER (ORDER BY competencia) AS arrecadacao_mes_anterior,
        LAG(arrecadacao_total, 12) OVER (ORDER BY competencia) AS arrecadacao_ano_anterior,
        (arrecadacao_total - LAG(arrecadacao_total,1)  OVER (ORDER BY competencia))
            * 100.0 / NULLIF(LAG(arrecadacao_total,1)  OVER (ORDER BY competencia),0) AS var_mom_pct,
        (arrecadacao_total - LAG(arrecadacao_total,12) OVER (ORDER BY competencia))
            * 100.0 / NULLIF(LAG(arrecadacao_total,12) OVER (ORDER BY competencia),0) AS var_yoy_pct
    FROM totais_mes t
)
SELECT
    competencia,
    ano,
    mes,
    ROUND(arrecadacao_total, 2)    AS arrecadacao_total,
    ROUND(potencial_total, 2)      AS potencial_total,
    ROUND(gap_total, 2)            AS gap_total,
    ROUND(eficiencia_pct, 2)       AS eficiencia_pct,
    ROUND(var_mom_pct, 2)          AS variacao_mes_anterior_pct,
    ROUND(var_yoy_pct, 2)          AS variacao_ano_anterior_pct
FROM com_variacao
ORDER BY competencia
