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

st.title("📊 In-Staffing: Planificación de Recursos")
st.markdown("---")

# Sección para cargar el archivo CSV
st.header("📂 Cargar Archivo CSV")
archivo_csv = st.file_uploader("Sube un archivo de datos de operaciones (CSV)", type=["csv"])

# Parámetros adicionales en la barra lateral
with st.sidebar:
    with st.expander("⚙️ Configuraciones Generales"):
        hora_apertura = st.slider("Hora de apertura de tienda", 0, 23, 8)
        hora_cierre = st.slider("Hora de cierre de tienda", 0, 23, 22)
        productividad_estimada = st.number_input("Productividad Estimada por Hora", min_value=10, max_value=500, value=100, step=10)

        # Fechas del pronóstico
        fecha_inicio_pronostico = st.date_input("Fecha de inicio del pronóstico", datetime.now() + timedelta(days=1))
        fecha_fin_pronostico = st.date_input("Fecha de fin del pronóstico", fecha_inicio_pronostico + timedelta(days=30))
        
        if (fecha_fin_pronostico - fecha_inicio_pronostico).days > 30:
            st.error("El periodo del pronóstico no puede ser mayor a 30 días.")

    with st.expander("📅 ¿Evento Especial?"):
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
    return df

# Función para generar el pronóstico en formato de tabla
def generar_tabla_pronostico(df):
    df = procesar_datos(df)
    if df is None or df.empty:
        st.warning("No hay datos disponibles para generar el pronóstico.")
        return

    total_dias = df['Fecha'].dt.date.nunique()
    
    # Generar fechas del pronóstico
    fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    
    # Crear un diccionario para almacenar los datos del pronóstico
    recursos_por_dia = {}

    for fecha in fechas_pronostico:
        demanda_dia_historico = df[df['Fecha'].dt.date.isin([fecha.date() - timedelta(days=30*i) for i in range(1, 4)])].groupby('slot_from')['items'].mean()
        recursos_dia = (demanda_dia_historico / productividad_estimada).fillna(1).astype(int)

        # Aplicar incremento de evento especial si aplica
        if evento_especial and fecha_inicio_evento and fecha_fin_evento:
            if fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
                recursos_dia = (recursos_dia * (1 + impacto_evento / 100)).round().astype(int)

        recursos_por_dia[fecha.date()] = recursos_dia

    # Convertir el diccionario en DataFrame
    recursos_df = pd.DataFrame(recursos_por_dia).T.fillna(1).astype(int)
    
    # Asegurar que las columnas corresponden a las horas de apertura y cierre
    horas = list(range(hora_apertura, hora_cierre + 1))
    for hora in horas:
        if hora not in recursos_df.columns:
            recursos_df[hora] = 1  # Asignar mínimo 1 recurso si no hay datos
    
    # Ordenar las columnas para que aparezcan en orden de las horas del día
    recursos_df = recursos_df[horas]

    # Mostrar la tabla con formato
    st.header("📋 Pronóstico de Recursos por Hora vs Día")
    st.dataframe(recursos_df.style.applymap(lambda x: 'background-color: lightgreen' if x < 5 else 
                                                       'background-color: yellow' if 5 <= x < 10 else 
                                                       'background-color: red'))

# Cargar archivo CSV y ejecutar el análisis
if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("✅ Archivo cargado correctamente")
    st.dataframe(df.head())

    if st.button("📄 Generar Pronóstico"):
        generar_tabla_pronostico(df)

st.write("🚀 Listo para generar reportes en la nube con In-Staffing!")
