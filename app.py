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
archivo_csv = st.file_uploader("Sube un archivo de datos de operaciones (CSV)", type=["csv"])

with st.sidebar:
    with st.expander("Configuraciones Generales"):
        hora_apertura = st.slider("Hora de apertura de tienda", 0, 23, 8)
        hora_cierre = st.slider("Hora de cierre de tienda", 0, 23, 22)
        productividad_estimada = st.number_input("Productividad Estimada por Hora", min_value=10, max_value=500, value=100, step=10)

        fecha_inicio_pronostico = st.date_input("Fecha de inicio del pronóstico", datetime.now() + timedelta(days=1))
        fecha_fin_pronostico = st.date_input("Fecha de fin del pronóstico", fecha_inicio_pronostico + timedelta(days=30))
        if (fecha_fin_pronostico - fecha_inicio_pronostico).days > 30:
            st.error("El periodo del pronóstico no puede ser mayor a 30 días.")

        max_recursos_disponibles = st.number_input(
            "Máximo de recursos disponibles (0 = sin tope)",
            min_value=0,
            step=1,
            value=0,
            help="Si la tienda sólo cuenta con un número fijo de recursos, indíquelo aquí para recibir advertencias de Under/Over‑Staff.")

    with st.expander("Evento Especial"):
        evento_especial = st.checkbox("¿Habrá un evento especial?")
        fecha_inicio_evento = None
        fecha_fin_evento = None
        impacto_evento = 0

        if evento_especial:
            fecha_inicio_evento = st.date_input("Fecha de inicio del evento")
            fecha_fin_evento = st.date_input("Fecha de fin del evento")
            impacto_evento = st.slider("Incremento en demanda (%)", min_value=0, max_value=200, value=20, step=1)

    with st.expander("Extensión del turno"):
        col_h, col_m = st.columns(2)
        turno_horas = col_h.number_input("Horas", min_value=4, max_value=9, value=6, step=1)
        turno_minutos = col_m.number_input("Minutos", min_value=0, max_value=59, value=0, step=1)
        duracion_turno_min = int(turno_horas * 60 + turno_minutos)
        if duracion_turno_min < 240 or duracion_turno_min > 540:
            st.error("La duración total debe estar entre 4 y 9 horas (inclusive).")

########################################
# Funciones Principales
########################################

def procesar_datos(df: pd.DataFrame) -> pd.DataFrame:
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)
    df["slot_from"] = pd.to_datetime(df["slot_from"], errors="coerce").dt.hour
    df = df[df["estado"] == "FINISHED"]
    df = df[(df["slot_from"] >= hora_apertura) & (df["slot_from"] <= hora_cierre)]

    # Mapeo de weekday a español y orden
    dias_map = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    df["weekday_num"] = df["Fecha"].dt.weekday
    df["day_of_week"] = df["weekday_num"].map(dias_map).fillna("Desconocido")

    DIAS_ORDENADOS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    df["day_of_week"] = pd.Categorical(df["day_of_week"], categories=DIAS_ORDENADOS, ordered=True)
    return df

# ----- GRÁFICAS Y TABLAS (sin cambios en lógica) ----- #
# ... (se conserva tu lógica original de gráficos y pronósticos)

########################################
# Nuevas funciones para turnos flexibles y alertas
########################################

def asignar_turnos(df_recursos: pd.DataFrame, duracion_min: int) -> pd.DataFrame:
    """Genera sistema de turnos con duración flexible (min)."""
    resultados = []
    bloque_horas = math.ceil(duracion_min / 60)  # nº de horas completas que cubre el turno

    for fecha_idx in df_recursos.index:
        fila = df_recursos.loc[fecha_idx]
        horas_orden = sorted(fila.index, key=lambda x: int(x))
        i = 0
        while i < len(horas_orden):
            start_h = int(horas_orden[i])
            end_h = min(start_h + bloque_horas - 1, int(horas_orden[-1]))
            subset_hours = [h for h in horas_orden if start_h <= int(h) <= end_h]
            max_recs = int(fila[subset_hours].max())

            # Etiqueta de turno con minutos exactos
            hora_inicio_lbl = f"{start_h:02d}:00"
            fecha_dummy = datetime(2000, 1, 1, start_h, 0)
            hora_fin_lbl = (fecha_dummy + timedelta(minutes=duracion_min - 1)).strftime("%H:%M")

            turno_info = {
                "Fecha": fecha_idx,
                "Turno": f"{hora_inicio_lbl} - {hora_fin_lbl}",
                "Recursos": max_recs,
            }
            resultados.append(turno_info)
            i += len(subset_hours)
    return pd.DataFrame(resultados)

########################################
# Generar análisis (reordenado para mostrar turnos primero)
########################################

def generar_analisis(df: pd.DataFrame, duracion_turno_min: int, max_recursos: int):
    # Placeholder para que la tabla final aparezca PRIMERO
    turnos_container = st.container()
    tablas_por_modelo = {}

    # 1) Pronósticos por modelo (se mantiene tu lógica, sin gráficos aún)
    modelos_operativos = df["operational_model"].unique()
    for modelo in modelos_operativos:
        df_modelo = df[df["operational_model"] == modelo].copy()
        pron_df = tabla_pronostico(df_modelo, modelo)  # Usa tu función original
        tablas_por_modelo[modelo] = pron_df

    # 2) Consolidar recursos y crear sistema de turnos
    if len(tablas_por_modelo) > 1:
        df_suma = unir_tablas_recursos(tablas_por_modelo)
    else:
        df_suma = list(tablas_por_modelo.values())[0]

    df_turnos = asignar_turnos(df_suma, duracion_turno_min)

    # -- Advertencias Under / Over Staff --
    if max_recursos > 0:
        total_req = df_turnos["Recursos"].sum()
        if total_req > max_recursos:
            st.warning(f"⚠️ UnderStaff: se requieren {total_req} recursos y el máximo configurado es {max_recursos}.")
        elif total_req < max_recursos:
            st.info(f"ℹ️ OverStaff: se requieren {total_req} recursos de un máximo de {max_recursos}.")

    # 3) Mostrar la tabla de turnos **antes** de los gráficos
    with turnos_container:
        st.subheader("Sistema de Turnos – Recursos Totales")
        st.dataframe(df_turnos)

    st.markdown("---")

    # 4) Gráficos y detalles por modelo (tu lógica original)
    for modelo in modelos_operativos:
        df_modelo = df[df["operational_model"] == modelo].copy()
        colA, colB = st.columns(2)
        with colA:
            grafico1_historia(df_modelo, modelo)
        with colB:
            grafico2_dia_semana(df_modelo, modelo)
        grafico3_preferencia_slot(df_modelo, modelo)
        st.markdown("---")

########################################
# Ejecución principal
########################################
if archivo_csv is not None:
    df_original = pd.read_csv(archivo_csv)
    st.success("Archivo cargado correctamente")
    st.dataframe(df_original.head())

    if st.button("Generar Análisis"):
        df_proc = procesar_datos(df_original)
        generar_analisis(df_proc, duracion_turno_min, max_recursos_disponibles)

st.write("¡Listo para generar reportes con In-Staffing!")

