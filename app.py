import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🏦 Procesador Maestro BCP (Preservando Metadatos)")

archivo_maestro = st.file_uploader("Sube tu Formato Maestro (.csv)", type=["csv"])
archivo_bcp = st.file_uploader("Sube el BCP (.xlsx)", type=["xlsx"])

if archivo_maestro and archivo_bcp:
    df_maestro = pd.read_csv(archivo_maestro)
    
    # 1. Leer el Excel sin saltar filas para no perder nada
    df_raw = pd.read_excel(archivo_bcp, header=None)
    
    # 2. Extraer Metadatos (Filas superiores)
    # Buscamos la fila donde aparece la palabra 'Fecha'
    idx_header = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains('Fecha').any(), axis=1)].index[0]
    
    # Datos de cabecera (Filas 0 a idx_header-1)
    metadatos = df_raw.iloc[:idx_header]
    
    # 3. Leer tabla real usando idx_header como ancla
    df_bcp = pd.read_excel(archivo_bcp, skiprows=idx_header)
    
    # 4. Procesar el resultado
    df_resultado = pd.DataFrame(columns=df_maestro.columns)
    
    fechas = pd.to_datetime(df_bcp['Fecha'], dayfirst=True)
    
    df_resultado['Año'] = fechas.dt.year
    df_resultado['Mes '] = fechas.dt.month
    df_resultado['Semana'] = fechas.dt.isocalendar().week
    df_resultado['BANCO'] = '01.BCP'
    df_resultado['Cuenta'] = str(df_raw.iloc[0, 1])[-3:] # Extraemos últimos 3 dígitos de la celda B1
    df_resultado['Moneda'] = '01.Soles'
    df_resultado['Fecha'] = df_bcp['Fecha']
    df_resultado['Descripción operación'] = df_bcp['Descripción operación']
    df_resultado['Monto'] = df_bcp['Monto']
    df_resultado['Saldo'] = df_bcp['Saldo']
    df_resultado['Operación - Número'] = df_bcp['Operación - Número']
    
    st.success("✅ ¡Datos extraídos sin perder el encabezado!")
    st.write("Vista previa de los datos procesados:")
    st.dataframe(df_resultado.head())
    
    csv = df_resultado.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Descargar", csv, "resultado_consolidado.csv", "text/csv")
