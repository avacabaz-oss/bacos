import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🏦 Procesador de Conciliación (Modo Seguro)")

# Subida de archivos
archivo_maestro = st.file_uploader("Sube tu Formato Maestro (.csv)", type=["csv"])
archivo_bcp = st.file_uploader("Sube el BCP (.xlsx)", type=["xlsx"])

if archivo_maestro and archivo_bcp:
    try:
        # 1. Leer maestro siempre como CSV
        df_maestro = pd.read_csv(archivo_maestro)
        
        # 2. Leer BCP EXCLUSIVAMENTE con el motor de Excel (engine='openpyxl')
        # Esto evita el UnicodeDecodeError porque le decimos explícitamente qué es
        df_raw = pd.read_excel(archivo_bcp, engine='openpyxl', header=None)
        
        # Encontrar donde empieza la tabla
        idx_header = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains('Fecha', na=False).any(), axis=1)].index[0]
        
        # Leer tabla real
        df_bcp = pd.read_excel(archivo_bcp, engine='openpyxl', skiprows=idx_header)
        
        # 3. Crear resultado vacío basado en columnas del maestro
        df_resultado = pd.DataFrame(columns=df_maestro.columns)
        
        # Mapeo de datos (Asegúrate que los nombres 'Fecha', 'Monto', etc. coincidan con tu Excel)
        fechas = pd.to_datetime(df_bcp['Fecha'], dayfirst=True)
        
        df_resultado['Año'] = fechas.dt.year
        df_resultado['Mes '] = fechas.dt.month
        df_resultado['Semana'] = fechas.dt.isocalendar().week
        df_resultado['BANCO'] = '01.BCP'
        df_resultado['Cuenta'] = '010' 
        df_resultado['Moneda'] = '01.Soles'
        
        # Mapeo de columnas existentes
        columnas_mapeo = {
            'Fecha': 'Fecha',
            'Descripción operación': 'Descripción operación',
            'Monto': 'Monto',
            'Saldo': 'Saldo',
            'Operación - Número': 'Operación - Número'
        }
        
        for col_maestro, col_bcp in columnas_mapeo.items():
            if col_bcp in df_bcp.columns:
                df_resultado[col_maestro] = df_bcp[col_bcp]
                
        st.success("✅ ¡Archivo procesado sin errores de codificación!")
        st.dataframe(df_resultado.head())
        
        # Descarga
        csv = df_resultado.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar", csv, "resultado_limpio.csv", "text/csv")

    except Exception as e:
        st.error(f"Error técnico: {e}")
        st.write("Si el error persiste, por favor confirma si el archivo BCP tiene una columna llamada 'Fecha'.")
