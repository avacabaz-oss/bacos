import streamlit as st
import pandas as pd
import io

st.set_page_config(layout="wide")
st.title("🏦 Procesador Maestro de Conciliación")

# 1. Definición del orden maestro (Inmutable)
COLUMNAS_MAESTRO = [
    'Año', 'Mes ', 'Semana', 'BANCO', 'Cuenta', 'Moneda', 'Fecha', 'Fecha valuta', 
    'Descripción operación', 'Monto', 'Saldo', 'Sucursal - agencia', 
    'Operación - Número', 'Operación - Hora', 'Usuario', 'UTC', 'Referencia2', 
    'Factura', 'Glosa', 'Estado', 'Rubro de ingreso', 'Tipos de ingresos', 
    'Tipo Op', 'ordenante'
]

def procesar_archivo_bancario(archivo):
    # Detectar tipo de archivo
    if archivo.name.endswith('.csv'):
        df_raw = pd.read_csv(archivo, header=None)
    else:
        df_raw = pd.read_excel(archivo, header=None)

    # Detectar metadatos (Cuenta y Moneda)
    cuenta_full = str(df_raw.iloc[0, 1])
    cuenta_final = cuenta_full.split('-')[1] if '-' in cuenta_full else cuenta_full[-7:]
    moneda = "01.Soles" if "Soles" in str(df_raw.iloc[1, 1]) else "02.Dolares"
    
    # Buscar inicio de tabla
    idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('Fecha', na=False).any(), axis=1)].idxmax()[0]
    
    # Leer datos reales
    df = pd.read_csv(archivo, skiprows=idx) if archivo.name.endswith('.csv') else pd.read_excel(archivo, skiprows=idx)
    df.columns = df.columns.str.strip()
    
    # Construir resultado vacío con columnas maestro
    df_res = pd.DataFrame(columns=COLUMNAS_MAESTRO)
    
    # Cálculos dinámicos
    fechas = pd.to_datetime(df['Fecha'], dayfirst=True)
    
    # Mapeo
    df_res['Año'] = fechas.dt.year
    df_res['Mes '] = fechas.dt.month
    df_res['Semana'] = fechas.dt.isocalendar().week
    df_res['BANCO'] = '01.BCP'
    df_res['Cuenta'] = cuenta_final
    df_res['Moneda'] = moneda
    
    # Mapeo de columnas existentes en el BCP
    mapeo_simple = {
        'Fecha': 'Fecha', 'Fecha valuta': 'Fecha valuta', 'Descripción operación': 'Descripción operación',
        'Monto': 'Monto', 'Saldo': 'Saldo', 'Sucursal - agencia': 'Sucursal - agencia',
        'Operación - Hora': 'Operación - Hora', 'Usuario': 'Usuario', 'UTC': 'UTC', 'Referencia2': 'Referencia2'
    }
    
    for col_maestro, col_bcp in mapeo_simple.items():
        if col_bcp in df.columns:
            df_res[col_maestro] = df[col_bcp]
            
    # Mapeo especial
    df_res['Operación - Número'] = df['Operación - Número'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
    
    return df_res

# Interfaz
archivo_banco = st.file_uploader("📥 Sube nuevo Extracto BCP (Excel o CSV)", type=["xlsx", "csv"])

if archivo_banco:
    try:
        df_nuevo = procesar_archivo_bancario(archivo_banco)
        st.success("✅ Estructura adaptada perfectamente al Maestro.")
        st.dataframe(df_nuevo.head())
        
      output = io.BytesIO()
        # Usamos engine='openpyxl' en lugar de 'xlsxwriter'
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_nuevo.to_excel(writer, index=False)
        
        st.download_button(
            label="💾 Descargar Excel con Formato Maestro", 
            data=output.getvalue(), 
            file_name="resultado_consolidado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
