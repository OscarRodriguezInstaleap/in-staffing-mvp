import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

########################################
# Estilo y Ajustes
########################################

# Ajuste de fuente para Plotly (puede que no se aplique en todos los entornos)
CUSTOM_FONT = dict(family="Roboto", size=12)

# Utilidad para encerrar un chart en un contenedor con borde
def chart_with_border(fig):
    """Muestra la figura en un contenedor con borde y padding."""
    container_style = """
    <div style="
        border: 1px solid #CCC;
        padding: 10px;
        margin-bottom: 15px;
        border-radius: 5px;
    ">
    """
    st.markdown(container_style, unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


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

    with st.expander("Evento Especial"):
        evento_especial = st.checkbox("¿Habrá un evento especial?")
        fecha_inicio_evento = None
        fecha_fin_evento = None
        impacto_evento = 0

        if evento_especial:
            fecha_inicio_evento = st.date_input("Fecha de inicio del evento")
            fecha_fin_evento = st.date_input("Fecha de fin del evento")
            impacto_evento = st.slider("Incremento en demanda (%)", min_value=0, max_value=200, value=20, step=1)


########################################
# Procesamiento de datos base
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

    # Ordenar días
    DIAS_ORDENADOS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    df["day_of_week"] = pd.Categorical(df["day_of_week"], categories=DIAS_ORDENADOS, ordered=True)
    return df

########################################
# Gráficas
########################################
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
    chart_with_border(fig_hist)  # Usamos el contenedor con borde

def grafico2_dia_semana(df_modelo: pd.DataFrame, modelo: str):
    """Gráfico de barras color #c7e59fff con la demanda promedio de ítems por día de la semana."""
    st.subheader(f"Comportamiento histórico de demanda {modelo} por día de la semana")
    demanda_por_dia = df_modelo.groupby("day_of_week")["items"].sum().reset_index()
    conteo_por_dia = (df_modelo.groupby("day_of_week")["Fecha"]
                      .nunique()
                      .reset_index()
                      .rename(columns={"Fecha": "Cant_dias"}))
    merge_dia = pd.merge(demanda_por_dia, conteo_por_dia, on="day_of_week", how="left")
    merge_dia["items_promedio"] = merge_dia["items"] / merge_dia["Cant_dias"].replace(0, 1)

    fig_dia = px.bar(
        merge_dia,
        x="day_of_week",
        y="items_promedio",
        labels={"items_promedio": "Ítems Promedio", "day_of_week": "Día de la semana"},
        color_discrete_sequence=["#c7e59f"],  # #c7e59fff
        title="",
        category_orders={"day_of_week": ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]},
    )
    fig_dia.update_layout(font=CUSTOM_FONT, title_font_size=16)
    chart_with_border(fig_dia)

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
        color_discrete_sequence=["#1e9d51"],  # #1e9d51ff
        title="",
    )
    fig_slot.update_layout(font=CUSTOM_FONT, title_font_size=16)
    chart_with_border(fig_slot)

########################################
# Tabla pronóstico y unificación
########################################
def tabla_pronostico(df_modelo: pd.DataFrame, modelo: str) -> pd.DataFrame:
    """
    Devuelve un DataFrame con el pronóstico (filas = fechas, cols = horas).
    """
    st.subheader(f"Pronóstico de demanda - {modelo}")
    fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}

    # Precalcular info
    df_modelo["weekday_num"] = df_modelo["Fecha"].dt.weekday
    sum_items = df_modelo.groupby(["weekday_num", "slot_from"])["items"].sum().reset_index()
    days_count = (df_modelo.groupby("weekday_num")["Fecha"]
                  .apply(lambda x: x.dt.date.nunique())
                  .reset_index()
                  .rename(columns={"Fecha": "Cant_dias"}))
    pivot_sum = sum_items.pivot(index="weekday_num", columns="slot_from", values="items").fillna(0)
    days_count_dict = dict(zip(days_count["weekday_num"], days_count["Cant_dias"]))

    for fecha in fechas_pronostico:
        wd = fecha.weekday()
        ndias = days_count_dict.get(wd, 1)

        if wd not in pivot_sum.index:
            base_items = pd.Series(1, index=pivot_sum.columns)
        else:
            base_items = pivot_sum.loc[wd].copy()
            base_items = base_items / max(ndias, 1)

        if evento_especial and fecha_inicio_evento and fecha_fin_evento:
            if fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
                base_items = base_items * (1 + impacto_evento / 100)

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

    return pronostico_df.fillna(1).astype(int)

