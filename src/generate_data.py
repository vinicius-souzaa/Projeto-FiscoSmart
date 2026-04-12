"""
FiscoSmart — Gerador de Dados Sintéticos
Cobre: ISS, IPTU, ITBI, Taxas, COSIP, Contribuição de Melhoria, Dívida Ativa
Baseado em benchmarks reais do Simples Nacional / SICONFI / Tesouro Nacional
"""
import pandas as pd
import numpy as np
from faker import Faker
from datetime import date, timedelta
import random
import os
import sqlite3

fake = Faker('pt_BR')
np.random.seed(42)
random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── CONSTANTES ───────────────────────────────────────────────────────────────

MUNICIPIO = "São Vicente"
POPULACAO = 355_000
N_CONTRIBUINTES_ISS = 2_000
N_IMOVEIS = 15_000
MESES = 36
DATA_INICIO = date(2022, 1, 1)

# CNAEs com benchmark de receita mensal por porte (baseado em dados Simples Nacional)
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

REGIMES = ["Simples Nacional", "Lucro Presumido", "Lucro Real", "MEI"]
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
    "Ilha Porchat", "Porto Grande"
]

ISS_ALIQUOTAS = {
    "6201-5": 0.03, "6202-3": 0.03, "7490-1": 0.03, "8599-6": 0.02,
    "5611-2": 0.03, "5620-1": 0.03, "4120-4": 0.02, "4330-4": 0.02,
    "8630-5": 0.02, "8650-0": 0.02, "6911-7": 0.05, "6920-6": 0.03,
    "7711-0": 0.03, "9602-5": 0.02, "8511-2": 0.02, "8512-1": 0.02,
    "4771-7": 0.03, "5310-5": 0.02, "9311-5": 0.03, "4921-3": 0.02,
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def gerar_cnpj():
    n = [random.randint(0, 9) for _ in range(12)]
    return f"{''.join(map(str,n[:2]))}.{''.join(map(str,n[2:5]))}.{''.join(map(str,n[5:8]))}/{''.join(map(str,n[8:12]))}-00"

def meses_range(inicio: date, n: int):
    meses = []
    d = inicio
    for _ in range(n):
        meses.append(d)
        m = d.month + 1
        y = d.year + (m > 12)
        d = date(y, m % 12 or 12, 1)
    return meses

def sazonalidade_iss(mes: int, cnae: str) -> float:
    """Fatores sazonais reais por setor e mês"""
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

# ─── 1. CONTRIBUINTES ISS ─────────────────────────────────────────────────────

def gerar_contribuintes():
    print("Gerando contribuintes ISS...")
    rows = []
    cnaes_lista = list(CNAES.keys())
    for i in range(N_CONTRIBUINTES_ISS):
        porte = np.random.choice(PORTES, p=PORTE_PESO)
        cnae = random.choice(cnaes_lista)
        regime = random.choice(REGIME_POR_PORTE[porte])
        bairro = random.choice(BAIRROS)
        abertura = fake.date_between(start_date='-10y', end_date='-6m')
        # perfil de risco latente (0=ok, 1=suspeito, 2=evasão sistemática)
        risco_lat = np.random.choice([0, 1, 2], p=[0.60, 0.25, 0.15])
        rows.append({
            "id_contribuinte": i + 1,
            "cnpj": gerar_cnpj(),
            "razao_social": fake.company(),
            "cnae": cnae,
            "desc_cnae": CNAES[cnae]["desc"],
            "porte": porte,
            "regime_tributario": regime,
            "bairro": bairro,
            "data_abertura": abertura,
            "ativo": 1 if random.random() > 0.05 else 0,
            "risco_latente": risco_lat,
            "email": fake.company_email(),
            "telefone": fake.phone_number(),
        })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/contribuintes.csv", index=False)
    print(f"  {len(df)} contribuintes gerados")
    return df

# ─── 2. DECLARAÇÕES ISS ───────────────────────────────────────────────────────

def gerar_declaracoes_iss(contribuintes: pd.DataFrame):
    print("Gerando declarações ISS (36 meses)...")
    meses = meses_range(DATA_INICIO, MESES)
    rows = []
    for _, c in contribuintes.iterrows():
        if not c["ativo"]:
            continue
        bench = CNAES[c["cnae"]]["bench"][c["porte"]]
        aliq = ISS_ALIQUOTAS[c["cnae"]]
        risco = c["risco_latente"]
        for mes in meses:
            # fator sazonal
            fs = sazonalidade_iss(mes.month, c["cnae"])
            # ruído natural
            ruido = np.random.normal(1.0, 0.12)
            receita_real = bench * fs * ruido
            # subnotificação conforme risco latente
            if risco == 0:
                fator_decl = np.random.uniform(0.92, 1.02)
                prob_omissao = 0.02
                prob_retif = 0.03
            elif risco == 1:
                fator_decl = np.random.uniform(0.55, 0.85)
                prob_omissao = 0.08
                prob_retif = 0.12
            else:
                fator_decl = np.random.uniform(0.20, 0.55)
                prob_omissao = 0.18
                prob_retif = 0.05
            omitiu = random.random() < prob_omissao
            retificou = random.random() < prob_retif
            receita_declarada = 0 if omitiu else max(0, receita_real * fator_decl * np.random.normal(1,0.05))
            iss_devido = receita_real * aliq
            iss_declarado = receita_declarada * aliq
            iss_recolhido = iss_declarado * (np.random.uniform(0.95, 1.0) if not omitiu else 0)
            prazo_ok = not omitiu and random.random() > 0.05
            rows.append({
                "id_decl": len(rows) + 1,
                "id_contribuinte": c["id_contribuinte"],
                "cnae": c["cnae"],
                "porte": c["porte"],
                "competencia": mes.strftime("%Y-%m"),
                "ano": mes.year,
                "mes": mes.month,
                "receita_real_estimada": round(receita_real, 2),
                "receita_declarada": round(receita_declarada, 2),
                "iss_devido_estimado": round(iss_devido, 2),
                "iss_declarado": round(iss_declarado, 2),
                "iss_recolhido": round(iss_recolhido, 2),
                "gap_absoluto": round(iss_devido - iss_recolhido, 2),
                "gap_percentual": round((iss_devido - iss_recolhido) / iss_devido * 100, 2) if iss_devido > 0 else 0,
                "omitiu_declaracao": int(omitiu),
                "retificou": int(retificou),
                "entregue_prazo": int(prazo_ok),
                "aliquota": aliq,
            })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/declaracoes_iss.csv", index=False)
    print(f"  {len(df)} registros de declaração ISS gerados")
    return df

# ─── 3. IPTU ──────────────────────────────────────────────────────────────────

def gerar_iptu():
    print("Gerando cadastro imobiliário e IPTU...")
    tipos = ["Residencial", "Comercial", "Industrial", "Territorial"]
    tipo_peso = [0.65, 0.20, 0.05, 0.10]
    aliq_tipo = {"Residencial": 0.01, "Comercial": 0.015, "Industrial": 0.015, "Territorial": 0.02}
    imoveis = []
    for i in range(N_IMOVEIS):
        tipo = np.random.choice(tipos, p=tipo_peso)
        bairro = random.choice(BAIRROS)
        area = {
            "Residencial": np.random.lognormal(4.8, 0.5),
            "Comercial":   np.random.lognormal(5.2, 0.6),
            "Industrial":  np.random.lognormal(6.0, 0.7),
            "Territorial": np.random.lognormal(6.5, 0.8),
        }[tipo]
        valor_m2_bairro = {
            "Centro": 4800, "Ilha Porchat": 5500, "Japuí": 3200,
            "Vila Margarida": 2800, "Catiapoa": 2600, "Porto Grande": 3800,
        }.get(bairro, 3000)
        valor_venal = round(area * valor_m2_bairro * np.random.uniform(0.85, 1.15), 2)
        aliq = aliq_tipo[tipo]
        isencao = random.random() < 0.08  # 8% têm alguma isenção
        iptu_lancado = 0 if isencao else round(valor_venal * aliq, 2)
        # inadimplência real: ~22% no Brasil
        inadimplente = not isencao and random.random() < 0.22
        iptu_pago = 0 if inadimplente else round(iptu_lancado * np.random.uniform(0.98, 1.0), 2)
        imoveis.append({
            "id_imovel": i + 1,
            "inscricao_imobiliaria": f"SV{str(i+1).zfill(6)}",
            "tipo": tipo,
            "bairro": bairro,
            "area_m2": round(area, 1),
            "valor_venal": valor_venal,
            "aliquota": aliq,
            "iptu_lancado": iptu_lancado,
            "iptu_pago": iptu_pago,
            "isencao": int(isencao),
            "inadimplente": int(inadimplente),
            "ano_construcao": random.randint(1960, 2022),
            "ultima_atualizacao_cadastral": fake.date_between(start_date='-5y', end_date='today'),
        })
    df_imoveis = pd.DataFrame(imoveis)
    # Gerar parcelas mensais (IPTU parcelado em até 10x)
    meses = meses_range(DATA_INICIO, MESES)
    parcelas = []
    for _, im in df_imoveis.iterrows():
        for ano_ref in [2022, 2023, 2024]:
            if im["iptu_lancado"] <= 0:
                continue
            n_parcelas = random.choice([1, 5, 10])
            valor_parcela = round(im["iptu_lancado"] / n_parcelas, 2)
            for p in range(1, n_parcelas + 1):
                mes_vcto = date(ano_ref, p if n_parcelas > 1 else 1, 10)
                pago = im["iptu_pago"] > 0 and random.random() > 0.15
                parcelas.append({
                    "id_imovel": im["id_imovel"],
                    "ano_referencia": ano_ref,
                    "parcela": p,
                    "vencimento": mes_vcto,
                    "valor": valor_parcela,
                    "pago": int(pago),
                    "data_pagamento": fake.date_between(start_date=mes_vcto, end_date=date(ano_ref,12,31)) if pago else None,
                })
    df_parcelas = pd.DataFrame(parcelas)
    df_imoveis.to_csv(f"{OUTPUT_DIR}/imoveis.csv", index=False)
    df_parcelas.to_csv(f"{OUTPUT_DIR}/iptu_parcelas.csv", index=False)
    print(f"  {len(df_imoveis)} imóveis e {len(df_parcelas)} parcelas IPTU geradas")
    return df_imoveis, df_parcelas

# ─── 4. ITBI ──────────────────────────────────────────────────────────────────

def gerar_itbi(imoveis: pd.DataFrame):
    print("Gerando transações ITBI...")
    aliquota_itbi = 0.02
    n_transacoes = MESES * 35  # ~35 escrituras/mês
    rows = []
    meses = meses_range(DATA_INICIO, MESES)
    for i in range(n_transacoes):
        mes = random.choice(meses)
        im = imoveis.sample(1).iloc[0]
        valor_venal = im["valor_venal"]
        # Subavaliação: ~20% dos contribuintes declaram menos
        subavaliou = random.random() < 0.20
        fator_decl = np.random.uniform(0.45, 0.75) if subavaliou else np.random.uniform(0.95, 1.05)
        valor_declarado = round(valor_venal * fator_decl, 2)
        base_calc = max(valor_declarado, valor_venal * 0.80)  # município usa valor venal como piso
        itbi_devido = round(valor_venal * aliquota_itbi, 2)
        itbi_recolhido = round(base_calc * aliquota_itbi, 2)
        rows.append({
            "id_itbi": i + 1,
            "id_imovel": im["id_imovel"],
            "mes_competencia": mes.strftime("%Y-%m"),
            "ano": mes.year,
            "mes": mes.month,
            "tipo_imovel": im["tipo"],
            "bairro": im["bairro"],
            "valor_venal_iptu": valor_venal,
            "valor_declarado_escritura": valor_declarado,
            "razao_decl_venal": round(valor_declarado / valor_venal, 3) if valor_venal > 0 else 1,
            "base_calculo_efetiva": base_calc,
            "aliquota": aliquota_itbi,
            "itbi_devido": itbi_devido,
            "itbi_recolhido": itbi_recolhido,
            "subavaliacao_detectada": int(subavaliou),
            "gap_itbi": round(itbi_devido - itbi_recolhido, 2),
        })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/itbi.csv", index=False)
    print(f"  {len(df)} transações ITBI geradas")
    return df

# ─── 5. TAXAS MUNICIPAIS ──────────────────────────────────────────────────────

def gerar_taxas(contribuintes: pd.DataFrame):
    print("Gerando taxas municipais...")
    meses = meses_range(DATA_INICIO, MESES)
    # Taxa de Alvará / Licença de Funcionamento (anual)
    alvaras = []
    for _, c in contribuintes.iterrows():
        for ano in [2022, 2023, 2024]:
            valor = {"MEI":120, "ME":350, "EPP":800, "MD":2500, "GR":8000}[c["porte"]]
            pago = random.random() > 0.12
            alvaras.append({
                "id_contribuinte": c["id_contribuinte"],
                "ano": ano,
                "tipo_taxa": "Alvará de Funcionamento",
                "valor_lancado": valor,
                "valor_pago": valor if pago else 0,
                "adimplente": int(pago),
            })
    # COSIP (mensal, por imóvel)
    cosip = []
    n_economias = N_IMOVEIS
    for i in range(n_economias):
        for mes in meses:
            faixa = random.choice([1,2,3,4])
            valor = {1: 8.50, 2: 15.00, 3: 28.00, 4: 55.00}[faixa]
            pago = random.random() > 0.08
            cosip.append({
                "id_economia": i + 1,
                "competencia": mes.strftime("%Y-%m"),
                "faixa_consumo": faixa,
                "valor_lancado": valor,
                "valor_pago": valor if pago else 0,
                "adimplente": int(pago),
            })
    # Taxa de Coleta de Lixo (semestral por imóvel)
    lixo = []
    for i in range(N_IMOVEIS):
        for ano in [2022, 2023, 2024]:
            for sem in [1, 2]:
                valor = round(np.random.uniform(80, 250), 2)
                pago = random.random() > 0.15
                lixo.append({
                    "id_imovel": i + 1,
                    "ano": ano,
                    "semestre": sem,
                    "tipo_taxa": "Taxa de Coleta de Lixo",
                    "valor_lancado": valor,
                    "valor_pago": valor if pago else 0,
                    "adimplente": int(pago),
                })
    df_alv = pd.DataFrame(alvaras)
    df_cos = pd.DataFrame(cosip)
    df_lxo = pd.DataFrame(lixo)
    df_alv.to_csv(f"{OUTPUT_DIR}/taxa_alvara.csv", index=False)
    df_cos.to_csv(f"{OUTPUT_DIR}/cosip.csv", index=False)
    df_lxo.to_csv(f"{OUTPUT_DIR}/taxa_lixo.csv", index=False)
    print(f"  {len(df_alv)} alvarás, {len(df_cos)} COSIP, {len(df_lxo)} taxas de lixo")
    return df_alv, df_cos, df_lxo

# ─── 6. CONTRIBUIÇÃO DE MELHORIA ──────────────────────────────────────────────

def gerar_contrib_melhoria(imoveis: pd.DataFrame):
    print("Gerando contribuição de melhoria...")
    obras = [
        {"id_obra": 1, "desc": "Recapeamento Av. Central", "data": date(2022,6,1), "custo": 2_800_000, "bairros": ["Centro","Vila Nova"]},
        {"id_obra": 2, "desc": "Nova Praça Japuí",         "data": date(2023,3,1), "custo": 980_000,   "bairros": ["Japuí","Catiapoa"]},
    ]
    rows = []
    for obra in obras:
        imoveis_beneficiados = imoveis[imoveis["bairro"].isin(obra["bairros"])]
        total_venal = imoveis_beneficiados["valor_venal"].sum()
        for _, im in imoveis_beneficiados.iterrows():
            proporcao = im["valor_venal"] / total_venal if total_venal > 0 else 0
            valor_lancado = round(obra["custo"] * 0.60 * proporcao, 2)  # 60% do custo rateado
            pago = random.random() > 0.20
            rows.append({
                "id_obra": obra["id_obra"],
                "desc_obra": obra["desc"],
                "data_lancamento": obra["data"],
                "id_imovel": im["id_imovel"],
                "bairro": im["bairro"],
                "valor_venal": im["valor_venal"],
                "valor_lancado": valor_lancado,
                "valor_pago": valor_lancado if pago else 0,
                "adimplente": int(pago),
            })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/contrib_melhoria.csv", index=False)
    print(f"  {len(df)} lançamentos de contribuição de melhoria")
    return df

# ─── 7. DÍVIDA ATIVA ──────────────────────────────────────────────────────────

def gerar_divida_ativa(decl_iss: pd.DataFrame, df_iptu: pd.DataFrame, df_itbi: pd.DataFrame):
    print("Gerando dívida ativa consolidada...")
    rows = []
    id_da = 1
    # ISS em atraso > 90 dias
    iss_atraso = decl_iss[decl_iss["gap_absoluto"] > 500].sample(frac=0.15, random_state=42)
    for _, r in iss_atraso.iterrows():
        inscricao = date.fromisoformat(r["competencia"] + "-01") + timedelta(days=90)
        fase = random.choice(["Administrativa","Administrativa","Judicial"])
        valor = r["gap_absoluto"]
        juros = valor * 0.12 * random.uniform(0.5, 2.5)
        multa = valor * 0.20
        total = round(valor + juros + multa, 2)
        recuperado = total * random.uniform(0, 0.3) if random.random() < 0.35 else 0
        rows.append({
            "id_da": id_da, "tipo_tributo": "ISS",
            "id_contribuinte": r["id_contribuinte"],
            "competencia_origem": r["competencia"],
            "data_inscricao": inscricao,
            "valor_principal": round(valor,2), "juros": round(juros,2), "multa": round(multa,2),
            "valor_total": total, "valor_recuperado": round(recuperado,2),
            "fase": fase, "situacao": "Parcelado" if recuperado > 0 else "Em aberto",
        })
        id_da += 1
    # IPTU inadimplente
    iptu_inad = df_iptu[df_iptu["inadimplente"] == 1].sample(frac=0.30, random_state=42)
    for _, im in iptu_inad.iterrows():
        valor = im["iptu_lancado"]
        juros = valor * 0.12
        multa = valor * 0.20
        total = round(valor + juros + multa, 2)
        recuperado = total * random.uniform(0, 0.4) if random.random() < 0.40 else 0
        rows.append({
            "id_da": id_da, "tipo_tributo": "IPTU",
            "id_contribuinte": None,
            "competencia_origem": f"{random.choice([2022,2023,2024])}-01",
            "data_inscricao": fake.date_between(start_date='-2y', end_date='-6m'),
            "valor_principal": round(valor,2), "juros": round(juros,2), "multa": round(multa,2),
            "valor_total": total, "valor_recuperado": round(recuperado,2),
            "fase": random.choice(["Administrativa","Judicial"]),
            "situacao": "Parcelado" if recuperado > 0 else "Em aberto",
        })
        id_da += 1
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/divida_ativa.csv", index=False)
    print(f"  {len(df)} registros de dívida ativa")
    return df

# ─── 8. AÇÕES FISCAIS HISTÓRICAS ──────────────────────────────────────────────

def gerar_acoes_fiscais(contribuintes: pd.DataFrame):
    print("Gerando histórico de ações fiscais...")
    rows = []
    # ~400 fiscalizações nos últimos 3 anos
    contribuintes_fiscalizados = contribuintes.sample(400, random_state=42)
    tipos_acao = ["Auditoria Fiscal", "Notificação Prévia", "Auto de Infração", "Ação Preventiva"]
    for i, (_, c) in enumerate(contribuintes_fiscalizados.iterrows()):
        data_acao = fake.date_between(start_date='-3y', end_date='-1m')
        tipo = random.choice(tipos_acao)
        # contribuintes com risco latente > 0 têm mais chance de irregularidade confirmada
        prob_irreg = {0: 0.15, 1: 0.55, 2: 0.85}[c["risco_latente"]]
        irregularidade = random.random() < prob_irreg
        valor_autuado = 0
        if irregularidade and tipo == "Auto de Infração":
            bench = CNAES[c["cnae"]]["bench"][c["porte"]]
            valor_autuado = round(bench * random.uniform(0.5, 3.0) * ISS_ALIQUOTAS[c["cnae"]] * random.uniform(3,18), 2)
        rows.append({
            "id_acao": i + 1,
            "id_contribuinte": c["id_contribuinte"],
            "cnae": c["cnae"],
            "porte": c["porte"],
            "data_acao": data_acao,
            "tipo_acao": tipo,
            "irregularidade_confirmada": int(irregularidade),
            "valor_autuado": valor_autuado,
            "resultado": "Autuado" if irregularidade and valor_autuado > 0 else ("Irregular s/ autuação" if irregularidade else "Regular"),
            "meses_sem_fiscalizacao_antes": random.randint(6, 48),
        })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/acoes_fiscais.csv", index=False)
    print(f"  {len(df)} ações fiscais históricas")
    return df

# ─── 9. TRANSFERÊNCIAS CONSTITUCIONAIS ────────────────────────────────────────

def gerar_transferencias():
    print("Gerando transferências constitucionais...")
    meses = meses_range(DATA_INICIO, MESES)
    rows = []
    # Valores mensais baseados em médias reais para município de ~350k hab (R$ milhões)
    bases = {"FPM": 8.2, "ICMS": 12.5, "IPVA": 1.8, "ITR": 0.3, "FUNDEB": 4.5}
    for mes in meses:
        fs = 1 + 0.05 * np.sin(2 * np.pi * mes.month / 12)  # leve sazonalidade
        for tipo, base in bases.items():
            valor = base * fs * np.random.normal(1, 0.08) * 1_000_000
            rows.append({
                "competencia": mes.strftime("%Y-%m"),
                "ano": mes.year,
                "mes": mes.month,
                "tipo_transferencia": tipo,
                "valor": round(valor, 2),
            })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/transferencias.csv", index=False)
    print(f"  {len(df)} registros de transferências")
    return df

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("FiscoSmart — Gerando dados sintéticos completos")
    print("=" * 60)
    contribs = gerar_contribuintes()
    decl_iss  = gerar_declaracoes_iss(contribs)
    imoveis, iptu_parc = gerar_iptu()
    itbi      = gerar_itbi(imoveis)
    alv, cos, lxo = gerar_taxas(contribs)
    cm        = gerar_contrib_melhoria(imoveis)
    da        = gerar_divida_ativa(decl_iss, imoveis, itbi)
    acoes     = gerar_acoes_fiscais(contribs)
    transf    = gerar_transferencias()
    # Resumo
    print("\n" + "=" * 60)
    print("Dados gerados com sucesso em data/raw/")
    total_iss = decl_iss["iss_recolhido"].sum()
    total_iptu = imoveis["iptu_pago"].sum()
    total_itbi = itbi["itbi_recolhido"].sum()
    print(f"  ISS recolhido total (36m):  R$ {total_iss:,.0f}")
    print(f"  IPTU pago total:            R$ {total_iptu:,.0f}")
    print(f"  ITBI recolhido total (36m): R$ {total_itbi:,.0f}")
    print(f"  Dívida ativa total:         R$ {da['valor_total'].sum():,.0f}")
    print("=" * 60)

if __name__ == "__main__":
    main()
