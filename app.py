import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import math

########################################
# Estilo global
########################################
CUSTOM_FONT = dict(family="Roboto", size=12)

########################################
# Config básica de Streamlit
########################################
st.set_page_config(page_title="In-Staffing MVP", layout="wide")
os.makedirs("reports", exist_ok=True)

st.title("In-Staffing: Planificación de Recursos")
st.markdown("---")

########################################
# Cargar archivo
########################################
st.header("Cargar Archivo CSV")
archivo_csv = st.file_uploader("Sube un archivo de operaciones (CSV)", type=["csv"])

########################################
# Parámetros laterales
########################################
with st.sidebar:
    with st.expander("Configuraciones Generales", expanded=True):
        hora_apertura = st.slider("Hora de apertura", 0, 23, 8)
        hora_cierre = st.slider("Hora de cierre", 0, 23, 22)
        productividad_estimada = st.number_input(
            "Productividad (ítems/hora)",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
        )
        fecha_inicio_pronostico = st.date_input(
            "Pronóstico desde", datetime.now() + timedelta(days=1)
        )
        fecha_fin_pronostico = st.date_input(
            "Pronóstico hasta", fecha_inicio_pronostico + timedelta(days=30)
        )
        if (fecha_fin_pronostico - fecha_inicio_pronostico).days > 30:
            st.error("El pronóstico no puede exceder 30 días.")

    with st.expander("Evento Especial"):
        evento_especial = st.checkbox("¿Hay evento especial?")
        fecha_inicio_evento, fecha_fin_evento, impacto_evento = None, None, 0
        if evento_especial:
            fecha_inicio_evento = st.date_input("Inicio del evento")
            fecha_fin_evento = st.date_input("Fin del evento")
            impacto_evento = st.slider(
                "Incremento demanda (%)", 0, 200, 20, 1
            )

    with st.expander("Extensión de los turnos"):
        col_h, col_m = st.columns(2)
        horas_turno = col_h.number_input("Horas", 4, 9, 6, 1)
        minutos_turno = col_m.number_input("Minutos", 0, 59, 0, 5)
        duracion_turno_min = int(horas_turno) * 60 + int(minutos_turno)
        if duracion_turno_min > 540:
            st.error("Duración máxima 9 h (540 min).")
            st.stop()
        turno_horas_label = f"{horas_turno}h {minutos_turno}m"

    with st.expander("Máximo de Recursos Disponibles"):
        max_recursos_val = st.number_input(
            "Recursos fijos (0 = sin tope)", 0, 1000, 0, 1
        )
        max_recursos = max_recursos_val if max_recursos_val > 0 else None

########################################
# Mapeo de columnas multilingüe
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
        "Início de Slot de Entrega",
        "Inicio de Slot de Entrega",
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
            f"Faltan columnas requeridas: {faltantes}. "
            f"Encontradas: {list(df.columns)}"
        )
        st.stop()
    return df


########################################
# Procesamiento y visualización
########################################
def procesar_datos(df: pd.DataFrame) -> pd.DataFrame:
    df = estandarizar_columnas(df)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)
    df["slot_from"] = (
        pd.to_datetime(df["slot_from"], errors="coerce")
        .dt.hour.fillna(0)
        .astype(int)
    )
    df = df[df["estado"].str.upper() == "FINISHED"]
    df = df[(df["slot_from"] >= hora_apertura) & (df["slot_from"] <= hora_cierre)]

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
    df["day_of_week"] = df["weekday_num"].map(dias_map)
    return df


def grafico1(df_modelo, modelo):
    st.subheader(f"Histórico – {modelo}")
    fig = px.bar(
        df_modelo,
        x="Fecha",
        y="items",
        labels={"items": "Ítems"},
        color_discrete_sequence=["#19521b"],
    )
    fig.update_layout(font=CUSTOM_FONT)
    st.plotly_chart(fig, use_container_width=True)


def grafico2(df_modelo, modelo):
    st.subheader(f"Ítems promedio por día – {modelo}")
    demanda = (
        df_modelo.groupby("day_of_week")["items"]
        .mean()
        .reindex(["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"])
        .reset_index()
    )
    fig = px.bar(
        demanda,
        x="day_of_week",
        y="items",
        labels={"items": "Ítems promedio"},
        color_discrete_sequence=["#c7e59f"],
    )
    fig.update_layout(font=CUSTOM_FONT)
    st.plotly_chart(fig, use_container_width=True)


def grafico3(df_modelo, modelo):
    st.subheader(f"Preferencia de slot – {modelo}")
    datos = df_modelo.groupby("slot_from")["items"].sum().reset_index()
    datos["pct"] = datos["items"] / datos["items"].sum() * 100
    fig = px.bar(
        datos,
        x="slot_from",
        y="pct",
        labels={"slot_from": "Hora", "pct": "% demanda"},
        color_discrete_sequence=["#1e9d51"],
    )
    fig.update_layout(font=CUSTOM_FONT)
    st.plotly_chart(fig, use_container_width=True)


