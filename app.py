import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# Ajuste de fuente para Plotly
CUSTOM_FONT = dict(family="Roboto", size=12)

# Mapeo de días de la semana para un orden y traducción correctos
DIAS_ORDENADOS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
dias_map = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo"
}

st.set_page_config(page_title="In-Staffing MVP", layout="wide")
os.makedirs("reports", exist_ok=True)

st.title("In-Staffing: Planificación de Recursos")
st.markdown("---")

st.header("Cargar Archivo CSV")
archivo_csv = st.file_uploader("Sube un archivo de datos de operaciones (CSV)", type=["csv"])

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

    # Convertir el weekday (0-6) a texto en español (lunes-domingo)
    df["weekday_num"] = df["Fecha"].dt.weekday
    df["day_of_week"] = df["weekday_num"].map(dias_map).fillna("Desconocido")

    # Convertir a categoría ordenada para graficar en orden (Lunes a Domingo)
    df["day_of_week"] = pd.Categorical(df["day_of_week"], categories=DIAS_ORDENADOS, ordered=True)

    return df

def grafico1_historia(df_modelo: pd.DataFrame, modelo: str):
    """Gráfico de barras color #19521bff con la demanda histórica por día."""
    st.subheader(f"Comportamiento histórico de demanda {modelo}")
    fig_hist = px.bar(
        df_modelo,
        x="Fecha",
        y="items",
        labels={"items": "Cantidad de Ítems", "Fecha": "Día"},
        color_discrete_sequence=["#19521b"],  # #19521bff
        title="",
    )
    fig_hist.update_layout(font=CUSTOM_FONT, title_font_size=16)
    st.plotly_chart(fig_hist, use_container_width=True)

def grafico2_dia_semana(df_modelo: pd.DataFrame, modelo: str):
    """
    Gráfico de barras color #c7e59fff con la demanda promedio de ítems por día de la semana.
    Se basa en el total de ítems del día de la semana / cantidad de ese día encontrado.
    """
    st.subheader(f"Comportamiento histórico de demanda {modelo} por día de la semana")
    demanda_por_dia = df_modelo.groupby("day_of_week")["items"].sum().reset_index()

    # Cuántos días de la semana hay
    conteo_por_dia = df_modelo.groupby("day_of_week")["Fecha"].nunique().reset_index().rename(columns={"Fecha": "Cant_dias"})
    merge_dia = pd.merge(demanda_por_dia, conteo_por_dia, on="day_of_week", how="left")

    # Ítems promedio
    merge_dia["items_promedio"] = merge_dia["items"] / merge_dia["Cant_dias"].replace(0, 1)

    fig_dia = px.bar(
        merge_dia,
        x="day_of_week",
        y="items_promedio",
        labels={"items_promedio": "Ítems promedio", "day_of_week": "Día de la semana"},
        color_discrete_sequence=["#c7e59f"],
        title="",
        category_orders={"day_of_week": DIAS_ORDENADOS},  # Asegura el orden de lunes a domingo
    )
    fig_dia.update_layout(font=CUSTOM_FONT, title_font_size=16)
    st.plotly_chart(fig_dia, use_container_width=True)

def grafico3_preferencia_slot(df_modelo: pd.DataFrame, modelo: str):
    """Gráfico de barras color #1e9d51ff con % de items por slot."""
    st.subheader(f"Preferencia de slot - {modelo}")
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
        labels={"slot_from": "Hora del día", "pct": "Porcentaje de demanda"},
        color_discrete_sequence=["#1e9d51"],
        title="",
    )
    fig_slot.update_layout(font=CUSTOM_FONT, title_font_size=16)
    st.plotly_chart(fig_slot, use_container_width=True)

def tabla_pronostico(df_modelo: pd.DataFrame, modelo: str):
    """
    Genera la tabla de pronóstico de recursos por día (fecha_inicio_pronostico a fecha_fin_pronostico)
    con filas = fechas y columnas = horas (hora_apertura a hora_cierre).
    """
    st.subheader(f"Pronóstico de demanda - {modelo}")
    fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}

    # Precalcular info para evitar picos
    # Agrupamos por (weekday_num, slot_from). Suma total de items en el histórico
    df_modelo["weekday_num"] = df_modelo["Fecha"].dt.weekday
    sum_items = df_modelo.groupby(["weekday_num", "slot_from"])["items"].sum().reset_index()
    # Cantidad de días en el histórico para un weekday_num
    days_count = df_modelo.groupby("weekday_num")["Fecha"].apply(lambda x: x.dt.date.nunique()).reset_index().rename(columns={"Fecha": "Cant_dias"})

    # Pivot para tener slot_from en columnas
    pivot_sum = sum_items.pivot(index="weekday_num", columns="slot_from", values="items").fillna(0)
    days_count_dict = dict(zip(days_count["weekday_num"], days_count["Cant_dias"]))

    for fecha in fechas_pronostico:
        wd = fecha.weekday()
        ndias = days_count_dict.get(wd, 1)

        if wd not in pivot_sum.index:
            # Sin datos para este day_of_week => asignar 1 item
            base_items = pd.Series(1, index=pivot_sum.columns)
        else:
            base_items = pivot_sum.loc[wd].copy()
            base_items = base_items / max(ndias, 1)

        if evento_especial and fecha_inicio_evento and fecha_fin_evento:
            if fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
                base_items = base_items * (1 + impacto_evento / 100)

        # Convertimos a recursos
        recursos_dia = (base_items / productividad_estimada).fillna(1).apply(np.ceil).astype(int)
        recursos_dia = recursos_dia.apply(lambda x: max(x, 1))

        recursos_por_dia[fecha.strftime("%d/%m/%Y")] = recursos_dia

    pronostico_df = pd.DataFrame(recursos_por_dia).T
    if not pronostico_df.empty:
        horas = list(range(hora_apertura, hora_cierre + 1))
        for hora in horas:
            if hora not in pronostico_df.columns:
                pronostico_df[hora] = 1
        pronostico_df = pronostico_df[horas]

    st.dataframe(pronostico_df.fillna(1).astype(int))

def generar_analisis(df: pd.DataFrame):
    """Genera para cada modelo operativo las 3 gráficas y la tabla de pronóstico."""
    modelos_operativos = df["operational_model"].unique()

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
