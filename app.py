import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Tablero de Conciliación Bancaria", page_icon="🏦", layout="wide")

st.title("🏦 Sistema Centralizado de Conciliación Multi-Banco")
st.write("Visualiza, consolida y depura los estados de cuenta eliminando duplicados automáticamente.")

# --- FUNCIÓN DE LIMPIEZA DE TEXTO PARA IDENTIFICACIÓN ---
def limpiar_texto(txt):
    if pd.isna(txt): return ""
    txt = str(txt).lower().strip()
    txt = re.sub(r'[áäâà]', 'a', txt)
    txt = re.sub(r'[éëêè]', 'e', txt)
    txt = re.sub(r'[íïîì]', 'i', txt)
    txt = re.sub(r'[óöôò]', 'o', txt)
    txt = re.sub(r'[úüûù]', 'u', txt)
    return re.sub(r'[^a-z0-9]', '', txt)

# --- MOTOR DE DETECCIÓN Y PROCESAMIENTO ---
def procesar_archivo_bancario(file_upload):
    """Lee el archivo, detecta dinámicamente el membrete, la cuenta y las columnas"""
    df_raw = pd.read_excel(file_upload, header=None)
    
    # 1. Extraer el texto de la cuenta/banco desde el membrete (primeras filas)
    cuenta_origen = "No detectada"
    for fila in range(min(5, len(df_raw))):
        valores = df_raw.iloc[fila].dropna().tolist()
        if any("cuenta" in str(v).lower() or "camara" in str(v).lower() or "banco" in str(v).lower() for v in valores):
            cuenta_origen = " - ".join([str(v) for v in valores])
            break

    # 2. Buscar en qué fila empiezan los encabezados reales de la tabla
    fila_cabecera = 0
    for idx, row in df_raw.iterrows():
        valores_limpios = [limpiar_texto(x) for x in row.values]
        if any("operacion" in v or "numero" in v or "fecha" in v for v in valores_limpios):
            fila_cabecera = idx
            break
            
    # 3. Leer el archivo real desde la fila correcta
    df = pd.read_excel(file_upload, skiprows=fila_cabecera)
    df.columns = [str(c).strip() for c in df.columns] # Limpiar espacios fantasmas en títulos
    
    # 4. Mapear nombres variables internos para la lógica del sistema
    for col in df.columns:
        col_l = limpiar_texto(col)
        # Detecta variaciones de "Operación - Número" o "Número - Operación"
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

# --- PANEL LATERAL DE CARGA ---
with st.sidebar:
    st.header("⚙️ Carga de Archivos")
    archivo_p = st.file_uploader("1. Sube el Extracto Principal (.xlsx)", type=["xlsx"])
    archivos_s = st.file_uploader("2. Sube los Archivos Secundarios (.xlsx)", type=["xlsx"], accept_multiple_files=True)

