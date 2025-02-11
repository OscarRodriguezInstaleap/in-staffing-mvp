import streamlit as st
import pandas as pd
import os
import numpy as np
import altair as alt
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

with st.expander("📅 ¿Evento Especial?"):
    evento_especial = st.checkbox("¿Habrá un evento especial?")
    fecha_inicio_evento = None
    fecha_fin_evento = None
    impacto_evento = 0
    
    if evento_especial:
        fecha_inicio_evento = st.date_input("Fecha de inicio del evento")
        fecha_fin_evento = st.date_input("Fecha de fin del evento")
        impacto_evento = st.slider("Incremento en demanda (%)", min_value=0, max_value=200, value=20, step=1)

def procesar_datos(df):
df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
df['items'] = pd.to_numeric(df['items'], errors='coerce').fillna(0)
df['slot_from'] = pd.to_datetime(df['slot_from'], errors='coerce').dt.hour
df = df[df['estado'] == 'FINISHED']
df = df[(df['slot_from'] >= hora_apertura) & (df['slot_from'] <= hora_cierre)]
return df

def generar_reporte(df):
df = procesar_datos(df)
if df is None:
return

total_dias = df['Fecha'].dt.date.nunique()

if 'items' in df.columns and 'slot_from' in df.columns:
    demanda_horaria = df.groupby('slot_from')['items'].sum() / total_dias
    ftes_horarios = (demanda_horaria / productividad_estimada).apply(np.ceil).astype(int)

    st.header("📊 Recursos Necesarios por Hora")
    chart = alt.Chart(pd.DataFrame({'Hora': ftes_horarios.index, 'Recursos': ftes_horarios.values}))\
        .mark_bar(color='#c7e59f')\
        .encode(x='Hora:O', y='Recursos:Q')\
        .properties(title="Recursos Necesarios por Hora")
    st.altair_chart(chart, use_container_width=True)

    fechas_pronostico = pd.date_range(start=datetime.now() + timedelta(days=1), periods=7)
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
    st.header("📋 Recursos por Hora vs Día")
    st.dataframe(recursos_df)
else:
    st.warning("No se puede calcular el número de recursos porque faltan las columnas 'items' o 'slot_from'.")

if archivo_csv is not None:
df = pd.read_csv(archivo_csv)
st.success("✅ Archivo cargado correctamente")
st.dataframe(df.head())

if st.button("📄 Generar Reporte PDF"):
    generar_reporte(df)

st.write("🚀 Listo para generar reportes en la nube con In-Staffing!")
