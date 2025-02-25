import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# Configuración inicial de la aplicación
st.set_page_config(page_title="In-Staffing MVP", layout="wide")
os.makedirs("reports", exist_ok=True)

# Ajustes de estilo de la fuente Roboto para Plotly (no siempre se aplican en todos los entornos, pero lo intentamos)
# Nota: Esto no siempre tendrá efecto en Streamlit Cloud si la fuente no está instalada en el contenedor.
custom_font = dict(family="Roboto", size=12)

# Título principal
st.title("In-Staffing: Planificación de Recursos")
st.markdown("---")

# Sección para cargar el archivo CSV
st.header("Cargar Archivo CSV")
archivo_csv = st.file_uploader("Sube un archivo de datos de operaciones (CSV)", type=["csv"])

# Parámetros en la barra lateral
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
    """
    Convierte columnas en formatos adecuados,
    filtra pedidos en estado FINISHED y valida
    las horas de apertura y cierre.
    """
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)
    df["slot_from"] = pd.to_datetime(df["slot_from"], errors="coerce").dt.hour
    df = df[df["estado"] == "FINISHED"]
    df = df[(df["slot_from"] >= hora_apertura) & (df["slot_from"] <= hora_cierre)]

    # Crea columna para nombre del día de la semana
    df["day_of_week"] = df["Fecha"].dt.day_name().fillna("Desconocido")
    return df

def generar_grafico1_historia(df_modelo: pd.DataFrame, modelo: str):
    """
    Gráfico 1: Comportamiento histórico de demanda (barras) por día (Eje X),
    mostrando la cantidad de Items (Eje Y).
    Color de la gráfica: #19521bff
    """
    st.subheader(f"Comportamiento Historico de demanda {modelo}")
    fig_hist = px.bar(
        df_modelo,
        x="Fecha",
        y="items",
        labels={"items": "Cantidad de Ítems", "Fecha": "Día"},
        color_discrete_sequence=["#19521b"],
        title="",
    )
    fig_hist.update_layout(font=custom_font)
    st.plotly_chart(fig_hist, use_container_width=True)

def generar_grafico2_por_dia_semana(df_modelo: pd.DataFrame, modelo: str):
    """
    Gráfico 2: Comportamiento Historico de demanda por día de la semana (promedio).
    Color de la gráfica: #c7e59fff
    """
    st.subheader(f"Comportamiento Historico de demanda {modelo} por día de la semana")
    demanda_por_dia = df_modelo.groupby("day_of_week")["items"].sum().reset_index()
    # Calculamos cuántos registros hay por cada día de la semana para hacer el promedio total.
    conteo_por_dia = df_modelo.groupby("day_of_week")["Fecha"].nunique().reset_index().rename(columns={"Fecha": "Cant_dias"})
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
    fig_dia.update_layout(font=custom_font)
    st.plotly_chart(fig_dia, use_container_width=True)

def generar_grafico3_preferencia_slot(df_modelo: pd.DataFrame, modelo: str):
    """
    Gráfico 3: Preferencia de Slot (porcentaje de items por hora).
    Color de la gráfica: #1e9d51ff
    """
    st.subheader(f"Preferencia de Slot - {modelo}")
    demanda_slot = df_modelo.groupby("slot_from")["items"].sum().reset_index()
    if demanda_slot["items"].sum() == 0:
        demanda_slot["pct"] = 0
    else:
        demanda_slot["pct"] = (demanda_slot["items"] / demanda_slot["items"].sum()) * 100

    fig_slot = px.bar(
        demanda_slot,
        x="slot_from",
        y="pct",
        labels={"slot_from": "Hora del Día", "pct": "Porcentaje de Demanda"},
        color_discrete_sequence=["#1e9d51"],
        title="",
    )
    fig_slot.update_layout(font=custom_font)
    st.plotly_chart(fig_slot, use_container_width=True)