def tabla_pronostico(df_modelo, modelo):
    st.subheader(f"Pronóstico – {modelo}")
    fechas_rango = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}

    sum_items = df_modelo.groupby(["weekday_num", "slot_from"])["items"].sum().reset_index()
    days_count = (
        df_modelo.groupby("weekday_num")["Fecha"]
        .apply(lambda x: x.dt.date.nunique())
        .reset_index(name="Cant_dias")
    )
    pivot_sum = sum_items.pivot(index="weekday_num", columns="slot_from", values="items").fillna(0)
    days_dict = dict(zip(days_count["weekday_num"], days_count["Cant_dias"]))

    for fecha in fechas_rango:
        wd = fecha.weekday()
        ndias = days_dict.get(wd, 1)
        base = (
            pivot_sum.loc[wd] / ndias
            if wd in pivot_sum.index
            else pd.Series(1, index=pivot_sum.columns)
        )
        if (
            evento_especial
            and fecha_inicio_evento
            and fecha_fin_evento
            and fecha_inicio_evento <= fecha.date() <= fecha_fin_evento
        ):
            base *= 1 + impacto_evento / 100
        recursos = (base / productividad_estimada).fillna(1).apply(np.ceil).astype(int)
        recursos = recursos.apply(lambda x: max(x, 1))
        recursos_por_dia[fecha.strftime("%d/%m/%Y")] = recursos

    pron_df = pd.DataFrame(recursos_por_dia).T
    if not pron_df.empty:
        horas = list(range(hora_apertura, hora_cierre + 1))
        for h in horas:
            if h not in pron_df.columns:
                pron_df[h] = 1
        pron_df = pron_df[horas]
    st.dataframe(pron_df)
    return pron_df


def unir_tablas(tablas):
    modelos = list(tablas.keys())
    resultado = tablas[modelos[0]].copy()
    for modelo in modelos[1:]:
        resultado = resultado.add(tablas[modelo], fill_value=0)
    return resultado.fillna(0).astype(int)


def asignar_turnos(df_recursos: pd.DataFrame, duracion_min: int) -> pd.DataFrame:
    """
    Genera bloques de `duracion_min` minutos.
    Ajusta cada bloque a `max_recursos` si está definido.
    Rango mostrado como hh:mm – hh:mm.
    """
    resultados = []
    for fecha_idx in df_recursos.index:
        fila = df_recursos.loc[fecha_idx]
        horas_orden = sorted(fila.index)
        i = 0
        while i < len(horas_orden):
            start_h = int(horas_orden[i])
            start_min_tot = start_h * 60
            end_min_tot = start_min_tot + duracion_min - 1
            end_h = end_min_tot // 60
            end_m = end_min_tot % 60

            subset = [h for h in horas_orden if start_h <= int(h) <= end_h]
            req_block = int(fila[subset].max())
            # Respeta máximo de recursos fijos
            rec_block = min(req_block, max_recursos) if max_recursos else req_block

            resultados.append(
                {
                    "Fecha": fecha_idx,
                    "Turno": f"{start_h:02d}:00 – {end_h:02d}:{end_m:02d}",
                    "Recursos Requeridos": req_block,
                    "Recursos Asignados": rec_block,
                }
            )
            i += len(subset)
    return pd.DataFrame(resultados)


def generar_analisis(df):
    modelos = df["operational_model"].unique()
    tablas_pron = {}
    placeholder_turnos = st.empty()

    for modelo in modelos:
        df_mod = df[df["operational_model"] == modelo]
        col1, col2 = st.columns(2)
        with col1:
            grafico1(df_mod, modelo)
        with col2:
            grafico2(df_mod, modelo)
        grafico3(df_mod, modelo)
        pron = tabla_pronostico(df_mod, modelo)
        tablas_pron[modelo] = pron
        st.markdown("---")

    df_total = unir_tablas(tablas_pron) if len(tablas_pron) > 1 else list(tablas_pron.values())[0]

    placeholder_turnos.subheader(f"Sistema de Turnos ({turno_horas_label}) – Recursos Totales")
    df_turnos = asignar_turnos(df_total, duracion_turno_min)
    placeholder_turnos.dataframe(df_turnos)

    # ==== Alertas =========================================================
    # Pico requerido / asignado por día
    pico_req = df_turnos.groupby("Fecha")["Recursos Requeridos"].max()
    pico_asig = df_turnos.groupby("Fecha")["Recursos Asignados"].max()

    if max_recursos:
        if (pico_req > max_recursos).any():
            st.warning(
                f"⚠️ UnderStaff detectado. "
                f"Pico requerido diario máximo: {int(pico_req.max())}  >  tope {max_recursos}."
            )
        elif (pico_req < max_recursos).all():
            st.info(
                f"OverStaff: el pico requerido diario máximo es "
                f"{int(pico_req.max())} y el tope configurado es {max_recursos}."
            )

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
