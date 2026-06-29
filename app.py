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

# Inicializar la base de datos histórica en memoria
if 'df_consolidado' not in st.session_state:
    st.session_state.df_consolidado = pd.DataFrame(columns=COLUMNAS_MAESTRO)

if st.sidebar.button("🧹 Limpiar Base Histórica"):
    st.session_state.df_consolidado = pd.DataFrame(columns=COLUMNAS_MAESTRO)
    st.sidebar.success("Base histórica reiniciada correctamente.")

# Única zona de carga
archivo_banco = st.file_uploader("📥 Arrastra aquí cualquier extracto de Excel o CSV", type=["xlsx", "xls", "csv"])

if archivo_banco:
    try:
        nombre_archivo = archivo_banco.name.lower()
        
        # Lector inteligente y controlador de trampas binarias (.xls falsos)
        if nombre_archivo.endswith('.csv'):
            df_raw = pd.read_csv(archivo_banco, header=None)
        elif nombre_archivo.endswith('.xls'):
            try:
                df_raw = pd.read_excel(archivo_banco, header=None, engine='xlrd')
            except Exception as e:
                if "BOF" in str(e) or "Expected BOF record" in str(e):
                    st.info("💡 Detectado archivo web disfrazado de Excel (Típico del BBVA). Procesando...")
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

        # Ruteador Inteligente de Motores Bancarios
        if "RUC" in texto_muestra and "Trans." in texto_muestra and "Abono" in texto_muestra:
            st.success("🔍 **Origen Detectado:** Banco de la Nación")
            df_nuevo = procesar_banco_nacion(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        elif "ccmn" in texto_muestra.lower() or "ccmd" in texto_muestra.lower() or "movimientos de cuenta" in texto_muestra.lower():
            st.success("🔍 **Origen Detectado:** Scotiabank")
            df_nuevo = procesar_scotiabank(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        elif "Consulta de Movimientos" in texto_muestra or "Saldo contable" in texto_muestra:
            st.success("🔍 **Origen Detectado:** Interbank")
            df_nuevo = procesar_interbank(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        elif "Cuenta Actual:" in texto_muestra or "Histórico de Movimientos" in texto_muestra:
            st.success("🔍 **Origen Detected:** BBVA")
            df_nuevo = procesar_bbva(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        elif "Descripción operación" in texto_muestra or (df_raw.shape[1] > 1 and '-' in str(df_raw.iloc[0, 1])):
            st.success("🔍 **Origen Detectado:** BCP")
            df_nuevo = procesar_bcp(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        else:
            st.error("❌ Archivo no reconocido por el sistema.")

        # Procesamiento y Control de Duplicados integrado en el Hub Central
        if df_nuevo is not None and not df_nuevo.empty:
            
            # Clasificación automática del tipo de operación (Ingreso / Egreso)
            df_nuevo['Monto'] = pd.to_numeric(df_nuevo['Monto'], errors='coerce').fillna(0.0)
            df_nuevo['Tipo Op'] = df_nuevo['Monto'].apply(lambda x: 'INGRESO' if x > 0 else ('EGRESO' if x < 0 else ''))
            
            # Concatenación automática y estándar de la glosa maestra
            diccionario_bancos = {
                '01.BCP': 'BCP', '02.BBVA': 'BBVA', '03.INTERBANK': 'ITB', '04.SCOTIABANK': 'SCT', '05.BN': 'BN'
            }
            banco_resumido = df_nuevo['BANCO'].map(diccionario_bancos).fillna(df_nuevo['BANCO']).astype(str)
            cuenta_limpia = df_nuevo['Cuenta'].fillna('000').astype(str)
            fecha_limpia = df_nuevo['Fecha'].fillna('').astype(str)
            operacion_limpia = df_nuevo['Operación - Número'].fillna('').astype(str)
            df_nuevo['Glosa'] = banco_resumido + " " + cuenta_limpia + " " + fecha_limpia + " " + operacion_limpia
            
            # Control de duplicados (Histórico y en archivo)
            df_nuevo = df_nuevo.dropna(subset=['Año'])
            filas_originales = len(df_nuevo)
            
            df_nuevo = df_nuevo.drop_duplicates(subset=['BANCO', 'Fecha', 'Monto', 'Operación - Número'])
            duplicados_internos = filas_originales - len(df_nuevo)
            
            duplicados_historicos = 0
            if not st.session_state.df_consolidado.empty:
                historico = st.session_state.df_consolidado
                llaves_historico = (historico['BANCO'].astype(str) + "_" + 
                                    historico['Fecha'].astype(str) + "_" + 
                                    historico['Monto'].astype(float).round(2).astype(str) + "_" + 
                                    historico['Operación - Número'].astype(str))
                
                llaves_nuevas = (df_nuevo['BANCO'].astype(str) + "_" + 
                                 df_nuevo['Fecha'].astype(str) + "_" + 
                                 df_nuevo['Monto'].astype(float).round(2).astype(str) + "_" + 
                                 df_nuevo['Operación - Número'].astype(str))
                
                filas_antes_filtro = len(df_nuevo)
                df_nuevo = df_nuevo[~llaves_nuevas.isin(llaves_historico)]
                duplicados_historicos = filas_antes_filtro - len(df_nuevo)
            
            if len(df_nuevo) > 0:
                st.session_state.df_consolidado = pd.concat([st.session_state.df_consolidado, df_nuevo], ignore_index=True)
                st.success(f"🎉 Se añadieron {len(df_nuevo)} nuevas transacciones únicas al consolidado.")
            else:
                st.info("ℹ️ El archivo cargado no contiene transacciones nuevas.")
                
            if duplicados_internos > 0 or duplicados_historicos > 0:
                with st.expander("🔍 Ver reporte de prevención de duplicados"):
                    if duplicados_internos > 0:
                        st.write(f"• **{duplicados_internos}** filas repetidas dentro del mismo archivo fueron limpiadas.")
                    if duplicados_historicos > 0:
                        st.write(f"• **{duplicados_historicos}** transacciones se omitieron porque ya existían en tu Libro Mayor.")

    except Exception as e:
        st.error(f"Error técnico procesando la tabla: {e}")

# =========================================================================
# DESPLIEGUE DE RESULTADOS, ESTADÍSTICAS Y DESCARGA
# =========================================================================
if not st.session_state.df_consolidado.empty:
    df_c = st.session_state.df_consolidado.copy()
    df_c['Monto'] = pd.to_numeric(df_c['Monto'], errors='coerce').fillna(0.0)
    
    st.write("---")
    st.subheader("📈 Cuadro de Mando del Flujo de Caja")
    
    # 1. Separación de datos para KPIs globales
    ingresos_df = df_c[df_c['Tipo Op'] == 'INGRESO']
    egresos_df = df_c[df_c['Tipo Op'] == 'EGRESO']
    
    sum_ingresos = ingresos_df['Monto'].sum()
    count_ingresos = len(ingresos_df)
    
    sum_egresos = egresos_df['Monto'].sum()
    count_egresos = len(egresos_df)
    
    saldo_neto = sum_ingresos + sum_egresos  # Los egresos ya figuran con signo negativo
    
    # Despliegue visual de tarjetas de control
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("🟢 Ingresos Totales", f"S/. {sum_ingresos:,.2f}", f"{count_ingresos} operaciones encontradas")
    kpi2.metric("🔴 Egresos Totales", f"S/. {sum_egresos:,.2f}", f"{count_egresos} operaciones encontradas")
    kpi3.metric("⚖️ Saldo Neto de Caja", f"S/. {saldo_neto:,.2f}", "Balance de fondos")
    
    # 2. Tabla resumida y colapsada de ingresos y egresos por Banco y Cuenta Corriente
    st.markdown("### 🏦 Consolidado Estructurado por Entidad y Cuenta")
    
    df_resumen = df_c.groupby(['BANCO', 'Cuenta', 'Tipo Op']).agg(
        Número_Operaciones=('Monto', 'count'),
        Monto_Consolidado=('Monto', 'sum')
    ).reset_index()
    
    # Formatear montos para su correcta visualización estética en la interfaz web
    df_resumen['Monto_Consolidado'] = df_resumen['Monto_Consolidado'].map(lambda x: f"S/. {x:,.2f}")
    st.dataframe(df_resumen, use_container_width=True)
    
    st.write("---")
    st.subheader("📊 Vista Previa de las Últimas Líneas del Libro Mayor")
    st.dataframe(df_c.tail(20))
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_c.to_excel(writer, index=False)
    
    st.download_button("💾 Descargar Libro Mayor Completo (.xlsx)", output.getvalue(), "Libro_Mayor.xlsx")
else:
    st.info("El sistema está listo y esperando archivos. Arrastra un extracto bancario para comenzar.")