def generar_tabla_pronostico(df_modelo: pd.DataFrame, modelo: str):
    """
    Tabla #4: Pronóstico de demanda por modelo operativo
    Se genera una tabla con horas (08:00,09:00,etc) y días (por fecha de pronóstico)
    donde cada casilla es el número de recursos requeridos.
    """
    st.subheader(f"Tabla Pronostico de demanda - {modelo}")

    fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}
    
    for fecha in fechas_pronostico:
        # Ejemplo de cálculo para 30 días atrás: 
        # Podrías ajustar la lógica de cómo se hace el pronóstico aquí.
        day_of_week = fecha.weekday()  # 0= Lunes, 6= Domingo
        # Filtramos df_modelo para el mismo día de la semana del histórico
        df_same_day = df_modelo[df_modelo["Fecha"].dt.weekday == day_of_week]
        # Agrupamos por slot y sumamos items
        items_same_day = df_same_day.groupby("slot_from")["items"].sum()
        
        # Efecto de evento especial
        if evento_especial and fecha_inicio_evento and fecha_fin_evento:
            if fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
                items_same_day = items_same_day * (1 + impacto_evento / 100)
        
        recursos_dia = (items_same_day / productividad_estimada).fillna(1).apply(np.ceil).astype(int)
        recursos_por_dia[fecha.strftime("%d/%m/%Y")] = recursos_dia
    
    pronostico_df = pd.DataFrame(recursos_por_dia).T.fillna(1).astype(int)

    # Asegurar que las columnas corresponden a las horas de apertura y cierre
    horas = list(range(hora_apertura, hora_cierre + 1))
    for hora in horas:
        if hora not in pronostico_df.columns:
            pronostico_df[hora] = 1

    pronostico_df = pronostico_df[horas]
    # Mostramos la tabla
    st.dataframe(pronostico_df)

def generar_analisis(df: pd.DataFrame):
    """
    Genera para cada modelo operativo:
     - Linea 1: 
         * Grafico 1 (izquierda)
         * Grafico 2 (derecha)
     - Linea 2:
         * Grafico 3 (toda la linea)
     - Linea 3:
         * Tabla
    """
    # Obtenemos los modelos
    modelos_operativos = df["operational_model"].unique()
    
    for modelo in modelos_operativos:
        df_modelo = df[df["operational_model"] == modelo].copy()

        # LINEA 1: GRAFICO 1 (IZQUIERDA) Y GRAFICO 2 (DERECHA)
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"Comportamiento Historico de demanda {modelo}")
            fig_hist = px.bar(
                df_modelo,
                x="Fecha",
                y="items",
                labels={"items": "Cantidad de Ítems", "Fecha": "Día"},
                color_discrete_sequence=["#19521b"],  # Color #19521bff
                title="",
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        with col2:
            st.subheader(f"Comportamiento Historico de demanda {modelo} por día de la semana")
            demanda_por_dia = df_modelo.groupby("day_of_week")["items"].sum().reset_index()
            # Calculamos cuántos días de la semana se registran en el df_modelo para hacer promedio
            conteo_por_dia = df_modelo.groupby("day_of_week")["Fecha"].nunique().reset_index().rename(columns={"Fecha": "Cant_dias"})
            merge_dia = pd.merge(demanda_por_dia, conteo_por_dia, on="day_of_week", how="left")
            merge_dia["items_promedio"] = merge_dia["items"] / merge_dia["Cant_dias"].replace(0, 1)
            fig_dia = px.bar(
                merge_dia,
                x="day_of_week",
                y="items_promedio",
                labels={"items_promedio": "Ítems Promedio", "day_of_week": "Día de la Semana"},
                color_discrete_sequence=["#c7e59f"],  # #c7e59fff
                title="",
            )
            st.plotly_chart(fig_dia, use_container_width=True)

        # LINEA 2: GRAFICO 3 PREFERENCIA DE SLOT
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
        st.plotly_chart(fig_slot, use_container_width=True)

        # LINEA 3: TABLA
        generar_tabla_pronostico(df_modelo, modelo)
        st.markdown("---")

if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("Archivo cargado correctamente")
    st.dataframe(df.head())

    if st.button("Generar Análisis"):
        df = procesar_datos(df)
        generar_analisis(df)

st.write("Listo para generar reportes con In-Staffing!")

