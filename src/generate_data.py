"""
FiscoSmart — Gerador de Dados Sintéticos v2
Cobre: ISS, IPTU, ITBI, Taxas, COSIP, Contribuição de Melhoria, Dívida Ativa

FIXES v2:
  - COSIP: salva cosip_mensal.csv pré-agregado (144 linhas) — dashboard não carrega 648k
  - IPTU parcelas: vencimentos distribuídos nos 36 meses reais do período (não só 2024)
  - gerar_divida_ativa: ignora imóveis com iptu_lancado=0 (isentos)
"""
import pandas as pd
import numpy as np
from faker import Faker
from datetime import date, timedelta
import random, os

fake = Faker('pt_BR')
np.random.seed(42)
random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
os.makedirs(OUTPUT_DIR, exist_ok=True)

N_CONTRIBUINTES_ISS = 2_000
N_IMOVEIS = 15_000
MESES = 36
DATA_INICIO = date(2022, 1, 1)

CNAES = {
    "6201-5": {"desc": "Desenvolvimento de software",      "bench": {"MEI":4500,  "ME":28000, "EPP":95000,  "MD":380000, "GR":1200000}},
    "6202-3": {"desc": "Desenvolvimento de sistemas",       "bench": {"MEI":3800,  "ME":22000, "EPP":80000,  "MD":320000, "GR":980000}},
    "7490-1": {"desc": "Consultoria empresarial",           "bench": {"MEI":4200,  "ME":25000, "EPP":85000,  "MD":290000, "GR":750000}},
    "8599-6": {"desc": "Treinamento e capacitação",         "bench": {"MEI":3500,  "ME":18000, "EPP":55000,  "MD":180000, "GR":450000}},
    "5611-2": {"desc": "Restaurantes e similares",          "bench": {"MEI":6500,  "ME":35000, "EPP":120000, "MD":420000, "GR":1500000}},
    "5620-1": {"desc": "Serviços de alimentação",           "bench": {"MEI":5800,  "ME":30000, "EPP":98000,  "MD":350000, "GR":1100000}},
    "4120-4": {"desc": "Construção de edifícios",           "bench": {"MEI":8000,  "ME":55000, "EPP":220000, "MD":800000, "GR":3500000}},
    "4330-4": {"desc": "Acabamentos em construção",         "bench": {"MEI":5500,  "ME":38000, "EPP":130000, "MD":480000, "GR":1800000}},
    "8630-5": {"desc": "Atividades de atenção à saúde",     "bench": {"MEI":6000,  "ME":45000, "EPP":180000, "MD":650000, "GR":2200000}},
    "8650-0": {"desc": "Atividades de saúde humana",        "bench": {"MEI":5500,  "ME":40000, "EPP":150000, "MD":520000, "GR":1800000}},
    "6911-7": {"desc": "Atividades jurídicas",              "bench": {"MEI":5000,  "ME":32000, "EPP":110000, "MD":400000, "GR":1200000}},
    "6920-6": {"desc": "Atividades contábeis",              "bench": {"MEI":4500,  "ME":28000, "EPP":90000,  "MD":310000, "GR":900000}},
    "7711-0": {"desc": "Locação de automóveis",             "bench": {"MEI":7000,  "ME":50000, "EPP":200000, "MD":750000, "GR":2800000}},
    "9602-5": {"desc": "Cabeleireiros e similares",         "bench": {"MEI":3200,  "ME":15000, "EPP":45000,  "MD":150000, "GR":400000}},
    "8511-2": {"desc": "Educação infantil",                 "bench": {"MEI":4000,  "ME":22000, "EPP":75000,  "MD":260000, "GR":750000}},
    "8512-1": {"desc": "Ensino fundamental",                "bench": {"MEI":4500,  "ME":28000, "EPP":95000,  "MD":330000, "GR":950000}},
    "4771-7": {"desc": "Comércio farmacêutico",             "bench": {"MEI":8000,  "ME":60000, "EPP":250000, "MD":950000, "GR":3800000}},
    "5310-5": {"desc": "Atividades dos correios",           "bench": {"MEI":3000,  "ME":18000, "EPP":60000,  "MD":200000, "GR":600000}},
    "9311-5": {"desc": "Academias e fitness",               "bench": {"MEI":4500,  "ME":28000, "EPP":95000,  "MD":340000, "GR":1000000}},
    "4921-3": {"desc": "Transporte rodoviário coletivo",    "bench": {"MEI":7500,  "ME":55000, "EPP":220000, "MD":800000, "GR":3000000}},
}

