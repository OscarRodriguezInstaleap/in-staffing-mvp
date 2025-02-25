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
    """Convierte columnas a formatos adecuados, filtra pedidos FINISHED y valida horas de apertura/cierre."""
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)
    df["slot_from"] = pd.to_datetime(df["slot_from"], errors="coerce").dt.hour
    df = df[df["estado"] == "FINISHED"]
    df = df[(df["slot_from"] >= hora_apertura) & (df["slot_from"] <= hora_cierre)]
    df["day_of_week"] = df["Fecha"].dt.day_name().fillna("Desconocido")
    return df


def grafico1_historia(df_modelo: pd.DataFrame, modelo: str):
    """Grafico 1: Comportamiento Histórico de demanda (barras color #19521bff) por día."""
    st.subheader(f"Comportamiento Historico de demanda {modelo}")
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
    Grafico 2: Comportamiento Histórico de demanda por día de la semana (promedio).
    Barras color #c7e59fff.
    """
    st.subheader(f"Comportamiento Historico de demanda {modelo} por día de la semana")
    demanda_por_dia = df_modelo.groupby("day_of_week")["items"].sum().reset_index()

    # Cuántos días de la semana hay en df_modelo para el promedio
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
        labels={"items_promedio": "Ítems Promedio", "day_of_week": "Día de la Semana"},
        color_discrete_sequence=["#c7e59f"],
        title="",
    )
    fig_dia.update_layout(font=CUSTOM_FONT, title_font_size=16)
    st.plotly_chart(fig_dia, use_container_width=True)


def grafico3_preferencia_slot(df_modelo: pd.DataFrame, modelo: str):
    """
    Grafico 3: Preferencia de slot (porcentaje de items por hora del día).
    Barras color #1e9d51ff.
    """
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
        color_discrete_sequence=["#1e9d51"],  # #1e9d51ff
        title="",
    )
    fig_slot.update_layout(font=CUSTOM_FONT, title_font_size=16)
    st.plotly_chart(fig_slot, use_container_width=True)


def tabla_pronostico(df_modelo: pd.DataFrame, modelo: str):
    """
    Tabla #4: Pronóstico de demanda por modelo operativo para los días
    definidos en la barra lateral. Se proyecta el nº de recursos por hora.
    """
    st.subheader(f"Pronóstico de demanda - {modelo}")
    fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}

    for fecha in fechas_pronostico:
        # Lógica de pronóstico: Tomamos el día de la semana y buscamos en el histórico esos días de la semana
        day_of_week = fecha.weekday()  # 0 = Lunes, 6 = Domingo
        df_same_day = df_modelo[df_modelo["Fecha"].dt.weekday == day_of_week]

        # Sumamos items por slot
        demanda_slot = df_same_day.groupby("slot_from")["items"].sum().fillna(0)

        # Ajuste por evento especial
        if evento_especial and fecha_inicio_evento and fecha_fin_evento:
            if fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
                demanda_slot = demanda_slot * (1 + impacto_evento / 100)

        # Calculamos los recursos por hora
        recursos_dia = (demanda_slot / productividad_estimada).fillna(1).apply(np.ceil).astype(int)
        recursos_dia = recursos_dia.apply(lambda x: max(x, 1))

        recursos_por_dia[fecha.strftime("%d/%m/%Y")] = recursos_dia

    pronostico_df = pd.DataFrame(recursos_por_dia).T.fillna(1).astype(int)

    # Asegurar columnas con las horas disponibles
    horas = list(range(hora_apertura, hora_cierre + 1))
    for hora in horas:
        if hora not in pronostico_df.columns:
            pronostico_df[hora] = 1

    pronostico_df = pronostico_df[horas]
    st.dataframe(pronostico_df)


def grafico5_recursos_totales(df: pd.DataFrame):
    """
    Grafico #5: total de recursos por día (barras apiladas)
    donde se suman los recursos para cada modelo operativo.
    """
    st.subheader("Total de recursos por día (Barras apiladas)")

    # Asumiendo que ya calculamos un pronóstico por modelo operativo, lo ideal
    # es armar un df con la suma de recursos por día y por modelo.
    # Como no tenemos la parte del pronóstico en un df unificado, se ejemplifica aquí.

    # Para la demostración, generamos un df hipotético.
    # En un escenario real, recogeríamos los datos de la parte pronóstico de cada modelo.
    # Ejemplo:
    # fecha, modelo_operativo, recursos
    # 01/01/2025, PICK_AND_DELIVERY, 10
    # 01/01/2025, PICK_AND_COLLECT, 5
    # 02/01/2025, PICK_AND_DELIVERY, 11
    # etc.

    # Aquí dejamos una estructura base. Deberás adaptar a tu lógica de pronóstico real.
    data_mock = {
        "Fecha": [
            "01/01/2025", "01/01/2025", "02/01/2025", "02/01/2025"
        ],
        "Modelo": [
            "PICK_AND_DELIVERY", "PICK_AND_COLLECT", "PICK_AND_DELIVERY", "PICK_AND_COLLECT"
        ],
        "Recursos": [10, 5, 11, 6]
    }
    df_mock = pd.DataFrame(data_mock)

    fig = px.bar(
        df_mock,
        x="Fecha",
        y="Recursos",
        color="Modelo",
        title="",
    )
    fig.update_layout(font=CUSTOM_FONT, title_font_size=16)
    st.plotly_chart(fig, use_container_width=True)


def tabla6_recursos_totales(df: pd.DataFrame):
    """
    Tabla #6: total recursos por hora por día (suma de las tablas anteriores).
    Similar a grafico5_recursos_totales, pero en tabla.
    """
    st.subheader("Tabla total recursos por hora por día")
    # De manera similar, se requiere la suma de todos los modelos operativos
    # a nivel de día y hora.
    # Aquí dejamos un ejemplo base.

    # Ejemplo en un df hipotético, donde la fila es (Fecha, Hora) y columnas son Modelos.
    # Sumamos la fila para un total.
    data_mock = {
        "Fecha": ["01/01/2025", "01/01/2025", "02/01/2025", "02/01/2025"],
        "Hora": [8, 9, 8, 9],
        "PICK_AND_DELIVERY": [3, 2, 4, 3],
        "PICK_AND_COLLECT": [2, 1, 2, 1],
    }
    df_mock = pd.DataFrame(data_mock)
    df_mock["Total"] = df_mock["PICK_AND_DELIVERY"] + df_mock["PICK_AND_COLLECT"]

    st.dataframe(df_mock)


def generar_analisis(df: pd.DataFrame):
    """
    1) Linea 1:
       * Grafico1 (izquierda)
       * Grafico2 (derecha)
    2) Linea 2:
       * Grafico 3
    3) Linea 3:
       * Tabla pronostico
    Al final:
       * Grafico 5
       * Tabla 6
    """

    modelos_operativos = df["operational_model"].unique()

    for modelo in modelos_operativos:
        # Filtro para el modelo
        df_modelo = df[df["operational_model"] == modelo].copy()

        # LINEA 1: Grafico1 (izq) y Grafico2 (der)
        colA, colB = st.columns(2)
        with colA:
            grafico1_historia(df_modelo, modelo)
        with colB:
            grafico2_dia_semana(df_modelo, modelo)

        # LINEA 2: Grafico 3
        grafico3_preferencia_slot(df_modelo, modelo)

        # LINEA 3: Tabla
        tabla_pronostico(df_modelo, modelo)

        st.markdown("---")

    # Al final acomodar en la misma fila grafico5 y tabla6
    st.subheader("Resumen Total de Recursos")
    colR1, colR2 = st.columns(2)
    with colR1:
        grafico5_recursos_totales(df)
    with colR2:
        tabla6_recursos_totales(df)


# EJECUCIÓN PRINCIPAL
if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("Archivo cargado correctamente")
    st.dataframe(df.head())

    if st.button("Generar Análisis"):
        df = procesar_datos(df)
        generar_analisis(df)

st.write("Listo para generar reportes con In-Staffing!")
