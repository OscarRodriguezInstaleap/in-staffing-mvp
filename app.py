import streamlit as st
import pandas as pd
import os
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

# Estilos gráficos
plt.rcParams['font.family'] = 'Montserrat'
sns.set_style("whitegrid")

st.title("📊 In-Staffing: Planificación de Recursos")
st.markdown("---")

# Sección para cargar el archivo CSV
st.header("📂 Cargar Archivo CSV")
archivo_csv = st.file_uploader("Sube un archivo de datos de operaciones (CSV)", type=["csv"])

# Parámetros adicionales en la barra lateral
st.sidebar.header("⚙️ Configuración de Parámetros")

# Horario de tienda
hora_apertura = st.sidebar.slider("Hora de apertura de tienda", 0, 23, 8)
hora_cierre = st.sidebar.slider("Hora de cierre de tienda", 0, 23, 22)
turno_recursos = st.sidebar.slider("Duración del turno de trabajo (horas)", 4, 12, 8)

# Factor productivo (antes llamado Factor de Fatiga)
factor_productivo = st.sidebar.slider("Factor Productivo (%)", min_value=50, max_value=100, value=85, step=1)

# Evento especial
evento_especial = st.sidebar.checkbox("¿Habrá un evento especial?")
if evento_especial:
    fecha_inicio = st.sidebar.date_input("Fecha de inicio del evento")
    fecha_fin = st.sidebar.date_input("Fecha de fin del evento")
    impacto_evento = st.sidebar.slider("Incremento en demanda (%)", min_value=0, max_value=100, value=20, step=1)

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

def generar_scorecard(df):
    # Crear scorecard basado en items recolectados, velocidad y cumplimiento de tiempos óptimos
    df['tiempo_picking'] = (df['actual_fin_picking'] - df['actual_inicio_picking']).dt.total_seconds() / 60
    df['cumplimiento_tiempo'] = (df['actual_fin_picking'] <= df['optimo_fin_picking']).astype(int)
    df['puntaje'] = df['items'] * 0.5 + (1 / df['tiempo_picking']) * 0.3 + df['cumplimiento_tiempo'] * 0.2
    ranking = df.groupby('picker')['puntaje'].mean().sort_values(ascending=False)
    st.header("🏆 Scorecard de Productividad de Pickers")
    st.dataframe(ranking)
    return ranking

def generar_reporte(df):
    if df is None or df.empty:
        st.error("No hay datos para generar el reporte.")
        return
    
    df, productividad_promedio = procesar_datos(df)
    ranking = generar_scorecard(df)
    
    # Calcular FTEs por hora basado en la productividad real de la tienda
    df['FTEs'] = (df['items'] / productividad_promedio) * (factor_productivo / 100)
    if evento_especial:
        df['FTEs'] *= (1 + impacto_evento / 100)
    
    # Calcular máximos recursos involucrados históricamente
    max_recursos_historicos = df.groupby('Hora')['picker'].nunique()
    
    # Agrupar datos por hora para el promedio general
    df['Dia'] = df['Fecha'].dt.date
    resumen = df.groupby('Hora')['FTEs'].mean()
    
    # Graficar los FTEs promedio por hora con límite de recursos históricos
    st.header("📊 Pronóstico Promedio de Recursos por Hora")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(x=resumen.index, y=resumen.values, ax=ax, color="#c7e59f", label="Recursos Necesarios")
    ax.bar(resumen.index, max_recursos_historicos, color="#a7baf0", alpha=0.5, label="Máximo Histórico")
    ax.set_xlabel("Hora del Día")
    ax.set_ylabel("FTEs Necesarios")
    ax.set_title("Recursos Promedio Necesarios por Hora")
    ax.legend()
    st.pyplot(fig)
    
    # Generar sugerencia de mayas de trabajo
    sugerencias = df.groupby(['Dia', 'Hora'])['picker'].apply(lambda x: x.mode()).tail(30)
    st.header("📅 Sugerencia de Mayas de Trabajo para los Próximos 30 Días")
    st.dataframe(sugerencias)
    
    # Generación del Reporte en PDF
    report_name = f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    report_path = os.path.join(REPORTS_DIR, report_name)
    try:
        c = canvas.Canvas(report_path, pagesize=letter)
        c.drawString(100, 750, "Reporte de Planificación de Recursos")
        c.drawString(100, 730, f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawString(100, 710, f"Factor Productivo: {factor_productivo}%")
        c.drawString(100, 690, f"Productividad promedio: {round(productividad_promedio, 2)} items/hora")
        c.save()
        st.success(f"✅ Reporte generado: {report_name}")
        with open(report_path, "rb") as f:
            st.download_button("📥 Descargar Reporte", f, file_name=report_name, mime="application/pdf")
    except Exception as e:
        st.error(f"❌ Error al generar el reporte PDF: {e}")

# Cargar y visualizar el CSV
if archivo_csv is not None:
    df = pd.read_csv(archivo_csv)
    st.success("✅ Archivo cargado correctamente")
    st.dataframe(df.head())

    if st.button("📄 Generar Reporte PDF"):
        generar_reporte(df)

st.write("🚀 Listo para generar reportes en la nube con Streamlit!")
