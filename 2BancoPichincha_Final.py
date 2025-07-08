# -*- coding: utf-8 -*-
"""
BANCO Pichincha - PROCESAMIENTO DE ARCHIVOS TXT OPTIMIZADO
Versión optimizada del procesador original usando componentes comunes
"""
from datetime import datetime
import time
import os
import re
from componentes_comunes import (
    LectorArchivos,
    LogManager,
    BaseDatos,
    SubprocesoManager,
    ConfiguracionManager,
    RUTAS_CONFIG
)

# ==================== CONFIGURACIÓN GLOBAL ====================

# DATABASE = "RegistrosBancosPRUEBA"
# DATABASE_LOGS = "AutomationLogPRUEBA"
# DATABASE_RUNS = "AutomationRunPRUEBA"
DATABASE = "RegistrosBancos"
DATABASE_LOGS = "AutomationLog"
DATABASE_RUNS = "AutomationRun"
NOMBRE_BANCO = "Banco Pichincha"

# ==================== FUNCIONES DE BASE DE DATOS ====================

EMPRESAS_PICHINCHA = {
    "AUTOLLANTA": {"numCuenta": "2100031073", "empresa": "AUTOLLANTA C LTDA"},
    "MAXXIMUNDO": {"numCuenta": "3485449004", "empresa": "MAXXIMUNDO CIA LTDA"},
    "STOX": {"numCuenta": "2100275013", "empresa": "STOX CIA LTDA"},
    "IKONIX": {"numCuenta": "2100295036", "empresa": "IKONIX CIA LTDA"},
}


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


def obtenerIDEjecucion():
    """Obtiene el siguiente ID de ejecución de la BD"""
    try:
        sql = f"SELECT MAX(idAutomationRun) FROM {DATABASE_RUNS}"
        resultado = BaseDatos.consultarBD(sql)
        if resultado and resultado[0] and resultado[0][0]:
            return resultado[0][0] + 1
        return 1
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error obteniendo ID ejecución: {str(e)}")
        return int(time.time())  # Fallback


def datosEjecucion(sql):
    """Ejecuta una consulta en la BD"""
    try:
        BaseDatos.ejecutarSQL(sql)
        return True
    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error ejecutando SQL: {str(e)}")
        return False


def escribirLog(mensaje, id_ejecucion, estado, accion):
    """Escribe un log en la BD"""
    texto_limpio = mensaje.replace("'", "''")
    sql = f"""
        INSERT INTO {DATABASE_LOGS} (idAutomationRun, processName, dateLog, statusLog, action)
        VALUES ({id_ejecucion}, '{texto_limpio}',
                SYSDATETIME(), '{estado}', '{accion}')
    """
    datosEjecucion(sql)


# ==================== FUNCIONES DE PROCESAMIENTO ====================

def safe_float(valor):
    try:
        return float(valor.replace(",", ""))
    except Exception:
        return 0.0

def obtener_documentos_con_mismo_numero_base(num_base, documentos_bd):
    """Obtiene documentos existentes con el mismo número base"""
    documentos_encontrados = []
    for doc_bd in documentos_bd:
        num_doc_bd_completo = doc_bd["numDocumento"].strip()
        num_base_bd = num_doc_bd_completo.split(' - ')[0].strip()
        if num_base_bd == num_base:
            documentos_encontrados.append(num_doc_bd_completo)
    return documentos_encontrados


def movimiento_ya_existe(documento, fecha_sql, monto, saldo, tipo, documentos_bd):
    """
    Verifica si ya existe un movimiento exactamente igual en la BD.
    """
    for doc_bd in documentos_bd:
        num_doc_bd_completo = doc_bd["numDocumento"].strip()
        num_base_bd = num_doc_bd_completo.split(' - ')[0].strip()
        if (
            num_base_bd == documento and
            doc_bd.get("fechaTransaccion") == fecha_sql and
            abs(float(doc_bd.get("valor", 0)) - float(monto)) < 0.01 and
            abs(float(doc_bd.get("saldoContable", 0)) - float(saldo)) < 0.01 and
            doc_bd.get("tipo", "").strip() == tipo
        ):
            return True
    return False
    
