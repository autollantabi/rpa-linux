# -*- coding: utf-8 -*-
"""
BANCO BOLIVARIANO - PROCESAMIENTO DE ARCHIVOS TXT OPTIMIZADO
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
NOMBRE_BANCO = "Banco Bolivariano"

# ==================== FUNCIONES DE BASE DE DATOS ====================


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
        VALUES ({id_ejecucion}, '{texto_limpio}', SYSDATETIME(), '{estado}', '{accion}')
    """
    datosEjecucion(sql)


def contadorFecha(cuenta, empresa, fecha):
    """Obtiene el siguiente contador de fecha para evitar duplicados"""
    try:
        sql = f"""
            SELECT COALESCE(MAX(contFecha), 0) + 1 AS maxCont 
            FROM {DATABASE} 
            WHERE numCuenta = '{cuenta}' 
            AND banco = '{NOMBRE_BANCO}' 
            AND empresa = '{empresa}' 
            AND fechaTransaccion = '{fecha}'
        """
        resultado = BaseDatos.consultarBD(sql)
        if resultado and resultado[0]:
            return int(resultado[0][0])
        return 1
    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Error obteniendo contador fecha: {str(e)}")
        return 1

# ==================== FUNCIONES DE PROCESAMIENTO ====================


def obtenerArchivos():
    """Obtiene la lista de archivos TXT para procesar, ordenados por fecha"""
    try:

        # Ruta por defecto si no está configurada
        ruta_archivos = RUTAS_CONFIG['bolivariano']

        if not os.path.exists(ruta_archivos):
            LogManager.escribir_log(
                "ERROR", f"La ruta no existe: {ruta_archivos}")
            return []

        # Obtener archivos TXT
        archivos_txt = []
        for archivo in os.listdir(ruta_archivos):
            if archivo.lower().endswith('.txt'):
                ruta_completa = os.path.join(ruta_archivos, archivo)
                archivos_txt.append(ruta_completa)

        # Ordenar por fecha de modificación (más reciente primero)
        archivos_ordenados = sorted(
            archivos_txt,
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


def leerArchivoTXT(ruta_archivo):
    """Lee un archivo TXT y lo convierte en lista de listas"""
    try:
        LogManager.escribir_log(
            "INFO", f"Leyendo archivo: {os.path.basename(ruta_archivo)}")

        with open(ruta_archivo, 'r', encoding='utf-8') as file:
            data = []
            for line_num, line in enumerate(file, 1):
                line = line.strip()
                if line:
                    # Dividir por tabulaciones
                    row = [col.replace("'", "").strip()
                           for col in line.split('\t')]
                    data.append(row)

            LogManager.escribir_log(
                "INFO", f"Archivo leído: {len(data)} líneas procesadas")
            return data

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error leyendo archivo {ruta_archivo}: {str(e)}")
        return None


def procesar_archivo(ruta_archivo, id_ejecucion):
    """Procesa un archivo TXT de Banco Bolivariano"""
    try:
        LogManager.escribir_log(
            "INFO", f"Procesando archivo: {os.path.basename(ruta_archivo)}")

        # Leer contenido del archivo
        contenido = leerArchivoTXT(ruta_archivo)
        if not contenido:
            LogManager.escribir_log(
                "ERROR", "No se pudo leer el contenido del archivo")
            return False

        if len(contenido) < 7:
            LogManager.escribir_log(
                "WARNING", "Archivo no tiene suficientes líneas de datos")
            return False

        # Extraer información del encabezado según estructura original
        try:
            # Línea 2 (índice 1) = Número de cuenta
            cuenta = contenido[1][1] if len(contenido) > 1 and len(
                contenido[1]) > 1 else "CUENTA_NO_ENCONTRADA"

            # Línea 5 (índice 4) = Empresa (remover asteriscos)
            empresa_raw = contenido[4][1] if len(contenido) > 4 and len(
                contenido[4]) > 1 else "EMPRESA_NO_ENCONTRADA"
            empresa = empresa_raw.replace('*', '').strip()

            LogManager.escribir_log(
                "INFO", f"Datos del archivo - Cuenta: {cuenta}, Empresa: {empresa}")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"Error extrayendo datos del encabezado: {str(e)}")
            cuenta = "CUENTA_NO_ENCONTRADA"
            empresa = "EMPRESA_NO_ENCONTRADA"

        movimientos_procesados = 0
        movimientos_insertados = 0
        movimientos_omitidos = 0

        # Procesar movimientos (empiezan en línea 7, índice 6)
        for i in range(7, len(contenido)):
            try:
                fila = contenido[i]

                # Verificar que la fila tenga suficientes columnas
                if len(fila) < 10:
                    LogManager.escribir_log(
                        "DEBUG", f"Línea {i+1}: Insuficientes columnas ({len(fila)})")
                    continue

                # Extraer datos según estructura original:
                # [0] = ?, [1] = Fecha, [2] = ?, [3] = Oficina, [4] = Referencia,
                # [5] = NumDocumento, [6] = Signo (+/-), [7] = Valor, [8] = Disponible, [9] = Saldo

                fecha_str = fila[1].replace(
                    "'", "").strip() if len(fila) > 1 else ""
                oficina = fila[3].replace(
                    "'", "").strip() if len(fila) > 3 else ""
                referencia = fila[4].replace(
                    "'", "").strip() if len(fila) > 4 else ""
                num_documento = fila[5].replace(
                    "'", "").strip() if len(fila) > 5 else ""
                signo = fila[6].replace(
                    "'", "").strip() if len(fila) > 6 else ""
                valor_str = fila[7].replace("'", "").replace(
                    ",", "").strip() if len(fila) > 7 else "0"
                disponible_str = fila[8].replace("'", "").replace(
                    ",", "").strip() if len(fila) > 8 else "0"
                saldo_str = fila[9].replace("'", "").replace(
                    ",", "").strip() if len(fila) > 9 else "0"

                # Validar datos obligatorios
                if not fecha_str or not valor_str:
                    LogManager.escribir_log(
                        "DEBUG", f"Línea {i+1}: Datos obligatorios faltantes")
                    continue

                # Procesar fecha: MM/DD/YYYY -> YYYY-MM-DD
                try:
                    split_fecha = fecha_str.split("/")
                    if len(split_fecha) == 3:
                        # Formato MM/DD/YYYY
                        fecha_sql = f"{split_fecha[2]}-{split_fecha[0].zfill(2)}-{split_fecha[1].zfill(2)}"
                    else:
                        LogManager.escribir_log(
                            "WARNING", f"Formato de fecha no válido: {fecha_str}")
                        continue
                except Exception as e:
                    LogManager.escribir_log(
                        "WARNING", f"Error procesando fecha {fecha_str}: {str(e)}")
                    continue

                # Determinar tipo de transacción
                tipo_trx = "C" if signo == "+" else "D"

                # Limpiar valores monetarios (remover $ y comas)
                def limpiar_valor(valor):
                    if not valor:
                        return 0.0
                    try:
                        valor_limpio = str(valor).replace(
                            '$', '').replace(',', '').strip()
                        return float(valor_limpio) if valor_limpio else 0.0
                    except:
                        return 0.0

                valor = limpiar_valor(valor_str)
                disponible = limpiar_valor(disponible_str)
                saldo = limpiar_valor(saldo_str)

                # Obtener contador de fecha para evitar duplicados
                cont_fecha = contadorFecha(cuenta, empresa, fecha_sql)

                # Verificar duplicados
                sql_check = f"""
                    SELECT COUNT(*) FROM {DATABASE}
                    WHERE numCuenta = '{cuenta}'
                    AND banco = '{NOMBRE_BANCO}'
                    AND empresa = '{empresa}'
                    AND numDocumento = '{num_documento}'
                    AND fechaTransaccion = '{fecha_sql}'
                    AND valor = {valor}
                """

                resultado_check = BaseDatos.consultarBD(sql_check)
                if resultado_check and resultado_check[0][0] > 0:
                    movimientos_omitidos += 1
                    continue

                # Limpiar strings para SQL
                empresa_limpia = empresa.replace("'", "''")
                oficina_limpia = str(oficina).replace("'", "''")
                referencia_limpia = str(referencia).replace("'", "''")

                # Insertar en base de datos
                columnas = """
                    numCuenta, banco, empresa, numDocumento, idEjecucion,
                    fechaTransaccion, tipo, valor, saldoContable, disponible,
                    oficina, referencia, contFecha
                """

                valores = f"""
                    '{cuenta}', '{NOMBRE_BANCO}', '{empresa_limpia}', '{num_documento}', {id_ejecucion},
                    '{fecha_sql}', '{tipo_trx}', {valor}, {saldo}, {disponible},
                    '{oficina_limpia}', '{referencia_limpia}', {cont_fecha}
                """

                sql_insert = f"INSERT INTO {DATABASE} ({columnas}) VALUES ({valores})"

                if BaseDatos.ejecutarSQL(sql_insert):
                    movimientos_insertados += 1
                else:
                    movimientos_omitidos += 1

                movimientos_procesados += 1

            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error procesando línea {i+1}: {str(e)}")
                movimientos_omitidos += 1
                continue

        # Resumen del procesamiento
        LogManager.escribir_log("INFO", f"=== RESUMEN ARCHIVO ===")
        LogManager.escribir_log(
            "INFO", f"📄 Archivo: {os.path.basename(ruta_archivo)}")
        LogManager.escribir_log("INFO", f"🏢 Empresa: {empresa}")
        LogManager.escribir_log("INFO", f"💳 Cuenta: {cuenta}")
        LogManager.escribir_log(
            "INFO", f"📊 Movimientos procesados: {movimientos_procesados}")
        LogManager.escribir_log(
            "INFO", f"✅ Registros insertados: {movimientos_insertados}")
        LogManager.escribir_log(
            "INFO", f"⏭️ Registros omitidos: {movimientos_omitidos}")

        # Eliminar archivo después de procesarlo
        try:
            os.remove(ruta_archivo)
            LogManager.escribir_log(
                "INFO", f"Archivo eliminado: {os.path.basename(ruta_archivo)}")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"No se pudo eliminar el archivo: {str(e)}")

        return movimientos_insertados > 0

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando archivo {ruta_archivo}: {str(e)}")
        return False

# ==================== FUNCIÓN PRINCIPAL ====================


def main():
    """Función principal que procesa todos los archivos de Banco Bolivariano"""
    id_ejecucion = None

    try:
        # Obtener ID de ejecución
        id_ejecucion = obtenerIDEjecucion()

        LogManager.iniciar_proceso(NOMBRE_BANCO, id_ejecucion, f"Procesamiento archivos TXT Bolivariano - ID: {id_ejecucion}")

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

                if procesar_archivo(archivo, id_ejecucion):
                    archivos_exitosos += 1
                    escribirLog(f"Archivo procesado exitosamente: {os.path.basename(archivo)}",
                                id_ejecucion, "Information", "Procesamiento")
                else:
                    escribirLog(f"Archivo procesado sin nuevos registros: {os.path.basename(archivo)}",
                                id_ejecucion, "Warning", "Procesamiento")

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
        escribirLog(mensaje_final, id_ejecucion, "Information", "Fin")

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
