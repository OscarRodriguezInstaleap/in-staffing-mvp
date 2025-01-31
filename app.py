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

def generar_reporte(df):
    if df is None:
        st.error("No hay datos para generar el reporte.")
        return

    # Simulación de pronóstico (Ejemplo basado en la primera columna de datos)
    try:
        df['Recursos Necesarios'] = df.iloc[:, 1] / 19
    except Exception as e:
        st.error(f"Error en el cálculo del pronóstico: {e}")
        return

    # Generación del Reporte en PDF
    report_name = f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    report_path = os.path.join(REPORTS_DIR, report_name)

    try:
        c = canvas.Canvas(report_path, pagesize=letter)
        c.drawString(100, 750, "Reporte de Planificación de Recursos")
        c.drawString(100, 730, f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawString(100, 710, "Factor de Fatiga: 85%")  # Valor predeterminado
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
