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

    # Agregar filtro de día de la semana
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dia_seleccionado = st.selectbox("📅 Selecciona un día de la semana", dias_semana)

# Función para procesar los datos con filtro de día de la semana
def procesar_datos(df):
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    df['items'] = pd.to_numeric(df['items'], errors='coerce').fillna(0)
    df['slot_from'] = pd.to_datetime(df['slot_from'], errors='coerce').dt.hour
    df['dia_semana'] = df['Fecha'].dt.day_name(locale='es_ES')
    
    df = df[df['estado'] == 'FINISHED']
    df = df[(df['slot_from'] >= hora_apertura) & (df['slot_from'] <= hora_cierre)]
    
    # Filtrar por el día seleccionado
    nombre_dia_seleccionado = dia_seleccionado.lower().capitalize()
    df = df[df['dia_semana'] == nombre_dia_seleccionado]
    
    return df

# Función para generar el reporte
def generar_reporte(df):
    df = procesar_datos(df)
    if df.empty:
        st.warning("⚠️ No hay datos disponibles para el día seleccionado.")
        return

    total_dias = df['Fecha'].dt.date.nunique()
    col1, col2 = st.columns(2)

    if 'items' in df.columns and 'slot_from' in df.columns:
        demanda_por_slot = df.groupby(['slot_from', 'operational_model'])['items'].sum().reset_index()
        chart1 = alt.Chart(demanda_por_slot).mark_line(point=True).encode(
            x='slot_from:O',
            y='items:Q',
            color='operational_model:N',
            tooltip=['slot_from', 'items', 'operational_model']
        ).properties(title=f"📊 Preferencia de Slot por Modelo Operativo - {dia_seleccionado}")
        
        col1.altair_chart(chart1, use_container_width=True)

        demanda_horaria = df.groupby('slot_from')['items'].sum() / total_dias
        ftes_horarios = (demanda_horaria / productividad_estimada).apply(np.ceil).astype(int)
        
        chart2 = alt.Chart(pd.DataFrame({'Hora': ftes_horarios.index, 'Recursos': ftes_horarios.values}))\
            .mark_bar(color='#c7e59f')\
            .encode(x='Hora:O', y='Recursos:Q', tooltip=['Hora', 'Recursos'])\
            .properties(title=f"📊 Recursos Necesarios por Hora - {dia_seleccionado}")
        
        col2.altair_chart(chart2, use_container_width=True)

    st.markdown("---")
    col3, col4 = st.columns(2)
    explicacion = f"""
    ### Justificación del Pronóstico de Recursos
    - Datos mostrados para **{dia_seleccionado}**.
    - Se calcula la demanda promedio por hora basada en el histórico.
    - En caso de evento especial, se aplica un incremento del {impacto_evento}%.
    - Los recursos se basan en una productividad estimada de {productividad_estimada} items por hora.
    """
    col4.markdown(explicacion)

# Cargar archivo CSV y ejecutar el análisis
if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    df = procesar_datos(df)
    
    if not df.empty:
        st.success(f"✅ Datos cargados para {dia_seleccionado}")
        st.dataframe(df.head())
        generar_reporte(df)
    else:
        st.warning("⚠️ No hay datos disponibles para el día seleccionado.")

st.write("🚀 Listo para generar reportes en la nube con In-Staffing!")
