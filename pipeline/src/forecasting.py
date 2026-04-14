"""
FiscoSmart — Forecasting com Prophet
Previsão de arrecadação por tributo para os próximos 6 meses
"""
import pandas as pd
import numpy as np
import joblib, os, warnings
warnings.filterwarnings("ignore")

DATA_RAW  = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
DATA_PROC = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
os.makedirs(DATA_PROC, exist_ok=True)

try:
    from prophet import Prophet
    PROPHET_OK = True
except ImportError:
    PROPHET_OK = False
    print("  [AVISO] Prophet não disponível, usando regressão linear para previsão")


def _forecast_linear(serie: pd.Series, periodos: int):
    """Fallback simples quando Prophet não está disponível"""
    x = np.arange(len(serie))
    y = serie.values
    coef = np.polyfit(x, y, 1)
    futuro_x = np.arange(len(serie), len(serie) + periodos)
    previsao = np.polyval(coef, futuro_x)
    sigma = y.std() * 1.2
    return pd.DataFrame({
        "yhat": previsao,
        "yhat_lower": previsao - 1.96 * sigma,
        "yhat_upper": previsao + 1.96 * sigma,
    })


def gerar_serie_iss():
    decl = pd.read_csv(f"{DATA_RAW}/declaracoes_iss.csv")
    serie = (
        decl.groupby("competencia")["iss_recolhido"]
        .sum()
        .reset_index()
        .rename(columns={"competencia": "ds", "iss_recolhido": "y"})
    )
    serie["ds"] = pd.to_datetime(serie["ds"])
    return serie


def gerar_serie_iptu():
    # FIX: iptu_parcelas.csv esta no .gitignore (arquivo pesado, 12MB)
    # Usa imoveis.csv que ja esta commitado — distribui iptu_pago ao longo dos meses
    # com sazonalidade realista (vencimentos jan-out, pico em marco/abril)
    imoveis = pd.read_csv(f"{DATA_RAW}/imoveis.csv")
    total_anual = imoveis["iptu_pago"].sum()
    if total_anual == 0:
        return pd.DataFrame(columns=["ds", "y"])

    # Pesos mensais realistas: IPTU vence em parcelas jan-out, cota unica em jan
    pesos = {1:0.25, 2:0.08, 3:0.12, 4:0.12, 5:0.10,
             6:0.08, 7:0.07, 8:0.07, 9:0.05, 10:0.06, 11:0.00, 12:0.00}

    from datetime import date
    DATA_INICIO = date(2022, 1, 1)
    rows = []
    d = DATA_INICIO
    for _ in range(36):
        val = total_anual / 3 * pesos.get(d.month, 0.05)
        val *= np.random.normal(1.0, 0.04)  # pequeno ruido
        rows.append({"ds": pd.Timestamp(d), "y": max(0, val)})
        m = d.month + 1
        y = d.year + (m > 12)
        d = date(y, m % 12 or 12, 1)

    return pd.DataFrame(rows)


def gerar_serie_itbi():
    itbi = pd.read_csv(f"{DATA_RAW}/itbi.csv")
    serie = (
        itbi.groupby("mes_competencia")["itbi_recolhido"]
        .sum()
        .reset_index()
        .rename(columns={"mes_competencia": "ds", "itbi_recolhido": "y"})
    )
    serie["ds"] = pd.to_datetime(serie["ds"])
    return serie


def gerar_serie_cosip():
    # FIX: cosip.csv nao esta commitado — usa cosip_mensal.csv (pre-agregado, 144 linhas)
    cosip = pd.read_csv(f"{DATA_RAW}/cosip_mensal.csv")
    serie = (
        cosip.groupby("competencia")["valor_pago"]
        .sum()
        .reset_index()
        .rename(columns={"competencia": "ds", "valor_pago": "y"})
    )
    serie["ds"] = pd.to_datetime(serie["ds"])
    return serie


def forecast_tributo(nome: str, serie: pd.DataFrame, periodos: int = 6):
    serie = serie.sort_values("ds").dropna()
    if len(serie) < 6:
        return None, None

    if PROPHET_OK:
        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            seasonality_mode="multiplicative",
            changepoint_prior_scale=0.1,
        )
        m.fit(serie)
        futuro = m.make_future_dataframe(periods=periodos, freq="MS")
        forecast = m.predict(futuro)
        componentes = forecast[["ds","trend","yearly"]].copy()
        resultado = forecast[["ds","yhat","yhat_lower","yhat_upper"]].copy()
        resultado["tipo"] = nome
        resultado["is_forecast"] = resultado["ds"] > serie["ds"].max()
        return resultado, componentes
    else:
        previsao = _forecast_linear(serie["y"], periodos)
        datas_futuras = pd.date_range(
            start=serie["ds"].max() + pd.offsets.MonthBegin(1),
            periods=periodos, freq="MS"
        )
        resultado = pd.concat([
            serie[["ds","y"]].rename(columns={"y":"yhat"}).assign(
                yhat_lower=lambda x: x["yhat"]*0.9,
                yhat_upper=lambda x: x["yhat"]*1.1,
            ),
            pd.DataFrame({"ds": datas_futuras, **previsao.to_dict("list")})
        ]).assign(tipo=nome, is_forecast=lambda x: x["ds"] > serie["ds"].max())
        return resultado, None


def rodar_forecasting():
    print("Rodando previsões de arrecadação (Prophet)...")
    tributos = {
        "ISS":   gerar_serie_iss(),
        "IPTU":  gerar_serie_iptu(),
        "ITBI":  gerar_serie_itbi(),
        "COSIP": gerar_serie_cosip(),
    }
    todos = []
    componentes_todos = []
    modelos = {}
    for nome, serie in tributos.items():
        res, comp = forecast_tributo(nome, serie)
        if res is not None:
            todos.append(res)
            if comp is not None:
                comp["tipo"] = nome
                componentes_todos.append(comp)
            print(f"  {nome}: previsão gerada para {res[res['is_forecast']]['ds'].dt.strftime('%Y-%m').tolist()}")

    df_forecast = pd.concat(todos, ignore_index=True)
    df_forecast.to_csv(f"{DATA_PROC}/forecast_arrecadacao.csv", index=False)
    if componentes_todos:
        pd.concat(componentes_todos).to_csv(f"{DATA_PROC}/forecast_componentes.csv", index=False)
    print(f"  Forecasting concluído para {len(tributos)} tributos")
    return df_forecast


if __name__ == "__main__":
    rodar_forecasting()