def procesar_csv_pichincha(ruta_csv, id_ejecucion):
    """Procesa un archivo CSV de Banco Pichincha"""
    try:

        empresa_key = obtener_empresa_desde_nombre_archivo(ruta_csv)
        info_empresa = EMPRESAS_PICHINCHA.get(
            empresa_key, {"numCuenta": "", "empresa": empresa_key})
        num_cuenta = info_empresa["numCuenta"]
        empresa = info_empresa["empresa"]

        registros = LectorArchivos.leerCSV(ruta_csv)
        # print(f"Registros leídos: {registros}")
        if not registros or len(registros) < 2:
            LogManager.escribir_log(
                "ERROR", "El archivo CSV no tiene datos suficientes")
            return False

        encabezado = [col.strip().lower().replace(" ", "") for col in registros[0]]

        movimientos_insertados = 0
        movimientos_omitidos = 0

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
                    fecha_sql = datetime.strptime(
                        fecha, "%d/%m/%Y").strftime("%Y-%m-%d")
                except Exception:
                    LogManager.escribir_log(
                        "WARNING", f"Fila {i}: Fecha inválida: {fecha}")
                    continue

                # Verificar duplicados
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

                # Buscar documentos existentes con el mismo número base
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
                        if ' - ' in doc_existente:
                            try:
                                sufijo_existente = int(doc_existente.split(' - ')[1])
                                mayor_sufijo = max(mayor_sufijo, sufijo_existente)
                            except (ValueError, IndexError):
                                pass
                    sufijo = mayor_sufijo + 1
                    numDocumento_final = f"{documento} - {sufijo}"

                # Insertar en base de datos
                sql_insert = f"""
                    INSERT INTO {DATABASE}
                    (numCuenta, banco, empresa, numDocumento, idEjecucion, fechaTransaccion,
                     tipo, valor, saldoContable, oficina, conceptoTransaccion)
                    VALUES (
                        '{num_cuenta}', '{NOMBRE_BANCO}', '{empresa}', '{numDocumento_final}', {
                            id_ejecucion},
                        '{fecha_sql}', '{tipo}', {monto}, {
                            saldo}, '{oficina}', '{concepto}'
                    )
                """
                if BaseDatos.ejecutarSQL(sql_insert):
                    movimientos_insertados += 1
                else:
                    movimientos_omitidos += 1

            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error procesando fila {i}: {str(e)}")
                movimientos_omitidos += 1
                continue

        return {
            "empresa": empresa,
            "archivo": os.path.basename(ruta_csv),
            "insertados": movimientos_insertados,
            "omitidos": movimientos_omitidos
        }

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error procesando archivo CSV: {str(e)}")
        return False


def obtenerArchivos():
    """Obtiene la lista de archivos TXT para procesar, ordenados por fecha"""
    try:

        # Ruta por defecto si no está configurada
        ruta_archivos = RUTAS_CONFIG['pichincha']

        if not os.path.exists(ruta_archivos):
            LogManager.escribir_log(
                "ERROR", f"La ruta no existe: {ruta_archivos}")
            return []

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
            "INFO", f"Encontrados {len(archivos_ordenados)} archivos TXT para procesar")
        return archivos_ordenados

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error obteniendo archivos: {str(e)}")
        return []


# ==================== FUNCIÓN PRINCIPAL ====================


