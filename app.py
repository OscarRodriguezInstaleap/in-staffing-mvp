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
        turno_recursos = st.slider("Duración del turno de trabajo (horas)", 4, 12, 8)
        factor_productivo = st.slider("Factor Productivo (%)", min_value=50, max_value=100, value=85, step=1)
        productividad_estimada = st.number_input("Productividad Estimada por Hora", min_value=10, max_value=500, value=100, step=10)

        # Fechas del pronóstico
        fecha_inicio_pronostico = st.date_input("Fecha de inicio del pronóstico", datetime.now() + timedelta(days=1))
        fecha_fin_pronostico = st.date_input("Fecha de fin del pronóstico", fecha_inicio_pronostico + timedelta(days=30))
        
        if (fecha_fin_pronostico - fecha_inicio_pronostico).days > 31:
            st.error("El periodo del pronóstico no puede ser mayor a 31 días.")
        if (fecha_inicio_pronostico - datetime.now().date()).days > 21:
            st.error("No se pueden crear pronósticos con más de 3 semanas de anticipación.")

    with st.expander("📅 ¿Evento Especial?"):
        evento_especial = st.checkbox("¿Habrá un evento especial?")
        if evento_especial:
            fecha_inicio_evento = st.date_input("Fecha de inicio del evento")
            fecha_fin_evento = st.date_input("Fecha de fin del evento")
            impacto_evento = st.slider("Incremento en demanda (%)", min_value=0, max_value=200, value=20, step=1)
    
    resumen_detallado = st.checkbox("📊 Resumen Detallado (Día por Día)")

def procesar_datos(df):
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    df['actual_inicio_picking'] = pd.to_datetime(df['actual_inicio_picking'], errors='coerce')
    df['actual_fin_picking'] = pd.to_datetime(df['actual_fin_picking'], errors='coerce')
    df['items'] = pd.to_numeric(df['items'], errors='coerce').fillna(0)
    df['slot_from'] = pd.to_datetime(df['slot_from'], errors='coerce').dt.hour
    df['picker'] = df['picker'].fillna('Sin_Asignar')
    df['ontime'] = df['ontime'].fillna('unknown')
    
    df = df[df['estado'] == 'FINISHED']
    df['Hora'] = df['actual_inicio_picking'].dt.hour
    df = df[(df['Hora'] >= hora_apertura) & (df['Hora'] <= hora_cierre)]
    
    return df

def limpiar_columnas_y_indices(df):
    df.columns = df.columns.map(str).str.replace(r'[^a-zA-Z0-9_]', '', regex=True)
    df.index = df.index.map(str).str.replace(r'[^a-zA-Z0-9_]', '', regex=True)
    return df

def generar_reporte(df):
    df = procesar_datos(df)
    total_dias = df['Fecha'].dt.date.nunique()

    # Preferencia Histórica de Demanda
    demanda_por_slot = df.groupby(['slot_from', 'operational_model'])['items'].sum().reset_index()
    demanda_total = demanda_por_slot.groupby('operational_model')['items'].transform('sum')
    demanda_por_slot['% Demanda'] = (demanda_por_slot['items'] / demanda_total) * 100

    col1, col2 = st.columns(2)
    with col1:
        st.header("📊 Preferencia Histórica de Demanda")
        fig, ax = plt.subplots(figsize=(10, 5))
        for model in demanda_por_slot['operational_model'].unique():
            data = demanda_por_slot[demanda_por_slot['operational_model'] == model]
            ax.plot(data['slot_from'], data['% Demanda'], marker='o', label=model)
        ax.set_xlabel("Hora del Día")
        ax.set_ylabel("% de Demanda")
        ax.set_title("Distribución Histórica de la Demanda por Modelo Operativo")
        ax.legend()
        st.pyplot(fig)

    # Cálculo de FTEs por hora
    demanda_horaria = df.groupby('slot_from')['items'].sum() / total_dias
    ftes_horarios = (demanda_horaria.shift(-1).fillna(0) / productividad_estimada).apply(np.ceil).astype(int)

    with col2:
        st.header("📊 Número de Recursos por Hora")
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.barplot(x=ftes_horarios.index, y=ftes_horarios.values, ax=ax, color="#c7e59f")
        ax.set_xlabel("Hora del Día")
        ax.set_ylabel("Número de Recursos (FTE)")
        ax.set_title("Recursos Necesarios por Hora")
        st.pyplot(fig)

    # Cuadro de Recursos por Hora vs Día
    st.header("📋 Recursos por Hora vs Día")
    fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, end=fecha_fin_pronostico)
    recursos_por_dia = {}

    for fecha in fechas_pronostico:
        fechas_historicas = [fecha - pd.DateOffset(months=m) for m in range(1, 4)]
        demanda_dia_historico = df[df['Fecha'].dt.date.isin([f.date() for f in fechas_historicas])].groupby('slot_from')['items'].mean()
        recursos_dia = (demanda_dia_historico / productividad_estimada).apply(np.ceil).fillna(1).astype(int) + 1
        recursos_por_dia[fecha.date()] = recursos_dia

    recursos_df = pd.DataFrame(recursos_por_dia).T.fillna(1).astype(int)
    recursos_df = limpiar_columnas_y_indices(recursos_df)
    
    # Inspección para encontrar valores problemáticos
    st.write("🔍 Verificación de Recursos por Hora vs Día:")
    st.write(recursos_df.head(10))

    st.dataframe(recursos_df)

    # Productividad de Pickers
    st.header("🏆 Productividad de Pickers")
    ranking = df.groupby('picker').agg({
        'items': 'sum',
        'actual_fin_picking': 'count',
        'ontime': lambda x: (x == 'on_time').sum()
    }).rename(columns={'items': 'Total_Items', 'actual_fin_picking': 'Ordenes_Procesadas', 'ontime': 'Ordenes_On_Time'})

    ranking['Velocidad_Promedio_Items_h'] = (ranking['Total_Items'] / ranking['Ordenes_Procesadas']).fillna(0)
    ranking['Porcentaje_Ordenes_On_Time'] = ((ranking['Ordenes_On_Time'] / ranking['Ordenes_Procesadas']) * 100).fillna(0)
    ranking['Puntaje'] = (ranking['Total_Items'] * 0.4 + ranking['Velocidad_Promedio_Items_h'] * 0.3 + ranking['Porcentaje_Ordenes_On_Time'] * 0.3).apply(lambda x: min(100, round(x)))
    ranking = ranking.sort_values(by='Puntaje', ascending=False)
    ranking = limpiar_columnas_y_indices(ranking)

    # Inspección para encontrar valores problemáticos en el ranking
    st.write("🔍 Verificación de Productividad de Pickers:")
    st.write(ranking.head(10))

    st.dataframe(ranking)

if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("✅ Archivo cargado correctamente")
    st.dataframe(df.head())
    
    if st.button("📄 Generar Reporte PDF"):
        generar_reporte(df)

st.write("🚀 Listo para generar reportes en la nube con Streamlit!")