def unir_tablas_recursos(tablas: dict) -> pd.DataFrame:
    """
    Recibe un dict {modelo: dfPronostico} y los suma.
    Cada df tiene las mismas filas (fechas) y cols (horas).
    """
    modelos = list(tablas.keys())
    df_final = tablas[modelos[0]].copy()

    for modelo in modelos[1:]:
        df_final = df_final.add(tablas[modelo], fill_value=0)

    return df_final.fillna(0).astype(int)

########################################
# Asignación de turnos
########################################
def asignar_turnos(df_recursos: pd.DataFrame, bloque_horas=6) -> pd.DataFrame:
    """
    Crea un sistema básico de turnos donde cada bloque de X horas
    se asigna la máx. de recursos de ese rango horario.
    Retorna un df con col [Fecha, Turno, Recursos].
    """
    resultados = []
    for fecha_idx in df_recursos.index:
        fila = df_recursos.loc[fecha_idx]
        horas_orden = sorted(fila.index, key=lambda x: int(x))
        i = 0
        while i < len(horas_orden):
            start_h = int(horas_orden[i])
            end_h = min(start_h + bloque_horas - 1, int(horas_orden[-1]))
            subset_hours = [h for h in horas_orden if start_h <= int(h) <= end_h]
            max_recs = int(fila[subset_hours].max())
            turno_info = {
                "Fecha": fecha_idx,
                "Turno": f"{start_h:02d}:00 - {end_h:02d}:00",
                "Recursos": max_recs
            }
            resultados.append(turno_info)
            i += len(subset_hours)
    return pd.DataFrame(resultados)

########################################
# Generar análisis principal
########################################
def generar_analisis(df: pd.DataFrame):
    modelos_operativos = df["operational_model"].unique()
    tablas_por_modelo = {}

    for modelo in modelos_operativos:
        df_modelo = df[df["operational_model"] == modelo].copy()

        # LINEA 1: Grafico 1 + Grafico 2
        colA, colB = st.columns(2)
        with colA:
            grafico1_historia(df_modelo, modelo)
        with colB:
            grafico2_dia_semana(df_modelo, modelo)

        # LINEA 2: Grafico 3
        grafico3_preferencia_slot(df_modelo, modelo)

        # LINEA 3: Tabla pronóstico
        pron_df = tabla_pronostico(df_modelo, modelo)
        tablas_por_modelo[modelo] = pron_df
        st.markdown("---")

    # Unimos todas las tablas en una sola
    if len(tablas_por_modelo) > 1:
        st.subheader("Recursos Totales (Suma de todos los modelos)")
        df_suma = unir_tablas_recursos(tablas_por_modelo)
        st.dataframe(df_suma)

        # Asignamos turnos con bloque de 6h (por ejemplo)
        st.subheader("Sistema de Turnos (ejemplo 6h) - Recursos Totales")
        df_turnos = asignar_turnos(df_suma, bloque_horas=6)
        st.dataframe(df_turnos)
    else:
        st.info("Solo hay un modelo operativo en el archivo, no se requiere unificación de tablas ni turnos.")


########################################
# EJECUCIÓN PRINCIPAL
########################################
if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("Archivo cargado correctamente")
    st.dataframe(df.head())

    if st.button("Generar Análisis"):
        df = procesar_datos(df)
        generar_analisis(df)

st.write("¡Listo para generar reportes con In-Staffing!")
