# -*- coding: utf-8 -*-
"""
BANCO Pichincha - SCRIPT DE PRUEBAS / SIMULACIÓN
Procesa los archivos CSV de Banco Pichincha, aplica la misma lógica de duplicados
y fecha, pero en lugar de insertar en la BD, genera un reporte en Excel de lo que se subiría.
No elimina los archivos procesados.
"""
from datetime import datetime, timedelta
import time
import os
import pandas as pd
from componentes_comunes import (
    LectorArchivos,
    LogManager,
    BaseDatos,
    ConfiguracionManager,
    RUTAS_CONFIG
)

# ==================== CONFIGURACIÓN GLOBAL ====================
DATABASE = "RegistrosBancos"
NOMBRE_BANCO = "Banco Pichincha"

EMPRESAS_PICHINCHA = {
    "AUTOLLANTA": {"numCuenta": "2100031073", "empresa": "AUTOLLANTA C LTDA"},
    "MAXXIMUNDO": {"numCuenta": "3485449004", "empresa": "MAXXIMUNDO CIA LTDA"},
    "STOX": {"numCuenta": "2100275013", "empresa": "STOX CIA LTDA"},
    "IKONIX": {"numCuenta": "2100295036", "empresa": "IKONIX CIA LTDA"},
}

# ==================== FUNCIONES AUXILIARES ====================

def obtener_empresa_desde_nombre_archivo(nombre_archivo):
    base = os.path.basename(nombre_archivo).lower()
    if base.startswith("au"):
        return "AUTOLLANTA"
    elif base.startswith("ma"):
        return "MAXXIMUNDO"
    elif base.startswith("st"):
        return "STOX"
    elif base.startswith("ik"):
        return "IKONIX"
    else:
        return base.split(".")[0].upper()


def obtener_base_y_sufijo(num_doc):
    """
    Dada una cadena de número de documento (posiblemente con sufijo),
    retorna una tupla (base, sufijo_entero).
    Soporta formatos: "1234567890", "1234567890-1", "1234567890 - 1"
    """
    num_doc = num_doc.strip()
    if '-' in num_doc:
        parts = num_doc.rsplit('-', 1)
        base = parts[0].strip()
        sufijo_str = parts[1].strip()
        if sufijo_str.isdigit():
            return base, int(sufijo_str)
    return num_doc, 0


def obtener_documentos_con_mismo_numero_base(num_base, documentos_bd):
    """Obtiene documentos existentes con el mismo número base"""
    documentos_encontrados = []
    for doc_bd in documentos_bd:
        num_doc_bd_completo = doc_bd["numDocumento"].strip()
        base, _ = obtener_base_y_sufijo(num_doc_bd_completo)
        if base == num_base:
            documentos_encontrados.append(num_doc_bd_completo)
    return documentos_encontrados


def movimiento_ya_existe(documento, fecha_sql, monto, saldo, tipo, documentos_bd):
    """
    Verifica si ya existe un movimiento exactamente igual en la BD.
    """
    for doc_bd in documentos_bd:
        num_doc_bd_completo = doc_bd["numDocumento"].strip()
        num_base_bd, _ = obtener_base_y_sufijo(num_doc_bd_completo)
        if (
            num_base_bd == documento and
            doc_bd.get("fechaTransaccion") == fecha_sql and
            abs(float(doc_bd.get("valor", 0)) - float(monto)) < 0.01 and
            abs(float(doc_bd.get("saldoContable", 0)) - float(saldo)) < 0.01 and
            doc_bd.get("tipo", "").strip() == tipo
        ):
            return True
    return False


def safe_float(valor):
    try:
        return float(valor.replace(",", ""))
    except Exception:
        return 0.0

# ==================== FUNCIONES DE PROCESAMIENTO ====================

