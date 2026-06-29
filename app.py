import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(layout="wide")
st.title("Hub de Consolidación Bancaria Automatizada")

# 1. Estructura Única del Libro Mayor (Inmutable)
COLUMNAS_MAESTRO = [
    'Año', 'Mes ', 'Semana', 'BANCO', 'Cuenta', 'Moneda', 'Fecha', 'Fecha valuta', 
    'Descripción operación', 'Monto', 'Saldo', 'Sucursal - agencia', 
    'Operación - Número', 'Operación - Hora', 'Usuario', 'UTC', 'Referencia2', 
    'Factura', 'Glosa', 'Estado', 'Rubro de ingreso', 'Tipos de ingresos', 
    'Tipo Op', 'ordenante'
]

# Inicializar la base de datos histórica en la memoria de la sesión permanente
if 'df_consolidado' not in st.session_state:
    st.session_state.df_consolidado = pd.DataFrame(columns=COLUMNAS_MAESTRO)

# Botón en la barra lateral para reiniciar el histórico cuando desees empezar un nuevo periodo
if st.sidebar.button("🧹 Limpiar Base Histórica"):
    st.session_state.df_consolidado = pd.DataFrame(columns=COLUMNAS_MAESTRO)
    st.sidebar.success("Base histórica reiniciada correctamente.")

# Única zona de carga para todos los bancos (Agregado soporte .xls)
archivo_banco = st.file_uploader("📥 Arrastra aquí cualquier extracto de Excel o CSV", type=["xlsx", "xls", "csv"])

if archivo_banco:
    try:
        # LECTURA CRUDA CON SELECCIÓN DE MOTOR (ENGINE) FORZADA
        nombre_archivo = archivo_banco.name.lower()
        if nombre_archivo.endswith('.csv'):
            df_raw = pd.read_csv(archivo_banco, header=None)
        elif nombre_archivo.endswith('.xls'):
            df_raw = pd.read_excel(archivo_banco, header=None, engine='xlrd')
        else:
            df_raw = pd.read_excel(archivo_banco, header=None, engine='openpyxl')
        
        # Convertir las primeras 15 filas a un solo bloque de texto para buscar patrones
        texto_muestra = df_raw.iloc[:15].astype(str).to_string()
        
        df_res = pd.DataFrame(columns=COLUMNAS_MAESTRO)
        banco_detectado = None

        # =========================================================================
        # DETECCIÓN Y PROCESAMIENTO DEL BBVA
        # =========================================================================
        if "Cuenta Actual:" in texto_muestra or "Histórico de Movimientos" in texto_muestra:
            banco_detectado = "02.BBVA"
            st.info("🔍 **Origen Detectado:** BBVA (Procesando estructura...)")
            
            # Localizar la fila donde empiezan los encabezados reales del BBVA
            idx_header = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('F. Operación|Concepto', na=False).any(), axis=1)].index[0]
            
            # Leer la tabla de datos omitiendo la cabecera del banco (Forzando el motor)
            if nombre_archivo.endswith('.csv'):
                df_datos = pd.read_csv(archivo_banco, skiprows=idx_header)
            elif nombre_archivo.endswith('.xls'):
                df_datos = pd.read_excel(archivo_banco, skiprows=idx_header, engine='xlrd')
            else:
                df_datos = pd.read_excel(archivo_banco, skiprows=idx_header, engine='openpyxl')
                
            df_datos.columns = df_datos.columns.str.strip()
            
            # FILTRO CRÍTICO: Eliminar "Filas Fantasma" de saldos intermedios del BBVA
            df_datos = df_datos[df_datos['F. Operación'].notna()]
            df_datos = df_datos[df_datos['F. Operación'].astype(str).str.contains(r'\d')] # Asegura que sea una fecha con números
            
            # Extracción blindada de cuenta y moneda desde los metadatos superiores
            cuenta_final = "000"
            moneda = "01.Soles"
            for _, row in df_raw.iterrows():
                linea_texto = " ".join(row.astype(str))
                if "Cuenta Actual:" in linea_texto:
                    solo_nums = re.sub(r'\D', '', linea_texto)
                    cuenta_final = solo_nums[-3:] if solo_nums else "000"
                    if "USD" in linea_texto or "DOLARES" in linea_texto.upper():
                        moneda = "02.Dolares"
                    break
            
            # Construcción y mapeo de columnas al maestro
            fechas = pd.to_datetime(df_datos['F. Operación'], dayfirst=True, errors='coerce')
            df_res['Año'] = fechas.dt.year
            df_res['Mes '] = fechas.dt.month
            df_res['Semana'] = fechas.dt.isocalendar().week
            df_res['BANCO'] = banco_detectado
            df_res['Cuenta'] = cuenta_final
            df_res['Moneda'] = moneda
            df_res['Fecha'] = df_datos['F. Operación']
            df_res['Fecha valuta'] = df_datos['F. Valor']
            df_res['Descripción operación'] = df_datos['Concepto']
            df_res['Monto'] = df_datos['Importe']
            df_res['Sucursal - agencia'] = df_datos['Oficina']
            df_res['Operación - Número'] = df_datos['Nº. Doc.'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)

        # =========================================================================
        # DETECCIÓN Y PROCESAMIENTO DEL BCP
        # =========================================================================
        elif "Descripción operación" in texto_muestra or (df_raw.shape[1] > 1 and '-' in str(df_raw.iloc[0, 1])):
            banco_detectado = "01.BCP"
            st.info("🔍 **Origen Detectado:** BCP (Procesando estructura...)")
            
            idx_header = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('Fecha', na=False).any(), axis=1)].index[0]
            
            # Forzando el motor para el BCP también
            if nombre_archivo.endswith('.csv'):
                df_datos = pd.read_csv(archivo_banco, skiprows=idx_header)
            elif nombre_archivo.endswith('.xls'):
                df_datos = pd.read_excel(archivo_banco, skiprows=idx_header, engine='xlrd')
            else:
                df_datos = pd.read_excel(archivo_banco, skiprows=idx_header, engine='openpyxl')
                
            df_datos.columns = df_datos.columns.str.strip()
            
            # Extracción blindada de cuenta y moneda
            cuenta_full = str(df_raw.iloc[0, 1])
            solo_numeros = re.sub(r'\D', '', cuenta_full)
            cuenta_final = solo_numeros[-3:] if solo_numeros else "000"
            moneda = "01.Soles" if "Soles" in str(df_raw.iloc[1, 1]) else "02.Dolares"
            
            fechas = pd.to_datetime(df_datos['Fecha'], dayfirst=True, errors='coerce')
