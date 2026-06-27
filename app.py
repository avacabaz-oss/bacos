import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Gestor Bancario Permanente")
st.title("🏦 Gestor Bancario: Maestro Permanente")

# --- MEMORIA PERMANENTE ---
if 'df_maestro' not in st.session_state:
    st.session_state.df_maestro = None

# --- CARGA DEL MAESTRO (SOLO UNA VEZ) ---
if st.session_state.df_maestro is None:
    archivo_maestro = st.file_uploader("📂 Sube tu Formato Maestro (.csv)", type=["csv"])
    if archivo_maestro:
        st.session_state.df_maestro = pd.read_csv(archivo_maestro)
        st.success("✅ Maestro cargado en memoria. ¡Ya puedes procesar extractos!")
        st.rerun() # Recargamos para ocultar el cargador
else:
    st.info("✅ Maestro activo en sistema. (Si necesitas cambiarlo, recarga la página)")

# --- PROCESAMIENTO DE EXTRACTOS (INFINITO) ---
if st.session_state.df_maestro is not None:
    archivo_banco = st.file_uploader("📥 Sube Nuevo Extracto Bancario", type=["csv", "xlsx"])
    
    if archivo_banco:
        try:
            # Lógica de carga (detectando encabezados desde 'Fecha')
            df_raw = pd.read_csv(archivo_banco) if archivo_banco.name.endswith('.csv') else pd.read_excel(archivo_banco, header=None)
            idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('Fecha', na=False).any(), axis=1)].idxmax()[0]
            df_nuevo = pd.read_csv(archivo_banco, skiprows=idx) if archivo_banco.name.endswith('.csv') else pd.read_excel(archivo_banco, skiprows=idx)
            df_nuevo.columns = df_nuevo.columns.str.strip()
            
            # --- TRANSFORMACIÓN A FORMATO MAESTRO ---
            fechas = pd.to_datetime(df_nuevo['Fecha'], dayfirst=True)
            
            df_res = pd.DataFrame(columns=st.session_state.df_maestro.columns)
            df_res['Fecha'] = df_nuevo['Fecha']
            df_res['Año'] = fechas.dt.year
            df_res['Mes '] = fechas.dt.month
            df_res['Semana'] = fechas.dt.isocalendar().week
            df_res['BANCO'] = '01.BCP'
            df_res['Cuenta'] = '010'
            df_res['Moneda'] = '01.Soles'
            df_res['Descripción operación'] = df_nuevo['Descripción operación']
            df_res['Monto'] = df_nuevo['Monto']
            df_res['Operación - Número'] = df_nuevo['Operación - Número'].astype(str).str.zfill(8)
            
            # Unir al Maestro en memoria
            st.session_state.df_maestro = pd.concat([st.session_state.df_maestro, df_res], ignore_index=True)
            
            st.success("🎉 ¡Extracto integrado al Maestro en memoria!")
            st.dataframe(st.session_state.df_maestro.tail(10))
            
            # Botón de descarga
            csv = st.session_state.df_maestro.to_csv(index=False).encode('latin-1')
            st.download_button("💾 Descargar Maestro Actualizado", csv, "Base_Acumulada.csv")
            
        except Exception as e:
            st.error(f"Error: {e}")
