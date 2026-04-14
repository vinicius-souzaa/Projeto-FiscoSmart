"""
FiscoSmart — Batch Diário de Eventos de Pagamento
Gera eventos de pagamento D-1 e acumula em pagamentos_iss.csv.

Regras:
  - Executado todo dia às 04h Brasília pelo GitHub Actions
  - Simula eventos de pagamento do dia anterior (D-1)
  - Guarda sentinela .batch_corte para evitar duplicatas
  - Retorna dict de stats para logging no CI
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
import random, os, json

DATA_RAW = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
SENTINELA = os.path.join(DATA_RAW, '.batch_corte')
PAG_PATH  = os.path.join(DATA_RAW, 'pagamentos_iss.csv')

np.random.seed(int(date.today().strftime("%Y%m%d")))   # seed determinístico por dia
random.seed(int(date.today().strftime("%Y%m%d")))


# ─── Probabilidade de pagamento por risco latente e dias de atraso ───────────
_PROB_PAGAMENTO = {
    0: {0: 0.88, 1: 0.70, 2: 0.45, 3: 0.20},   # risco baixo
    1: {0: 0.70, 1: 0.50, 2: 0.25, 3: 0.08},   # risco médio
    2: {0: 0.45, 1: 0.20, 2: 0.06, 3: 0.02},   # risco alto
}


def _faixa_atraso(dias: int) -> int:
    if dias <= 0:  return 0
    if dias <= 15: return 1
    if dias <= 45: return 2
    return 3


def _sentinela_do_dia(dia: date) -> bool:
    """Retorna True se o batch deste dia já rodou (idempotência)."""
    if not os.path.exists(SENTINELA):
        return False
    with open(SENTINELA) as f:
        ultimo = f.read().strip()
    return ultimo == dia.isoformat()


def _gravar_sentinela(dia: date):
    os.makedirs(DATA_RAW, exist_ok=True)
    with open(SENTINELA, 'w') as f:
        f.write(dia.isoformat())


def rodar_batch_diario(forcar: bool = False) -> dict:
    """
    Parâmetros
    ----------
    forcar : bool
        Se True, ignora a sentinela e reprocessa mesmo que já tenha rodado hoje.

    Retorna
    -------
    dict com estatísticas do batch: pagamentos_gerados, contribuintes_afetados,
    valor_total_pago, data_processada, ja_rodou.
    """
    hoje = date.today()
    d_ontem = hoje - timedelta(days=1)

    if not forcar and _sentinela_do_dia(hoje):
        print(f"[batch_diario] Batch de {hoje} já executado — abortando (use forcar=True para reprocessar).")
        return {"ja_rodou": True, "data_processada": hoje.isoformat()}

    # ── Carregar dados base ───────────────────────────────────────────────────
    try:
        decl     = pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv")
        contribs = pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
    except FileNotFoundError as e:
        print(f"[batch_diario] ERRO: arquivo base ausente — {e}")
        return {"ja_rodou": False, "erro": str(e)}

    # ── Pagamentos existentes (para não duplicar) ─────────────────────────────
    if os.path.exists(PAG_PATH):
        pag_exist = pd.read_csv(PAG_PATH)
        chaves_existentes = set(
            zip(pag_exist['id_contribuinte'].astype(int),
                pag_exist['competencia'],
                pag_exist['data_pagamento'])
        )
    else:
        pag_exist = pd.DataFrame()
        chaves_existentes = set()

    # ── Determinar competências no intervalo de vencimento ───────────────────
    # Vencimento: dia 15 do mês seguinte à competência.
    # D-1 pode ter pagamentos para múltiplas competências (atraso, antecipação).
    competencias_todas = sorted(decl['competencia'].unique())
    competencias_alvo = []
    for comp in competencias_todas:
        ano, mes = int(comp[:4]), int(comp[5:7])
        mes_v = mes + 1
        ano_v = ano + (mes_v > 12)
        mes_v = mes_v % 12 or 12
        try:
            venc = date(ano_v, mes_v, 15)
        except ValueError:
            continue
        # Inclui competências com vencimento entre 0 e 90 dias atrás (janela real de pagamento)
        dias_atraso = (d_ontem - venc).days
        if -5 <= dias_atraso <= 90:
            competencias_alvo.append((comp, venc, dias_atraso))

    if not competencias_alvo:
        print(f"[batch_diario] Nenhuma competência com vencimento próximo de {d_ontem}.")
        _gravar_sentinela(hoje)
        return {"ja_rodou": False, "pagamentos_gerados": 0, "data_processada": d_ontem.isoformat()}

    # ── Gerar eventos de pagamento ────────────────────────────────────────────
    risco_map = contribs.set_index('id_contribuinte')['risco_latente'].to_dict()
    rows_novos = []

    for comp, venc, dias_atraso in competencias_alvo:
        faixa = _faixa_atraso(dias_atraso)
        decl_comp = decl[decl['competencia'] == comp].copy()

        for _, r in decl_comp.iterrows():
            cid = int(r['id_contribuinte'])
            chave = (cid, comp, d_ontem.isoformat())
            if chave in chaves_existentes:
                continue  # idempotência

            risco = risco_map.get(cid, 1)
            prob_pag = _PROB_PAGAMENTO[risco][faixa]

            # 30% de chance de o evento ser "pagamento do dia" mesmo se não venceu ontem
            if random.random() > prob_pag:
                continue

            valor_devido = float(r['iss_recolhido']) if r['iss_recolhido'] > 0 else float(r['iss_devido_estimado'])
            if valor_devido <= 0:
                continue

            # Pago em atraso ou em dia
            status = 'pago_atraso' if dias_atraso > 0 else 'pago'
            # Juros de mora: 1% a.m. + 0,033%/dia para atraso > 30 dias
            juros = 0.0
            if dias_atraso > 30:
                juros = valor_devido * 0.01 * (dias_atraso / 30) + valor_devido * 0.00033 * dias_atraso
            valor_pago = round(valor_devido + juros, 2)

            rows_novos.append({
                'id_contribuinte': cid,
                'competencia': comp,
                'data_vencimento': venc.isoformat(),
                'data_pagamento': d_ontem.isoformat(),
                'valor_devido': round(valor_devido, 2),
                'valor_pago': valor_pago,
                'juros_mora': round(juros, 2),
                'dias_atraso': max(0, dias_atraso),
                'status': status,
            })
            chaves_existentes.add(chave)

    # ── Persistir ─────────────────────────────────────────────────────────────
    n_gerados = len(rows_novos)
    if n_gerados > 0:
        df_novos = pd.DataFrame(rows_novos)
        if len(pag_exist) > 0:
            df_final = pd.concat([pag_exist, df_novos], ignore_index=True)
        else:
            df_final = df_novos
        df_final.to_csv(PAG_PATH, index=False)
        print(f"[batch_diario] {n_gerados} eventos de pagamento gerados para D-1 ({d_ontem}).")
    else:
        print(f"[batch_diario] Nenhum novo evento de pagamento em {d_ontem}.")

    _gravar_sentinela(hoje)

    contribuintes_unicos = len(set(r['id_contribuinte'] for r in rows_novos))
    valor_total = sum(r['valor_pago'] for r in rows_novos)

    stats = {
        "ja_rodou": False,
        "data_processada": d_ontem.isoformat(),
        "competencias_cobertas": [c for c, _, _ in competencias_alvo],
        "pagamentos_gerados": n_gerados,
        "contribuintes_afetados": contribuintes_unicos,
        "valor_total_pago": round(valor_total, 2),
    }
    print(f"[batch_diario] Stats: {json.dumps(stats, ensure_ascii=False)}")
    return stats


def bootstrap_pagamentos(n_dias: int = 90) -> dict:
    """
    Gera pagamentos retroativos para os últimos n_dias dias.
    Útil para popular pagamentos_iss.csv na primeira execução.
    """
    hoje = date.today()
    total_pag = 0
    for i in range(n_dias, 0, -1):
        dia = hoje - timedelta(days=i)
        # Simula o batch daquele dia sem checar sentinela
        _rodar_para_data(dia)
        total_pag += 1
    return {"dias_processados": n_dias, "data_inicio": (hoje - timedelta(days=n_dias)).isoformat()}


def _rodar_para_data(data_alvo: date):
    """Versão interna que processa para uma data específica (bootstrap)."""
    try:
        decl     = pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv")
        contribs = pd.read_csv(f"{DATA_RAW}/contribuintes.csv")
    except FileNotFoundError:
        return

    risco_map = contribs.set_index('id_contribuinte')['risco_latente'].to_dict()

    if os.path.exists(PAG_PATH):
        pag_exist = pd.read_csv(PAG_PATH)
        chaves_existentes = set(
            zip(pag_exist['id_contribuinte'].astype(int),
                pag_exist['competencia'],
                pag_exist['data_pagamento'])
        )
    else:
        pag_exist = pd.DataFrame()
        chaves_existentes = set()

    competencias_todas = sorted(decl['competencia'].unique())
    rows_novos = []

    for comp in competencias_todas:
        ano, mes = int(comp[:4]), int(comp[5:7])
        mes_v = mes + 1
        ano_v = ano + (mes_v > 12)
        mes_v = mes_v % 12 or 12
        try:
            venc = date(ano_v, mes_v, 15)
        except ValueError:
            continue
        dias_atraso = (data_alvo - venc).days
        if not (-5 <= dias_atraso <= 90):
            continue

        faixa = _faixa_atraso(dias_atraso)
        decl_comp = decl[decl['competencia'] == comp]

        for _, r in decl_comp.iterrows():
            cid = int(r['id_contribuinte'])
            chave = (cid, comp, data_alvo.isoformat())
            if chave in chaves_existentes:
                continue

            risco = risco_map.get(cid, 1)
            prob_pag = _PROB_PAGAMENTO[risco][faixa]
            if random.random() > prob_pag * 0.15:   # fator baixo para bootstrap realista
                continue

            valor_devido = float(r['iss_recolhido']) if r['iss_recolhido'] > 0 else float(r['iss_devido_estimado'])
            if valor_devido <= 0:
                continue

            status = 'pago_atraso' if dias_atraso > 0 else 'pago'
            juros = 0.0
            if dias_atraso > 30:
                juros = valor_devido * 0.01 * (dias_atraso / 30) + valor_devido * 0.00033 * dias_atraso

            rows_novos.append({
                'id_contribuinte': cid,
                'competencia': comp,
                'data_vencimento': venc.isoformat(),
                'data_pagamento': data_alvo.isoformat(),
                'valor_devido': round(valor_devido, 2),
                'valor_pago': round(valor_devido + juros, 2),
                'juros_mora': round(juros, 2),
                'dias_atraso': max(0, dias_atraso),
                'status': status,
            })
            chaves_existentes.add(chave)

    if rows_novos:
        df_novos = pd.DataFrame(rows_novos)
        if len(pag_exist) > 0:
            df_final = pd.concat([pag_exist, df_novos], ignore_index=True)
        else:
            df_final = df_novos
        df_final.to_csv(PAG_PATH, index=False)


if __name__ == "__main__":
    import sys
    if '--bootstrap' in sys.argv:
        stats = bootstrap_pagamentos(n_dias=90)
        print(f"Bootstrap concluído: {stats}")
    else:
        stats = rodar_batch_diario()
        print(f"Resultado: {stats}")
