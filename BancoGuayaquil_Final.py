# -*- coding: utf-8 -*-
"""
BANCO GUAYAQUIL - AUTOMATIZACIÓN COMPLETA OPTIMIZADA
"""
import os
import sys
import time
import json
import threading
import re
import email
import email.utils
import imaplib
from datetime import datetime, date, timedelta, timezone
from functools import wraps
from email.header import decode_header

from componentes_comunes import (
    PlaywrightManager,
    ComponenteInteraccion,
    EsperasInteligentes,
    LectorArchivos,
    LogManager,
    BaseDatos,
    SubprocesoManager,
    CorreoManager,
    ConfiguracionManager,
    RUTAS_CONFIG,
    esperarConLoader,
    esperarConLoaderSimple,
)

# ==================== CONTEXTO DE TIMEOUT ====================


class TimeoutManager:
    """Maneja timeouts globales de manera automática"""

    def __init__(self, timeout_seconds=600):
        self.timeout_seconds = timeout_seconds
        self.start_time = None
        self.timer = None
        self.is_timeout = False

    def start(self):
        """Inicia el timer de timeout"""
        self.start_time = datetime.now()
        self.is_timeout = False
        LogManager.escribir_log(
            "INFO", f"Timeout manager iniciado: {self.timeout_seconds//60} minutos")

        # Configurar timer
        self.timer = threading.Timer(
            self.timeout_seconds, self._timeout_callback)
        self.timer.daemon = True
        self.timer.start()

    def _timeout_callback(self):
        """Callback que se ejecuta cuando se alcanza el timeout"""
        self.is_timeout = True
        tiempo_str = formatear_tiempo_ejecucion(
            datetime.now() - self.start_time)
        LogManager.escribir_log(
            "ERROR", f"TIMEOUT GLOBAL ALCANZADO: {tiempo_str}")

        # Forzar salida del programa
        os._exit(1)

    def check(self):
        """Verifica si se ha alcanzado el timeout"""
        if self.is_timeout:
            tiempo_str = formatear_tiempo_ejecucion(
                datetime.now() - self.start_time)
            raise TimeoutError(
                f"Proceso terminado por timeout global ({tiempo_str})")

    def get_elapsed_time(self):
        """Obtiene el tiempo transcurrido"""
        if self.start_time:
            return datetime.now() - self.start_time
        return timedelta(0)

    def stop(self):
        """Detiene el timer"""
        if self.timer:
            self.timer.cancel()
            self.timer = None


# Instancia global del timeout manager
timeout_manager = TimeoutManager(600)  # 10 minutos