PORTES = ["MEI", "ME", "EPP", "MD", "GR"]
PORTE_PESO = [0.35, 0.30, 0.20, 0.10, 0.05]
REGIME_POR_PORTE = {
    "MEI": ["MEI"],
    "ME":  ["Simples Nacional", "Lucro Presumido"],
    "EPP": ["Simples Nacional", "Lucro Presumido"],
    "MD":  ["Lucro Presumido", "Lucro Real"],
    "GR":  ["Lucro Real"],
}
BAIRROS = [
    "Centro", "Vila Margarida", "Japuí", "Catiapoa", "Cidade Nautica",
    "Vila São Jorge", "Vila Bocaina", "Parque Bitaru", "Esplanada dos Barreiros",
    "Alto da Boa Vista", "Vila Nova", "Jardim Rio Branco", "Glória",
    "Ilha Porchat", "Porto Grande",
]
ISS_ALIQUOTAS = {
    "6201-5": 0.03, "6202-3": 0.03, "7490-1": 0.03, "8599-6": 0.02,
    "5611-2": 0.03, "5620-1": 0.03, "4120-4": 0.02, "4330-4": 0.02,
    "8630-5": 0.02, "8650-0": 0.02, "6911-7": 0.05, "6920-6": 0.03,
    "7711-0": 0.03, "9602-5": 0.02, "8511-2": 0.02, "8512-1": 0.02,
    "4771-7": 0.03, "5310-5": 0.02, "9311-5": 0.03, "4921-3": 0.02,
}


def _cnpj():
    n = [random.randint(0, 9) for _ in range(12)]
    return f"{''.join(map(str,n[:2]))}.{''.join(map(str,n[2:5]))}.{''.join(map(str,n[5:8]))}/{''.join(map(str,n[8:12]))}-00"


def meses_range(inicio: date, n: int):
    meses, d = [], inicio
    for _ in range(n):
        meses.append(d)
        m = d.month + 1
        y = d.year + (m > 12)
        d = date(y, m % 12 or 12, 1)
    return meses


def sazonalidade_iss(mes: int, cnae: str) -> float:
    base = {
        "construção": [0.7, 0.75, 0.9, 1.0, 1.1, 1.15, 1.2, 1.15, 1.1, 1.05, 1.0, 0.8],
        "alimentação": [1.2, 0.95, 0.9, 0.95, 1.0, 1.1, 1.2, 1.15, 1.0, 1.0, 1.1, 1.3],
        "educação":    [0.5, 1.1, 1.1, 1.1, 1.1, 0.6, 0.5, 1.1, 1.1, 1.1, 1.1, 0.6],
        "saude":       [0.95, 0.95, 1.0, 1.0, 1.05, 1.0, 0.9, 0.95, 1.05, 1.05, 1.0, 0.95],
        "geral":       [0.95, 0.9, 1.0, 1.0, 1.05, 1.0, 0.95, 1.0, 1.05, 1.05, 1.1, 1.0],
    }
    if cnae in ("4120-4","4330-4"): k = "construção"
    elif cnae in ("5611-2","5620-1"): k = "alimentação"
    elif cnae in ("8511-2","8512-1","8599-6"): k = "educação"
    elif cnae in ("8630-5","8650-0"): k = "saude"
    else: k = "geral"
    return base[k][mes - 1]


