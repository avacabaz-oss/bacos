import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(layout="wide")
st.title("Hub de Concesión Bancaria Automatizada")

# 1. Estructura Única del Libro Mayor (Inmutable)
COLUMNAS_MAESTRO = [
    'Año', 'Mes ', 'Semana', 'BANCO', 'Cuenta', 'Moneda', 'Fecha', 'Fecha valuta', 
    'Descripción operación', 'Monto', 'Saldo', 'Sucursal - agencia', 
    'Operación - Número', 'Operación - Hora', 'Usuario', 'UTC', 'Referencia2', 
    'Factura', 'Glosa', 'Estado', 'Rubro de ingreso', 'Tipos de ingresos', 
    'Tipo Op', 'ordenante'
]

# Inicializar la base de datos histórica
if 'df_consolidado' not in st.session_state:
    st.session_state.df_consolidado = pd.DataFrame(columns=COLUMNAS_MAESTRO)

if st.sidebar.button("🧹 Limpiar Base Histórica"):
    st.session_state.df_consolidado = pd.DataFrame(columns=COLUMNAS_MAESTRO)
    st.sidebar.success("Base histórica reiniciada correctamente.")

# Única zona de carga
archivo_banco = st.file_uploader("📥 Arrastra aquí cualquier extracto de Excel o CSV", type=["xlsx", "xls", "csv"])