def procesar_csv_pichincha_pruebas(ruta_csv, registros_a_insertar):
    """Procesa un archivo CSV de Banco Pichincha y simula inserciones en memoria"""
    try:
        empresa_key = obtener_empresa_desde_nombre_archivo(ruta_csv)
        info_empresa = EMPRESAS_PICHINCHA.get(
            empresa_key, {"numCuenta": "", "empresa": empresa_key})
        num_cuenta = info_empresa["numCuenta"]
        empresa = info_empresa["empresa"]

        registros = LectorArchivos.leerCSV(ruta_csv)
        if not registros or len(registros) < 2:
            LogManager.escribir_log(
                "ERROR", f"El archivo CSV no tiene datos suficientes: {os.path.basename(ruta_csv)}")
            return False

        encabezado = [col.strip().lower().replace(" ", "") for col in registros[0]]

        movimientos_omitidos = 0
        registros_nuevos_archivo = 0

        for i, fila in enumerate(registros[1:], start=2):
            try:
                fila_dict = dict(zip(encabezado, fila))
                documento = str(fila_dict.get("documento", "")).strip().zfill(10)
                
                fecha = fila_dict.get("fecha", "").strip()
                tipo = fila_dict.get("tipo", "").strip()
                monto = safe_float(fila_dict.get("monto", "0"))
                saldo = safe_float(fila_dict.get("saldo", "0"))
                oficina = fila_dict.get("oficina", "").strip()
                concepto = fila_dict.get("concepto", "").strip()

                # Convertir fecha a YYYY-MM-DD
                try:
                    fecha_obj = datetime.strptime(fecha, "%d/%m/%Y")
                    fecha_sql = fecha_obj.strftime("%Y-%m-%d")
                except Exception:
                    LogManager.escribir_log(
                        "WARNING", f"Fila {i}: Fecha inválida: {fecha}")
                    continue

                # Validar que la fecha sea mayor a 30 días antes de la fecha actual
                fecha_limite = (datetime.now() - timedelta(days=30)).date()
                if fecha_obj.date() <= fecha_limite:
                    movimientos_omitidos += 1
                    continue

                # Verificar duplicados en la base de datos (para simulación real)
                sql_check = f"""
                    SELECT COUNT(*) FROM {DATABASE}
                    WHERE numDocumento = '{documento}'
                    AND banco = '{NOMBRE_BANCO}'
                    AND empresa = '{empresa}'
                    AND fechaTransaccion = '{fecha_sql}'
                    AND valor = {monto}
                """
                resultado_check = BaseDatos.consultarBD(sql_check)
                if resultado_check and resultado_check[0][0] > 0:
                    movimientos_omitidos += 1
                    continue

                # Buscar documentos existentes con el mismo número base en la BD
                sql_buscar = f"""
                    SELECT numDocumento, fechaTransaccion, valor, saldoContable, tipo FROM {DATABASE}
                    WHERE banco = '{NOMBRE_BANCO}'
                    AND empresa = '{empresa}'
                    AND numCuenta = '{num_cuenta}'
                    AND numDocumento LIKE '{documento}%'
                """

                resultado_buscar = BaseDatos.consultarBD(sql_buscar)
                documentos_bd = [
                    {
                        "numDocumento": row[0],
                        "fechaTransaccion": row[1],
                        "valor": row[2],
                        "saldoContable": row[3],
                        "tipo": row[4]
                    }
                    for row in resultado_buscar
                ]

                # 1. Si ya existe exactamente el mismo movimiento, omitir
                if movimiento_ya_existe(documento, fecha_sql, monto, saldo, tipo, documentos_bd):
                    movimientos_omitidos += 1
                    continue

                # 2. Si existe el número base pero con algún campo diferente, asignar sufijo
                documentos_existentes = obtener_documentos_con_mismo_numero_base(documento, documentos_bd)
                sufijo = 0
                numDocumento_final = documento

                if documentos_existentes:
                    mayor_sufijo = 0
                    for doc_existente in documentos_existentes:
                        _, sufijo_existente = obtener_base_y_sufijo(doc_existente)
                        mayor_sufijo = max(mayor_sufijo, sufijo_existente)
                    sufijo = mayor_sufijo + 1
                    numDocumento_final = f"{documento}-{sufijo}"

                # En lugar de preparar SQL, guardamos en memoria para el reporte Excel
                registro_dict = {
                    "numCuenta": num_cuenta,
                    "banco": NOMBRE_BANCO,
                    "empresa": empresa,
                    "numDocumento": numDocumento_final,
                    "fechaTransaccion": fecha_sql,
                    "tipo": tipo,
                    "valor": monto,
                    "saldoContable": saldo,
                    "oficina": oficina if oficina else "N/D",
                    "conceptoTransaccion": concepto,
                    "archivoOrigen": os.path.basename(ruta_csv)
                }

                # Evitar insertar duplicados que se generen en esta misma ejecución
                ya_registrado = False
                for r in registros_a_insertar:
                    if (r["numCuenta"] == num_cuenta and
                        r["numDocumento"] == numDocumento_final and
                        r["fechaTransaccion"] == fecha_sql and
                        abs(r["valor"] - monto) < 0.01 and
                        abs(r["saldoContable"] - saldo) < 0.01 and
                        r["tipo"] == tipo):
                        ya_registrado = True
                        break

                if ya_registrado:
                    movimientos_omitidos += 1
                    continue

                registros_a_insertar.append(registro_dict)
                registros_nuevos_archivo += 1

            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error procesando fila {i} en archivo {os.path.basename(ruta_csv)}: {str(e)}")
                movimientos_omitidos += 1
                continue

        # Validar si el archivo es posiblemente incorrecto (0 omitidos)
        if movimientos_omitidos == 0:
            LogManager.escribir_log(
                "WARNING", f"El archivo {os.path.basename(ruta_csv)} posiblemente esté incorrecto (0 omitidos).")
            return False

        return {
            "empresa": empresa,
            "archivo": os.path.basename(ruta_csv),
            "nuevos": registros_nuevos_archivo,
            "omitidos": movimientos_omitidos
        }

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error procesando archivo CSV: {str(e)}")
        return False


