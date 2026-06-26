import streamlit as st
import pandas as pd
import datetime

st.title("🏦 Procesador Maestro de Movimientos BCP")

# 1. Subida de archivos
archivo_maestro = st.file_uploader("Sube tu archivo Maestro (Formato base)", type=["csv"])
archivo_bcp = st.file_uploader("Sube el archivo BCP", type=["csv"])

if archivo_maestro and archivo_bcp:
    # Cargar maestro solo para obtener el orden de las columnas
    df_maestro = pd.read_csv(archivo_maestro)
    
    # Cargar BCP saltando las primeras 4 filas basura
    df_bcp = pd.read_csv(archivo_bcp, skiprows=4)
    
    # Crear un contenedor vacío con tus columnas
    df_resultado = pd.DataFrame(columns=df_maestro.columns)
    
    # Mapeo de columnas: Lo que viene del BCP -> Lo que va a tu Maestro
    df_resultado['Fecha'] = pd.to_datetime(df_bcp['Fecha'], dayfirst=True)
    df_resultado['Año'] = df_resultado['Fecha'].dt.year
    df_resultado['Mes'] = df_resultado['Fecha'].dt.month
    df_resultado['Semana'] = df_resultado['Fecha'].dt.isocalendar().week
    df_resultado['BANCO'] = '01.BCP'
    df_resultado['Cuenta'] = '010' # Basado en tu archivo
    df_resultado['Moneda'] = '01.Soles'
    df_resultado['Descripción operación'] = df_bcp['Descripción operación']
    df_resultado['Monto'] = df_bcp['Monto']
    df_resultado['Saldo'] = df_bcp['Saldo']
    df_resultado['Operación - Número'] = df_bcp['Operación - Número']
    
    # Mostrar vista previa
    st.write("Vista previa de los datos procesados:")
    st.dataframe(df_resultado.head())
    
    # Descarga
    csv = df_resultado.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Descargar Archivo Final", csv, "resultado_final.csv", "text/csv")
