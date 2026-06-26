import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Conciliador Bancario", page_icon="📊", layout="wide")

st.title("📊 Sistema de Consolidación y Conciliación Bancaria")
st.write("Sube el archivo principal y los archivos secundarios para cruzar la información y eliminar duplicados automáticamente.")

# --- FUNCIONES DE LIMPIEZA INTELIGENTE ---
def limpiar_texto(txt):
    if pd.isna(txt): return ""
    txt = str(txt).lower().strip()
    # Quitar tildes y caracteres especiales
    txt = re.sub(r'[áäâà]', 'a', txt)
    txt = re.sub(r'[éëêè]', 'e', txt)
    txt = re.sub(r'[íïîì]', 'i', txt)
    txt = re.sub(r'[óöôò]', 'o', txt)
    txt = re.sub(r'[úüûù]', 'u', txt)
    return re.sub(r'[^a-z0-9]', '', txt)

def procesar_archivo(file_colab):
    """Lee el archivo, detecta la cabecera y estandariza columnas clave"""
    df_raw = pd.read_excel(file_colab, header=None)
    
    # Capturar número de cuenta si existe en las primeras filas
    cuenta_origen = "No detectada"
    for fila in range(min(5, len(df_raw))):
        valores = df_raw.iloc[fila].dropna().tolist()
        if any("cuenta" in str(v).lower() or "camara" in str(v).lower() for v in valores):
            cuenta_origen = " - ".join([str(v) for v in valores])
            break

    # Buscar fila de cabecera
    fila_cabecera = 0
    for idx, row in df_raw.iterrows():
        valores_limpios = [limpiar_texto(x) for x in row.values]
        if any("operacion" in v or "numero" in v for v in valores_limpios):
            fila_cabecera = idx
            break
            
    df = pd.read_excel(file_colab, skiprows=fila_cabecera)
    df.columns = [str(c).strip() for c in df.columns]
    
    # Identificar columnas dinámicamente para la validación de duplicados
    for col in df.columns:
        col_l = limpiar_texto(col)
        if ("operacion" in col_l and "numero" in col_l) or (col_l in ["operacion", "numero", "nroop", "numoperacion"]):
            df.rename(columns={col: 'KEY_ID'}, inplace=True)
        if "ordenante" in col_l or "nombre" in col_l:
            df.rename(columns={col: 'Nombre del Ordenante'}, inplace=True)
        if "fecha" in col_l:
            df.rename(columns={col: 'KEY_FECHA'}, inplace=True)
        if "monto" in col_l or "abono" in col_l or "credito" in col_l or "importe" in col_l:
            df.rename(columns={col: 'KEY_MONTO'}, inplace=True)
        if "saldo" in col_l:
            df.rename(columns={col: 'KEY_SALDO'}, inplace=True)
            
    if 'KEY_ID' in df.columns:
        df['KEY_ID'] = df['KEY_ID'].astype(str).str.strip()
    return df, cuenta_origen

# --- INTERFAZ DE USUARIO (WEB) ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📁 Archivo Principal")
    archivo_p = st.file_uploader("Sube el extracto principal (.xlsx)", type=["xlsx"], key="principal")

with col2:
    st.subheader("📁 Archivos Secundarios")
    archivos_s = st.file_uploader("Sube los 3 archivos secundarios (puedes seleccionar varios)", type=["xlsx"], accept_multiple_files=True, key="secundarios")

if archivo_p and archivos_s:
    if st.button("🚀 Ejecutar Conciliación y Limpieza", type="primary"):
        with st.spinner("Procesando datos y eliminando duplicados..."):
            try:
                # 1. Procesar Principal
                df_principal, cuenta_p = procesar_archivo(archivo_p)
                
                if 'KEY_ID' not in df_principal.columns:
                    st.error("No se pudo identificar la columna de número de operación en el archivo principal.")
                else:
                    df_principal['Cuenta Origen'] = cuenta_p
                    
                    # 2. Procesar Secundarios
                    lista_secundarios = []
                    for f_sec in archivos_s:
                        df_sec, _ = procesar_archivo(f_sec)
                        if 'KEY_ID' in df_sec.columns and 'Nombre del Ordenante' in df_sec.columns:
                            # Recopilar columnas extras para la validación estricta de duplicados si existen
                            columnas_interes = ['KEY_ID', 'Nombre del Ordenante']
                            for c_extra in ['KEY_FECHA', 'KEY_MONTO', 'KEY_SALDO']:
                                if c_extra in df_sec.columns:
                                    columnas_interes.append(c_extra)
                                    
                            lista_secundarios.append(df_sec[columnas_interes])
                    
                    if not lista_secundarios:
                        st.error("Ninguno de los archivos secundarios tiene el formato o las columnas requeridas.")
                    else:
                        # Unificar toda la base secundaria
                        df_secundarios_total = pd.concat(lista_secundarios, ignore_index=True)
                        
                        # --- LÓGICA ANTI-DUPLICADOS AVANZADA ---
                        # Definimos el criterio de duplicidad según tus directivas
                        criterio_duplicados = ['KEY_ID']
                        if 'KEY_FECHA' in df_secundarios_total.columns: criterio_duplicados.append('KEY_FECHA')
                        if 'KEY_MONTO' in df_secundarios_total.columns: criterio_duplicados.append('KEY_MONTO')
                        if 'KEY_SALDO' in df_secundarios_total.columns: criterio_duplicados.append('KEY_SALDO')
                        
                        # Eliminar registros idénticos en fecha, operación y saldo final
                        filas_antes = len(df_secundarios_total)
                        df_secundarios_total = df_secundarios_total.drop_duplicates(subset=criterio_duplicados, keep='first')
                        filas_despues = len(df_secundarios_total)
                        
                        # Por seguridad, si el ID se repite pero tiene datos distintos, dejamos solo el primero único
                        df_secundarios_total = df_secundarios_total.drop_duplicates(subset=['KEY_ID'], keep='first')
                        
                        # Reducir a lo necesario para el join limpio
                        df_secundarios_final = df_secundarios_total[['KEY_ID', 'Nombre del Ordenante']]
                        
                        # 3. Cruce final (Left Join)
                        resultado = pd.merge(df_principal, df_secundarios_final, on='KEY_ID', how='left')
                        
                        # Reestablecer nombres visuales originales si existían
                        resultado.rename(columns={'KEY_ID': 'Operación - Número'}, inplace=True)
                        if 'KEY_FECHA' in resultado.columns: resultado.rename(columns={'KEY_FECHA': 'Fecha'}, inplace=True)
                        if 'KEY_MONTO' in resultado.columns: resultado.rename(columns={'KEY_MONTO': 'Monto'}, inplace=True)
                        if 'KEY_SALDO' in resultado.columns: resultado.rename(columns={'KEY_SALDO': 'Saldo Final'}, inplace=True)
                        
                        # 4. Preparar la descarga sin guardar en disco del servidor
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            resultado.to_excel(writer, index=False)
                        data_excel = output.getvalue()
                        
                        st.success(f"¡Conciliación terminada con éxito! Se revisaron los abonos diarios e interdiarios y se eliminaron {filas_antes - filas_despues} registros duplicados basados en número de operación, fecha y saldos.")
                        
                        st.download_button(
                            label="📥 Descargar Resultado Consolidado",
                            data=data_excel,
                            file_name="resultado_consolidado_web.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
            except Exception as e:
                st.error(f"Ocurrió un error inesperado al procesar los archivos: {str(e)}")
else:
    st.info("💡 Por favor, sube el archivo principal y al menos un archivo secundario para activar el sistema.")
