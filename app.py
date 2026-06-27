import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🏦 Conciliador Maestro: Extracción Inteligente")

def extraer_metadatos_bcp(archivo):
    # Leemos solo las primeras 4 filas para extraer los metadatos
    meta = pd.read_csv(archivo, nrows=4, header=None)
    # Extraer cuenta (fila 0, col 1) y moneda (fila 1, col 1)
    cuenta_full = str(meta.iloc[0, 1])
    cuenta_corta = cuenta_full.split('-')[-2] if '-' in cuenta_full else cuenta_full[-3:]
    moneda = "01.Soles" if "Soles" in str(meta.iloc[1, 1]) else "02.Dolares"
    return cuenta_corta, moneda

def procesar_archivo(archivo):
    # 1. Extraer metadatos
    cuenta, moneda = extraer_metadatos_bcp(archivo)
    
    # 2. Leer tabla real (saltando 4 filas)
    df = pd.read_csv(archivo, skiprows=4)
    df.columns = df.columns.str.strip()
    
    # 3. Normalizar al Formato Maestro
    fechas = pd.to_datetime(df['Fecha'], dayfirst=True)
    df_res = pd.DataFrame()
    
    df_res['Fecha'] = df['Fecha']
    df_res['Año'] = fechas.dt.year
    df_res['Mes '] = fechas.dt.month
    df_res['Semana'] = fechas.dt.isocalendar().week
    df_res['BANCO'] = '01.BCP'
    df_res['Cuenta'] = cuenta
    df_res['Moneda'] = moneda
    df_res['Descripción operación'] = df['Descripción operación']
    df_res['Monto'] = df['Monto']
    df_res['Saldo'] = df['Saldo']
    df_res['Operación - Número'] = df['Operación - Número'].astype(str).str.zfill(8)
    
    return df_res

# Interfaz
archivo_maestro = st.file_uploader("📂 Sube tu Maestro Acumulado (.csv)", type=["csv"])
archivo_nuevo = st.file_uploader("📥 Sube Nuevo Extracto BCP (.csv)", type=["csv"])

if archivo_maestro and archivo_nuevo:
    df_maestro = pd.read_csv(archivo_maestro)
    df_nuevo = procesar_archivo(archivo_nuevo)
    
    # Unir y guardar
    df_final = pd.concat([df_maestro, df_nuevo], ignore_index=True)
    
    st.success(f"✅ Integrado. Cuenta detectada: {df_nuevo['Cuenta'].iloc[0]} | Moneda: {df_nuevo['Moneda'].iloc[0]}")
    st.dataframe(df_final.tail(10))
    
    csv = df_final.to_csv(index=False).encode('latin-1')
    st.download_button("💾 Descargar Maestro Actualizado", csv, "Base_Acumulada.csv")
