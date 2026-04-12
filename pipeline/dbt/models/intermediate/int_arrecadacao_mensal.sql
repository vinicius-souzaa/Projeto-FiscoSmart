-- models/intermediate/int_arrecadacao_mensal.sql
-- Consolida arrecadação mensal de todos os tributos

{{ config(materialized='table') }}

WITH iss AS (
    SELECT
        competencia,
        ano,
        mes,
        'ISS' AS tributo,
        SUM(iss_recolhido)           AS arrecadado,
        SUM(iss_devido_estimado)     AS potencial,
        SUM(gap_absoluto)            AS gap_total,
        COUNT(*)                     AS n_registros,
        SUM(omitiu_declaracao)       AS n_omissoes,
        AVG(gap_percentual)          AS gap_medio_pct
    FROM raw_declaracoes_iss
    GROUP BY competencia, ano, mes
),
iptu AS (
    SELECT
        CAST(ano_referencia AS TEXT) || '-' ||
        CASE WHEN parcela <= 12 THEN
            CASE WHEN parcela < 10 THEN '0' || CAST(parcela AS TEXT)
            ELSE CAST(parcela AS TEXT) END
        END                          AS competencia,
        ano_referencia               AS ano,
        parcela                      AS mes,
        'IPTU'                       AS tributo,
        SUM(CASE WHEN pago=1 THEN valor ELSE 0 END)  AS arrecadado,
        SUM(valor)                                    AS potencial,
        SUM(CASE WHEN pago=0 THEN valor ELSE 0 END)  AS gap_total,
        COUNT(*)                                      AS n_registros,
        0                                             AS n_omissoes,
        AVG(CASE WHEN pago=0 THEN 100.0 ELSE 0 END)  AS gap_medio_pct
    FROM raw_iptu_parcelas
    GROUP BY ano_referencia, parcela
),
itbi AS (
    SELECT
        mes_competencia              AS competencia,
        ano,
        mes,
        'ITBI'                       AS tributo,
        SUM(itbi_recolhido)          AS arrecadado,
        SUM(itbi_devido)             AS potencial,
        SUM(gap_itbi)                AS gap_total,
        COUNT(*)                     AS n_registros,
        0                            AS n_omissoes,
        AVG(CASE WHEN subavaliacao_detectada=1 THEN 100.0 ELSE 0 END) AS gap_medio_pct
    FROM raw_itbi
    GROUP BY mes_competencia, ano, mes
)

SELECT * FROM iss
UNION ALL
SELECT * FROM iptu
UNION ALL
SELECT * FROM itbi