def with_timeout_check(func):
    """Decorator que verifica timeout antes de ejecutar funciones críticas"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        timeout_manager.check()
        return func(*args, **kwargs)
    return wrapper


def formatear_tiempo_ejecucion(tiempo_delta):
    """Formatea un timedelta a string legible"""
    total_seconds = int(tiempo_delta.total_seconds())
    minutos = total_seconds // 60
    segundos = total_seconds % 60
    return f"{minutos}m {segundos}s"

# ==================== CONFIGURACIÓN GLOBAL ====================


# DATABASE = "RegistrosBancosPRUEBA"
# DATABASE_LOGS = "AutomationLogPRUEBA"
# DATABASE_RUNS = "AutomationRunPRUEBA"
DATABASE = "RegistrosBancos"
DATABASE_LOGS = "AutomationLog"
DATABASE_RUNS = "AutomationRun"
NOMBRE_BANCO = "Banco Guayaquil"

URLS = {
    'login': "https://bancavirtual.bancoguayaquil.com/loginNR/auth/login",
}

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

# ==================== FUNCIONES DE LOGIN ====================


def realizar_login_completo(page):
    """Realiza el login completo en Banco Guayaquil"""
    try:
        LogManager.escribir_log("INFO", "Iniciando proceso de login")

        # Leer credenciales
        credenciales = LectorArchivos.leerCSV(
            RUTAS_CONFIG['credenciales_banco'],
            filtro_columna=0,
            valor_filtro="Banco Guayaquil"
        )

        if not credenciales:
            raise Exception(
                "No se pudieron leer las credenciales de Banco Guayaquil")

        credenciales = credenciales[0]
        usuario = credenciales[1]
        password = credenciales[2]

        # Navegar a la página
        page.goto(URLS['login'])
        EsperasInteligentes.esperar_carga_pagina(page)

        # Escribir credenciales - ajustar selectores según la página real
        if not ComponenteInteraccion.escribirComponente(
            page,
            "input[placeholder=\"Usuario\"]",
            usuario,
            descripcion="usuario"
        ):
            raise Exception("No se pudo escribir el usuario")

        if not ComponenteInteraccion.escribirComponente(
            page,
            "input[id=\"password\"]",
            password,
            descripcion="password"
        ):
            # Buscar y hacer clic en botón de login
            raise Exception("No se pudo escribir la contraseña")
        if not ComponenteInteraccion.clickComponente(
            page,
            "//button[.//span[contains(text(),'Ingresar')]]",
            descripcion="botón login"
        ):
            raise Exception("No se pudo hacer clic en el botón de login")

       
        # Obtener código del correo usando la función simplificada
        codigo = CorreoManager.obtener_codigo_correo(
            asunto="Código para ingresar a tu Banca Empresas",  # Asunto específico de Guayaquil
        )

        if codigo and re.fullmatch(r"^\d{6}$", codigo):
            LogManager.escribir_log(
                "SUCCESS", f"Código válido recibido: {codigo}")

            # Escribir cada dígito en su campo correspondiente
            for i, digito in enumerate(codigo):
                selector_input = f"//input[@id='cb-otp__input-{i}-securityCode']"

                ComponenteInteraccion.escribirComponente(
                    page,
                    selector_input,
                    digito,
                    descripcion=f"código seguridad dígito {i+1}"
                )

            # Manejo de diálogos opcionales
            ComponenteInteraccion.clickComponente(
                page,
                "//button[.//span[contains(text(), 'Continuar')]]",
                descripcion="diálogo confirmación",
                intentos=2,
                timeout=3000
            )
            # Manejar diálogos posteriores
            esperarConLoaderSimple(2, "Procesando código de seguridad")

        else:
            raise Exception(
                "No se pudo validar código de seguridad después de todos los intentos")

        # Manejar posibles diálogos o ventanas emergentes
        ComponenteInteraccion.clickComponenteOpcional(
            page,
            "//button[.//span[contains(text(), 'Aceptar')]]",
            descripcion="diálogo de confirmación",
            intentos=2,
            timeout=3000
        )
        # Manejar posibles diálogos o ventanas emergentes
        ComponenteInteraccion.clickComponente(
            page,
            "//button[.//span[contains(text(), 'Ir a mi Resumen')]]",
            descripcion="diálogo de confirmación",
            intentos=2,
            timeout=3000
        )

        LogManager.escribir_log("SUCCESS", "Login completado exitosamente")
        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error en login: {str(e)}")
        return False

# ==================== FUNCIONES DE NAVEGACIÓN ====================


def navegar_a_movimientos(page):
    """Navega a la página de movimientos/consulta de cuentas"""
    try:
        LogManager.escribir_log("INFO", "Navegando a página de movimientos...")

        esperarConLoaderSimple(3, "Esperando carga de página principal")

        # Buscar opciones de consulta de cuentas o movimientos
        selector_cuentas = "//a[contains(text(), 'Cuentas')] | //span[contains(text(), 'Cuentas')]"

        navegacion_exitosa = False

        if ComponenteInteraccion.esperarElemento(page, selector_cuentas, timeout=5000, descripcion="menú cuentas"):
            if ComponenteInteraccion.clickComponente(page, selector_cuentas, descripcion="menú cuentas"):

                ComponenteInteraccion.clickComponente(
                    page,
                    "//div[contains(text(),'Consultar movimientos')]",
                    descripcion="Opción consultar movimientos",
                    intentos=2,
                    timeout=2000
                )
                navegacion_exitosa = True

        esperarConLoaderSimple(2, "Esperando carga de página de movimientos")

        if navegacion_exitosa:
            LogManager.escribir_log(
                "SUCCESS", "Navegación a movimientos exitosa")
            return True
        else:
            raise Exception("No se pudo navegar a la página de movimientos")

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error navegando a movimientos: {str(e)}")
        return False

# ==================== FUNCIONES DE CONSULTA ====================


@with_timeout_check
def obtener_y_procesar_movimientos(page, id_ejecucion):
    """Obtiene y procesa los movimientos de todas las empresas disponibles"""
    try:
        LogManager.escribir_log(
            "INFO", "Iniciando obtención de movimientos...")

        # Procesar múltiples empresas
        return procesar_todas_las_empresas(page, id_ejecucion)

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error obteniendo movimientos: {str(e)}")
        return False


def procesar_todas_las_empresas(page, id_ejecucion):
    """Procesa todas las empresas disponibles en el dropdown"""
    try:
        LogManager.escribir_log(
            "INFO", "Iniciando procesamiento de todas las empresas...")

        empresas_procesadas = []
        nombres_empresas_procesadas = []
        max_intentos_globales = 3
        intentos_globales = 0

        while intentos_globales < max_intentos_globales:
            try:
                LogManager.escribir_log(
                    "INFO", f"Intento {intentos_globales + 1}/{max_intentos_globales} para procesar empresas")
                # Abrir el dropdown para obtener todas las opciones

                selector_autocomplete = "//input[contains(@name, 'enterpriseCustomerId')]"
                # esperarConLoader(500, "Esperando carga de selector de empresa")

                if not ComponenteInteraccion.esperarElemento(page, selector_autocomplete, timeout=10000, descripcion="selector empresa"):
                    LogManager.escribir_log(
                        "ERROR", "No se encontró el selector de empresa")
                    return False

                ComponenteInteraccion.clickComponente(
                    page, selector_autocomplete, descripcion="abrir dropdown empresas")
                esperarConLoaderSimple(1, "Esperando carga de opciones")

                # Obtener todas las opciones
                selector_opciones = "//ul[contains(@class, 'p-autocomplete-items')]//li[contains(@class, 'p-autocomplete-item')]"
                opciones = page.locator(selector_opciones).all()

                if not opciones:
                    LogManager.escribir_log(
                        "WARNING", "No se encontraron opciones de empresa")
                    return False

                total_empresas = len(opciones)
                LogManager.escribir_log(
                    "INFO", f"Se encontraron {total_empresas} empresas para procesar")

                # Lista de empresas objetivo en orden de prioridad
                empresas_objetivo = ["MAXXIMUNDO", "AUTOLLANTA"]
                empresas_disponibles = []

                # Crear lista de empresas disponibles con sus elementos
                for opcion in opciones:
                    texto = opcion.locator("span").text_content().strip()
                    empresas_disponibles.append(
                        {"nombre": texto, "elemento": opcion})

                # Procesar empresas por prioridad
                for empresa_objetivo in empresas_objetivo:
                    LogManager.escribir_log(
                        "INFO", f"=== BUSCANDO EMPRESA: {empresa_objetivo} ===")

                    # Si ya fue procesada, saltarla
                    if empresa_objetivo in nombres_empresas_procesadas:
                        LogManager.escribir_log(
                            "INFO", f"Empresa {empresa_objetivo} ya procesada, saltando...")
                        continue

                    empresa_seleccionada = False

                    # Buscar empresa específica
                    for empresa_data in empresas_disponibles:
                        texto = empresa_data["nombre"]
                        elemento = empresa_data["elemento"]

                        if empresa_objetivo.upper() in texto.upper():
                            LogManager.escribir_log(
                                "INFO", f"📍 Encontrada empresa: '{texto}'")
                            ComponenteInteraccion.clickComponente(
                                page, selector_autocomplete, descripcion="abrir dropdown empresas")

                            # Seleccionar empresa
                            elemento.click()
                            LogManager.escribir_log(
                                "SUCCESS", f"✅ Empresa seleccionada: '{texto}'")
                            esperarConLoaderSimple(
                                3, f"Procesando selección de {texto}")

                            # Procesar movimientos para esta empresa
                            if procesar_movimientos_empresa(page, id_ejecucion, texto):
                                nombres_empresas_procesadas.append(
                                    empresa_objetivo)
                                empresas_procesadas.append(
                                    len(empresas_procesadas))
                                LogManager.escribir_log(
                                    "SUCCESS", f"🎉 Empresa {texto} procesada exitosamente")
                            else:
                                LogManager.escribir_log(
                                    "WARNING", f"❌ No se pudieron procesar movimientos para {texto}")

                            empresa_seleccionada = True
                            break

                    if not empresa_seleccionada:
                        LogManager.escribir_log(
                            "WARNING", f"❌ No se encontró la empresa: {empresa_objetivo}")

                # Si procesamos todas las empresas objetivo, salir
                if len(nombres_empresas_procesadas) == len(empresas_objetivo):
                    LogManager.escribir_log(
                        "SUCCESS", f"🎉 Todas las empresas objetivo procesadas: {nombres_empresas_procesadas}")
                    return True

                # Si no procesamos ninguna empresa en este intento, incrementar intentos
                if len(empresas_procesadas) == 0:
                    intentos_globales += 1
                else:
                    # Si procesamos al menos una, considerar éxito
                    LogManager.escribir_log(
                        "SUCCESS", f"✅ Procesamiento parcial completado: {len(nombres_empresas_procesadas)} empresas")
                    return True

            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error general procesando empresas (intento {intentos_globales+1}): {str(e)}")
                intentos_globales += 1
                esperarConLoaderSimple(5, "Esperando antes de reintentar")

        LogManager.escribir_log(
            "INFO", f"Procesamiento completado: {len(empresas_procesadas)} empresas exitosas")
        return len(empresas_procesadas) > 0

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error en procesar_todas_las_empresas: {str(e)}")
        return False


def procesar_archivo_excel(ruta_archivo, id_ejecucion, empresa):
    """Procesa el archivo Excel descargado usando la estructura del Banco Guayaquil"""
    try:
        LogManager.escribir_log(
            "INFO", f"Procesando archivo Excel: {ruta_archivo}")

        # Leer el archivo Excel usando componentes comunes
        contenido = LectorArchivos.leerExcel(ruta_archivo)
        if contenido is None:
            LogManager.escribir_log(
                "ERROR", f"No se pudo leer el archivo: {ruta_archivo}")
            return False

        # Validar que hay suficientes filas
        if len(contenido) < 15:
            LogManager.escribir_log(
                "WARNING", f"El archivo solo tiene {len(contenido)} filas, se esperaban al menos 15")
            return False

        # Extraer número de cuenta
        cuenta_raw = ""
        if len(contenido) > 6 and len(contenido[6]) > 0:
            cuenta_raw = str(contenido[6][0])
        cuenta = cuenta_raw.split(":")[1].strip(
        ) if ":" in cuenta_raw else cuenta_raw.strip()

        LogManager.escribir_log("INFO", f"Cuenta procesada: '{cuenta}'")

        if not cuenta:
            LogManager.escribir_log(
                "WARNING", "No se pudo extraer número de cuenta")
            cuenta = "SIN_CUENTA"

        # NUEVO: Obtener rango de fechas del archivo para la consulta previa
        LogManager.escribir_log(
            "INFO", "🔍 Analizando rango de fechas en el archivo...")
        fechas_archivo = []

        for i in range(14, len(contenido)):
            fila = contenido[i]
            if fila and len(fila) > 1 and fila[1]:
                fecha_str = str(fila[1])
                if fecha_str not in fechas_archivo:
                    fechas_archivo.append(fecha_str)

        if not fechas_archivo:
            LogManager.escribir_log(
                "WARNING", "No se encontraron fechas válidas en el archivo")
            return False

        # Determinar rango de fechas (del más antiguo al más reciente)
        fecha_min = min(fechas_archivo)
        fecha_max = max(fechas_archivo)
        LogManager.escribir_log(
            "INFO", f"📅 Rango de fechas en archivo: {fecha_min} a {fecha_max}")

        # PASO 1: Consultar registros existentes en la BD para este rango de fechas
        LogManager.escribir_log(
            "INFO", "🔎 Consultando registros existentes en la base de datos...")

        sql_existentes = f"""
            SELECT 
                numDocumento, 
                fechaTransaccion, 
                valor, 
                tipo
            FROM {DATABASE} 
            WHERE numCuenta = '{cuenta}' 
            AND banco = 'Banco Guayaquil' 
            AND empresa = '{empresa}' 
            AND fechaTransaccion BETWEEN '{fecha_min}' AND '{fecha_max}'
        """

        registros_existentes = BaseDatos.consultarBD(sql_existentes)

        # CAMBIO CLAVE: Crear set de combinaciones únicas YA EXISTENTES (sin considerar sufijos)
        combinaciones_existentes = set()
        documentos_existentes_en_bd = set()

        if registros_existentes:
            for registro in registros_existentes:
                doc_completo = registro[0]  # numDocumento (puede tener sufijo)
                fecha = registro[1]
                valor = registro[2]
                tipo = registro[3]

                # Extraer documento original (sin sufijo) usando Python
                if " - " in doc_completo:
                    doc_original = doc_completo.split(" - ")[0]
                else:
                    doc_original = doc_completo

                # Crear clave con documento original
                key_original = f"{doc_original}|{fecha}|{valor}|{tipo}"
                combinaciones_existentes.add(key_original)

                # Mantener documento completo para manejo de sufijos
                documentos_existentes_en_bd.add(doc_completo)

                # DEBUG para los primeros registros
                if len(combinaciones_existentes) <= 5:
                    LogManager.escribir_log(
                        "DEBUG", f"Registro BD: Doc='{doc_completo}' → Original='{doc_original}' → Key='{key_original}'")

        LogManager.escribir_log(
            "INFO", f"📋 Se encontraron {len(combinaciones_existentes)} combinaciones únicas existentes")
        LogManager.escribir_log(
            "INFO", f"📋 Se encontraron {len(documentos_existentes_en_bd)} documentos totales con sufijos")

        # PASO 2: Procesar el contenido del archivo Excel
        movimientos_insertados = 0
        movimientos_omitidos = 0
        filas_procesadas = 0
        # Para evitar duplicados en el mismo archivo
        documentos_procesados_en_memoria = set()
        # NUEVO: Para evitar duplicados en el mismo archivo
        combinaciones_procesadas_memoria = set()

        # La tabla comienza en la fila 15 (índice 14) según la estructura original
        for i in range(14, len(contenido)):
            fila = contenido[i]

            # Validaciones básicas
            if not fila or len(fila) < 2 or not fila[1]:
                continue

            try:
                filas_procesadas += 1

                # Extraer datos de cada columna
                fecha = fila[1] if len(fila) > 1 else ""  # Columna B
                tipo_raw = fila[3] if len(fila) > 3 else ""  # Columna D
                numero_documento_base = str(fila[4]) if len(
                    fila) > 4 else ""  # Columna E
                concepto_transaccion = str(fila[5]) if len(
                    fila) > 5 else ""  # Columna F
                oficina = str(fila[6]) if len(fila) > 6 else ""  # Columna G
                valor_raw = fila[7] if len(fila) > 7 else "0"  # Columna H
                saldo_raw = fila[9] if len(fila) > 9 else "0"  # Columna J
                referencia = str(fila[10]) if len(
                    fila) > 10 else ""  # Columna K

                # Procesar tipo (crédito/débito)
                tipo = "D" if "débito" in str(tipo_raw).lower() else "C"

                # Procesar valores monetarios
                valor = str(valor_raw).replace("'", "").replace(
                    "$", "").replace(",", "").strip()
                saldo_contable = str(saldo_raw).replace(
                    "'", "").replace("$", "").replace(",", "").strip()

                # Validar que los valores sean numéricos
                try:
                    valor_float = float(
                        valor) if valor and valor != "" else 0.0
                    saldo_float = float(
                        saldo_contable) if saldo_contable and saldo_contable != "" else 0.0
                except ValueError as ve:
                    LogManager.escribir_log(
                        "WARNING", f"Error convirtiendo valores en fila {i}: valor='{valor}', saldo='{saldo_contable}' - {str(ve)}")
                    valor_float = 0.0
                    saldo_float = 0.0

                # Validar datos mínimos requeridos
                if not fecha or not numero_documento_base:
                    LogManager.escribir_log(
                        "WARNING", f"Fila {i}: Datos insuficientes - fecha: '{fecha}', documento: '{numero_documento_base}'")
                    continue

                # NUEVA VALIDACIÓN CORRECTA: Verificar si la COMBINACIÓN ÚNICA ya existe
                key_combinacion_original = f"{numero_documento_base}|{fecha}|{valor_float}|{tipo}"

                # PRIMERA VERIFICACIÓN: ¿Esta combinación exacta ya existe en BD?
                if key_combinacion_original in combinaciones_existentes:
                    movimientos_omitidos += 1
                    if movimientos_omitidos <= 10:
                        LogManager.escribir_log(
                            "INFO", f"⏭️ Omitiendo registro EXISTENTE: Doc={numero_documento_base}, Fecha={fecha}, Valor=${valor_float}")
                    continue

                # SEGUNDA VERIFICACIÓN: ¿Ya procesé esta combinación en este archivo?
                if key_combinacion_original in combinaciones_procesadas_memoria:
                    movimientos_omitidos += 1
                    if movimientos_omitidos <= 5:
                        LogManager.escribir_log(
                            "INFO", f"⏭️ Omitiendo registro DUPLICADO en archivo: Doc={numero_documento_base}, Fecha={fecha}, Valor=${valor_float}")
                    continue

                # Si llegamos aquí, es un registro NUEVO que debe insertarse

                # LÓGICA DE SUFIJOS: Similar a Banco Pichincha
                def existe_num_documento_bd(doc_numero):
                    """Verifica si un número de documento existe en BD"""
                    return doc_numero in documentos_existentes_en_bd

                def existe_en_memoria(doc_numero):
                    """Verifica si el documento ya está en memoria"""
                    return doc_numero in documentos_procesados_en_memoria

                # Determinar número de documento final con sufijo si es necesario
                sufijo = 0
                numero_documento_final = numero_documento_base

                # SOLO aplicar sufijos si el NÚMERO DE DOCUMENTO (independientemente de fecha/valor) ya existe
                while (existe_num_documento_bd(numero_documento_final) or
                       existe_en_memoria(numero_documento_final)):
                    sufijo += 1
                    numero_documento_final = f"{numero_documento_base} - {sufijo}"

                # Registrar en memoria para evitar duplicados en el mismo archivo
                documentos_procesados_en_memoria.add(numero_documento_final)
                combinaciones_procesadas_memoria.add(key_combinacion_original)

                # Log de sufijo aplicado
                if sufijo > 0:
                    LogManager.escribir_log(
                        "INFO", f"📝 Sufijo aplicado: '{numero_documento_base}' → '{numero_documento_final}' (nuevo registro con documento existente)")

                # Obtener contador de fecha
                sql_contador = f"""
                    SELECT COALESCE(MAX(contFecha), 0) + 1 AS maxCont 
                    FROM {DATABASE} 
                    WHERE numCuenta = '{cuenta}' 
                    AND banco = 'Banco Guayaquil' 
                    AND empresa = '{empresa}' 
                    AND fechaTransaccion = '{fecha}'
                """

                resultado_contador = BaseDatos.consultarBD(sql_contador)
                contFecha = resultado_contador[0][0] if resultado_contador and resultado_contador[0] else 1

                # Limpiar valores para SQL
                concepto_limpio = concepto_transaccion.replace("'", "''")
                referencia_limpia = referencia.replace("'", "''")
                oficina_limpia = oficina.replace("'", "''")
                numero_documento_limpio = numero_documento_final.replace(
                    "'", "''")

                # Preparar SQL de inserción
                sql_insercion = f"""
                    INSERT INTO {DATABASE} (
                        numCuenta, banco, empresa, numDocumento, idEjecucion, 
                        fechaTransaccion, tipo, valor, saldoContable, referencia, 
                        contFecha, conceptoTransaccion, oficina
                    ) VALUES (
                        '{cuenta}', 
                        'Banco Guayaquil', 
                        '{empresa}', 
                        '{numero_documento_limpio}', 
                        {id_ejecucion}, 
                        '{fecha}', 
                        '{tipo}', 
                        {valor_float}, 
                        {saldo_float}, 
                        '{referencia_limpia}', 
                        {contFecha}, 
                        '{concepto_limpio}', 
                        '{oficina_limpia}'
                    )
                """

                # Insertar en BD
                if BaseDatos.ejecutarSQL(sql_insercion):
                    movimientos_insertados += 1

                    # IMPORTANTE: Actualizar estructuras en memoria
                    documentos_existentes_en_bd.add(numero_documento_final)
                    combinaciones_existentes.add(key_combinacion_original)

                else:
                    LogManager.escribir_log(
                        "ERROR", f"❌ Falla insertando fila {i}")

            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error procesando fila {i}: {str(e)}")
                continue

        # Resumen final detallado
        LogManager.escribir_log("INFO", f"=== RESUMEN PROCESAMIENTO ===")
        LogManager.escribir_log("INFO", f"🏢 Empresa: {empresa}")
        LogManager.escribir_log("INFO", f"💳 Cuenta: {cuenta}")
        LogManager.escribir_log(
            "INFO", f"📊 Total filas procesadas: {filas_procesadas}")
        LogManager.escribir_log(
            "INFO", f"✅ Registros nuevos insertados: {movimientos_insertados}")
        LogManager.escribir_log(
            "INFO", f"⏭️ Registros omitidos (existentes/duplicados): {movimientos_omitidos}")
        LogManager.escribir_log(
            "INFO", f"📅 Rango de fechas: {fecha_min} a {fecha_max}")
        LogManager.escribir_log(
            "INFO", f"📝 Documentos únicos procesados: {len(documentos_procesados_en_memoria)}")
        LogManager.escribir_log(
            "INFO", f"🔑 Combinaciones únicas procesadas: {len(combinaciones_procesadas_memoria)}")

        # CAMBIO PRINCIPAL: Considerar éxito tanto si hay nuevos como si no hay
        if movimientos_insertados > 0:
            LogManager.escribir_log(
                "SUCCESS", f"✅ Procesamiento exitoso: {movimientos_insertados} nuevos movimientos para {empresa}")
        else:
            LogManager.escribir_log(
                "SUCCESS", f"✅ Procesamiento exitoso: No se encontraron registros nuevos para {empresa} (todos ya existen)")

        # Eliminar archivo después de procesarlo
        try:
            os.remove(ruta_archivo)
            LogManager.escribir_log(
                "INFO", f"Archivo eliminado: {ruta_archivo}")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"No se pudo eliminar archivo: {str(e)}")

        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error procesando Excel: {str(e)}")
        return False


def obtener_contador_fecha(cuenta, empresa, fecha):
    """Obtiene el siguiente contador de fecha para evitar duplicados"""
    try:
        sql = f"""
            SELECT COALESCE(MAX(contFecha), 0) + 1 AS maxCont 
            FROM {DATABASE} 
            WHERE numCuenta = '{cuenta}' 
            AND banco = 'Banco Guayaquil' 
            AND empresa = '{empresa}' 
            AND fechaTransaccion = '{fecha}'
        """
        resultado = BaseDatos.consultarBD(sql)
        return resultado[0][0] if resultado and resultado[0] else 1
    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Error obteniendo contador fecha: {str(e)}")
        return 1


def procesar_movimientos_empresa(page, id_ejecucion, nombre_empresa):
    """Procesa los movimientos de una empresa específica"""
    try:
        LogManager.escribir_log(
            "INFO", f"Procesando movimientos para empresa: {nombre_empresa}")

        # Paso 1: Configurar fechas (último mes)
        LogManager.escribir_log("INFO", "Configurando fechas...")

        # Clic en campo de fecha
        ComponenteInteraccion.clickComponente(
            page,
            "//input[@readonly and contains(@class, 'cb-input__input')]",
            descripcion="campo fecha",
            intentos=2,
            timeout=5000
        )

        esperarConLoaderSimple(1, "Esperando selector de fechas")

        # Seleccionar "Último mes"
        ComponenteInteraccion.clickComponente(
            page,
            "//button[.//span[contains(text(), 'Último mes')]]",
            descripcion="opción último mes",
            intentos=2,
            timeout=5000
        )

        # Aplicar fechas
        ComponenteInteraccion.clickComponente(
            page,
            "//button[.//span[contains(text(), 'Aplicar')]]",
            descripcion="aplicar fechas",
            intentos=2,
            timeout=5000
        )

        esperarConLoaderSimple(2, "Esperando carga de movimientos")

        # Paso 2: Exportar datos
        LogManager.escribir_log("INFO", "Iniciando exportación...")

        ComponenteInteraccion.clickComponente(
            page,
            "//button[.//span[contains(text(), 'Exportar')]]",
            descripcion="botón exportar",
            intentos=2,
            timeout=5000
        )

        esperarConLoaderSimple(1, "Esperando modal de descarga")

        # Paso 3: Descargar archivo
        LogManager.escribir_log("INFO", "Descargando archivo...")

        ruta_archivo = ComponenteInteraccion.esperarDescarga(
            page,
            "//button[.//span[contains(text(), 'Descargar')]]",
            timeout=30000,
            descripcion="botón descargar movimientos"
        )

        if not ruta_archivo:
            LogManager.escribir_log(
                "ERROR", f"No se pudo descargar archivo para {nombre_empresa}")
            return False

        # Paso 4: Procesar archivo descargado
        if procesar_archivo_excel(ruta_archivo, id_ejecucion, nombre_empresa):
            LogManager.escribir_log(
                "SUCCESS", f"Movimientos de {nombre_empresa} procesados exitosamente")
            return True
        else:
            LogManager.escribir_log(
                "ERROR", f"Error procesando archivo de {nombre_empresa}")
            return False

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando movimientos de {nombre_empresa}: {str(e)}")
        return False

# ==================== FUNCIONES AUXILIARES ====================


def convertir_fecha_sql(fecha_str):
    """Convierte string de fecha a formato SQL Server"""
    try:
        if not fecha_str:
            return None

        # Intentar diferentes formatos de fecha
        formatos = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y']

        for formato in formatos:
            try:
                fecha_obj = datetime.strptime(fecha_str, formato)
                return fecha_obj.strftime('%Y-%m-%d')
            except ValueError:
                continue

        LogManager.escribir_log(
            "WARNING", f"No se pudo convertir fecha: {fecha_str}")
        return None

    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Error convirtiendo fecha {fecha_str}: {str(e)}")
        return None


def limpiar_valor_monetario(valor_str):
    """Limpia y convierte valores monetarios a float"""
    try:
        if not valor_str:
            return 0.0

        # Limpiar caracteres no numéricos excepto punto y coma
        valor_limpio = str(valor_str).replace(
            '$', '').replace(',', '').replace(' ', '').strip()

        # Manejar valores negativos entre paréntesis
        if valor_limpio.startswith('(') and valor_limpio.endswith(')'):
            valor_limpio = '-' + valor_limpio[1:-1]

        return float(valor_limpio) if valor_limpio and valor_limpio != '-' else 0.0

    except (ValueError, TypeError):
        return 0.0


def esperar_carga_completa_pagina(page):
    """Espera que la página cargue completamente"""
    try:
        EsperasInteligentes.esperar_carga_pagina(page)
        esperarConLoaderSimple(2, "Esperando carga completa")
        return True
    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Timeout esperando carga: {str(e)}")
        return False

# ==================== FUNCIÓN PRINCIPAL ====================


@with_timeout_check
def main():
    """Función principal de automatización Banco Guayaquil"""
    playwright = None
    browser = None
    page = None
    id_ejecucion = None

    try:
        # Obtener ID de ejecución
        id_ejecucion = obtenerIDEjecucion()
        
        LogManager.iniciar_proceso(NOMBRE_BANCO, id_ejecucion, f"Automatización Banco Guayaquil - ID: {id_ejecucion}")
        # Iniciar timeout manager
        timeout_manager.start()

        # Registrar inicio de ejecución
        sql_inicio = f"""
            INSERT INTO {DATABASE_RUNS} (idAutomationRun, processName, startDate, finalizationStatus) VALUES ({id_ejecucion}, 'Descarga comprobantes-Banco Guayaquil', SYSDATETIME(), 'Running')
        """
        datosEjecucion(sql_inicio)
        escribirLog("Proceso iniciado", id_ejecucion, "Information", "Inicio")

        # Inicializar Playwright
        LogManager.escribir_log("INFO", "Inicializando navegador...")
        manager = PlaywrightManager(
            headless=False, download_path=RUTAS_CONFIG['descargas'])
        playwright, browser, context, page = manager.iniciar_navegador()

        # Realizar login
        if not realizar_login_completo(page):
            raise Exception("Login falló")
        escribirLog("Login exitoso", id_ejecucion, "Success", "Login")

        # Navegar a movimientos
        if not navegar_a_movimientos(page):
            raise Exception("Navegación a movimientos falló")
        escribirLog("Navegación exitosa", id_ejecucion,
                    "Success", "Navegación")

        # Obtener y procesar movimientos
        if not obtener_y_procesar_movimientos(page, id_ejecucion):
            raise Exception("Procesamiento de movimientos falló")
        escribirLog("Movimientos procesados exitosamente",
                    id_ejecucion, "Success", "Procesamiento")

        # Registrar éxito
        sql_fin = f"""
            UPDATE {DATABASE_RUNS} 
            SET endDate = GETDATE(), finalizationStatus = 'Completado'
            WHERE idAutomationRun = {id_ejecucion}
        """
        datosEjecucion(sql_fin)
        escribirLog("Proceso completado exitosamente",
                    id_ejecucion, "Success", "Fin")

        # Ejecutar BAT para subir moviemientos al portal
        LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
        SubprocesoManager.ejecutar_bat_final()

        LogManager.finalizar_proceso(
            "GUAYAQUIL", True, "Automatización completada exitosamente")
        return True

    except Exception as e:
        error_msg = f"Error en proceso principal: {str(e)}"
        LogManager.escribir_log("ERROR", error_msg)

        if id_ejecucion:
            sql_error = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = GETDATE(), finalizationStatus = 'Error'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_error)
            escribirLog(error_msg, id_ejecucion, "Error", "Error General")

            # Ejecutar BAT para subir moviemientos al portal
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
            SubprocesoManager.ejecutar_bat_final()

        LogManager.finalizar_proceso("GUAYAQUIL", False, error_msg)
        return False

    finally:
        # Limpiar recursos
        try:
            timeout_manager.stop()
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"Error cerrando recursos: {str(e)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        LogManager.escribir_log("WARNING", "Proceso interrumpido por usuario")
    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error no controlado: {str(e)}")
    finally:
        LogManager.escribir_log("INFO", "Finalizando aplicación")
