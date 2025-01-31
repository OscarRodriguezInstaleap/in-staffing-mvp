import streamlit as st
import pandas as pd
import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Configuración de la aplicación
st.set_page_config(page_title="In-Staffing MVP", layout="wide")

# Carpeta para almacenar reportes PDF
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

# Estilos gráficos mejorados
plt.rcParams['font.family'] = 'Montserrat'
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.spines.right'] = False
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.linestyle'] = '--'
sns.set_style("whitegrid")

def procesar_datos(df):
    # Convertir columnas de fecha y hora a datetime
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    df['actual_inicio_picking'] = pd.to_datetime(df['actual_inicio_picking'], errors='coerce')
    df['actual_fin_picking'] = pd.to_datetime(df['actual_fin_picking'], errors='coerce')
    df['items'] = pd.to_numeric(df['items'], errors='coerce')
    
    # Filtrar solo las órdenes con estado 'FINISHED'
    df = df[df['estado'] == 'FINISHED']
    
    # Calcular la productividad promedio de los pickers
    productividad_promedio = df.groupby('picker')['items'].mean().mean()
    if pd.isna(productividad_promedio):
        productividad_promedio = 100  # Valor por defecto si no hay datos
    
    # Filtrar datos dentro del horario de tienda
    df['Hora'] = df['actual_inicio_picking'].dt.hour
    df = df[(df['Hora'] >= hora_apertura) & (df['Hora'] <= hora_cierre)]
    
    return df, productividad_promedio

def generar_reporte(df):
    if df is None or df.empty:
        st.error("No hay datos para generar el reporte.")
        return
    
    df, productividad_promedio = procesar_datos(df)
    
    # Corregir lógica de Factor Productivo
    df['FTEs'] = (df['items'] / productividad_promedio) / (factor_productivo / 100)
    if evento_especial:
        df['FTEs'] *= (1 + impacto_evento / 100)
    
    # Filtrar valores extremos (percentil 80)
    lower_bound, upper_bound = np.percentile(df['FTEs'].dropna(), [10, 90])
    df = df[(df['FTEs'] >= lower_bound) & (df['FTEs'] <= upper_bound)]
    
    # Agrupar datos por hora usando la mediana
    df['Dia'] = df['Fecha'].dt.date
    resumen = df.groupby('Hora')['FTEs'].median()
    
    # Crear layout de primera fila con gráfica y tabla semaforizada
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📊 Pronóstico Mediano de Recursos por Hora")
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.barplot(x=resumen.index, y=resumen.values, ax=ax, color="#c7e59f", label="Recursos Necesarios")
        ax.set_xlabel("Hora del Día", fontsize=12)
        ax.set_ylabel("FTEs Necesarios", fontsize=12)
        ax.set_title("Recursos Medianos Necesarios por Hora", fontsize=14, fontweight='bold')
        st.pyplot(fig)
    
    with col2:
        st.header("📋 Resumen Hora vs Día")
        resumen_tabla = df.groupby(['Dia', 'Hora'])['FTEs'].sum().unstack().tail(dias_pronostico)
        st.dataframe(resumen_tabla.style.applymap(lambda x: "background-color: #ffcccc" if x > resumen.median() * 1.5 else ("background-color: #ccffcc" if x < resumen.median() * 0.5 else "")))
    
    # Tabla de Productividad de Pickers
    st.header("🏆 Productividad de Pickers")
    ranking = df.groupby('picker').agg({
        'items': 'sum',
        'actual_fin_picking': 'count',
        'ontime': lambda x: (x == 'on_time').sum()
    }).rename(columns={'items': 'Total Items', 'actual_fin_picking': 'Órdenes Procesadas', 'ontime': 'Órdenes On_Time'})
    ranking['Velocidad Promedio (Items/h)'] = ranking['Total Items'] / ranking['Órdenes Procesadas']
    ranking['% Órdenes On_Time'] = (ranking['Órdenes On_Time'] / ranking['Órdenes Procesadas']) * 100
    ranking['Puntaje'] = ranking[['Total Items', 'Velocidad Promedio (Items/h)', '% Órdenes On_Time']].mean(axis=1)
    ranking.fillna(1, inplace=True)  # Reemplazar valores None por 1
    ranking = ranking.sort_values(by='Puntaje', ascending=False)
    st.dataframe(ranking)

# Configuración de la Aplicación
st.title("📊 In-Staffing: Planificación de Recursos")
st.markdown("---")

# Sección para cargar el archivo CSV
st.header("📂 Cargar Archivo CSV")
archivo_csv = st.file_uploader("Sube un archivo de datos de operaciones (CSV)", type=["csv"])

if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("✅ Archivo cargado correctamente")
    st.dataframe(df.head())
    
    if st.button("📄 Generar Reporte PDF"):
        generar_reporte(df)
