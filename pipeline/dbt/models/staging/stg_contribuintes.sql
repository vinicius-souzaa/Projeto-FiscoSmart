-- models/staging/stg_contribuintes.sql
-- Padroniza e limpa o cadastro de contribuintes ISS

{{ config(materialized='view') }}

SELECT
    id_contribuinte,
    UPPER(TRIM(cnpj))                           AS cnpj,
    UPPER(TRIM(razao_social))                   AS razao_social,
    cnae,
    UPPER(TRIM(desc_cnae))                      AS desc_cnae,
    porte,
    regime_tributario,
    bairro,
    CAST(data_abertura AS DATE)                 AS data_abertura,
    CAST(ativo AS BOOLEAN)                      AS ativo,
    risco_latente,
    -- Tempo de atividade em meses
    CAST(
        (JULIANDAY('now') - JULIANDAY(data_abertura)) / 30.44
    AS INTEGER)                                 AS meses_ativo
FROM {{ source('raw', 'contribuintes') }}
WHERE id_contribuinte IS NOT NULL
  AND cnpj IS NOT NULL
