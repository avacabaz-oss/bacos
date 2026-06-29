import pandas as pd
import re

def procesar_banco_nacion(df_raw, texto_muestra, columnas_maestro):
    idx_header = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('Trans\.|Abono', na=False).any(), axis=1)].index[0]
    df_datos = df_raw.iloc[idx_header+1:].copy()
    df_datos.columns = [str(c).strip() for c in df_raw.iloc[idx_header].values]
    df_datos = df_datos[df_datos['Fecha'].notna()]
    
    cuenta_final = "897"
    moneda = "01.Soles"
    
    fecha_limpia = df_datos['Fecha'].astype(str).str.replace('.', '-', regex=False).str.strip()
    fechas = pd.to_datetime(fecha_limpia, format='%Y-%m-%d', errors='coerce')
    
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
    
    df_res = pd.DataFrame(columns=columnas_maestro)
    df_res['Año'] = fechas.dt.year
    df_res['Mes '] = fechas.dt.month
    df_res['Semana'] = fechas.dt.isocalendar().week
    df_res['BANCO'] = "05.BN"
    df_res['Cuenta'] = cuenta_final
    df_res['Moneda'] = moneda
    df_res['Fecha'] = fechas.dt.strftime('%d/%m/%Y')
    df_res['Descripción operación'] = df_datos['RUC'].fillna('').astype(str).str.replace(r'\.0', '', regex=True)
    df_res['Operación - Número'] = df_datos['Documento'].fillna('').astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
    df_res['Monto'] = monto_final
    df_res['Sucursal - agencia'] = df_datos['Oficina'].astype(str).str.replace(r'\.0', '', regex=True)
    return df_res

def procesar_scotiabank(df_raw, texto_muestra, columnas_maestro):
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
    
    df_res = pd.DataFrame(columns=columnas_maestro)
    df_res['Año'] = fechas.dt.year
    df_res['Mes '] = fechas.dt.month
    df_res['Semana'] = fechas.dt.isocalendar().week
    df_res['BANCO'] = "04.SCOTIABANK"
    df_res['Cuenta'] = cuenta_final
    df_res['Moneda'] = moneda
    df_res['Fecha'] = fechas.dt.strftime('%d/%m/%Y')
    df_res['Descripción operación'] = df_datos['Movimiento']
    df_res['Monto'] = pd.to_numeric(df_datos['Importe'], errors='coerce')
    df_res['Operación - Número'] = df_datos['Referencia'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
    return df_res

def procesar_interbank(df_raw, texto_muestra, columnas_maestro):
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
    fechas_valuta = pd.to_datetime(df_datos['Fecha de proceso'], dayfirst=True, errors='coerce')
    monto_final = pd.to_numeric(df_datos['Abono'], errors='coerce').fillna(pd.to_numeric(df_datos['Cargo'], errors='coerce'))
    
    df_res = pd.DataFrame(columns=columnas_maestro)
    df_res['Año'] = fechas.dt.year
    df_res['Mes '] = fechas.dt.month
    df_res['Semana'] = fechas.dt.isocalendar().week
    df_res['BANCO'] = "03.INTERBANK"
    df_res['Cuenta'] = cuenta_final
    df_res['Moneda'] = moneda
    df_res['Fecha'] = fechas.dt.strftime('%d/%m/%Y')
    if not fechas_valuta.isna().all():
        df_res['Fecha valuta'] = fechas_valuta.dt.strftime('%d/%m/%Y')
    df_res['Descripción operation'] = df_datos['Movimiento'].astype(str) + " - " + df_datos['Descripción'].astype(str)
    df_res['Monto'] = monto_final
    df_res['Saldo'] = df_datos['Saldo contable']
    df_res['Operación - Número'] = df_datos['Nro. de operación'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
    return df_res

def procesar_bbva(df_raw, texto_muestra, columnas_maestro):
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
    fechas_valuta = pd.to_datetime(df_datos['F. Valor'], dayfirst=True, errors='coerce')
    
    df_res = pd.DataFrame(columns=columnas_maestro)
    df_res['Año'] = fechas.dt.year
    df_res['Mes '] = fechas.dt.month
    df_res['Semana'] = fechas.dt.isocalendar().week
    df_res['BANCO'] = "02.BBVA"
    df_res['Cuenta'] = cuenta_final
    df_res['Moneda'] = moneda
    df_res['Fecha'] = fechas.dt.strftime('%d/%m/%Y')
    df_res['Fecha valuta'] = fechas_valuta.dt.strftime('%d/%m/%Y')
    df_res['Descripción operación'] = df_datos['Concepto']
    df_res['Monto'] = df_datos['Importe']
    df_res['Sucursal - agencia'] = df_datos['Oficina']
    df_res['Operación - Número'] = df_datos['Nº. Doc.'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
    return df_res

def procesar_bcp(df_raw, texto_muestra, columnas_maestro):
    idx_header = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('Fecha', na=False).any(), axis=1)].index[0]
    df_datos = df_raw.iloc[idx_header+1:].copy()
    df_datos.columns = [str(c).strip() for c in df_raw.iloc[idx_header].values]
    
    cuenta_full = str(df_raw.iloc[0, 1])
    solo_numeros = re.sub(r'\D', '', cuenta_full)
    cuenta_final = solo_numeros[-3:] if solo_numeros else "000"
    moneda = "01.Soles" if "Soles" in str(df_raw.iloc[1, 1]) else "02.Dolares"
    
    fechas = pd.to_datetime(df_datos['Fecha'], dayfirst=True, errors='coerce')
    fechas_valuta = pd.to_datetime(df_datos['Fecha valuta'], dayfirst=True, errors='coerce')
    
    df_res = pd.DataFrame(columns=columnas_maestro)
    df_res['Año'] = fechas.dt.year
    df_res['Mes '] = fechas.dt.month
    df_res['Semana'] = fechas.dt.isocalendar().week
    df_res['BANCO'] = "01.BCP"
    df_res['Cuenta'] = cuenta_final
    df_res['Moneda'] = moneda
    df_res['Fecha'] = fechas.dt.strftime('%d/%m/%Y')
    df_res['Fecha valuta'] = fechas_valuta.dt.strftime('%d/%m/%Y')
    
    mapeo_bcp = {
        'Descripción operación': 'Descripción operación',
        'Monto': 'Monto', 'Saldo': 'Saldo', 'Sucursal - agencia': 'Sucursal - agencia',
        'Operación - Hora': 'Operación - Hora', 'Usuario': 'Usuario', 'UTC': 'UTC', 'Referencia2': 'Referencia2'
    }
    for c_m, c_b in mapeo_bcp.items():
        if c_b in df_datos.columns:
            df_res[c_m] = df_datos[c_b]
            
    df_res['Operación - Número'] = df_datos['Operación - Número'].astype(str).str.replace(r'\.0', '', regex=True).str.zfill(8)
    return df_res
