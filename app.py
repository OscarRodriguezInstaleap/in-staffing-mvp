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

# Generar la tabla de pronóstico
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

        recursos_dia = recursos_dia.apply(lambda x: max(x, 1))  # Asegurar mínimo 1 recurso por hora
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
    st.dataframe(recursos_df)

# Generar gráfico de Preferencia de Slot
def generar_grafico_slot(df):
    demanda_slot = df.groupby(['slot_from', 'operational_model'])['items'].sum().reset_index()
    fig = px.line(demanda_slot, x='slot_from', y='items', color='operational_model', markers=True, 
                  labels={'slot_from': "Hora del Día", 'items': "Cantidad de Ítems"},
                  title="📊 Preferencia de Slot por Modelo Operativo")
    st.plotly_chart(fig, use_container_width=True)

# Generar gráfico de Recursos Necesarios por Hora
def generar_grafico_recursos(df):
    demanda_horaria = df.groupby('slot_from')['items'].sum() / df['Fecha'].dt.date.nunique()
    ftes_horarios = (demanda_horaria / productividad_estimada).apply(np.ceil).astype(int)

    fig = px.bar(x=ftes_horarios.index, y=ftes_horarios.values, 
                 labels={'x': "Hora del Día", 'y': "Recursos Necesarios"},
                 title="📊 Recursos Necesarios por Hora")
    st.plotly_chart(fig, use_container_width=True)

# Score Card de Productividad de Pickers
def generar_score_card(df):
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

    st.dataframe(ranking)

# Cargar archivo CSV y ejecutar el análisis
if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("✅ Archivo cargado correctamente")
    st.dataframe(df.head())

    if st.button("📊 Generar Análisis"):
        generar_grafico_slot(df)
        generar_grafico_recursos(df)
        generar_tabla_pronostico(df)
        generar_score_card(df)

st.write("🚀 Listo para generar reportes en la nube con In-Staffing!")
