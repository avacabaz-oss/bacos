import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="Consolidador con Formato Estricto", layout="wide")

def procesar_bcp(df_bcp, nombre_archivo):
    # 1. Limpieza inicial: buscamos donde empieza la data real
    df = df_bcp.copy()
    
    # 2. Extracción de Metadatos del BCP
    # Asumimos que el número de cuenta está en las primeras filas
    cuenta_completa = str(df.iloc[0, 1]) # Ajusta según la estructura de tu CSV
    ultimos_3 = cuenta_completa[-3:] if len(cuenta_completa) >= 3 else "010"
    
    # 3. Conversión de fechas
    df['Fecha_dt'] = pd.to_datetime(df['Fecha'], dayfirst=True)
    
    # 4. Creación de columnas según tu formato
    df.insert(0, 'Año', df['Fecha_dt'].dt.year)
    df.insert(1, 'Mes', df['Fecha_dt'].dt.month)
    df.insert(2, 'Semana', df['Fecha_dt'].dt.isocalendar().week)
    df.insert(3, 'BANCO', '01.BCP')
    df.insert(4, 'Cuenta', ultimos_3)
    df.insert(5, 'Moneda', '01.Soles') # Ajustable si detectamos dólares
    
    return df

with st.sidebar:
    archivo_maestro = st.file_uploader("Sube tu archivo formato maestro", type=["xlsx", "csv"])
    archivo_bcp = st.file_uploader("Sube el extracto BCP", type=["csv"])

if archivo_maestro and archivo_bcp:
    # Cargar maestro
    df_maestro = pd.read_csv(archivo_maestro) if archivo_maestro.name.endswith('.csv') else pd.read_excel(archivo_maestro)
    
    # Cargar BCP (saltando filas basura si es necesario)
    df_bcp_raw = pd.read_csv(archivo_bcp, skiprows=4) 
    
    # Procesar BCP con tus reglas
    df_final = procesar_bcp(df_bcp_raw, archivo_bcp.name)
    
    # Mantener solo las columnas que existen en tu maestro para no romper el orden
    columnas_maestro = df_maestro.columns.tolist()
    df_final_ordenado = df_final.reindex(columns=columnas_maestro)
    
    st.write("### Vista previa con tu formato:")
    st.dataframe(df_final_ordenado.head())
    
    # Descarga
    csv = df_final_ordenado.to_csv(index=False).encode('utf-8')
    st.download_button("Descargar consolidado", csv, "reporte_final.csv", "text/csv")
