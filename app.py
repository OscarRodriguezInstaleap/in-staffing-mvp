import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# Modelos de forecasting
import statsmodels.api as sm
from prophet import Prophet

# Ajuste de fuente para plotly (puede que no se aplique en todos los entornos)
CUSTOM_FONT = dict(family="Roboto", size=12)

# Configuración de la aplicación
st.set_page_config(page_title="In-Staffing MVP", layout="wide")
os.makedirs("reports", exist_ok=True)

st.title("In-Staffing: Planificación de Recursos")
st.markdown("---")

# Sección para cargar el archivo CSV
st.header("Cargar Archivo CSV")
archivo_csv = st.file_uploader("Sube un archivo de datos de operaciones (CSV)", type=["csv"])

# Parámetros adicionales en la barra lateral
with st.sidebar:
    with st.expander("Configuraciones Generales"):
        hora_apertura = st.slider("Hora de apertura de tienda", 0, 23, 8)
        hora_cierre = st.slider("Hora de cierre de tienda", 0, 23, 22)
        productividad_estimada = st.number_input("Productividad Estimada por Hora", min_value=10, max_value=500, value=100, step=10)

        # Fechas del pronóstico
        fecha_inicio_pronostico = st.date_input("Fecha de inicio del pronóstico", datetime.now() + timedelta(days=1))
        fecha_fin_pronostico = st.date_input("Fecha de fin del pronóstico", fecha_inicio_pronostico + timedelta(days=30))

        if (fecha_fin_pronostico - fecha_inicio_pronostico).days > 30:
            st.error("El periodo del pronóstico no puede ser mayor a 30 días.")

    with st.expander("Evento Especial"):
        evento_especial = st.checkbox("¿Habrá un evento especial?")
        fecha_inicio_evento = None
        fecha_fin_evento = None
        impacto_evento = 0

        if evento_especial:
            fecha_inicio_evento = st.date_input("Fecha de inicio del evento")
            fecha_fin_evento = st.date_input("Fecha de fin del evento")
            impacto_evento = st.slider("Incremento en demanda (%)", min_value=0, max_value=200, value=20, step=1)

    with st.expander("Tipo de Modelo de Forecast"):
        tipo_modelo = st.radio(
            "Selecciona el modelo de pronóstico:",
            options=["ARIMA", "Prophet"],
            index=0
        )

###################################
# Funciones de Forecast
###################################

def pronostico_arima(df: pd.DataFrame, steps: int = 30) -> pd.DataFrame:
    """
    Realiza un forecast (ARIMA) para la columna 'items'.
    Devuelve un DataFrame con las fechas y la predicción 'mean'.
    """
    df_temp = df.copy()
    # Aseguramos que 'Fecha' esté en el índice
    df_temp = df_temp.set_index("Fecha").sort_index()
    # Serie diaria de items
    series = df_temp["items"].resample("D").sum()

    # Ajustamos un modelo ARIMA(1,1,1) como ejemplo (se puede tunear)
    model = sm.tsa.arima.ARIMA(series, order=(1,1,1))
    results = model.fit()

    # Forecast para 'steps' días
    forecast_results = results.get_forecast(steps=steps)
    forecast_df = forecast_results.summary_frame()

    # Construimos el DataFrame final
    start_date = series.index[-1] + pd.Timedelta(days=1)
    pred_df = pd.DataFrame({
        "ds": pd.date_range(start=start_date, periods=steps, freq="D"),
        "yhat_arima": forecast_df["mean"]
    })
    return pred_df

def pronostico_prophet(df: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    """
    Realiza un forecast (Prophet) para la columna 'items'.
    Devuelve un DataFrame con ds, yhat, yhat_lower, yhat_upper.
    """
    df_temp = df.copy()
    # Prophet requiere columnas ds (fecha) e y (valor)
    df_temp = df_temp[["Fecha", "items"]].dropna()
    df_temp.columns = ["ds", "y"]

    # Creamos y ajustamos el modelo Prophet
    model = Prophet()
    model.fit(df_temp)

    # Construimos el futuro y realizamos el forecast
    future = model.make_future_dataframe(periods=days)
    forecast = model.predict(future)

    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]

###################################
# Lógica principal
###################################

def procesar_datos(df: pd.DataFrame) -> pd.DataFrame:
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)
    df["slot_from"] = pd.to_datetime(df["slot_from"], errors="coerce").dt.hour
    df = df[df["estado"] == "FINISHED"]
    df = df[(df["slot_from"] >= hora_apertura) & (df["slot_from"] <= hora_cierre)]
    df["day_of_week"] = df["Fecha"].dt.day_name().fillna("Desconocido")
    return df

def grafico1_historia(df_modelo: pd.DataFrame, modelo: str):
    st.subheader(f"Comportamiento Historico de demanda {modelo}")
    fig_hist = px.bar(
        df_modelo,
        x="Fecha",
        y="items",
        labels={"items": "Cantidad de Ítems", "Fecha": "Día"},
        color_discrete_sequence=["#19521b"],
        title="",
    )
    fig_hist.update_layout(font=CUSTOM_FONT, title_font_size=16)
    st.plotly_chart(fig_hist, use_container_width=True)

