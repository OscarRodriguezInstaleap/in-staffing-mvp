# app.py ──────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta
from math import ceil

# ───── Config inicial ───────────────────────────────────────
st.set_page_config(page_title="In‑Staffing MVP", layout="wide")
os.makedirs("reports", exist_ok=True)
CUSTOM_FONT = dict(family="Roboto", size=12)

st.title("In‑Staffing: Planificación de Recursos")
st.markdown("---")

# ───── Carga de archivo ─────────────────────────────────────
st.header("Cargar Archivo CSV")
archivo_csv = st.file_uploader(
    "Sube un archivo de datos de operaciones (CSV)", type=["csv"]
)

# ───── Barra lateral con todos los parámetros ───────────────
with st.sidebar:
    with st.expander("Configuraciones Generales", expanded=True):
        hora_apertura = st.slider("Hora de apertura de tienda", 0, 23, 8)
        hora_cierre   = st.slider("Hora de cierre de tienda",   0, 23, 22)
        productividad_estimada = st.number_input(
            "Productividad Estimada por Hora",
            min_value=1, max_value=1_000, value=100, step=5
        )

        fecha_inicio_pronostico = st.date_input(
            "Fecha de inicio del pronóstico", datetime.now() + timedelta(days=1)
        )
        fecha_fin_pronostico = st.date_input(
            "Fecha de fin del pronóstico",
            fecha_inicio_pronostico + timedelta(days=30)
        )
        if (fecha_fin_pronostico - fecha_inicio_pronostico).days > 30:
            st.error("El periodo del pronóstico no puede ser mayor a 30 días.")

    with st.expander("Evento Especial"):
        evento_especial = st.checkbox("¿Habrá un evento especial?")
        fecha_inicio_evento = fecha_fin_evento = None
        impacto_evento = 0
        if evento_especial:
            fecha_inicio_evento = st.date_input("Fecha de inicio del evento")
            fecha_fin_evento    = st.date_input("Fecha de fin del evento")
            impacto_evento      = st.slider(
                "Incremento en demanda (%)", 0, 200, 20, 1
            )

    with st.expander("Extensión de los turnos"):
        col_h, col_m = st.columns(2)
        with col_h:
            turno_horas = st.number_input(
                "Horas (4‑9)", 4, 9, 6, 1
            )
        with col_m:
            turno_minutos = st.number_input(
                "Minutos (0‑59)", 0, 59, 0, 5
            )
        duracion_turno = turno_horas + turno_minutos / 60.0
        if not 4 <= duracion_turno <= 9:
            st.error("La duración del turno debe estar entre 4 y 9 horas.")

    with st.expander("Capacidad Fija de Recursos"):
        max_recursos_disponibles = st.number_input(
            "Máx. recursos disponibles (0 = sin tope)",
            0, 10_000, 0, 1
        )
        if max_recursos_disponibles == 0:
            max_recursos_disponibles = None

# ───── Funciones utilitarias ────────────────────────────────
def procesar_datos(df: pd.DataFrame) -> pd.DataFrame:
    df["Fecha"]     = pd.to_datetime(df["Fecha"], errors="coerce")
    df["items"]     = pd.to_numeric(df["items"], errors="coerce").fillna(0)
    df["slot_from"] = pd.to_datetime(df["slot_from"], errors="coerce").dt.hour
    df              = df[df["estado"] == "FINISHED"]
    df              = df[(df["slot_from"] >= hora_apertura) & (df["slot_from"] <= hora_cierre)]

    dias_map = {
        0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
        4: "Viernes", 5: "Sábado", 6: "Domingo"
    }
    df["weekday_num"] = df["Fecha"].dt.weekday
    df["day_of_week"] = df["weekday_num"].map(dias_map).fillna("Desconocido")
    orden = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    df["day_of_week"] = pd.Categorical(df["day_of_week"], categories=orden, ordered=True)
    return df


def grafico1_historia(df_modelo, modelo):
    fig = px.bar(
        df_modelo, x="Fecha", y="items",
        labels={"items":"Ítems","Fecha":"Día"},
        color_discrete_sequence=["#19521b"]
    )
    fig.update_layout(font=CUSTOM_FONT)
    st.subheader(f"Demanda histórica — {modelo}")
    st.plotly_chart(fig, use_container_width=True)


def grafico2_dia_semana(df_modelo, modelo):
    demanda = df_modelo.groupby("day_of_week")["items"].sum().reset_index()
    conteo  = df_modelo.groupby("day_of_week")["Fecha"].nunique().reset_index().rename(columns={"Fecha":"dias"})
    merge   = pd.merge(demanda, conteo, on="day_of_week", how="left")
    merge["items_promedio"] = merge["items"] / merge["dias"].replace(0,1)
    fig = px.bar(
        merge, x="day_of_week", y="items_promedio",
        labels={"day_of_week":"Día","items_promedio":"Ítems promedio"},
        color_discrete_sequence=["#c7e59f"],
        category_orders={"day_of_week": demanda["day_of_week"].tolist()}
    )
    fig.update_layout(font=CUSTOM_FONT)
    st.subheader(f"Demanda promedio por día — {modelo}")
    st.plotly_chart(fig, use_container_width=True)