def main():
    """Función principal que procesa todos los archivos de Banco Pichincha"""
    id_ejecucion = None

    try:
        # Obtener ID de ejecución
        id_ejecucion = obtenerIDEjecucion()

        LogManager.iniciar_proceso(
            NOMBRE_BANCO, id_ejecucion, f"Procesamiento archivos TXT Pichincha - ID: {id_ejecucion}")

        # Registrar inicio en BD
        sql_inicio = f"""
            INSERT INTO {DATABASE_RUNS} (idAutomationRun, processName, startDate, finalizationStatus) 
            VALUES ({id_ejecucion}, 'Procesamiento archivos-{NOMBRE_BANCO}', SYSDATETIME(), 'Running')
        """
        datosEjecucion(sql_inicio)
        escribirLog("Inicio del proceso", id_ejecucion,
                    "Information", "Inicio")

        # Obtener archivos para procesar
        archivos = obtenerArchivos()

        if not archivos:
            LogManager.escribir_log(
                "WARNING", "No se encontraron archivos TXT para procesar")
            escribirLog("No se encontraron archivos para procesar",
                        id_ejecucion, "Warning", "Sin archivos")

            # Marcar como completado sin errores
            sql_fin = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = SYSDATETIME(), finalizationStatus = 'Completed' 
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_fin)

            LogManager.finalizar_proceso(
                NOMBRE_BANCO, exito=True, descripcion="No hay archivos para procesar")
            return True

        # Procesar cada archivo
        archivos_procesados = 0
        archivos_exitosos = 0

        for archivo in archivos:
            try:
                LogManager.escribir_log(
                    "INFO", f"📁 Procesando archivo {archivos_procesados + 1} de {len(archivos)}")

                if archivo.lower().endswith('.csv'):
                    resumen = procesar_csv_pichincha(archivo, id_ejecucion)
                else:
                    break

                if resumen:
                    archivos_exitosos += 1
                    escribirLog(f"Archivo procesado exitosamente: {resumen['archivo']}",
                                id_ejecucion, "Information", "Procesamiento")
                    # BORRAR ARCHIVO SOLO SI SE PROCESÓ EXITOSAMENTE
                    try:
                        os.remove(archivo)
                        LogManager.escribir_log("INFO", f"Archivo eliminado: {archivo}")
                    except Exception as e:
                        LogManager.escribir_log("WARNING", f"No se pudo eliminar el archivo {archivo}: {str(e)}")
                else:
                    escribirLog(f"Archivo procesado sin nuevos registros: {os.path.basename(archivo)}",
                                id_ejecucion, "Warning", "Procesamiento")

                # Log detallado por empresa
                if resumen:
                    LogManager.escribir_log(
                        "SUCCESS",
                        f"Empresa: {resumen['empresa']} | Archivo: {resumen['archivo']} | Insertados: {resumen['insertados']} | Omitidos: {resumen['omitidos']}"
                    )

                archivos_procesados += 1

            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error procesando archivo {archivo}: {str(e)}")
                escribirLog(f"Error en archivo {os.path.basename(archivo)}: {str(e)}",
                            id_ejecucion, "Error", "Procesamiento")
                archivos_procesados += 1
                continue

        # Marcar como completado
        sql_fin = f"""
            UPDATE {DATABASE_RUNS} 
            SET endDate = SYSDATETIME(), finalizationStatus = 'Completed' 
            WHERE idAutomationRun = {id_ejecucion}
        """
        datosEjecucion(sql_fin)

        # Mensaje final
        mensaje_final = f"Procesamiento completado - {archivos_procesados} archivos procesados, {archivos_exitosos} exitosos"
        LogManager.escribir_log("SUCCESS", mensaje_final)

        # Ejecutar BAT para subir movimientos al portal
        LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
        SubprocesoManager.ejecutar_bat_final()

        LogManager.finalizar_proceso(
            NOMBRE_BANCO, exito=True, descripcion=mensaje_final)
        return True

    except Exception as e:
        error_msg = f"Error en proceso principal: {str(e)}"
        LogManager.escribir_log("ERROR", error_msg)

        if id_ejecucion:
            sql_error = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = SYSDATETIME(), finalizationStatus = 'Failed' 
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_error)
            escribirLog(error_msg, id_ejecucion, "Error", "Error Fatal")

            # Ejecutar BAT para subir movimientos al portal
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
            SubprocesoManager.ejecutar_bat_final()

        LogManager.finalizar_proceso(
            NOMBRE_BANCO, exito=False, descripcion=error_msg)
        return False


if __name__ == "__main__":
    try:
        resultado = main()
        if resultado:
            LogManager.escribir_log(
                "SUCCESS", "=== PROCESAMIENTO COMPLETADO EXITOSAMENTE ===")
        else:
            LogManager.escribir_log("ERROR", "=== PROCESAMIENTO FALLÓ ===")
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error crítico en ejecución: {str(e)}")
    finally:
        LogManager.escribir_log("INFO", "=== FIN DE EJECUCIÓN ===")