# --- PROCESAMIENTO PRINCIPAL ---
if archivo_p and archivos_s:
    try:
        # Procesar el archivo principal
        df_principal, cuenta_p = procesar_archivo_bancario(archivo_p)
        
        if 'KEY_ID' not in df_principal.columns:
            st.error("❌ No se pudo identificar la columna de número de operación en el archivo principal.")
        else:
            # Inyectar metadato de cuenta de origen
            df_principal['Cuenta Origen'] = cuenta_p
            
            # Procesar todos los archivos secundarios
            lista_secundarios = []
            for f_sec in archivos_s:
                df_sec, _ = procesar_archivo_bancario(f_sec)
                if 'KEY_ID' in df_sec.columns and 'Nombre del Ordenante' in df_sec.columns:
                    columnas_validar = ['KEY_ID', 'Nombre del Ordenante']
                    for c_extra in ['KEY_FECHA', 'KEY_MONTO', 'KEY_SALDO']:
                        if c_extra in df_sec.columns:
                            columnas_validar.append(c_extra)
                    lista_secundarios.append(df_sec[columnas_validar])
            
            if not lista_secundarios:
                st.error("❌ Ninguno de los archivos secundarios contiene las columnas requeridas para el cruce.")
            else:
                # Consolidar base secundaria
                df_secundarios_total = pd.concat(lista_secundarios, ignore_index=True)
                
                # --- VALIDACIÓN ANTI-DUPLICADOS AVANZADA ---
                # Definir criterios estrictos basados en tus directivas (Misma fecha, operación y saldo final)
                criterio_duplicados = ['KEY_ID']
                if 'KEY_FECHA' in df_secundarios_total.columns: criterio_duplicados.append('KEY_FECHA')
                if 'KEY_MONTO' in df_secundarios_total.columns: criterio_duplicados.append('KEY_MONTO')
                if 'KEY_SALDO' in df_secundarios_total.columns: criterio_duplicados.append('KEY_SALDO')
                
                filas_antes = len(df_secundarios_total)
                # Eliminar registros duplicados interdiarios manteniendo solo el primero válido
                df_secundarios_total = df_secundarios_total.drop_duplicates(subset=criterio_duplicados, keep='first')
                df_secundarios_total = df_secundarios_total.drop_duplicates(subset=['KEY_ID'], keep='first')
                filas_despues = len(df_secundarios_total)
                
                # Reducir base secundaria para el join limpio
                df_secundarios_final = df_secundarios_total[['KEY_ID', 'Nombre del Ordenante']]
                
                # --- EJECUTAR CRUCE (LEFT JOIN) ---
                resultado = pd.merge(df_principal, df_secundarios_final, on='KEY_ID', how='left')
                
                # Normalizar nombres visuales para la exportación final
                resultado.rename(columns={
                    'KEY_ID': 'Operación - Número',
                    'KEY_FECHA': 'Fecha',
                    'KEY_MONTO': 'Monto',
                    'KEY_SALDO': 'Saldo Final'
                }, inplace=True)
                
                # =====================================================================
                # 📋 CONFIGURACIÓN EXCLUSIVA DE TU FORMATO HISTÓRICO
                # =====================================================================
                # Orden exacto de los campos que manejas para evitar errores de estructura:
                columnas_formato_antiguo = [
                    'Fecha',
                    'Operación - Número',
                    'Nombre del Ordenante',
                    'Monto',
                    'Saldo Final',
                    'Cuenta Origen'
                ]
                
                # Asegurar que solo se exporten las columnas deseadas en ese orden exacto
                # Si el archivo principal contiene columnas adicionales, puedes agregarlas aquí
                columnas_finales = [c for c in columnas_formato_antiguo if c in resultado.columns]
                resultado_formateado = resultado[columnas_finales]
                # =====================================================================
                
                # --- INTERFAZ DE VISUALIZACIÓN WEB ---
                st.success(f"🎉 ¡Conciliación y depuración completada! Se eliminaron {filas_antes - filas_despues} registros duplicados de abonos.")
                
                # Panel Métricas rápidas
                m1, m2, m3 = st.columns(3)
                with m1: st.metric("Total Operaciones", f"{len(resultado_formateado)}")
                with m2: st.metric("Cuenta de Origen", f"{cuenta_p[:30]}...")
                with m3: st.metric("Duplicados Removidos", f"{filas_antes - filas_despues}")
                
                tab1, tab2 = st.tabs(["📋 Vista Previa de Datos", "📥 Descargar Reporte"])
                
                with tab1:
                    st.subheader("Registros Organizados según tu Formato")
                    st.dataframe(resultado_formateado, use_container_width=True, height=400)
                    
                with tab2:
                    st.subheader("Exportar archivo consolidado")
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        resultado_formateado.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 Descargar Reporte Final Ordenado (.xlsx)",
                        data=output.getvalue(),
                        file_name="reporte_consolidado_bancos.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
                    
    except Exception as e:
        st.error(f"Ocurrió un inconveniente al procesar las estructuras de los archivos: {str(e)}")
else:
    st.info("👋 Panel activo. Carga el archivo principal y los secundarios en el menú de la izquierda para estructurar tus datos.")
