import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🏦 Conciliador Bancario: Formato Maestro Inmutable")

def cargar_archivo(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        return pd.read_csv(uploaded_file, encoding='latin-1', sep=None, engine='python')
    else:
        df_raw = pd.read_excel(uploaded_file, engine='openpyxl', header=None)
        # Búsqueda inteligente de cabeceras
        idx_header = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains('Fecha', na=False).any(), axis=1)].index[0]
        return pd.read_excel(uploaded_file, engine='openpyxl', skiprows=idx_header)

archivo_maestro = st.file_uploader("Sube tu Formato Maestro (Plantilla)", type=["csv", "xlsx"])
archivo_bcp = st.file_uploader("Sube el Extracto BCP", type=["csv", "xlsx"])

if archivo_maestro and archivo_bcp:
    try:
        df_maestro = cargar_archivo(archivo_maestro)
        df_bcp = cargar_archivo(archivo_bcp)
        
        # 1. Creamos el esqueleto vacío basado EXCLUSIVAMENTE en el Maestro
        df_final = pd.DataFrame(columns=df_maestro.columns)
        
        # 2. Procesamos el BCP
        fechas = pd.to_datetime(df_bcp['Fecha'], dayfirst=True)
        ops = df_bcp['Operación - Número'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
        
        # 3. Mapeo: Insertamos los datos en las columnas correspondientes del Maestro
        # Esta lógica asegura que no importa el orden del BCP, el destino siempre será el mismo
        df_final['Fecha'] = df_bcp['Fecha']
        df_final['Año'] = fechas.dt.year
        df_final['Mes '] = fechas.dt.month
        df_final['Semana'] = fechas.dt.isocalendar().week
        df_final['BANCO'] = '01.BCP'
        df_final['Cuenta'] = '010'
        df_final['Moneda'] = '01.Soles'
        
        # Mapeo de columnas dinámicas que sí existen en el BCP
        mapeo = {
            'Descripción operación': 'Descripción operación',
            'Monto': 'Monto',
            'Saldo': 'Saldo',
            'Operación - Número': ops,
            'Sucursal - agencia': 'Sucursal - agencia',
            'Operación - Hora': 'Operación - Hora',
            'Usuario': 'Usuario',
            'UTC': 'UTC',
            'Referencia2': 'Referencia2'
        }
        
        for col_maestro, col_bcp in mapeo.items():
            if col_maestro in df_final.columns:
                if isinstance(col_bcp, str) and col_bcp in df_bcp.columns:
                    df_final[col_maestro] = df_bcp[col_bcp]
                elif not isinstance(col_bcp, str):
                    df_final[col_maestro] = col_bcp

        st.success("✅ Datos adaptados exitosamente al Maestro.")
        st.dataframe(df_final.head())
        
        csv = df_final.to_csv(index=False).encode('latin-1')
        st.download_button("📥 Descargar Reporte Final", csv, "reporte_consolidado.csv", "text/csv")
        
    except Exception as e:
        st.error(f"Error: {e}")r técnico: {e}")
