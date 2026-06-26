import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🏦 Procesador Maestro BCP (Corregido)")

def cargar_archivo(uploaded_file):
    nombre = uploaded_file.name
    if nombre.endswith('.csv'):
        try:
            return pd.read_csv(uploaded_file, encoding='latin-1', sep=None, engine='python')
        except:
            return pd.read_csv(uploaded_file, encoding='utf-8', sep=None, engine='python')
    else:
        # AQUÍ ESTABA EL ERROR: Cambiado 'openxml' por 'openpyxl'
        df_raw = pd.read_excel(uploaded_file, engine='openpyxl', header=None)
        idx_header = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains('Fecha', na=False).any(), axis=1)].index[0]
        return pd.read_excel(uploaded_file, engine='openpyxl', skiprows=idx_header)

archivo_maestro = st.file_uploader("Sube tu Formato Maestro (.csv)", type=["csv", "xlsx"])
archivo_bcp = st.file_uploader("Sube el archivo BCP", type=["csv", "xlsx"])

if archivo_maestro and archivo_bcp:
    try:
        df_maestro = cargar_archivo(archivo_maestro)
        df_bcp = cargar_archivo(archivo_bcp)
        
        # Crear estructura vacía basada en el maestro
        df_res = pd.DataFrame(columns=df_maestro.columns)
        
        # Cálculos de fecha
        fechas = pd.to_datetime(df_bcp['Fecha'], dayfirst=True)
        
        # Mapeo garantizando el orden
        df_res['Fecha'] = df_bcp['Fecha']
        df_res['Año'] = fechas.dt.year
        df_res['Mes '] = fechas.dt.month
        df_res['Semana'] = fechas.dt.isocalendar().week
        df_res['BANCO'] = '01.BCP'
        df_res['Cuenta'] = '010'
        df_res['Moneda'] = '01.Soles'
        df_res['Descripción operación'] = df_bcp['Descripción operación']
        df_res['Monto'] = df_bcp['Monto']
        df_res['Saldo'] = df_bcp['Saldo']
        
        # Operación a 8 dígitos exactos
        ops = df_bcp['Operación - Número'].astype(str).str.replace(r'\.0', '', regex=True)
        df_res['Operación - Número'] = ops.str.zfill(8)
        
        st.success("✅ ¡El motor de Excel ya funciona correctamente!")
        st.dataframe(df_res.head())
        
        # Descarga
        csv = df_res.to_csv(index=False).encode('latin-1')
        st.download_button("📥 Descargar Resultado", csv, "resultado_final.csv", "text/csv")
        
    except Exception as e:
        st.error(f"Error técnico: {e}")
