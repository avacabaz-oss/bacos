import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🏦 Procesador de Conciliación: Orden Maestro")

# Función de carga robusta
def cargar_archivo(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        return pd.read_csv(uploaded_file, encoding='latin-1', sep=None, engine='python')
    else:
        df_raw = pd.read_excel(uploaded_file, engine='openpyxl', header=None)
        idx_header = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains('Fecha', na=False).any(), axis=1)].index[0]
        return pd.read_excel(uploaded_file, engine='openpyxl', skiprows=idx_header)

archivo_maestro = st.file_uploader("Sube tu Formato Maestro (.csv o .xlsx)", type=["csv", "xlsx"])
archivo_bcp = st.file_uploader("Sube el archivo BCP (.csv o .xlsx)", type=["csv", "xlsx"])

if archivo_maestro and archivo_bcp:
    try:
        df_maestro = cargar_archivo(archivo_maestro)
        df_bcp = cargar_archivo(archivo_bcp)
        
        # 1. Cálculos de campos
        fechas = pd.to_datetime(df_bcp['Fecha'], dayfirst=True)
        ops = df_bcp['Operación - Número'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
        
        # 2. Creamos un DataFrame nuevo que sigue el orden de tu Maestro
        # Asignamos los campos que calculamos
        df_res = pd.DataFrame(index=df_bcp.index)
        
        # -- ORDEN EXACTO SEGUN TU FORMATO --
        df_res['Año'] = fechas.dt.year
        df_res['Mes '] = fechas.dt.month
        df_res['Semana'] = fechas.dt.isocalendar().week
        df_res['BANCO'] = '01.BCP'
        df_res['Cuenta'] = '010'
        df_res['Moneda'] = '01.Soles'
        df_res['Fecha'] = df_bcp['Fecha']
        # (Aquí se insertarán el resto de columnas del maestro)
        
        # 3. Traemos las columnas que coinciden con el BCP
        mapeo = {
            'Descripción operación': 'Descripción operación',
            'Monto': 'Monto',
            'Saldo': 'Saldo',
            'Sucursal - agencia': 'Sucursal - agencia',
            'Operación - Número': ops,
            'Operación - Hora': 'Operación - Hora',
            'Usuario': 'Usuario',
            'UTC': 'UTC',
            'Referencia2': 'Referencia2'
        }
        
        for col_maestro, col_bcp in mapeo.items():
            if isinstance(col_bcp, str) and col_bcp in df_bcp.columns:
                df_res[col_maestro] = df_bcp[col_bcp]
            else:
                df_res[col_maestro] = col_bcp # Caso de las columnas calculadas

        # 4. Asegurar que TODAS las columnas del maestro existan
        for col in df_maestro.columns:
            if col not in df_res.columns:
                df_res[col] = None
        
        # 5. FORZAR ORDEN FINAL
        df_res = df_res[df_maestro.columns]
        
        st.success("✅ ¡Orden de columnas ajustado al formato maestro!")
        st.dataframe(df_res.head())
        
        csv = df_res.to_csv(index=False).encode('latin-1')
        st.download_button("📥 Descargar Resultado", csv, "resultado_final.csv", "text/csv")
        
    except Exception as e:
        st.error(f"Error técnico: {e}")
