import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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

# Función para generar el reporte
def generar_reporte(df):
    df = procesar_datos(df)
    if df is None:
        return

    total_dias = df['Fecha'].dt.date.nunique()

    col1, col2 = st.columns(2)

    if 'items' in df.columns and 'slot_from' in df.columns:
        demanda_por_slot = df.groupby(['slot_from', 'operational_model'])['items'].sum().reset_index()
        fig1 = px.line(demanda_por_slot, x='slot_from', y='items', color='operational_model', markers=True,
                       labels={'slot_from': 'Hora', 'items': 'Ítems'}, title="📊 Preferencia de Slot por Modelo Operativo")
        col1.plotly_chart(fig1, use_container_width=True)
        
        demanda_horaria = df.groupby('slot_from')['items'].sum() / total_dias
        ftes_horarios = (demanda_horaria / productividad_estimada).apply(np.ceil).astype(int)
        
        fig2 = px.bar(x=ftes_horarios.index, y=ftes_horarios.values, labels={'x': 'Hora', 'y': 'Recursos'},
                      title="📊 Recursos Necesarios por Hora")
        col2.plotly_chart(fig2, use_container_width=True)
    
    st.markdown("---")
    col3, col4 = st.columns(2)
    fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}

    for fecha in fechas_pronostico:
        demanda_dia_historico = df[df['Fecha'].dt.date == fecha.date()].groupby('slot_from')['items'].sum()
        recursos_dia = (demanda_dia_historico / productividad_estimada).apply(np.ceil).fillna(1).astype(int)

        if evento_especial and fecha_inicio_evento and fecha_fin_evento:
            if fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
                recursos_dia = recursos_dia * (1 + impacto_evento / 100)
                recursos_dia = recursos_dia.apply(np.ceil).astype(int)

        recursos_por_dia[fecha.date()] = recursos_dia

    recursos_df = pd.DataFrame(recursos_por_dia).fillna(1).astype(int)
    col3.header("📋 Pronóstico de Recursos por Hora vs Día")
    col3.dataframe(recursos_df)

if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("✅ Archivo cargado correctamente")
    st.dataframe(df.head())
    
    if st.button("📄 Generar Reporte PDF"):
        generar_reporte(df)

st.write("🚀 Listo para generar reportes en la nube con In-Staffing!")
