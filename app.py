import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🏦 Procesador Maestro: Versión Blindada")

# Función de carga robusta
def cargar_archivo(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        for enc in ['latin-1', 'utf-8', 'cp1252']:
            try:
                return pd.read_csv(uploaded_file, encoding=enc, sep=None, engine='python')
            except:
                continue
        return pd.read_csv(uploaded_file)
    else:
        df_raw = pd.read_excel(uploaded_file, engine='openpyxl', header=None)
        mask = df_raw.apply(lambda row: row.astype(str).str.contains('Fecha', na=False).any(), axis=1)
        if mask.any():
            idx_header = mask.idxmax()
            return pd.read_excel(uploaded_file, engine='openpyxl', skiprows=idx_header)
        return pd.read_excel(uploaded_file)

archivo_maestro = st.file_uploader("Sube tu Formato Maestro (.csv o .xlsx)", type=["csv", "xlsx"])
archivo_bcp = st.file_uploader("Sube el Extracto BCP (.csv o .xlsx)", type=["csv", "xlsx"])

if archivo_maestro and archivo_bcp:
    try:
        df_maestro = cargar_archivo(archivo_maestro)
        df_bcp = cargar_archivo(archivo_bcp)
        
        # Normalizar nombres de columnas
        df_bcp.columns = [str(c).strip() for c in df_bcp.columns]
        
        # Crear estructura vacía del maestro
        df_res = pd.DataFrame(columns=df_maestro.columns)
        
        # Calcular campos base
        fechas = pd.to_datetime(df_bcp['Fecha'], dayfirst=True)
        ops = df_bcp['Operación - Número'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
        
        # Asignación segura
        def asignar(col_nombre, valor):
            if col_nombre in df_res.columns:
                df_res[col_nombre] = valor

        asignar('Fecha', df_bcp['Fecha'])
        asignar('Año', fechas.dt.year)
        asignar('Mes ', fechas.dt.month)
        asignar('Semana', fechas.dt.isocalendar().week)
        asignar('BANCO', '01.BCP')
        asignar('Cuenta', '010')
        asignar('Moneda', '01.Soles')
        asignar('Descripción operación', df_bcp.get('Descripción operación', ''))
        asignar('Monto', df_bcp.get('Monto', 0))
        asignar('Saldo', df_bcp.get('Saldo', 0))
        asignar('Operación - Número', ops)
        
        st.success("✅ ¡Procesado exitosamente!")
        st.dataframe(df_res.head())
        
        csv = df_res.to_csv(index=False).encode('latin-1')
        st.download_button("📥 Descargar", csv, "resultado_final.csv", "text/csv")
        
    except Exception as e:
        st.error(f"Error Técnico: {e}")
