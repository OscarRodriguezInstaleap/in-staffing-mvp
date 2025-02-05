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
pass  # Asegura que este bloque no esté vacío para evitar errores de indentación

with st.expander("📅 ¿Evento Especial?"):
    pass  # Asegura que este bloque no esté vacío para evitar errores de indentación

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
df = df[(df['Hora'] >= 8) & (df['Hora'] <= 22)]

return df

def generar_reporte(df):
df = procesar_datos(df)
if df is None:
return

total_dias = df['Fecha'].dt.date.nunique()

if 'items' in df.columns and 'slot_from' in df.columns:
    demanda_horaria = df.groupby('slot_from')['items'].sum() / total_dias
    ftes_horarios = (demanda_horaria / 100).apply(np.ceil).astype(int)

    st.header("📊 Recursos Necesarios por Hora")
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(x=ftes_horarios.index, y=ftes_horarios.values, ax=ax, color="#c7e59f")
    ax.set_xlabel("Hora del Dia")
    ax.set_ylabel("Numero de Recursos (FTE)")
    ax.set_title("Recursos Necesarios por Hora")
    st.pyplot(fig)

    fechas_pronostico = pd.date_range(start=datetime.now() + timedelta(days=1), periods=7)
    recursos_por_dia = {}

    for fecha in fechas_pronostico:
        demanda_dia_historico = df[df['Fecha'].dt.date == fecha.date()].groupby('slot_from')['items'].sum()
        recursos_dia = (demanda_dia_historico / 100).apply(np.ceil).fillna(1).astype(int)

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
