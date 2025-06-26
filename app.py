import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
import math
from datetime import datetime, timedelta

########################################
# Estilo y Ajustes globales
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
# Carga del archivo CSV
########################################
st.header("Cargar Archivo CSV")
archivo_csv = st.file_uploader(
    "Sube un archivo de datos de operaciones (CSV)", type=["csv"]
)

########################################
# Sidebar – parámetros
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
        fecha_inicio_evento, fecha_fin_evento, impacto_evento = None, None, 0
        if evento_especial:
            fecha_inicio_evento = st.date_input("Fecha de inicio del evento")
            fecha_fin_evento = st.date_input("Fecha de fin del evento")
            impacto_evento = st.slider(
                "Incremento en demanda (%)", min_value=0, max_value=200, value=20, step=1
            )

    with st.expander("Extensión de los turnos"):
        col_h, col_m = st.columns(2)
        horas_turno = col_h.number_input("Horas", min_value=4, max_value=9, value=6, step=1)
        minutos_turno = col_m.number_input("Minutos", min_value=0, max_value=59, value=0, step=5)

        duracion_turno_min = int(horas_turno) * 60 + int(minutos_turno)
        if duracion_turno_min > 540:
            st.error("La duración no puede exceder 9 horas (540 min).")
            st.stop()
        turno_horas_label = f"{horas_turno}h {minutos_turno}m"

    with st.expander("Máximo de Recursos Disponibles"):
        max_recursos_val = st.number_input(
            "Tope máximo de recursos (0 = sin tope)", min_value=0, value=0, step=1
        )
        max_recursos = max_recursos_val if max_recursos_val > 0 else None

########################################
# Mapeo multilingüe de columnas
########################################
COLUMN_ALIASES = {
    "Fecha": ["Fecha", "Data", "Date"],
    "items": ["items", "Itens", "itens", "Items"],
    "estado": ["estado", "status", "Status"],
    "slot_from": [
        "slot_from", "slotfrom", "slot", "hora_slot",
        "slot_inicio", "slot início",
        "Início de Slot de Entrega", "Inicio de Slot de Entrega"
    ],
    "operational_model": [
        "operational_model", "modelo_operacional", "Modelo Operacional", "modelo"
    ],
}
REQUIRED_COLS = list(COLUMN_ALIASES.keys())

def estandarizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    alias_map = {}
    for std_col, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in df.columns and std_col not in df.columns:
                alias_map[a] = std_col
                break
    df = df.rename(columns=alias_map)
    faltantes = [c for c in REQUIRED_COLS if c not in df.columns]
    if faltantes:
        st.error(f"Faltan columnas requeridas: {faltantes}. Actualmente: {list(df.columns)}")
        st.stop()
    return df

########################################
# Funciones de análisis y visualización
########################################
def procesar_datos(df: pd.DataFrame) -> pd.DataFrame:
    df = estandarizar_columnas(df)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)
    df["slot_from"] = pd.to_datetime(df["slot_from"], errors="coerce").dt.hour.fillna(0).astype(int)
    df = df[df["estado"].str.upper() == "FINISHED"]
    df = df[(df["slot_from"] >= hora_apertura) & (df["slot_from"] <= hora_cierre)]

    dias_map = {0:"Lunes",1:"Martes",2:"Miércoles",3:"Jueves",4:"Viernes",5:"Sábado",6:"Domingo"}
    df["weekday_num"] = df["Fecha"].dt.weekday
    df["day_of_week"] = df["weekday_num"].map(dias_map)
    return df

def grafico1_historia(df_modelo, modelo):
    st.subheader(f"Comportamiento histórico – {modelo}")
    fig = px.bar(df_modelo, x="Fecha", y="items",
                 labels={"items":"Ítems"}, color_discrete_sequence=["#19521b"])
    fig.update_layout(font=CUSTOM_FONT)
    st.plotly_chart(fig, use_container_width=True)

def grafico2_dia_semana(df_modelo, modelo):
    st.subheader(f"Demanda por día – {modelo}")
    demanda = (
        df_modelo.groupby("day_of_week")["items"].mean()
        .reindex(index=["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"])
        .reset_index()
    )
    fig = px.bar(demanda, x="day_of_week", y="items",
                 labels={"items":"Ítems promedio"},
                 color_discrete_sequence=["#c7e59f"])
    fig.update_layout(font=CUSTOM_FONT)
    st.plotly_chart(fig, use_container_width=True)

def grafico3_preferencia_slot(df_modelo, modelo):
    st.subheader(f"Preferencia de slot – {modelo}")
    datos = df_modelo.groupby("slot_from")["items"].sum().reset_index()
    datos["pct"] = datos["items"] / datos["items"].sum() * 100
    fig = px.bar(datos, x="slot_from", y="pct",
                 labels={"slot_from":"Hora","pct":"% demanda"},
                 color_discrete_sequence=["#1e9d51"])
    fig.update_layout(font=CUSTOM_FONT)
    st.plotly_chart(fig, use_container_width=True)

