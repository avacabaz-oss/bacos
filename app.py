import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🏦 Procesador Maestro: Detección Automática")

def cargar_archivo(uploaded_file):
    """Detecta si es CSV o Excel y carga el DataFrame"""
    nombre = uploaded_file.name
    if nombre.endswith('.csv'):
        # Intentamos varias codificaciones por el error de la ñ
        try:
            return pd.read_csv(uploaded_file, encoding='latin-1', sep=None, engine='python')
        except:
            return pd.read_csv(uploaded_file, encoding='utf-8', sep=None, engine='python')
    else:
        # Modo robusto para Excel
        df_raw = pd.read_excel(uploaded_file, engine='openpyxl', header=None)
        idx_header = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains('Fecha', na=False).any(), axis=1)].index[0]
        return pd.read_excel(uploaded_file, engine='openpyxl', skiprows=idx_header)

# --- INTERFAZ ---
archivo_maestro = st.file_uploader("Sube tu Formato Maestro (CSV o Excel)", type=["csv", "xlsx"])
archivo_bcp = st.file_uploader("Sube el archivo BCP (CSV o Excel)", type=["csv", "xlsx"])

if archivo_maestro and archivo_bcp:
    try:
        # 1. Cargamos usando la función inteligente
        df_maestro = cargar_archivo(archivo_maestro)
        df_bcp = cargar_archivo(archivo_bcp)
        
        # 2. Creamos la estructura base
        df_resultado = pd.DataFrame(columns=df_maestro.columns)
        
        # 3. Mapeo lógico
        fechas = pd.to_datetime(df_bcp['Fecha'], dayfirst=True)
        df_resultado['Año'] = fechas.dt.year
        df_resultado['Mes '] = fechas.dt.month
        df_resultado['Semana'] = fechas.dt.isocalendar().week
        df_resultado['BANCO'] = '01.BCP'
        df_resultado['Cuenta'] = '010'
        df_resultado['Moneda'] = '01.Soles'
        
        # Completar columnas desde el BCP
        mapeo = {
            'Fecha': 'Fecha',
            'Descripción operación': 'Descripción operación',
            'Monto': 'Monto',
            'Saldo': 'Saldo',
            'Operación - Número': 'Operación - Número'
        }
        
        for col_maestro, col_bcp in mapeo.items():
            if col_bcp in df_bcp.columns:
                df_resultado[col_maestro] = df_bcp[col_bcp]
        
        st.success("✅ Archivos cargados y fusionados detectando formato automáticamente.")
        st.dataframe(df_resultado.head())
        
        # Descarga
        csv = df_resultado.to_csv(index=False).encode('latin-1')
        st.download_button("📥 Descargar", csv, "resultado_final.csv", "text/csv")
        
    except Exception as e:
        st.error(f"Error al procesar: {e}")
