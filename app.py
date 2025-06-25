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

########################################
# Cargar archivo
########################################
st.header("Cargar Archivo CSV")
archivo_csv = st.file_uploader("Sube un archivo de datos de operaciones (CSV)", type=["csv"])  # noqa: E501

########################################
# Sidebar – parámetros
########################################
with st.sidebar:
    with st.expander("Configuraciones Generales"):
        hora_apertura = st.slider("Hora de apertura de tienda", 0, 23, 8)
        hora_cierre = st.slider("Hora de cierre de tienda", 0, 23, 22)
        productividad_estimada = st.number_input(
            "Productividad Estimada por Hora", min_value=10, max_value=500, value=100, step=10
        )

        fecha_inicio_pronostico = st.date_input(
            "Fecha de inicio del pronóstico", datetime.now() + timedelta(days=1)
        )
        fecha_fin_pronostico = st.date_input(
            "Fecha de fin del pronóstico", fecha_inicio_pronostico + timedelta(days=30)
        )
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

    with st.expander("Extensión de los turnos"):
        col_h, col_m = st.columns(2)
        horas_turno = col_h.number_input("Horas", min_value=4, max_value=9, value=6, step=1)
        minutos_turno = col_m.number_input("Minutos", min_value=0, max_value=59, value=0, step=5)

        duracion_turno_min = horas_turno * 60 + minutos_turno
        if duracion_turno_min > 540:
            st.error("La duración no puede exceder 9 horas (540 min).")
            st.stop()
        turno_horas = math.ceil(duracion_turno_min / 60)  # para nombre en tabla

    with st.expander("Máximo de Recursos Disponibles"):
        max_recursos = st.number_input(
            "Tope máximo de recursos (vacío = sin tope)", min_value=0, value=0, step=1
        )
        if max_recursos == 0:
            max_recursos = None

########################################
# Utilidades – mapeo de columnas multinlingüe
########################################
COLUMN_ALIASES = {
    "Fecha": ["Fecha", "Data", "Date"],
    "items": ["items", "Itens", "itens", "Items"],
    "estado": ["estado", "status", "Status"],
    "slot_from": [
        "slot_from",
        "slotfrom",
        "slot",
        "hora_slot",
        "slot_inicio",
        "slot início",
    ],
    "operational_model": [
        "operational_model",
        "modelo_operacional",
        "Modelo Operacional",
        "modelo",
    ],
}

REQUIRED_COLS = list(COLUMN_ALIASES.keys())


def estandarizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas con base en aliases y valida requeridos."""
    alias_map = {}
    for std_col, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in df.columns and std_col not in df.columns:
                alias_map[a] = std_col
                break

    df = df.rename(columns=alias_map)

    faltantes = [c for c in REQUIRED_COLS if c not in df.columns]
    if faltantes:
        st.error(
            f"Faltan columnas requeridas: {faltantes}.\n"
            f"Columnas encontradas: {list(df.columns)}"
        )
        st.stop()
    return df

########################################
# Funciones Principales
########################################

def procesar_datos(df: pd.DataFrame) -> pd.DataFrame:
    df = estandarizar_columnas(df)

    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)
    df["slot_from"] = pd.to_datetime(df["slot_from"], errors="coerce").dt.hour.fillna(0).astype(int)

    df = df[df["estado"].str.upper() == "FINISHED"]
    df = df[(df["slot_from"] >= hora_apertura) & (df["slot_from"] <= hora_cierre)]

    # Mapeo de weekday a español y orden
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

    DIAS_ORDENADOS = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    ]
    df["day_of_week"] = pd.Categorical(df["day_of_week"], categories=DIAS_ORDENADOS, ordered=True)
    return df

# -------------- (todas las demás funciones sin cambios) --------------
# ... por brevedad no se muestran aquí, pero permanecen idénticas
# a tu versión anterior (gráficos, pronósticos, asignación de turnos,
# generación de análisis y llamada desde el botón)

########################################
# Ejecución principal
########################################

if archivo_csv is not None:
    df_raw = pd.read_csv(archivo_csv)
    st.success("Archivo cargado correctamente")
    st.dataframe(df_raw.head())

    if st.button("Generar Análisis"):
        df_clean = procesar_datos(df_raw)
        generar_analisis(df_clean)

st.write("¡Listo para generar reportes con In-Staffing!")