def tabla_pronostico(df_modelo, modelo):
    st.subheader(f"Pronóstico – {modelo}")
    fechas_rango = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}
    sum_items = df_modelo.groupby(["weekday_num","slot_from"])["items"].sum().reset_index()
    days_count = df_modelo.groupby("weekday_num")["Fecha"]\
        .apply(lambda x: x.dt.date.nunique())\
        .reset_index(name="Cant_dias")
    pivot_sum = sum_items.pivot(index="weekday_num", columns="slot_from", values="items").fillna(0)
    days_dict = dict(zip(days_count["weekday_num"], days_count["Cant_dias"]))

    for fecha in fechas_rango:
        wd = fecha.weekday()
        ndias = days_dict.get(wd,1)
        base = pivot_sum.loc[wd] / ndias if wd in pivot_sum.index else pd.Series(1, index=pivot_sum.columns)
        if evento_especial and fecha_inicio_evento and fecha_fin_evento and \
           fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
            base *= (1 + impacto_evento/100)
        recursos = (base / productividad_estimada).fillna(1).apply(np.ceil).astype(int)
        recursos = recursos.apply(lambda x: max(x,1))
        recursos_por_dia[fecha.strftime("%d/%m/%Y")] = recursos

    pron_df = pd.DataFrame(recursos_por_dia).T
    if not pron_df.empty:
        horas = list(range(hora_apertura, hora_cierre+1))
        for h in horas:
            if h not in pron_df.columns:
                pron_df[h] = 1
        pron_df = pron_df[horas]
    st.dataframe(pron_df)
    return pron_df

def unir_tablas_recursos(tablas):
    modelos = list(tablas.keys())
    final = tablas[modelos[0]].copy()
    for modelo in modelos[1:]:
        final = final.add(tablas[modelo], fill_value=0)
    return final.fillna(0).astype(int)

def asignar_turnos(df_recursos: pd.DataFrame, duracion_min: int) -> pd.DataFrame:
    """
    Crea bloques de `duracion_min` minutos.
    El rango se muestra como hh:mm - hh:mm (ej. 06:00 - 11:59).
    """
    resultados = []
    for fecha_idx in df_recursos.index:
        fila = df_recursos.loc[fecha_idx]
        horas_orden = sorted(fila.index)
        i = 0
        while i < len(horas_orden):
            start_h = int(horas_orden[i])
            start_min_total = start_h * 60
            end_min_total = start_min_total + duracion_min - 1  # minuto final incluido
            end_h = end_min_total // 60
            end_m = end_min_total % 60

            # Horas cubiertas por el bloque (enteras) para calcular max recursos
            subset = [h for h in horas_orden if start_h <= int(h) <= end_h]

            max_rec = int(fila[subset].max())
            turno_info = {
                "Fecha": fecha_idx,
                "Turno": f"{start_h:02d}:00 - {end_h:02d}:{end_m:02d}",
                "Recursos": max_rec,
            }
            resultados.append(turno_info)
            i += len(subset)  # avanza al siguiente bloque
    return pd.DataFrame(resultados)

def generar_analisis(df):
    modelos = df["operational_model"].unique()
    tablas = {}
    placeholder_turnos = st.empty()

    for modelo in modelos:
        df_modelo = df[df["operational_model"]==modelo]
        col1, col2 = st.columns(2)
        with col1:
            grafico1_historia(df_modelo, modelo)
        with col2:
            grafico2_dia_semana(df_modelo, modelo)
        grafico3_preferencia_slot(df_modelo, modelo)
        pron = tabla_pronostico(df_modelo, modelo)
        tablas[modelo] = pron
        st.markdown("---")

    suma = unir_tablas_recursos(tablas) if len(tablas)>1 else list(tablas.values())[0]

    # Mostrar sistema de turnos primero
    placeholder_turnos.subheader(f"Sistema de Turnos ({turno_horas_label}) – Recursos Totales")
    df_turnos = asignar_turnos(suma, duracion_turno_min)
    placeholder_turnos.dataframe(df_turnos)

    # Alertas Under/Over-Staff
    total_req = int(df_turnos["Recursos"].sum())
    if max_recursos and total_req > max_recursos:
        st.warning(f"⚠️ UnderStaff: se requieren {total_req} recursos y el tope es {max_recursos}")
    elif max_recursos and total_req < max_recursos:
        st.info(f"OverStaff: se requieren {total_req} recursos; tope configurado {max_recursos}")

########################################
# Ejecución principal
########################################
if archivo_csv is not None:
    try:
        df_raw = pd.read_csv(archivo_csv)
    except UnicodeDecodeError:
        df_raw = pd.read_csv(archivo_csv, encoding="latin-1")

    st.success("Archivo cargado correctamente")
    st.dataframe(df_raw.head())

    if st.button("Generar Análisis"):
        df_clean = procesar_datos(df_raw)
        generar_analisis(df_clean)

st.write("¡Listo para generar reportes con In-Staffing!")