if archivo_banco:
    try:
        # =========================================================================
        # LECTOR INTELIGENTE Y DETECTOR DE TRAMPAS DE FORMATO
        # =========================================================================
        nombre_archivo = archivo_banco.name.lower()
        
        if nombre_archivo.endswith('.csv'):
            df_raw = pd.read_csv(archivo_banco, header=None)
        elif nombre_archivo.endswith('.xls'):
            try:
                df_raw = pd.read_excel(archivo_banco, header=None, engine='xlrd')
            except Exception as e:
                if "BOF" in str(e) or "Expected BOF record" in str(e):
                    archivo_banco.seek(0)
                    html_content = archivo_banco.read().decode('latin-1', errors='ignore')
                    tablas = pd.read_html(io.StringIO(html_content))
                    df_raw = max(tablas, key=len)
                    
                    df_raw.loc[-1] = df_raw.columns.tolist()
                    df_raw.index = df_raw.index + 1
                    df_raw = df_raw.sort_index()
                    df_raw.columns = range(df_raw.shape[1])
                else:
                    raise e
        else:
            df_raw = pd.read_excel(archivo_banco, header=None, engine='openpyxl')
        
        texto_muestra = df_raw.iloc[:15].astype(str).to_string()
        df_res = pd.DataFrame(columns=COLUMNAS_MAESTRO)

        # =========================================================================
        # PROCESAMIENTO BANCO DE LA NACIÓN
        # =========================================================================
        if "RUC" in texto_muestra and "Trans." in texto_muestra and "Abono" in texto_muestra:
            st.success("🔍 **Origen Detectado:** Banco de la Nación")
            
            # Localizar fila de encabezados reales
            idx_header = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('Trans\.|Abono', na=False).any(), axis=1)].index[0]
            
            df_datos = df_raw.iloc[idx_header+1:].copy()
            df_datos.columns = [str(c).strip() for c in df_raw.iloc[idx_header].values]
            
            df_datos = df_datos[df_datos['Fecha'].notna()]
            
            # Asignación de cuenta por defecto configurada a 897
            cuenta_final = "897"
            moneda = "01.Soles"
            
            # Normalización de fechas del formato AAAA.MM.DD
            fecha_limpia = df_datos['Fecha'].astype(str).str.replace('.', '-', regex=False).str.strip()
            fechas = pd.to_datetime(fecha_limpia, format='%Y-%m-%d', errors='coerce')
            
            # Función limpiadora de texto numérico con comas de miles
            def transformar_monto(val):
                val_str = str(val).replace(',', '').strip()
                if val_str == '' or val_str.lower() == 'nan':
                    return 0.0
                try:
                    return float(val_str)
                except:
                    return 0.0
            
            abonos = df_datos['Abono'].apply(transformar_monto)
            cargos = df_datos['Cargo'].apply(transformar_monto)
            monto_final = abonos.where(abonos != 0, -cargos)
            
            df_res['Año'] = fechas.dt.year
            df_res['Mes '] = fechas.dt.month
            df_res['Semana'] = fechas.dt.isocalendar().week
            df_res['BANCO'] = "05.BN"
            df_res['Cuenta'] = cuenta_final
            df_res['Moneda'] = moneda
            df_res['Fecha'] = fecha_limpia
            df_res['Descripción operación'] = df_datos['Trans.'].astype(str) + " - RUC: " + df_datos['RUC'].astype(str).str.replace(r'\.0', '', regex=True)
            df_res['Monto'] = monto_final
            df_res['Sucursal - agencia'] = df_datos['Oficina'].astype(str).str.replace(r'\.0', '', regex=True)
            df_res['Operación - Número'] = df_datos['Documento'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)

        # =========================================================================
        # PROCESAMIENTO SCOTIABANK
        # =========================================================================
        elif "ccmn" in texto_muestra.lower() or "ccmd" in texto_muestra.lower() or "movimientos de cuenta" in texto_muestra.lower():
            st.success("🔍 **Origen Detectado:** Scotiabank")
            
            idx_header = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('Fecha', na=False).any() and r.astype(str).str.contains('Movimiento', na=False).any(), axis=1)].index[0]
            
            df_datos = df_raw.iloc[idx_header+1:].copy()
            df_datos.columns = [str(c).strip() for c in df_raw.iloc[idx_header].values]
            df_datos = df_datos[df_datos['Fecha'].notna()]
            
            cuenta_final, moneda = "000", "01.Soles"
            for _, row in df_raw.head(idx_header).iterrows():
                linea = " ".join([str(val) for val in row.values])
                if "cuenta" in linea.lower() or "ccmn" in linea.lower() or "ccmd" in linea.lower():
                    solo_nums = re.sub(r'\D', '', linea)
                    cuenta_final = solo_nums[-3:] if solo_nums else "000"
                    if "ccmd" in linea.lower() or "usd" in linea.lower() or "dolares" in linea.upper():
                        moneda = "02.Dolares"
                    break
            
            fechas = pd.to_datetime(df_datos['Fecha'], dayfirst=True, errors='coerce')
            
            df_res['Año'] = fechas.dt.year
            df_res['Mes '] = fechas.dt.month
            df_res['Semana'] = fechas.dt.isocalendar().week
            df_res['BANCO'] = "04.SCOTIABANK"
            df_res['Cuenta'] = cuenta_final
            df_res['Moneda'] = moneda
            df_res['Fecha'] = df_datos['Fecha']
            df_res['Descripción operación'] = df_datos['Movimiento']
            df_res['Monto'] = pd.to_numeric(df_datos['Importe'], errors='coerce')
            df_res['Operación - Número'] = df_datos['Referencia'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)

        # =========================================================================
        # PROCESAMIENTO INTERBANK
        # =========================================================================
        elif "Consulta de Movimientos" in texto_muestra or "Saldo contable" in texto_muestra:
            st.success("🔍 **Origen Detectado:** Interbank")
            
            idx_header = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('Fecha de operación|Saldo contable', na=False).any(), axis=1)].index[0]
            
            df_datos = df_raw.iloc[idx_header+1:].copy()
            df_datos.columns = [str(c).strip() for c in df_raw.iloc[idx_header].values]
            df_datos = df_datos[df_datos['Fecha de operación'].notna()]
            
            cuenta_final, moneda = "000", "01.Soles"
            for _, row in df_raw.head(idx_header).iterrows():
                linea = " ".join([str(val) for val in row.values])
                if "Cuenta:" in linea:
                    solo_nums = re.sub(r'\D', '', linea)
                    cuenta_final = solo_nums[-3:] if solo_nums else "000"
                    if "USD" in linea or "DOLAR" in linea.upper():
                        moneda = "02.Dolares"
                    break
            
            fechas = pd.to_datetime(df_datos['Fecha de operación'], dayfirst=True, errors='coerce')
            monto_final = pd.to_numeric(df_datos['Abono'], errors='coerce').fillna(pd.to_numeric(df_datos['Cargo'], errors='coerce'))
            
            df_res['Año'] = fechas.dt.year
            df_res['Mes '] = fechas.dt.month
            df_res['Semana'] = fechas.dt.isocalendar().week
            df_res['BANCO'] = "03.INTERBANK"
            df_res['Cuenta'] = cuenta_final
            df_res['Moneda'] = moneda
            df_res['Fecha'] = df_datos['Fecha de operación']
            df_res['Fecha valuta'] = df_datos['Fecha de proceso']
            df_res['Descripción operación'] = df_datos['Movimiento'].astype(str) + " - " + df_datos['Descripción'].astype(str)
            df_res['Monto'] = monto_final
            df_res['Saldo'] = df_datos['Saldo contable']
            df_res['Operación - Número'] = df_datos['Nro. de operación'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)

        # =========================================================================
        # PROCESAMIENTO BBVA
        # =========================================================================
        elif "Cuenta Actual:" in texto_muestra or "Histórico de Movimientos" in texto_muestra:
            st.success("🔍 **Origen Detectado:** BBVA")
            
            idx_header = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('F. Operación|Concepto', na=False).any(), axis=1)].index[0]
            
            df_datos = df_raw.iloc[idx_header+1:].copy()
            df_datos.columns = [str(c).strip() for c in df_raw.iloc[idx_header].values]
            
            df_datos = df_datos[df_datos['F. Operación'].notna()]
            df_datos = df_datos[df_datos['F. Operación'].astype(str).str.contains(r'\d')] 
            
            cuenta_final, moneda = "000", "01.Soles"
            for _, row in df_raw.head(idx_header).iterrows():
                linea = " ".join([str(val) for val in row.values])
                if "Cuenta Actual:" in linea:
                    solo_nums = re.sub(r'\D', '', linea)
                    cuenta_final = solo_nums[-3:] if solo_nums else "000"
                    if "USD" in linea or "DOLARES" in linea.upper():
                        moneda = "02.Dolares"
                    break
            
            fechas = pd.to_datetime(df_datos['F. Operación'], dayfirst=True, errors='coerce')
            df_res['Año'] = fechas.dt.year
            df_res['Mes '] = fechas.dt.month
            df_res['Semana'] = fechas.dt.isocalendar().week
            df_res['BANCO'] = "02.BBVA"
            df_res['Cuenta'] = cuenta_final
            df_res['Moneda'] = moneda
            df_res['Fecha'] = df_datos['F. Operación']
            df_res['Fecha valuta'] = df_datos['F. Valor']
            df_res['Descripción operación'] = df_datos['Concepto']
            df_res['Monto'] = df_datos['Importe']
            df_res['Sucursal - agencia'] = df_datos['Oficina']
            df_res['Operación - Número'] = df_datos['Nº. Doc.'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)

        # =========================================================================
        # PROCESAMIENTO BCP
        # =========================================================================
        elif "Descripción operación" in texto_muestra or (df_raw.shape[1] > 1 and '-' in str(df_raw.iloc[0, 1])):
            st.success("🔍 **Origen Detectado:** BCP")
            
            idx_header = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('Fecha', na=False).any(), axis=1)].index[0]
            
            df_datos = df_raw.iloc[idx_header+1:].copy()
            df_datos.columns = [str(c).strip() for c in df_raw.iloc[idx_header].values]
            
            cuenta_full = str(df_raw.iloc[0, 1])
            solo_numeros = re.sub(r'\D', '', cuenta_full)
            cuenta_final = solo_numeros[-3:] if solo_numeros else "000"
            moneda = "01.Soles" if "Soles" in str(df_raw.iloc[1, 1]) else "02.Dolares"
            
            fechas = pd.to_datetime(df_datos['Fecha'], dayfirst=True, errors='coerce')
            df_res['Año'] = fechas.dt.year
            df_res['Mes '] = fechas.dt.month
            df_res['Semana'] = fechas.dt.isocalendar().week
            df_res['BANCO'] = "01.BCP"
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

        else:
            st.error("❌ Archivo no reconocido por el sistema.")
            df_res = None

        # =========================================================================
        # GUARDAR EN MEMORIA
        # =========================================================================
        if df_res is not None and not df_res.empty:
            df_res = df_res.dropna(subset=['Año'])
            st.session_state.df_consolidado = pd.concat([st.session_state.df_consolidado, df_res], ignore_index=True)
            st.success(f"🎉 ¡Acumulado! Total en Libro Mayor: {len(st.session_state.df_consolidado)} filas.")

    except Exception as e:
        st.error(f"Error técnico procesando la tabla: {e}")

# =========================================================================
# VISTA Y DESCARGA
# =========================================================================
if not st.session_state.df_consolidado.empty:
    st.subheader("📊 Vista Previa del Libro Mayor")
    st.dataframe(st.session_state.df_consolidado.tail(20))
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        st.session_state.df_consolidado.to_excel(writer, index=False)
    
    st.download_button("💾 Descargar Libro Mayor (.xlsx)", output.getvalue(), "Libro_Mayor.xlsx")
else:
    st.info("El sistema está listo y esperando archivos. Arrastra un extracto del BCP, BBVA, Interbank, Scotiabank o Banco de la Nación para comenzar.")
