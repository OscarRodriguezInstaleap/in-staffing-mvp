import streamlit as st
import pandas as pd
import os
from datetime import datetime
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

# Factor de fatiga (cómo afecta el rendimiento de los empleados)
factor_fatiga = st.sidebar.slider("Factor de Fatiga (%)", min_value=50, max_value=100, value=85, step=1)

# Evento especial
evento_especial = st.sidebar.checkbox("¿Habrá un evento especial?")
if evento_especial:
    fecha_inicio = st.sidebar.date_input("Fecha de inicio del evento")
    fecha_fin = st.sidebar.date_input("Fecha de fin del evento")
    impacto_evento = st.sidebar.slider("Incremento en demanda (%)", min_value=0, max_value=100, value=20, step=1)

def generar_reporte(df, factor_fatiga, evento_especial, impacto_evento):
    if df is None:
        st.error("No hay datos para generar el reporte.")
        return
    
    try:
        # Convertir la columna relevante a numérico
        df.iloc[:, 1] = pd.to_numeric(df.iloc[:, 1], errors="coerce")
        
        if df.iloc[:, 1].isna().sum() > 0:
            st.error("❌ Hay valores no numéricos en la columna de datos. Verifica el archivo CSV.")
            return

        # Aplicar factor de fatiga y eventos especiales en el cálculo
        ajuste_fatiga = factor_fatiga / 100
        ajuste_evento = (1 + impacto_evento / 100) if evento_especial else 1
        
        df['Recursos Necesarios'] = (df.iloc[:, 1] / 19) * ajuste_fatiga * ajuste_evento
    
    except Exception as e:
        st.error(f"❌ Error en el cálculo del pronóstico: {e}")
        return

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
        generar_reporte(df, factor_fatiga, evento_especial, impacto_evento)

st.write("🚀 Listo para generar reportes en la nube con Streamlit!")