def gerar_contribuintes():
    print("Gerando contribuintes ISS...")
    cnaes_lista = list(CNAES.keys())
    rows = []
    for i in range(N_CONTRIBUINTES_ISS):
        porte = np.random.choice(PORTES, p=PORTE_PESO)
        cnae = random.choice(cnaes_lista)
        risco_lat = np.random.choice([0, 1, 2], p=[0.60, 0.25, 0.15])
        ativo_flag = 1 if random.random() > 0.05 else 0
        # situacao_cnpj: alguns inativos têm CNPJ baixado (potencial sonegação)
        if ativo_flag == 0 and random.random() < 0.60:
            situacao_cnpj = "Baixado"
        elif random.random() < 0.03:
            situacao_cnpj = "Suspenso"
        else:
            situacao_cnpj = "Ativo"
        rows.append({
            "id_contribuinte": i + 1,
            "cnpj": _cnpj(),
            "razao_social": fake.company(),
            "cnae": cnae,
            "desc_cnae": CNAES[cnae]["desc"],
            "porte": porte,
            "regime_tributario": random.choice(REGIME_POR_PORTE[porte]),
            "bairro": random.choice(BAIRROS),
            "data_abertura": fake.date_between(start_date='-10y', end_date='-6m'),
            "ativo": ativo_flag,
            "risco_latente": risco_lat,
            "situacao_cnpj": situacao_cnpj,
            "email": fake.company_email(),
            "telefone": fake.phone_number(),
        })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/contribuintes.csv", index=False)
    print(f"  {len(df)} contribuintes")
    return df


def gerar_declaracoes_iss(contribuintes: pd.DataFrame):
    print("Gerando declarações ISS (36 meses)...")
    meses = meses_range(DATA_INICIO, MESES)
    rows = []
    for _, c in contribuintes[contribuintes["ativo"] == 1].iterrows():
        bench = CNAES[c["cnae"]]["bench"][c["porte"]]
        aliq  = ISS_ALIQUOTAS[c["cnae"]]
        risco = c["risco_latente"]
        for mes in meses:
            receita_real = bench * sazonalidade_iss(mes.month, c["cnae"]) * np.random.normal(1.0, 0.12)
            if risco == 0:   fator = np.random.uniform(0.92, 1.02)
            elif risco == 1: fator = np.random.uniform(0.60, 0.90)
            else:            fator = np.random.uniform(0.25, 0.65)
            omitiu = int((risco == 1 and random.random() < 0.08) or (risco == 2 and random.random() < 0.20))
            rec_decl     = receita_real * fator if not omitiu else 0
            iss_devido   = receita_real * aliq
            iss_rec      = rec_decl * aliq
            gap_abs      = max(0, iss_devido - iss_rec)
            rows.append({
                "id_declaracao": len(rows) + 1,
                "id_contribuinte": c["id_contribuinte"],
                "cnae": c["cnae"],
                "competencia": mes.strftime("%Y-%m"),
                "ano": mes.year, "mes": mes.month,
                "receita_real_estimada": round(receita_real, 2),
                "receita_declarada": round(rec_decl, 2),
                "iss_devido_estimado": round(iss_devido, 2),
                "iss_recolhido": round(iss_rec, 2),
                "gap_absoluto": round(gap_abs, 2),
                "gap_percentual": round(gap_abs / iss_devido * 100 if iss_devido > 0 else 0, 2),
                "omitiu_declaracao": omitiu,
                "retificou": int(not omitiu and random.random() < 0.04),
                "aliquota": aliq,
            })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/declaracoes_iss.csv", index=False)
    print(f"  {len(df)} declarações")
    return df


