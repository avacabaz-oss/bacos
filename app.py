import streamlit as st
import pandas as pd
import datetime

st.set_page_config(layout="wide")
st.title("🏦 Procesador de Conciliación BCP")

# Carga de archivos
col1, col2 = st.columns(2)
with col1:
    archivo_maestro = st.file_uploader("Sube tu Formato Maestro (.csv)", type=["csv"])
with col2:
    archivo_bcp = st.file_uploader("Sube el BCP (.csv)", type=["csv"])

if archivo_maestro and archivo_bcp:
    # 1. Cargar estructuras
    df_maestro = pd.read_csv(archivo_maestro)
    # Saltamos las primeras 4 filas que son basura en el BCP
    df_bcp = pd.read_csv(archivo_bcp, skiprows=4)
    
    # 2. Crear resultado vacío basado en tu Maestro
    df_resultado = pd.DataFrame(columns=df_maestro.columns)
    
    # 3. Mapeo explícito (Aquí es donde forzamos la unión)
    fechas = pd.to_datetime(df_bcp['Fecha'], dayfirst=True)
    
    df_resultado['Año'] = fechas.dt.year
    df_resultado['Mes '] = fechas.dt.month
    df_resultado['Semana'] = fechas.dt.isocalendar().week
    df_resultado['BANCO'] = '01.BCP'
    df_resultado['Cuenta'] = '010'
    df_resultado['Moneda'] = '01.Soles'
    df_resultado['Fecha'] = df_bcp['Fecha']
    df_resultado['Descripción operación'] = df_bcp['Descripción operación']
    df_resultado['Monto'] = df_bcp['Monto']
    df_resultado['Saldo'] = df_bcp['Saldo']
    df_resultado['Sucursal - agencia'] = df_bcp['Sucursal - agencia']
    df_resultado['Operación - Número'] = df_bcp['Operación - Número']
    df_resultado['Operación - Hora'] = df_bcp['Operación - Hora']
    df_resultado['Usuario'] = df_bcp['Usuario']
    df_resultado['UTC'] = df_bcp['UTC']
    df_resultado['Referencia2'] = df_bcp['Referencia2']
    
    # 4. Limpieza final
    st.success("✅ Datos mapeados exitosamente al formato maestro.")
    st.dataframe(df_resultado.head())
    
    csv = df_resultado.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Descargar Archivo Final", csv, "resultado_consolidado.csv", "text/csv")