def grafico3_preferencia_slot(df_modelo, modelo):
    demanda = df_modelo.groupby("slot_from")["items"].sum().reset_index()
    total   = demanda["items"].sum()
    demanda["pct"] = 0 if total==0 else demanda["items"]*100/total
    fig = px.bar(
        demanda, x="slot_from", y="pct",
        labels={"slot_from":"Hora","pct":"% de demanda"},
        color_discrete_sequence=["#1e9d51"]
    )
    fig.update_layout(font=CUSTOM_FONT)
    st.subheader(f"Preferencia de slot — {modelo}")
    st.plotly_chart(fig, use_container_width=True)


def tabla_pronostico(df_modelo, modelo, mostrar=True) -> pd.DataFrame:
    fechas = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}

    df_modelo["weekday_num"] = df_modelo["Fecha"].dt.weekday
    sum_items = df_modelo.groupby(["weekday_num","slot_from"])["items"].sum().reset_index()
    count_days = df_modelo.groupby("weekday_num")["Fecha"].apply(lambda x: x.dt.date.nunique()).to_dict()
    pivot = sum_items.pivot(index="weekday_num", columns="slot_from", values="items").fillna(0)

    for fecha in fechas:
        wd = fecha.weekday()
        nd  = max(count_days.get(wd,1),1)
        base = (pivot.loc[wd] if wd in pivot.index else pd.Series(1, index=pivot.columns)) / nd

        if evento_especial and fecha_inicio_evento and fecha_fin_evento:
            if fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
                base *= 1 + impacto_evento/100

        recursos = np.ceil(base / productividad_estimada).astype(int).replace(0,1)
        recursos_por_dia[fecha.strftime("%d/%m/%Y")] = recursos

    pron = pd.DataFrame(recursos_por_dia).T
    horas = list(range(hora_apertura, hora_cierre+1))
    pron = pron.reindex(columns=horas, fill_value=1).astype(int)

    if mostrar:
        st.subheader(f"Pronóstico de demanda — {modelo}")
        st.dataframe(pron)

    return pron


def unir_tablas(tablas):
    modelos = list(tablas)
    total   = tablas[modelos[0]].copy()
    for m in modelos[1:]:
        total = total.add(tablas[m], fill_value=0)
    return total.fillna(0).astype(int)


def asignar_turnos(df_recursos, dur_turno, max_rec=None):
    resultados = []
    bloque = dur_turno
    for fecha in df_recursos.index:
        fila = df_recursos.loc[fecha]
        horas_ord = sorted(map(int, fila.index))
        i = 0
        while i < len(horas_ord):
            start_h = int(horas_ord[i])
            end_h   = int(min(start_h + bloque - 1, horas_ord[-1]))
            subset  = [h for h in horas_ord if start_h <= h <= end_h]
            req     = int(fila[subset].max())
            under   = False
            if max_rec is not None:
                under = req > max_rec
                req   = min(req, max_rec)
            resultados.append({
                "Fecha": fecha,
                "Turno": f"{start_h:02d}:00‑{end_h:02d}:00",
                "Recursos": req,
                "UnderStaff": "⚠️" if under else ""
            })
            i += len(subset)
    return pd.DataFrame(resultados)


# ───── Generación de análisis completo ───────────────────────
def generar_analisis(df):
    modelos = df["operational_model"].unique()
    pron_por_modelo = {}
    data_para_graficos = []

    # Primero calculamos pronósticos (sin mostrarlos) para disponer de totales
    for modelo in modelos:
        df_mod = df[df["operational_model"] == modelo]
        pron   = tabla_pronostico(df_mod, modelo, mostrar=False)
        pron_por_modelo[modelo] = pron
        data_para_graficos.append((modelo, df_mod))  # guardamos df para gráficos

    total = unir_tablas(pron_por_modelo) if len(pron_por_modelo) > 1 else list(pron_por_modelo.values())[0]

    # ─── 1) Recursos totales + Sistema de Turnos ──────────────
    st.subheader("Recursos totales (todos los modelos)" if len(pron_por_modelo)>1 else "Recursos totales")
    st.dataframe(total)

    st.subheader(f"Sistema de Turnos ({duracion_turno:.2f} h) – Recursos Totales")
    df_turnos = asignar_turnos(total, duracion_turno, max_recursos_disponibles)
    st.dataframe(df_turnos, hide_index=True)
    if (df_turnos["UnderStaff"] == "⚠️").any():
        st.warning("⚠️  Hay turnos UnderStaff (pico de demanda > recursos fijos).")

    with st.expander("Tabla de recursos hora a hora"):
        st.dataframe(total)

    st.markdown("---")

    # ─── 2) Detalles por modelo (gráficos + pronóstico) ──────
    for modelo, df_mod in data_para_graficos:
        col1, col2 = st.columns(2)
        with col1:
            grafico1_historia(df_mod, modelo)
        with col2:
            grafico2_dia_semana(df_mod, modelo)
        grafico3_preferencia_slot(df_mod, modelo)

        # Muestra pronóstico que ya calculamos
        st.subheader(f"Pronóstico de demanda — {modelo}")
        st.dataframe(pron_por_modelo[modelo])

        st.markdown("---")

# ───── Ejecución principal ──────────────────────────────────
if archivo_csv is not None:
    df_raw = pd.read_csv(archivo_csv)
    st.success("Archivo cargado correctamente")
    st.dataframe(df_raw.head())

    if st.button("Generar análisis"):
        df_clean = procesar_datos(df_raw)
        generar_analisis(df_clean)

st.write("¡Listo para generar reportes con In‑Staffing!")
