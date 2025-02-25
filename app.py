import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

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


def procesar_datos(df: pd.DataFrame) -> pd.DataFrame:
    """ Prepara el DataFrame y filtra los pedidos FINISHED y las horas dentro del rango. """
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)
    df["slot_from"] = pd.to_datetime(df["slot_from"], errors="coerce").dt.hour
    df = df[df["estado"] == "FINISHED"]
    df = df[(df["slot_from"] >= hora_apertura) & (df["slot_from"] <= hora_cierre)]
    df["day_of_week"] = df["Fecha"].dt.day_name().fillna("Desconocido")
    return df

def grafico1_historia(df_modelo: pd.DataFrame, modelo: str):
    """Gráfico de barras color #19521bff con la demanda histórica por día."""
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
    """Gráfico de barras color #c7e59fff con la demanda promedio de ítems por día de la semana."""
    st.subheader(f"Comportamiento Historico de demanda {modelo} por día de la semana")
    # Sumamos la cantidad de items por cada día de la semana
    demanda_por_dia = df_modelo.groupby("day_of_week")["items"].sum().reset_index()

    # Calculamos cuántos días hay de cada day_of_week para hacer un promedio correcto
    conteo_por_dia = (
        df_modelo.groupby("day_of_week")["Fecha"]
        .nunique()
        .reset_index()
        .rename(columns={"Fecha": "Cant_dias"})
    )
    merge_dia = pd.merge(demanda_por_dia, conteo_por_dia, on="day_of_week", how="left")

    # Dividimos total de ítems de cada día de la semana entre la cantidad de días que aparezcan en el archivo
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
    """Gráfico de barras color #1e9d51ff con % de items por slot."""
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
    """
    Tabla de pronóstico para los días en [fecha_inicio_pronostico, fecha_fin_pronostico].
    Se basa en la lógica:
      - Identificamos el day_of_week del día a pronosticar
      - Buscamos en df_modelo todos los registros con ese day_of_week
      - Sumamos items por slot
      - Dividimos por la cantidad de días de esa semana que tengamos en el histórico => items promedio
      - Aplica multiplicador de evento especial
      - Divide por productividad_estimada para obtener # de recursos
    """
    st.subheader(f"Pronóstico de demanda - {modelo}")

    fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}

    # Precalcular day_of_week, sum items por slot, conteo de días
    # De esta forma evitamos sumas exageradas
    df_modelo["weekday_number"] = df_modelo["Fecha"].dt.weekday
    # Suma de items por (weekday_number, slot_from)
    sum_items = df_modelo.groupby(["weekday_number", "slot_from"])["items"].sum().reset_index()
    # Conteo de días distintos por weekday_number
    days_count = (
        df_modelo.groupby("weekday_number")["Fecha"].apply(lambda x: x.dt.date.nunique())
        .reset_index()
        .rename(columns={"Fecha": "Cant_dias"})
    )

    # Convertimos a un pivot para más fácil acceso
    pivot_sum = sum_items.pivot(index="weekday_number", columns="slot_from", values="items").fillna(0)

    # Diccionario con la cantidad de días por weekday_number
    days_count_dict = dict(zip(days_count["weekday_number"], days_count["Cant_dias"]))

    for fecha in fechas_pronostico:
        # Sacamos el weekday_number
        wd = fecha.weekday()
        # Revisamos cuántos días hay en el histórico
        ndias = days_count_dict.get(wd, 1)

        if wd not in pivot_sum.index:
            # Si no tenemos datos para ese weekday, asignamos 1 a todo
            base_items = pd.Series(1, index=pivot_sum.columns)
        else:
            # Tomamos la fila con sums de items por slot
            base_items = pivot_sum.loc[wd].copy()
            # Dividimos por la cantidad de días de ese weekday
            base_items = base_items / max(ndias, 1)

        # Aplica evento especial
        if evento_especial and fecha_inicio_evento and fecha_fin_evento:
            if fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
                base_items = base_items * (1 + impacto_evento / 100)

        # Convertimos a recursos
        recursos_dia = (base_items / productividad_estimada).fillna(1).apply(np.ceil).astype(int)
        # Mínimo 1 recurso
        recursos_dia = recursos_dia.apply(lambda x: max(x, 1))

        recursos_por_dia[fecha.strftime("%d/%m/%Y")] = recursos_dia

    pronostico_df = pd.DataFrame(recursos_por_dia).T
    if not pronostico_df.empty:
        # Aseguramos que las columnas correspondan a las horas de apertura y cierre
        horas = list(range(hora_apertura, hora_cierre + 1))
        for hora in horas:
            if hora not in pronostico_df.columns:
                pronostico_df[hora] = 1
        pronostico_df = pronostico_df[horas]

    st.dataframe(pronostico_df.fillna(1).astype(int))

def generar_analisis(df: pd.DataFrame):
    """Genera las 3 gráficas y la tabla para cada modelo operativo."""
    modelos_operativos = df["operational_model"].unique()

    for modelo in modelos_operativos:
        # Filtramos para el modelo
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


#### EJECUCIÓN PRINCIPAL
if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("Archivo cargado correctamente")
    st.dataframe(df.head())

    if st.button("Generar Análisis"):
        df = procesar_datos(df)
        generar_analisis(df)

st.write("Listo para generar reportes con In-Staffing!")
