import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# Configuración de la aplicación
st.set_page_config(page_title="In-Staffing MVP", layout="wide")

# Carpeta para almacenar reportes PDF
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

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

# Función para procesar los datos
def procesar_datos(df):
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    df['items'] = pd.to_numeric(df['items'], errors='coerce').fillna(0)
    df['slot_from'] = pd.to_datetime(df['slot_from'], errors='coerce').dt.hour
    df = df[df['estado'] == 'FINISHED']
    df = df[(df['slot_from'] >= hora_apertura) & (df['slot_from'] <= hora_cierre)]
    df['day_of_week'] = df['Fecha'].dt.day_name()

    return df

# Generar gráficos de demanda por modelo operativo
def generar_graficos_demanda(df):
    modelos_operativos = df['operational_model'].unique()
    
    for modelo in modelos_operativos:
        df_modelo = df[df['operational_model'] == modelo]

        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"Comportamiento Histórico de Demanda - {modelo}")
            fig_hist = px.bar(df_modelo, x='Fecha', y='items', labels={'items': "Cantidad de Ítems", 'Fecha': "Día"})
            st.plotly_chart(fig_hist, use_container_width=True)

        with col2:
            st.subheader(f"Demanda Promedio por Día de la Semana - {modelo}")
            demanda_por_dia = df_modelo.groupby('day_of_week')['items'].sum().reset_index()
            fig_dia = px.bar(demanda_por_dia, x='day_of_week', y='items', labels={'items': "Ítems Promedio", 'day_of_week': "Día de la Semana"})
            st.plotly_chart(fig_dia, use_container_width=True)

        st.subheader(f"Preferencia de Slot - {modelo}")
        demanda_slot = df_modelo.groupby('slot_from')['items'].sum().reset_index()
        demanda_slot['% Demanda'] = (demanda_slot['items'] / demanda_slot['items'].sum()) * 100
        fig_slot = px.bar(demanda_slot, x='slot_from', y='% Demanda', labels={'slot_from': "Hora del Día", '% Demanda': "Porcentaje de Demanda"})
        st.plotly_chart(fig_slot, use_container_width=True)

# Generar tabla de pronóstico por modelo operativo
def generar_tabla_pronostico(df):
    modelos_operativos = df['operational_model'].unique()
    
    for modelo in modelos_operativos:
        df_modelo = df[df['operational_model'] == modelo]

        st.subheader(f"Pronóstico de Recursos por Hora vs Día - {modelo}")

        fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
        recursos_por_dia = {}

        for fecha in fechas_pronostico:
            fechas_historicas = [fecha.date() - timedelta(days=7 * i) for i in range(1, 5)]
            demanda_dia_historico = df_modelo[df_modelo['Fecha'].dt.date.isin(fechas_historicas)].groupby('slot_from')['items'].sum()
            recursos_dia = (demanda_dia_historico / productividad_estimada).fillna(1).astype(int)

            # Aplicar incremento de evento especial si aplica
            if evento_especial and fecha_inicio_evento and fecha_fin_evento:
                if fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
                    recursos_dia = (recursos_dia * (1 + impacto_evento / 100)).round().astype(int)

            recursos_dia = recursos_dia.apply(lambda x: max(x, 1))
            recursos_por_dia[fecha.date()] = recursos_dia

        recursos_df = pd.DataFrame(recursos_por_dia).T.fillna(1).astype(int)

        # Asegurar que las columnas corresponden a las horas de apertura y cierre
        horas = list(range(hora_apertura, hora_cierre + 1))
        for hora in horas:
            if hora not in recursos_df.columns:
                recursos_df[hora] = 1

        recursos_df = recursos_df[horas]
        st.dataframe(recursos_df)

# Cargar archivo CSV y ejecutar el análisis
if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("Archivo cargado correctamente")
    st.dataframe(df.head())

    if st.button("Generar Análisis"):
        df = procesar_datos(df)
        generar_graficos_demanda(df)
        generar_tabla_pronostico(df)

st.write("Listo para generar reportes con In-Staffing!")

