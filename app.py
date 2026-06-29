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

# Única zona de carga para todos los bancos
archivo_banco = st.file_uploader("📥 Arrastra aquí cualquier extracto de Excel o CSV", type=["xlsx","xls", "csv"])

if archivo_banco:
    try:
        # Leer el archivo de forma cruda para realizar la lectura de metadatos y escaneo
        if archivo_banco.name.endswith('.csv'):
            df_raw = pd.read_csv(archivo_banco, header=None)
        else:
            df_raw = pd.read_excel(archivo_banco, header=None)
        
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
            
            # Leer la tabla de datos omitiendo la cabecera del banco
            df_datos = pd.read_csv(archivo_banco, skiprows=idx_header) if archivo_banco.name.endswith('.csv') else pd.read_excel(archivo_banco, skiprows=idx_header)
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
            df_datos = pd.read_csv(archivo_banco, skiprows=idx_header) if archivo_banco.name.endswith('.csv') else pd.read_excel(archivo_banco, skiprows=idx_header)
            df_datos.columns = df_datos.columns.str.strip()
            
            # Extracción blindada de cuenta (aislando números de nombres extensos) y moneda
            cuenta_full = str(df_raw.iloc[0, 1])
            solo_numeros = re.sub(r'\D', '', cuenta_full)
            cuenta_final = solo_numeros[-3:] if solo_numeros else "000"
            moneda = "01.Soles" if "Soles" in str(df_raw.iloc[1, 1]) else "02.Dolares"
            
            fechas = pd.to_datetime(df_datos['Fecha'], dayfirst=True, errors='coerce')
            df_res['Año'] = fechas.dt.year
            df_res['Mes '] = fechas.dt.month
            df_res['Semana'] = fechas.dt.isocalendar().week
            df_res['BANCO'] = banco_detectado
            df_res['Cuenta'] = cuenta_final
            df_res['Moneda'] = moneda
            df_res['Fecha'] = df_datos['Fecha']
            
            mapeo_bcp = {
                'Fecha valuta': 'Fecha valuta', 'Descripción operación': 'Descripción operación',
                'Monto': 'Monto', 'Saldo': 'Saldo', 'Sucursal - agencia': 'Sucursal - agencia',
                'Operación - Hora': 'Operación - Hora', 'Usuario': 'Usuario', 'UTC': 'UTC', 'Referencia2': 'Referencia2'
            }
            for c_m, c_b in mapeo_bcp.items():
                if c_b in df_datos.columns:
                    df_res[c_m] = df_datos[c_b]
                    
            df_res['Operación - Número'] = df_datos['Operación - Número'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)

        # =========================================================================
        # BANCO NO RECONOCIDO
        # =========================================================================
        else:
            st.error("❌ Estructura de archivo no reconocida. El sistema no pudo determinar el banco de origen automáticamente.")
            df_res = None

        # 3. Integración en la base histórica acumulada
        if df_res is not None and not df_res.empty:
            st.session_state.df_consolidado = pd.concat([st.session_state.df_consolidado, df_res], ignore_index=True)
            st.success(f"🎉 Datos acumulados correctamente. Total en memoria: {len(st.session_state.df_consolidado)} filas.")

    except Exception as e:
        st.error(f"Error en el procesamiento interno del archivo: {e}")

# 4. Despliegue de Resultados y Descarga Nátiva de Excel
if not st.session_state.df_consolidado.empty:
    st.subheader("📊 Vista Previa del Libro Mayor Consolidado")
    st.dataframe(st.session_state.df_consolidado.tail(20))
    
    # Preparación de la salida nativa de Excel (.xlsx) usando openpyxl
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        st.session_state.df_consolidado.to_excel(writer, index=False)
    
    st.download_button(
        label="💾 Descargar Libro Mayor Acumulado (.xlsx)", 
        data=output.getvalue(), 
        file_name="Libro_Mayor_Bancario.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("El sistema está listo y esperando archivos. Arrastra un extracto del BCP o BBVA para comenzar la acumulación permanente.")
