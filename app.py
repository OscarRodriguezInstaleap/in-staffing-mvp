import streamlit as st
import pandas as pd
import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

st.set_page_config(page_title="In-Staffing MVP", layout="wide")

REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

plt.rcParams['font.family'] = 'Montserrat'
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.spines.right'] = False
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.linestyle'] = '--'
sns.set_style("whitegrid")

st.title("📊 In-Staffing: Planificacion de Recursos")
st.markdown("---")

st.header("📂 Cargar Archivo CSV")
archivo_csv = st.file_uploader("Sube un archivo de datos de operaciones (CSV)", type=["csv"])

with st.sidebar:
with st.expander("⚙️ Configuraciones Generales"):
hora_apertura = st.slider("Hora de apertura de tienda", 0, 23, 8)
hora_cierre = st.slider("Hora de cierre de tienda", 0, 23, 22)
turno_recursos = st.slider("Duracion del turno de trabajo (horas)", 4, 12, 8)
factor_productivo = st.slider("Factor Productivo (%)", min_value=50, max_value=100, value=85, step=1)
productividad_estimada = st.number_input("Productividad Estimada por Hora", min_value=10, max_value=500, value=100, step=10)

    fecha_inicio_pronostico = st.date_input("Fecha de inicio del pronostico", datetime.now() + timedelta(days=1))
    fecha_fin_pronostico = st.date_input("Fecha de fin del pronostico", fecha_inicio_pronostico + timedelta(days=30))
    
    if (fecha_fin_pronostico - fecha_inicio_pronostico).days > 31:
        st.error("El periodo del pronostico no puede ser mayor a 31 dias.")
    if (fecha_inicio_pronostico - datetime.now().date()).days > 21:
        st.error("No se pueden crear pronosticos con mas de 3 semanas de anticipacion.")

with st.expander("📅 ¿Evento Especial?"):
    evento_especial = st.checkbox("¿Habra un evento especial?")
    if evento_especial:
        fecha_inicio_evento = st.date_input("Fecha de inicio del evento")
        fecha_fin_evento = st.date_input("Fecha de fin del evento")
        impacto_evento = st.slider("Incremento en demanda (%)", min_value=0, max_value=200, value=20, step=1)

def procesar_datos(df):
columnas_requeridas = ['Fecha', 'estado']
columnas_opcionales = ['items', 'slot_from', 'picker', 'ontime', 'actual_inicio_picking', 'actual_fin_picking']

for col in columnas_requeridas:
    if col not in df.columns:
        st.error(f"La columna requerida '{col}' no esta presente en el archivo. Por favor, verifica el archivo cargado.")
        return None

if 'Fecha' in df.columns:
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')

if 'items' in df.columns:
    df['items'] = pd.to_numeric(df['items'], errors='coerce').fillna(0)

if 'slot_from' in df.columns:
    df['slot_from'] = pd.to_datetime(df['slot_from'], errors='coerce').dt.hour

if 'picker' in df.columns:
    df['picker'] = df['picker'].fillna('Sin_Asignar')

if 'ontime' in df.columns:
    df['ontime'] = df['ontime'].fillna('unknown')

if 'actual_inicio_picking' in df.columns:
    df['Hora'] = pd.to_datetime(df['actual_inicio_picking'], errors='coerce').dt.hour
else:
    df['Hora'] = df['Fecha'].dt.hour

df = df[df['estado'] == 'FINISHED']
df = df[(df['Hora'] >= hora_apertura) & (df['Hora'] <= hora_cierre)]

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
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(x=ftes_horarios.index, y=ftes_horarios.values, ax=ax, color="#c7e59f")
    ax.set_xlabel("Hora del Dia")
    ax.set_ylabel("Numero de Recursos (FTE)")
    ax.set_title("Recursos Necesarios por Hora")
    st.pyplot(fig)

    fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}

    for fecha in fechas_pronostico:
        demanda_dia_historico = df[df['Fecha'].dt.date == fecha.date()].groupby('slot_from')['items'].sum()
        recursos_dia = (demanda_dia_historico / productividad_estimada).apply(np.ceil).fillna(1).astype(int)

        if evento_especial and fecha_inicio_evento <= fecha.date() <= fecha_fin_evento:
            recursos_dia *= (1 + impacto_evento / 100)
            recursos_dia = recursos_dia.apply(np.ceil).astype(int)

        recursos_por_dia[fecha.date()] = recursos_dia

    recursos_df = pd.DataFrame(recursos_por_dia).fillna(1).astype(int)
    st.header("📋 Recursos por Hora vs Dia")
    st.dataframe(recursos_df)
else:
    st.warning("No se puede calcular el numero de recursos porque faltan las columnas 'items' o 'slot_from'.")

if 'picker' in df.columns and 'items' in df.columns:
    st.header("🏆 Productividad de Pickers")
    ranking = df.groupby('picker').agg({
        'items': 'sum',
        'actual_fin_picking': 'count' if 'actual_fin_picking' in df.columns else 'size',
        'ontime': lambda x: (x == 'on_time').sum() if 'ontime' in df.columns else 0
    }).rename(columns={'items': 'Total_Items', 'actual_fin_picking': 'Ordenes_Procesadas', 'ontime': 'Ordenes_On_Time'})

    ranking['Velocidad_Promedio_Items_h'] = (ranking['Total_Items'] / ranking['Ordenes_Procesadas']).fillna(0)
    if 'Ordenes_On_Time' in ranking.columns:
        ranking['Porcentaje_Ordenes_On_Time'] = ((ranking['Ordenes_On_Time'] / ranking['Ordenes_Procesadas']) * 100).fillna(0)
    else:
        ranking['Porcentaje_Ordenes_On_Time'] = 0

    ranking['Puntaje'] = (ranking['Total_Items'] * 0.4 + ranking['Velocidad_Promedio_Items_h'] * 0.3 + ranking['Porcentaje_Ordenes_On_Time'] * 0.3).apply(lambda x: min(100, round(x)))
    ranking = ranking.sort_values(by='Puntaje', ascending=False)
    st.dataframe(ranking)
else:
    st.warning("No se puede generar el scorecard de productividad porque faltan las columnas 'picker' o 'items'.")

if archivo_csv is not None:
df = pd.read_csv(archivo_csv)
st.success("✅ Archivo cargado correctamente")
st.dataframe(df.head())

if st.button("📄 Generar Reporte PDF"):
    generar_reporte(df)

st.write("🚀 Listo para generar reportes en la nube con In-Staffing!")
