import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
import math
from datetime import datetime, timedelta

########################################
# Estilo y Ajustes
########################################
CUSTOM_FONT = dict(family="Roboto", size=12)

########################################
# Configuración de la aplicación
########################################
st.set_page_config(page_title="In-Staffing MVP", layout="wide")
os.makedirs("reports", exist_ok=True)

st.title("In-Staffing: Planificación de Recursos")
st.markdown("---")

st.header("Cargar Archivo CSV")
archivo_csv = st.file_uploader(
    "Sube un archivo de datos de operaciones (CSV)",
    type=["csv"],
    help="Admite encabezados en Español, Inglés o Portugués",
)

########################################
# Sidebar – Parámetros
########################################
with st.sidebar:
    with st.expander("Configuraciones Generales", expanded=True):
        hora_apertura = st.slider("Hora de apertura de tienda", 0, 23, 8)
        hora_cierre = st.slider("Hora de cierre de tienda", 0, 23, 22)
        productividad_estimada = st.number_input(
            "Productividad Estimada por Hora", min_value=10, max_value=500, value=100, step=10
        )

        # Fechas de pronóstico
        fecha_inicio_pronostico = st.date_input(
            "Fecha de inicio del pronóstico", datetime.now() + timedelta(days=1)
        )
        fecha_fin_pronostico = st.date_input(
            "Fecha de fin del pronóstico", fecha_inicio_pronostico + timedelta(days=30)
        )
        if (fecha_fin_pronostico - fecha_inicio_pronostico).days > 30:
            st.error("El periodo del pronóstico no puede ser mayor a 30 días.")

        # Máximo de recursos disponibles
        max_recursos = st.number_input(
            "Máximo de recursos disponibles en tienda (opcional)",
            min_value=1,
            step=1,
            value=None,
            placeholder="Sin tope",
        )

    with st.expander("Evento Especial"):
        evento_especial = st.checkbox("¿Habrá un evento especial?")
        fecha_inicio_evento = None
        fecha_fin_evento = None
        impacto_evento = 0

        if evento_especial:
            fecha_inicio_evento = st.date_input("Fecha de inicio del evento")
            fecha_fin_evento = st.date_input("Fecha de fin del evento")
            impacto_evento = st.slider(
                "Incremento en demanda (%)", min_value=0, max_value=200, value=20, step=1
            )

    with st.expander("Extensión de los turnos", expanded=True):
        col_h, col_m = st.columns(2)
        horas_turno = col_h.number_input("Horas", min_value=4, max_value=9, step=1, value=6)
        minutos_turno = col_m.number_input("Minutos", min_value=0, max_value=59, step=1, value=0)
        duracion_turno_min = horas_turno * 60 + minutos_turno
        if duracion_turno_min > 540:
            st.error("La duración no puede exceder 9 horas (540 min).")

########################################
# Mapeo de nombres de columnas (ES‑EN‑PT)
########################################
ALT_COLS = {
    "Fecha": ["Fecha", "Data", "Date", "fecha", "data"],
    "items": ["items", "Itens", "itens"],
    "slot_from": [
        "slot_from",
        "Início de Slot de Entrega",
        "Inicio de Slot",
        "Início de Slot",
    ],
    "estado": ["estado", "Status", "status"],
    "operational_model": ["operational_model", "Modelo Operacional", "modelo_operacional"],
}


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas variables al estándar interno."""
    renames = {}
    for canon, posibles in ALT_COLS.items():
        for p in posibles:
            if p in df.columns:
                renames[p] = canon
                break
    df = df.rename(columns=renames)
    return df


########################################
# Funciones Principales
########################################

def procesar_datos(df: pd.DataFrame) -> pd.DataFrame:
    df = normalizar_columnas(df)

    # Comprobación de columnas requeridas
    required = ["Fecha", "items", "slot_from", "estado"]
    faltantes = [c for c in required if c not in df.columns]
    if faltantes:
        st.error(f"Faltan las columnas esperadas: {', '.join(faltantes)}")
        st.stop()

    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)

    # slot_from puede ser datetime o texto HH:MM
    if pd.api.types.is_datetime64_any_dtype(df["slot_from"]):
        df["slot_from"] = df["slot_from"].dt.hour
    else:
        df["slot_from"] = (
            pd.to_datetime(df["slot_from"], errors="coerce").dt.hour.fillna(-1).astype(int)
        )

    # Filtrado por estado terminado
    df = df[df["estado"].str.upper() == "FINISHED"]
    # Filtrado por rango horario tienda
    df = df[(df["slot_from"] >= hora_apertura) & (df["slot_from"] <= hora_cierre)]

    # Día de la semana en español
    dias_map = {
        0: "Lunes",
        1: "Martes",
        2: "Miércoles",
        3: "Jueves",
        4: "Viernes",
        5: "Sábado",
        6: "Domingo",
    }
    df["weekday_num"] = df["Fecha"].dt.weekday
    df["day_of_week"] = df["weekday_num"].map(dias_map).fillna("Desconocido")
    df["day_of_week"] = pd.Categorical(df["day_of_week"], categories=list(dias_map.values()), ordered=True)

    # Asegurar columna operational_model
    if "operational_model" not in df.columns:
        df["operational_model"] = "General"
    else:
        df["operational_model"].fillna("General", inplace=True)

    return df


def grafico1_historia(df_modelo: pd.DataFrame, modelo: str):
    st.subheader(f"Comportamiento histórico de demanda {modelo}")
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
    st.subheader(f"Comportamiento histórico de demanda {modelo} por día de la semana")
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
        labels={"items_promedio": "Ítems Promedio", "day_of_week": "Día de la semana"},
        color_discrete_sequence=["#c7e59f"],
        title="",
        category_orders={"day_of_week": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]},
    )
    fig_dia.update