def grafico2_dia_semana(df_modelo: pd.DataFrame, modelo: str):
    st.subheader(f"Comportamiento Historico de demanda {modelo} por día de la semana")
    demanda_por_dia = df_modelo.groupby("day_of_week")["items"].sum().reset_index()
    conteo_por_dia = (
        df_modelo.groupby("day_of_week")["Fecha"]
        .nunique()
        .reset_index()
        .rename(columns={"Fecha": "Cant_dias"})
    )
    merge_dia = pd.merge(demanda_por_dia, conteo_por_dia, on="day_of_week", how="left")
    merge_dia["items_promedio"] = merge_dia["items"] / merge_dia["Cant_dias"].replace(0, 1)

    fig_dia = px.bar(
        merge_dia,
        x="day_of_week",
        y="items_promedio",
        labels={"items_promedio": "Ítems Promedio", "day_of_week": "Día de la Semana"},
        color_discrete_sequence=["#c7e59f"],
        title="",
    )
    fig_dia.update_layout(font=CUSTOM_FONT, title_font_size=16)
    st.plotly_chart(fig_dia, use_container_width=True)

def grafico3_preferencia_slot(df_modelo: pd.DataFrame, modelo: str):
    st.subheader(f"Preferencia de Slot - {modelo}")
    demanda_slot = df_modelo.groupby("slot_from")["items"].sum().reset_index()
    total_items = demanda_slot["items"].sum()
    if total_items == 0:
        demanda_slot["pct"] = 0
    else:
        demanda_slot["pct"] = (demanda_slot["items"] / total_items) * 100

    fig_slot = px.bar(
        demanda_slot,
        x="slot_from",
        y="pct",
        labels={"slot_from": "Hora del Día", "pct": "Porcentaje de Demanda"},
        color_discrete_sequence=["#1e9d51"],
        title="",
    )
    fig_slot.update_layout(font=CUSTOM_FONT, title_font_size=16)
    st.plotly_chart(fig_slot, use_container_width=True)

def tabla_pronostico(df_modelo: pd.DataFrame, modelo: str):
    st.subheader(f"Pronóstico de demanda - {modelo}")

    fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}

    for fecha in fechas_pronostico:
        day_of_week = fecha.weekday()
        df_same_day = df_modelo[df_modelo["Fecha"].dt.weekday == day_of_week]
        demanda_slot = df_same_day.groupby("slot_from")["items"].sum().fillna(0)

        # Evento especial
        if evento_especial and fecha_inicio_evento and fecha_fin_evento:
            if fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
                demanda_slot = demanda_slot * (1 + impacto_evento / 100)

        recursos_dia = (demanda_slot / productividad_estimada).fillna(1).apply(np.ceil).astype(int)
        recursos_dia = recursos_dia.apply(lambda x: max(x, 1))

        recursos_por_dia[fecha.strftime("%d/%m/%Y")] = recursos_dia

    pronostico_df = pd.DataFrame(recursos_por_dia).T.fillna(1).astype(int)
    horas = list(range(hora_apertura, hora_cierre + 1))
    for hora in horas:
        if hora not in pronostico_df.columns:
            pronostico_df[hora] = 1
    pronostico_df = pronostico_df[horas]
    st.dataframe(pronostico_df)

#######################
# NUEVAS FUNCIONES FORECAST
#######################
def forecast_arima(df: pd.DataFrame, steps:int=30) -> pd.DataFrame:
    """
    Genera un forecast de items (resample diario) usando ARIMA(1,1,1).
    Devuelve un DF con ds y yhat_arima.
    """
    import statsmodels.api as sm

    # Copiar y preparar la serie
    df_temp = df.copy()
    df_temp = df_temp.set_index("Fecha").sort_index()
    series = df_temp["items"].resample("D").sum()

    # ARIMA(1,1,1)
    model = sm.tsa.arima.ARIMA(series, order=(1,1,1))
    results = model.fit()

    forecast_res = results.get_forecast(steps=steps)
    summary_df = forecast_res.summary_frame()

    pred_df = pd.DataFrame({
        "ds": pd.date_range(start=series.index[-1] + pd.Timedelta(days=1), periods=steps, freq="D"),
        "yhat_arima": summary_df["mean"]
    })
    return pred_df

def forecast_prophet(df: pd.DataFrame, days:int=30) -> pd.DataFrame:
    """
    Genera un forecast de items (resample diario) usando Prophet.
    Devuelve un DF con ds, yhat, yhat_lower, yhat_upper.
    """
    from prophet import Prophet

    df_temp = df.copy()
    # Requerimos ds e y
    df_prophet = df_temp[["Fecha", "items"]].dropna()
    df_prophet.columns = ["ds", "y"]
    df_prophet = df_prophet.groupby("ds")["y"].sum().reset_index()

    model = Prophet()
    model.fit(df_prophet)

    future = model.make_future_dataframe(periods=days)
    forecast = model.predict(future)
    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]

#######################


def generar_analisis(df: pd.DataFrame):
    modelos_operativos = df["operational_model"].unique()

    # Ejemplo de usar Prophet/ARIMA luego del "procesar_datos"
    # 1) ARIMA
    st.subheader("Forecast ARIMA (demostración)")
    df_arima = forecast_arima(df, 30)
    st.dataframe(df_arima.head())

    # 2) Prophet
    st.subheader("Forecast Prophet (demostración)")
    df_prop = forecast_prophet(df, 30)
    st.dataframe(df_prop.head())

    for modelo in modelos_operativos:
        df_modelo = df[df["operational_model"] == modelo].copy()

        # LINEA 1: Grafico1 (izq) y Grafico2 (der)
        colA, colB = st.columns(2)
        with colA:
            grafico1_historia(df_modelo, modelo)
        with colB:
            grafico2_dia_semana(df_modelo, modelo)

        # LINEA 2: Grafico 3
        grafico3_preferencia_slot(df_modelo, modelo)

        # LINEA 3: Tabla pronóstico
        tabla_pronostico(df_modelo, modelo)

        st.markdown("---")


if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("Archivo cargado correctamente")
    st.dataframe(df.head())

    if st.button("Generar Análisis"):
        df = procesar_datos(df)
        generar_analisis(df)

st.write("Listo para generar reportes con In-Staffing!")