def gerar_iptu():
    print("Gerando IPTU...")
    tipos = ["Residencial","Comercial","Industrial","Terreno"]
    tipo_peso = [0.65, 0.20, 0.05, 0.10]
    aliq_tipo = {"Residencial":0.008,"Comercial":0.012,"Industrial":0.012,"Terreno":0.020}
    prob_inad = {"Residencial":0.18,"Comercial":0.12,"Industrial":0.08,"Terreno":0.30}
    fator_bairro = {"Centro":1.4,"Ilha Porchat":1.6,"Alto da Boa Vista":1.3,
                    "Cidade Nautica":1.2,"Glória":1.1,"Porto Grande":1.2}
    # anos do período para distribuir parcelas
    anos = sorted({DATA_INICIO.year + i for i in range(MESES // 12 + 1)})

    rows_im, rows_parc = [], []
    id_parc = 1
    for i in range(N_IMOVEIS):
        tipo   = np.random.choice(tipos, p=tipo_peso)
        bairro = random.choice(BAIRROS)
        area   = np.random.lognormal(4.8, 0.6)
        vv_base = {"Residencial":2800,"Comercial":4500,"Industrial":3200,"Terreno":900}[tipo]
        valor_venal = round(area * vv_base * fator_bairro.get(bairro, 1.0) * np.random.uniform(0.85, 1.15), 2)
        iptu_lancado = round(valor_venal * aliq_tipo[tipo], 2)
        isencao = int(tipo == "Residencial" and valor_venal < 80_000 and random.random() < 0.15)
        if isencao: iptu_lancado = 0
        inadimplente = int(not isencao and random.random() < prob_inad[tipo])
        iptu_pago = 0 if inadimplente or isencao else iptu_lancado

        rows_im.append({
            "id_imovel": i+1, "inscricao_imobiliaria": f"SV{i+1:06d}",
            "tipo": tipo, "bairro": bairro, "area_m2": round(area,1),
            "valor_venal": valor_venal, "iptu_lancado": iptu_lancado,
            "iptu_pago": iptu_pago, "isencao": isencao, "inadimplente": inadimplente,
            "ultima_atualizacao_cadastral": fake.date_between(start_date='-8y', end_date='today'),
        })

        # FIX: parcelas distribuídas pelos anos reais do período analítico
        if iptu_lancado > 0:
            for ano in anos:
                n_parc = random.choice([1, 5, 10])
                valor_parc = round(iptu_lancado / n_parc, 2)
                for p in range(n_parc):
                    mes_venc = (p % 10) + 1  # jan–out
                    venc = date(ano, mes_venc, 10)
                    pago_parc = not inadimplente or random.random() < 0.4
                    rows_parc.append({
                        "id_parcela": id_parc, "id_imovel": i+1, "ano": ano,
                        "parcela": p+1, "vencimento": venc,
                        "valor": valor_parc, "pago": int(pago_parc),
                    })
                    id_parc += 1

    df_im   = pd.DataFrame(rows_im)
    df_parc = pd.DataFrame(rows_parc)
    df_im.to_csv(f"{OUTPUT_DIR}/imoveis.csv", index=False)
    df_parc.to_csv(f"{OUTPUT_DIR}/iptu_parcelas.csv", index=False)
    print(f"  {len(df_im)} imóveis, {len(df_parc)} parcelas IPTU")
    return df_im, df_parc


def gerar_itbi(imoveis: pd.DataFrame):
    print("Gerando ITBI...")
    meses = meses_range(DATA_INICIO, MESES)
    n = int(N_IMOVEIS * 0.08)
    sample = imoveis[imoveis["tipo"] != "Terreno"].sample(n=n, random_state=42, replace=True)
    rows = []
    for i, (_, im) in enumerate(sample.iterrows()):
        mes = random.choice(meses)
        subav = random.random() < 0.22
        razao = np.random.uniform(0.45, 0.79) if subav else np.random.uniform(0.80, 1.15)
        vd    = round(im["valor_venal"] * razao, 2)
        bc    = max(vd, im["valor_venal"])
        rows.append({
            "id_itbi": i+1, "id_imovel": im["id_imovel"], "bairro": im["bairro"],
            "tipo_imovel": im["tipo"], "mes_competencia": mes.strftime("%Y-%m"),
            "valor_venal_iptu": im["valor_venal"], "valor_declarado_escritura": vd,
            "razao_decl_venal": round(razao, 3), "base_calculo": bc,
            "itbi_devido": round(bc*0.02, 2), "itbi_recolhido": round(vd*0.02, 2),
            "gap_itbi": round(max(0, bc*0.02 - vd*0.02), 2),
            "subavaliacao_detectada": int(subav), "ano": mes.year,
        })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/itbi.csv", index=False)
    print(f"  {len(df)} transações ITBI")
    return df


def gerar_taxas(contribuintes: pd.DataFrame):
    """
    FIX: Salva cosip_mensal.csv (144 linhas) para o dashboard.
    cosip.csv mantido como amostra compacta para compatibilidade.
    """
    print("Gerando taxas municipais...")
    meses = meses_range(DATA_INICIO, MESES)
    anos  = sorted({m.year for m in meses})

    # Alvará
    rows_alv = []
    base_alv = {"MEI":180,"ME":480,"EPP":960,"MD":2400,"GR":6000}
    for ano in anos:
        for _, c in contribuintes[contribuintes["ativo"]==1].iterrows():
            lancado = round(base_alv[c["porte"]] * np.random.uniform(0.9, 1.1), 2)
            adim    = random.random() > 0.10
            rows_alv.append({"id_contribuinte":c["id_contribuinte"],"ano":ano,
                              "valor_lancado":lancado,"valor_pago":lancado if adim else 0,"adimplente":int(adim)})
    pd.DataFrame(rows_alv).to_csv(f"{OUTPUT_DIR}/taxa_alvara.csv", index=False)

    # COSIP: gera direto como agregado mensal por faixa (sem loop por economia)
    faixas  = {1:8.50, 2:15.00, 3:28.00, 4:55.00}
    fpesos  = [0.35, 0.30, 0.25, 0.10]
    n_eco   = 18_000
    rows_cm = []
    # cosip.csv compacto: uma linha por faixa/mês (compatibilidade com colunas adimplente)
    rows_cr = []
    id_eco  = 1
    for mes in meses:
        comp = mes.strftime("%Y-%m")
        for fid, fp in zip([1,2,3,4], fpesos):
            n      = int(n_eco * fp)
            val    = faixas[fid]
            tx_inad= 0.07 + np.random.uniform(-0.015, 0.015)
            adim_n = int(n * (1 - tx_inad))
            rows_cm.append({
                "competencia": comp, "faixa_consumo": fid, "n_economias": n,
                "valor_lancado": round(n * val, 2), "valor_pago": round(adim_n * val, 2),
                "adimplentes": adim_n,
                "taxa_adimplencia": round(adim_n / n * 100, 2),
            })
            # cosip.csv: representativo (1 linha por faixa/mês)
            rows_cr.append({
                "id_economia": id_eco, "competencia": comp, "faixa_consumo": fid,
                "valor_lancado": round(n * val, 2),
                "valor_pago": round(adim_n * val, 2),
                "adimplente": int(random.random() > tx_inad),
            })
            id_eco += 1

    pd.DataFrame(rows_cm).to_csv(f"{OUTPUT_DIR}/cosip_mensal.csv", index=False)
    pd.DataFrame(rows_cr).to_csv(f"{OUTPUT_DIR}/cosip.csv", index=False)

    # Taxa lixo semestral
    rows_lx = []
    for ano in anos:
        for sem in [1, 2]:
            for i in range(N_IMOVEIS):
                lancado = round(np.random.uniform(80, 220), 2)
                adim    = random.random() > 0.15
                rows_lx.append({"id_imovel":i+1,"ano":ano,"semestre":sem,
                                 "valor_lancado":lancado,"valor_pago":lancado if adim else 0,"adimplente":int(adim)})
    pd.DataFrame(rows_lx).to_csv(f"{OUTPUT_DIR}/taxa_lixo.csv", index=False)

    df_cosip_m = pd.read_csv(f"{OUTPUT_DIR}/cosip_mensal.csv")
    print(f"  alvarás: {len(rows_alv)} | cosip_mensal: {len(rows_cm)} linhas | lixo: {len(rows_lx)}")
    return pd.DataFrame(rows_alv), df_cosip_m, pd.DataFrame(rows_lx)


def gerar_contrib_melhoria(imoveis: pd.DataFrame):
    print("Gerando contribuição de melhoria...")
    obras = [
        {"id_obra":1,"desc":"Recapeamento Av. Central","data":date(2022,6,1),"custo":2_800_000,"bairros":["Centro","Vila Nova"]},
        {"id_obra":2,"desc":"Nova Praça Japuí",        "data":date(2023,3,1),"custo":980_000,  "bairros":["Japuí","Catiapoa"]},
    ]
    rows = []
    for obra in obras:
        imb = imoveis[imoveis["bairro"].isin(obra["bairros"])]
        tv  = imb["valor_venal"].sum()
        for _, im in imb.iterrows():
            vl   = round(obra["custo"] * 0.60 * (im["valor_venal"] / tv if tv > 0 else 0), 2)
            pago = random.random() > 0.20
            rows.append({
                "id_obra":obra["id_obra"],"desc_obra":obra["desc"],"data_lancamento":obra["data"],
                "id_imovel":im["id_imovel"],"bairro":im["bairro"],"valor_venal":im["valor_venal"],
                "valor_lancado":vl,"valor_pago":vl if pago else 0,"adimplente":int(pago),
            })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/contrib_melhoria.csv", index=False)
    print(f"  {len(df)} lançamentos de contribuição de melhoria")
    return df


def gerar_divida_ativa(decl_iss: pd.DataFrame, df_iptu: pd.DataFrame, df_itbi: pd.DataFrame):
    print("Gerando dívida ativa...")
    rows, id_da = [], 1

    for _, r in decl_iss[decl_iss["gap_absoluto"] > 500].sample(frac=0.15, random_state=42).iterrows():
        inscricao = date.fromisoformat(r["competencia"] + "-01") + timedelta(days=90)
        valor = r["gap_absoluto"]
        juros = valor * 0.12 * random.uniform(0.5, 2.5)
        multa = valor * 0.20
        total = round(valor + juros + multa, 2)
        rec   = total * random.uniform(0, 0.3) if random.random() < 0.35 else 0
        rows.append({
            "id_da":id_da,"tipo_tributo":"ISS","id_contribuinte":r["id_contribuinte"],
            "competencia_origem":r["competencia"],"data_inscricao":inscricao,
            "valor_principal":round(valor,2),"juros":round(juros,2),"multa":round(multa,2),
            "valor_total":total,"valor_recuperado":round(rec,2),
            "fase":random.choice(["Administrativa","Administrativa","Judicial"]),
            "situacao":"Parcelado" if rec > 0 else "Em aberto",
        })
        id_da += 1

    # FIX: ignorar imóveis isentos (iptu_lancado=0)
    for _, im in df_iptu[(df_iptu["inadimplente"]==1) & (df_iptu["iptu_lancado"]>0)].sample(frac=0.30, random_state=42).iterrows():
        valor = im["iptu_lancado"]
        juros = valor * 0.12; multa = valor * 0.20
        total = round(valor + juros + multa, 2)
        rec   = total * random.uniform(0, 0.4) if random.random() < 0.40 else 0
        rows.append({
            "id_da":id_da,"tipo_tributo":"IPTU","id_contribuinte":None,
            "competencia_origem":f"{random.choice([2022,2023,2024])}-01",
            "data_inscricao":fake.date_between(start_date='-2y', end_date='-6m'),
            "valor_principal":round(valor,2),"juros":round(juros,2),"multa":round(multa,2),
            "valor_total":total,"valor_recuperado":round(rec,2),
            "fase":random.choice(["Administrativa","Judicial"]),
            "situacao":"Parcelado" if rec > 0 else "Em aberto",
        })
        id_da += 1

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/divida_ativa.csv", index=False)
    print(f"  {len(df)} registros de dívida ativa")
    return df


def gerar_acoes_fiscais(contribuintes: pd.DataFrame):
    print("Gerando ações fiscais...")
    tipos = ["Auditoria Fiscal","Notificação Prévia","Auto de Infração","Ação Preventiva"]
    rows  = []
    for i, (_, c) in enumerate(contribuintes.sample(400, random_state=42).iterrows()):
        tipo        = random.choice(tipos)
        irreg       = random.random() < {0:0.15,1:0.55,2:0.85}[c["risco_latente"]]
        val_aut     = 0
        if irreg and tipo == "Auto de Infração":
            val_aut = round(CNAES[c["cnae"]]["bench"][c["porte"]] * random.uniform(0.5,3.0)
                            * ISS_ALIQUOTAS[c["cnae"]] * random.uniform(3,18), 2)
        rows.append({
            "id_acao":i+1,"id_contribuinte":c["id_contribuinte"],"cnae":c["cnae"],"porte":c["porte"],
            "data_acao":fake.date_between(start_date='-3y', end_date='-1m'),
            "tipo_acao":tipo,"irregularidade_confirmada":int(irreg),"valor_autuado":val_aut,
            "resultado":"Autuado" if irreg and val_aut>0 else ("Irregular s/ autuação" if irreg else "Regular"),
            "meses_sem_fiscalizacao_antes":random.randint(6,48),
        })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/acoes_fiscais.csv", index=False)
    print(f"  {len(df)} ações fiscais")
    return df


def gerar_transferencias():
    print("Gerando transferências constitucionais...")
    meses = meses_range(DATA_INICIO, MESES)
    bases = {"FPM":8.2,"ICMS":12.5,"IPVA":1.8,"ITR":0.3,"FUNDEB":4.5}
    rows  = []
    for mes in meses:
        fs = 1 + 0.05 * np.sin(2 * np.pi * mes.month / 12)
        for tipo, base in bases.items():
            rows.append({
                "competencia":mes.strftime("%Y-%m"),"ano":mes.year,"mes":mes.month,
                "tipo_transferencia":tipo,"valor":round(base * fs * np.random.normal(1,0.08) * 1_000_000, 2),
            })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/transferencias.csv", index=False)
    print(f"  {len(df)} transferências")
    return df


def main():
    print("=" * 60)
    print("FiscoSmart — Gerando dados sintéticos (v2)")
    print("=" * 60)
    contribs      = gerar_contribuintes()
    decl_iss      = gerar_declaracoes_iss(contribs)
    imoveis, parc = gerar_iptu()
    itbi          = gerar_itbi(imoveis)
    alv, cos, lxo = gerar_taxas(contribs)
    cm            = gerar_contrib_melhoria(imoveis)
    da            = gerar_divida_ativa(decl_iss, imoveis, itbi)
    acoes         = gerar_acoes_fiscais(contribs)
    transf        = gerar_transferencias()
    print("\n" + "=" * 60)
    print(f"  ISS recolhido (36m):  R$ {decl_iss['iss_recolhido'].sum():>15,.0f}")
    print(f"  IPTU pago:            R$ {imoveis['iptu_pago'].sum():>15,.0f}")
    print(f"  ITBI recolhido (36m): R$ {itbi['itbi_recolhido'].sum():>15,.0f}")
    print(f"  Dívida ativa total:   R$ {da['valor_total'].sum():>15,.0f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