def obtenerArchivos():
    """Obtiene la lista de archivos CSV para procesar de la misma carpeta que el script, ordenados por fecha de modificación"""
    try:
        ruta_archivos = os.path.dirname(os.path.abspath(__file__))

        archivos = []
        for archivo in os.listdir(ruta_archivos):
            if archivo.lower().endswith('.csv'):
                ruta_completa = os.path.join(ruta_archivos, archivo)
                archivos.append(ruta_completa)

        archivos_ordenados = sorted(
            archivos,
            key=lambda x: os.path.getmtime(x),
            reverse=True
        )

        LogManager.escribir_log(
            "INFO", f"Encontrados {len(archivos_ordenados)} archivos CSV para simulación")
        return archivos_ordenados

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error obteniendo archivos: {str(e)}")
        return []

# ==================== FUNCIÓN PRINCIPAL ====================

def main():
    """Función principal para la simulación"""
    try:
        LogManager.escribir_log("INFO", "=== INICIANDO SIMULACIÓN DE PROCESAMIENTO BANCO PICHINCHA ===")
        LogManager.escribir_log("INFO", "Nota: Los archivos no se eliminarán y no se modificará la Base de Datos.")

        archivos = obtenerArchivos()

        if not archivos:
            LogManager.escribir_log("WARNING", "No se encontraron archivos CSV para procesar")
            return False

        registros_a_insertar = []
        archivos_procesados = 0
        archivos_exitosos = 0

        for archivo in archivos:
            try:
                LogManager.escribir_log(
                    "INFO", f"📁 Analizando archivo {archivos_procesados + 1} de {len(archivos)}")

                resumen = procesar_csv_pichincha_pruebas(archivo, registros_a_insertar)

                if resumen:
                    archivos_exitosos += 1
                    LogManager.escribir_log(
                        "SUCCESS",
                        f"Simulación exitosa: {resumen['archivo']} | Empresa: {resumen['empresa']} | Nuevos: {resumen['nuevos']} | Omitidos: {resumen['omitidos']}"
                    )
                else:
                    LogManager.escribir_log(
                        "WARNING", f"Archivo omitido o sin nuevos registros: {os.path.basename(archivo)}")

                archivos_procesados += 1

            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error analizando archivo {archivo}: {str(e)}")
                archivos_procesados += 1
                continue

        # Generar Excel si hay registros a subir
        if registros_a_insertar:
            try:
                df = pd.DataFrame(registros_a_insertar)
                
                # Nombre del archivo excel con fecha/hora actual
                fecha_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
                nombre_excel = f"Simulacion_Pichincha_{fecha_hora}.xlsx"
                ruta_excel = os.path.join("/home/administrador/Escritorio/bancos", nombre_excel)
                
                df.to_excel(ruta_excel, index=False)
                
                LogManager.escribir_log("SUCCESS", "=== SIMULACIÓN COMPLETADA CON ÉXITO ===")
                LogManager.escribir_log("SUCCESS", f"Se generó el reporte Excel con {len(registros_a_insertar)} transacciones nuevas.")
                LogManager.escribir_log("SUCCESS", f"Reporte guardado en: {ruta_excel}")
            except Exception as e:
                LogManager.escribir_log("ERROR", f"Error al guardar archivo Excel: {str(e)}")
        else:
            LogManager.escribir_log("WARNING", "=== SIMULACIÓN COMPLETADA ===")
            LogManager.escribir_log("WARNING", "No se encontraron nuevos registros para reportar en Excel.")

        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error en proceso de simulación principal: {str(e)}")
        return False


if __name__ == "__main__":
    main()
