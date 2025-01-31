import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt
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
st.sidebar.header("⚙️ Configuración de Parámetros")

# Horario de tienda
hora_apertura = st.sidebar.slider("Hora de apertura de tienda", 0, 23, 8)
hora_cierre = st.sidebar.slider("Hora de cierre de tienda", 0, 23, 22)
turno_recursos = st.sidebar.slider("Duración del turno de trabajo (horas)", 4, 12, 8)

# Factor de fatiga (cómo afecta el rendimiento de los empleados)
factor_fatiga = st.sidebar.slider("Factor de Fatiga (%)", min_value=50, max_value=100, value=85, step=1)

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
    
    # Filtrar datos dentro del horario de tienda
    df['Hora'] = df['actual_inicio_picking'].dt.hour
    df = df[(df['Hora'] >= hora_apertura) & (df['Hora'] <= hora_cierre)]
    
    return df

def generar_reporte(df):
    if df is None or df.empty:
        st.error("No hay datos para generar el reporte.")
        return
    
    df = procesar_datos(df)
    
    # Calcular FTEs por hora
    df['FTEs'] = (df['items'] / 19) * (factor_fatiga / 100)
    if evento_especial:
        df['FTEs'] *= (1 + impacto_evento / 100)
    
    # Agrupar datos por hora y día
    df['Dia'] = df['Fecha'].dt.date
    resumen = df.groupby(['Dia', 'Hora'])['FTEs'].sum().unstack()
    
    # Generar gráficos
    st.header("📈 Pronóstico de Recursos para los Próximos 30 Días")
    fig, ax = plt.subplots(figsize=(12, 6))
    for dia in resumen.index[-30:]:
        ax.plot(resumen.columns, resumen.loc[dia], label=dia.strftime('%Y-%m-%d'))
    ax.set_xlabel("Hora del Día")
    ax.set_ylabel("FTEs Necesarios")
    ax.legend()
    st.pyplot(fig)
    
    # Generación del Reporte en PDF
    report_name = f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    report_path = os.path.join(REPORTS_DIR, report_name)
    try:
        c = canvas.Canvas(report_path, pagesize=letter)
        c.drawString(100, 750, "Reporte de Planificación de Recursos")
        c.drawString(100, 730, f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawString(100, 710, f"Factor de Fatiga: {factor_fatiga}%")
        if evento_especial:
            c.drawString(100, 690, f"Evento Especial: {fecha_inicio} - {fecha_fin} (+{impacto_evento}%)")
        c.drawString(100, 670, "Resumen de Productividad:")
        
        y_position = 650
        productividad = df.groupby('picker')['items'].sum().reset_index()
        for index, row in productividad.iterrows():
            c.drawString(100, y_position, f"{row['picker']}: {row['items']} ítems recogidos")
            y_position -= 20
            if y_position < 100:
                break
        
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
