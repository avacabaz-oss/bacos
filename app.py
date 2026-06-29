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
            st.success("🔍 **Origen Detectado:** BBVA")
            df_nuevo = procesar_bbva(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        elif "Descripción operación" in texto_muestra or (df_raw.shape[1] > 1 and '-' in str(df_raw.iloc[0, 1])):
            st.success("🔍 **Origen Detectado:** BCP")
            df_nuevo = procesar_bcp(df_raw, texto_muestra, COLUMNAS_MAESTRO)

        else:
            st.error("❌ Archivo no reconocido por el sistema.")

        # Motor de Control de Duplicados integrado en el Hub Central
        if df_nuevo is not None and not df_nuevo.empty:
            df_nuevo = df_nuevo.dropna(subset=['Año'])
            filas_originales = len(df_nuevo)
            
            # Capa 1: Duplicados internos del archivo
            df_nuevo = df_nuevo.drop_duplicates(subset=['BANCO', 'Fecha', 'Monto', 'Operación - Número'])
            duplicados_internos = filas_originales - len(df_nuevo)
            
            duplicados_historicos = 0
            # Capa 2: Duplicados contra la memoria histórica de la sesión
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

# Despliegue de resultados y descarga
if not st.session_state.df_consolidado.empty:
    st.subheader("📊 Vista Previa del Libro Mayor")
    st.dataframe(st.session_state.df_consolidado.tail(20))
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        st.session_state.df_consolidado.to_excel(writer, index=False)
    
    st.download_button("💾 Descargar Libro Mayor (.xlsx)", output.getvalue(), "Libro_Mayor.xlsx")
else:
    st.info("El sistema está listo y esperando archivos. Arrastra un extracto bancario para comenzar.")
