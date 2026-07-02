import streamlit as st
import pandas as pd
import io
import re
from motores_bancarios import (
    procesar_banco_nacion,
    procesar_scotiabank,
    procesar_interbank,
    procesar_bbva,
    procesar_bcp
)

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

# Inicializar la base de datos histórica en la memoria volátil de la sesión
if 'df_consolidado' not in st.session_state:
    st.session_state.df_consolidado = pd.DataFrame(columns=COLUMNAS_MAESTRO)

if st.sidebar.button("🧹 Limpiar Base Histórica"):
    st.session_state.df_consolidado = pd.DataFrame(columns=COLUMNAS_MAESTRO)
    st.sidebar.success("Base histórica reiniciada correctamente.")

# =========================================================================
# ZONA 1: CARGA DE EXTRACTOS BANCARIOS PRINCIPALES
# =========================================================================
st.subheader("1. Alimentador Principal de Movimientos")
archivo_banco = st.file_uploader("📥 Arrastra aquí cualquier extracto de movimientos (Excel o CSV)", type=["xlsx", "xls", "csv"], key="principal")

if archivo_banco:
    try:
        nombre_archivo = archivo_banco.name.lower()
        
        # Lector inteligente con rejilla ancha y tolerancia de codificación
        if nombre_archivo.endswith('.csv'):
            try:
                df_raw = pd.read_csv(archivo_banco, header=None, encoding='utf-8', names=range(50))
            except UnicodeDecodeError:
                archivo_banco.seek(0)
                df_raw = pd.read_csv(archivo_banco, header=None, encoding='latin-1', names=range(50))
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
        df_nuevo = None

        # Ruteador Inteligente
        if "RUC" in texto_muestra and "Trans." in texto_muestra and "Abono" in texto_muestra:
            st.success("🔍 **Origen Detectado:** Banco de la Nación")
            df_nuevo = procesar_banco_nacion(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        elif "Consulta de Movimientos" in texto_muestra or "Saldo contable" in texto_muestra:
            st.success("🔍 **Origen Detectado:** Interbank")
            df_nuevo = procesar_interbank(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        elif "ccmn" in texto_muestra.lower() or "ccmd" in texto_muestra.lower() or "movimientos de cuenta" in texto_muestra.lower():
            st.success("🔍 **Origen Detectado:** Scotiabank")
            df_nuevo = procesar_scotiabank(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        elif "Cuenta Actual:" in texto_muestra or "Histórico de Movimientos" in texto_muestra:
            st.success("🔍 **Origen Detectado:** BBVA")
            df_nuevo = procesar_bbva(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        elif "Descripción operación" in texto_muestra or (df_raw.shape[1] > 1 and '-' in str(df_raw.iloc[0, 1])):
            st.success("🔍 **Origen Detectado:** BCP")
            df_nuevo = procesar_bcp(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        else:
            st.error("❌ Archivo no reconocido por el sistema.")

        # Procesamiento unificado
        if df_nuevo is not None and not df_nuevo.empty:
            df_nuevo['Monto'] = pd.to_numeric(df_nuevo['Monto'], errors='coerce').fillna(0.0)
            df_nuevo['Tipo Op'] = df_nuevo['Monto'].apply(lambda x: 'INGRESO' if x > 0 else ('EGRESO' if x < 0 else ''))
            
            diccionario_bancos = {'01.BCP': 'BCP', '02.BBVA': 'BBVA', '03.INTERBANK': 'ITB', '04.SCOTIABANK': 'SCT', '05.BN': 'BN'}
            banco_resumido = df_nuevo['BANCO'].map(diccionario_bancos).fillna(df_nuevo['BANCO']).astype(str)
            cuenta_limpia = df_nuevo['Cuenta'].fillna('000').astype(str)
            fecha_limpia = df_nuevo['Fecha'].fillna('').astype(str)
            operacion_limpia = df_nuevo['Operación - Número'].fillna('').astype(str)
            df_nuevo['Glosa'] = banco_resumido + " " + cuenta_limpia + " " + fecha_limpia + " " + operacion_limpia
            
            df_nuevo = df_nuevo.dropna(subset=['Año'])
            filas_originales = len(df_nuevo)
            df_nuevo = df_nuevo.drop_duplicates(subset=['BANCO', 'Fecha', 'Monto', 'Operación - Número'])
            duplicados_internos = filas_originales - len(df_nuevo)
            
            duplicados_historicos = 0
            if not st.session_state.df_consolidado.empty:
                historico = st.session_state.df_consolidado
                llaves_historico = (historico['BANCO'].astype(str) + "_" + historico['Fecha'].astype(str) + "_" + historico['Monto'].astype(float).round(2).astype(str) + "_" + historico['Operación - Número'].astype(str))
                llaves_nuevas = (df_nuevo['BANCO'].astype(str) + "_" + df_nuevo['Fecha'].astype(str) + "_" + df_nuevo['Monto'].astype(float).round(2).astype(str) + "_" + df_nuevo['Operación - Número'].astype(str))
                filas_antes_filtro = len(df_nuevo)
                df_nuevo = df_nuevo[~llaves_nuevas.isin(llaves_historico)]
                duplicados_historicos = filas_antes_filtro - len(df_nuevo)
            
            if len(df_nuevo) > 0:
                st.session_state.df_consolidado = pd.concat([st.session_state.df_consolidado, df_nuevo], ignore_index=True)
                st.success(f"🎉 Se añadieron {len(df_nuevo)} nuevas transacciones al consolidado.")
            else:
                st.info("ℹ️ No hay transacciones nuevas para añadir.")

    except Exception as e:
        st.error(f"Error técnico procesando la tabla: {e}")

st.write("---")

# =========================================================================
# ZONA 2: CRUCE INTELIGENTE DE DETALLES (BCP TELECRÉDITO)
# =========================================================================
st.subheader("2. Motor de Triangulación de Ordenantes (BCP)")
archivos_detalle = st.file_uploader("🧩 Arrastra aquí los archivos de detalle BCP (Puedes subir los 3 a la vez)", type=["xlsx", "xls"], accept_multiple_files=True, key="detalles")

if archivos_detalle:
    lista_df_detalles = []
    
    # Lectura y normalización de los 3 formatos posibles
    for archivo in archivos_detalle:
        try:
            df_raw = pd.read_excel(archivo, nrows=20)
            idx_header = None
            for i, row in df_raw.iterrows():
                fila_texto = " ".join([str(val) for val in row.values]).lower()
                if 'ordenante' in fila_texto or 'tipo de operación' in fila_texto:
                    idx_header = i
                    break
            
            if idx_header is not None:
                df_det = pd.read_excel(archivo, skiprows=idx_header+1)
                cols = df_det.columns.astype(str)
                df_temp = pd.DataFrame()
                
                # Formato 1: Interbancarias (Tiene Operación)
                if 'Ordenante' in cols and 'Número - Operación' in cols:
                    df_temp['Ordenante'] = df_det['Ordenante']
                    df_temp['Operacion'] = df_det['Número - Operación'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
                    df_temp['Fecha'] = pd.to_datetime(df_det['Fecha de Abono'], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y')
                    df_temp['Monto'] = pd.to_numeric(df_det['Monto Abonado'], errors='coerce')
                
                # Formato 2: Transferencias (No tiene Operación)
                elif 'Ordenante' in cols and 'Cuenta - Número' in cols:
                    df_temp['Ordenante'] = df_det['Ordenante']
                    df_temp['Operacion'] = ''
                    df_temp['Fecha'] = pd.to_datetime(df_det['Fecha de Abono'], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y')
                    df_temp['Monto'] = pd.to_numeric(df_det['Monto abonado'], errors='coerce')
                    
                # Formato 3: Pagos (No tiene Operación)
                elif 'Ordenante - Nombre o Razón Social' in cols:
                    df_temp['Ordenante'] = df_det['Ordenante - Nombre o Razón Social']
                    df_temp['Operacion'] = ''
                    fecha_col = 'Fecha de pago' if 'Fecha de pago' in cols else 'Fecha de Abono'
                    if fecha_col in cols:
                        df_temp['Fecha'] = pd.to_datetime(df_det[fecha_col], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y')
                    df_temp['Monto'] = pd.to_numeric(df_det['Monto abonado'], errors='coerce')
                
                if not df_temp.empty:
                    df_temp = df_temp.dropna(subset=['Ordenante', 'Monto'])
                    lista_df_detalles.append(df_temp)
        except Exception as e:
            st.error(f"No se pudo procesar el archivo {archivo.name}: {e}")

    # Ejecución del Cruce contra el Libro Mayor
    if lista_df_detalles and not st.session_state.df_consolidado.empty:
        df_detalles_master = pd.concat(lista_df_detalles, ignore_index=True)
        df_c = st.session_state.df_consolidado
        df_c['ordenante'] = df_c['ordenante'].fillna('')
        
        coincidencias = 0
        
        for idx, row in df_c.iterrows():
            # Filtramos solo ingresos del BCP que aún no tengan ordenante
            if row['BANCO'] == '01.BCP' and row['Tipo Op'] == 'INGRESO' and row['ordenante'] == '':
                fecha_m = str(row['Fecha'])
                monto_m = float(row['Monto']) if pd.notna(row['Monto']) else 0.0
                operacion_m = str(row['Operación - Número'])
                
                match_encontrado = False
                
                # Nivel 1: Cruce de Precisión (Operación + Fecha)
                if operacion_m and operacion_m != 'nan' and operacion_m != '':
                    filtro_1 = df_detalles_master[(df_detalles_master['Operacion'] == operacion_m) & (df_detalles_master['Fecha'] == fecha_m)]
                    if not filtro_1.empty:
                        df_c.at[idx, 'ordenante'] = filtro_1.iloc[0]['Ordenante']
                        coincidencias += 1
                        match_encontrado = True
                
                # Nivel 2: Triangulación (Monto Exacto + Fecha)
                if not match_encontrado:
                    filtro_2 = df_detalles_master[(abs(df_detalles_master['Monto'] - monto_m) < 0.01) & (df_detalles_master['Fecha'] == fecha_m)]
                    if not filtro_2.empty:
                        df_c.at[idx, 'ordenante'] = filtro_2.iloc[0]['Ordenante']
                        coincidencias += 1
        
        st.session_state.df_consolidado = df_c
        if coincidencias > 0:
            st.success(f"🎯 ¡Cruce exitoso! Se identificaron y rellenaron {coincidencias} ordenantes en el Libro Mayor.")
        else:
            st.info("No se encontraron coincidencias nuevas para rellenar.")

# =========================================================================
# DESPLIEGUE DEL DASHBOARD Y VISTA PREVIA
# =========================================================================
if not st.session_state.df_consolidado.empty:
    df_c = st.session_state.df_consolidado.copy()
    df_c['Monto'] = pd.to_numeric(df_c['Monto'], errors='coerce').fillna(0.0)
    
    st.write("---")
    st.subheader("📈 Cuadro de Mando del Flujo de Caja")
    
    df_soles = df_c[df_c['Moneda'].astype(str).str.contains('Soles', case=False, na=False)]
    df_dolares = df_c[df_c['Moneda'].astype(str).str.contains('Dolares|USD', case=False, na=False)]
    
    if not df_soles.empty:
        ing_soles = df_soles[df_soles['Tipo Op'] == 'INGRESO']
        egr_soles = df_soles[df_soles['Tipo Op'] == 'EGRESO']
        sum_ing_soles = ing_soles['Monto'].sum()
        sum_egr_soles = egr_soles['Monto'].sum()
        st.markdown("#### 🇵🇪 Flujo de Caja en Soles (PEN)")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("🟢 Ingresos Soles", f"S/. {sum_ing_soles:,.2f}", f"{len(ing_soles)} op.")
        kpi2.metric("🔴 Egresos Soles", f"S/. {sum_egr_soles:,.2f}", f"{len(egr_soles)} op.")
        kpi3.metric("⚖️ Balance Soles", f"S/. {(sum_ing_soles + sum_egr_soles):,.2f}")
    
    if not df_dolares.empty:
        ing_usd = df_dolares[df_dolares['Tipo Op'] == 'INGRESO']
        egr_usd = df_dolares[df_dolares['Tipo Op'] == 'EGRESO']
        sum_ing_usd = ing_usd['Monto'].sum()
        sum_egr_usd = egr_usd['Monto'].sum()
        st.markdown("#### 🇺🇸 Flujo de Caja en Dólares (USD)")
        kpi4, kpi5, kpi6 = st.columns(3)
        kpi4.metric("🟢 Ingresos Dólares", f"$ {sum_ing_usd:,.2f}", f"{len(ing_usd)} op.")
        kpi5.metric("🔴 Egresos Dólares", f"$ {sum_egr_usd:,.2f}", f"{len(egr_usd)} op.")
        kpi6.metric("⚖️ Balance Dólares", f"$ {(sum_ing_usd + sum_egr_usd):,.2f}")
    
    st.write("---")
    st.markdown("### 🏦 Consolidado Estructurado por Entidad y Cuenta")
    df_resumen = df_c.groupby(['BANCO', 'Cuenta', 'Moneda', 'Tipo Op']).agg(Número_Operaciones=('Monto', 'count'), Monto_Consolidado=('Monto', 'sum')).reset_index()
    df_resumen['Monto_Consolidado'] = df_resumen.apply(lambda r: f"$ {r['Monto_Consolidado']:,.2f}" if 'dolar' in str(r['Moneda']).lower() or 'usd' in str(r['Moneda']).lower() else f"S/. {r['Monto_Consolidado']:,.2f}", axis=1)
    st.dataframe(df_resumen, use_container_width=True)
    
    st.write("---")
    st.subheader("📊 Vista Previa de las Últimas Líneas del Libro Mayor")
    # Mostrar la tabla, prestando especial atención a que la columna ordenante se visualice al final
    st.dataframe(df_c.tail(20))
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_c.to_excel(writer, index=False)
    st.download_button("💾 Descargar Libro Mayor Completo (.xlsx)", output.getvalue(), "Libro_Mayor.xlsx")
