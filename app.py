# app.py
# ──────────────────────────────────────────────────────────────
# MVP "In-Staffing" – versión demo con:
#  1) Tabla de turnos mostrada primero
#  2) Duración de turno en horas + minutos (4-9 h)
#  3) Máximo de recursos disponibles y alerta UnderStaff
# ──────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from math import ceil

st.set_page_config(page_title="In-Staffing MVP", layout="wide")

st.title("In-Staffing: Planificación de Recursos")
st.markdown("Carga tu archivo CSV para generar el plan de turnos.")

# ════════════════════════════════════════
# Barra lateral – parámetros de usuario
# ════════════════════════════════════════
with st.sidebar:
    st.header("Configuraciones Generales")

    productividad = st.number_input(
        "Productividad estimada (pedidos por persona por hora)",
        min_value=1, max_value=1000, value=10, step=1
    )

    st.subheader("Duración de turno")
    horas_turno = st.number_input("Horas", min_value=4, max_value=9, value=6, step=1)
    minutos_turno = st.number_input("Minutos", min_value=0, max_value=59, value=0, step=1)
    duracion_turno = horas_turno + minutos_turno / 60

    if duracion_turno < 4 or duracion_turno > 9:
        st.error("La duración del turno debe estar entre 4 h y 9 h.")
        st.stop()

    max_recursos = st.number_input(
        "Máx. recursos disponibles (0 = sin tope)",
        min_value=0, max_value=10_000, value=0, step=1
    )
    if max_recursos == 0:
        max_recursos = None

# ════════════════════════════════════════
# Carga del archivo
# ════════════════════════════════════════
archivo_csv = st.file_uploader("Sube un archivo CSV", type=["csv"])

def leer_datos(archivo) -> pd.DataFrame:
    """Devuelve DataFrame con columnas ['hora', 'demanda']"""
    df = pd.read_csv(archivo)
    # Aseguramos tipos
    df["hora"] = df["hora"].astype(int)
    df["demanda"] = df["demanda"].astype(float)
    return df

def calcular_recursos(df: pd.DataFrame, productividad: int) -> pd.DataFrame:
    """Añade columna 'recursos_necesarios' redondeada hacia arriba."""
    df = df.copy()
    df["recursos_necesarios"] = np.ceil(df["demanda"] / productividad).astype(int)
    return df

def construir_turnos(df: pd.DataFrame,
                     duracion: float,
                     max_rec: int | None = None) -> tuple[pd.DataFrame, bool]:
    """
    Crea tabla 'Sistema de Turnos – Recursos Totales'.
    Devuelve (df_turnos, under_staff_bool).
    Estrategia simple: usar el pico máximo de la demanda.
    """
    pico = int(df["recursos_necesarios"].max())
    requerido = pico
    under_staff = False

    if max_rec is not None and pico > max_rec:
        requerido = max_rec
        under_staff = True

    turnos = pd.DataFrame({
        "Turno": ["Turno 1"],
        "Duración (horas)": [round(duracion, 2)],
        "Recursos Asignados": [requerido]
    })
    return turnos, under_staff

def tabla_pronostico(df_modelo: pd.DataFrame) -> pd.DataFrame:
    """
    Placeholder para pronóstico/detalle adicional.
    Ahora mismo replica recursos necesarios.
    """
    return df_modelo.copy()

# ════════════════════════════════════════
# Ejecución principal
# ════════════════════════════════════════
if archivo_csv:
    try:
        df_base = leer_datos(archivo_csv)
    except Exception as e:
        st.error(f"Error leyendo el archivo: {e}")
        st.stop()

    df_proc = calcular_recursos(df_base, productividad)

    df_turnos, under_staff = construir_turnos(
        df_proc, duracion_turno, max_recursos
    )

    # ─── 1) Mostrar primero la tabla de turnos ─────────────────
    st.subheader("📋 Sistema de Turnos – Recursos Totales")
    st.dataframe(df_turnos, hide_index=True)

    if under_staff:
        st.warning(
            "⚠️  La demanda requiere más personal del disponible. "
            "Apareces *UnderStaff* para el pico de actividad."
        )

    # ─── 2) Resto del análisis ─────────────────────────────────
    with st.expander("Detalles hora a hora"):
        st.dataframe(df_proc, hide_index=True)

        # Gráfico
        fig, ax = plt.subplots()
        ax.bar(df_proc["hora"], df_proc["recursos_necesarios"])
        ax.set_xlabel("Hora del día")
        ax.set_ylabel("Recursos necesarios")
        ax.set_title("Recursos necesarios por hora")
        st.pyplot(fig)

    # ─── 3) Pronóstico / tabla adicional (placeholder) ─────────
    with st.expander("Tabla de Pronóstico (demo)"):
        st.dataframe(tabla_pronostico(df_proc), hide_index=True)

else:
    st.info("📄 Sube un archivo CSV para comenzar el análisis.")
