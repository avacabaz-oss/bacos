import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🏦 Conciliador Bancario: Procesador de Excel")

def procesar_excel_banco(archivo):
    # 1. Leemos el archivo entero para sacar metadatos
    df_raw = pd.read_excel(archivo, header=None)
    
    # Extraer Cuenta (Fila 0, Col 1) y Moneda (Fila 1, Col 1)
    cuenta_full = str(df_raw.iloc[0, 1])
    # Tomamos solo el número central de la cuenta (ej. 0112970)
    cuenta_limpia = cuenta_full.split('-')[1] if '-' in cuenta_full else cuenta_full[-7:]
    moneda_raw = str(df_raw.iloc[1, 1])
    moneda = "01.Soles" if "Soles" in moneda_raw else "02.Dolares"
    
    # 2. Buscar fila de encabezados real
    idx_header = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains('Fecha', na=False).any(), axis=1)].idxmax()[0]
    
    # 3. Leer la tabla real
    df = pd.read_excel(archivo, skiprows=idx_header)
    df.columns = df.columns.str.strip()
    
    # 4. Mapeo al Formato Maestro
    fechas = pd.to_datetime(df['Fecha'], dayfirst=True)
    df_res = pd.DataFrame()
    
    df_res['Fecha'] = df['Fecha']
    df_res['Año'] = fechas.dt.year
    df_res['Mes '] = fechas.dt.month
    df_res['Semana'] = fechas.dt.isocalendar().week
    df_res['BANCO'] = '01.BCP' # Esto podrías hacerlo dinámico según el nombre del archivo
    df_res['Cuenta'] = cuenta_limpia
    df_res['Moneda'] = moneda
    df_res['Descripción operación'] = df['Descripción operación']
    df_res['Monto'] = df['Monto']
    df_res['Saldo'] = df['Saldo']
    df_res['Operación - Número'] = df['Operación - Número'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
    
    return df_res

# Interfaz
archivo_maestro = st.file_uploader("📂 Sube tu Maestro Acumulado (.csv)", type=["csv"])
archivo_banco = st.file_uploader("📥 Sube Nuevo Extracto Excel (.xlsx)", type=["xlsx"])

if archivo_maestro and archivo_banco:
    try:
        df_maestro = pd.read_csv(archivo_maestro)
        df_nuevo = procesar_excel_banco(archivo_banco)
        
        # Unir acumulado
        df_final = pd.concat([df_maestro, df_nuevo], ignore_index=True)
        
        st.success(f"✅ Integrado. Cuenta: {df_nuevo['Cuenta'].iloc[0]} | Moneda: {df_nuevo['Moneda'].iloc[0]}")
        st.dataframe(df_final.tail(10))
        
        csv = df_final.to_csv(index=False).encode('latin-1')
        st.download_button("💾 Descargar Maestro Actualizado", csv, "Base_Acumulada.csv")
    except Exception as e:
        st.error(f"Error procesando Excel: {e}")
