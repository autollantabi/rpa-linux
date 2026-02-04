# -*- coding: utf-8 -*-
"""
BANCO PRODUBANCO - AUTOMATIZACIÓN COMPLETA OPTIMIZADA
"""
import os
import sys
import time
import json
import threading
import re
import subprocess
import csv
from datetime import datetime, date, timedelta, timezone
from functools import wraps

from componentes_comunes import (
    PlaywrightManager,
    ComponenteInteraccion,
    EsperasInteligentes,
    LectorArchivos,
    LogManager,
    BaseDatos,
    CorreoManager,
    ConfiguracionManager,
    SubprocesoManager,
    esperarConLoader,
    esperarConLoaderSimple,
    RUTAS_CONFIG
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
NOMBRE_BANCO = "Banco Produbanco"

URLS = {
    'login': "https://cashmanagement.produbanco.com/cashmanagement/index.html"
}

# Configuración específica de Produbanco
CONFIG_PRODUBANCO = {
    'banco_codigo': "Produbanco",
    'dias_consulta_default': 1
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

# ==================== FUNCIONES DE NAVEGACIÓN ====================


@with_timeout_check
def navegar_a_login(page):
    """Navega a la página de login de Produbanco"""
    try:
        LogManager.escribir_log("INFO", f"Navegando a: {URLS['login']}")
        page.goto(URLS['login'])
        page.wait_for_load_state("networkidle")
        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error navegando a login: {str(e)}")
        return False


@with_timeout_check
def navegar_a_movimientos(page):
    """Navega a la sección de movimientos de cuenta en Produbanco"""
    try:
        LogManager.escribir_log("INFO", "Navegando a movimientos de cuenta...")

        # Esperar carga completa de la página
        EsperasInteligentes.esperar_carga_pagina(page)
        esperarConLoaderSimple(3, "Esperando carga de página principal")

        # PASO 1: Buscar y hacer clic en Cash Management
        selector_cash_management = "//span[contains(@class, 'ng-binding') and text()='Cash Management']"

        if ComponenteInteraccion.esperarElemento(page, selector_cash_management, timeout=10000, descripcion="menú Cash Management"):
            try:
                LogManager.escribir_log(
                    "INFO", "Haciendo clic en Cash Management...")
                ComponenteInteraccion.clickComponente(
                    page,
                    selector_cash_management,
                    descripcion="expandir Cash Management"
                )
            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error haciendo clic en Cash Management: {str(e)}")
        else:
            raise Exception("No se encontró el menú 'Cash Management'")

        # PASO 2: Buscar y hacer clic en Resumen
        selector_resumen = "//span[contains(text(), 'Resumen')]//ancestor::a[contains(@class, 'nav-li-a-modulos')]"

        resumen_encontrado = False
        try:
            if ComponenteInteraccion.esperarElemento(page, selector_resumen, timeout=5000, descripcion=f"módulo Resumen ({selector_resumen})"):

                ComponenteInteraccion.clickComponente(
                    page,
                    selector_resumen,
                    descripcion="expandir módulo Resumen"
                )
                resumen_encontrado = True
        except Exception as e:
            LogManager.escribir_log(
                "DEBUG", f"Selector Resumen falló: {selector_resumen} - {str(e)}")

        if not resumen_encontrado:
            raise Exception("No se encontró el módulo 'Resumen'")

        # PASO 3: Hacer clic en "Movimientos de Cuenta"

        selector_movimientos = "//a[@data-ng-href='#/trans/CM/Consolidado/ESTADOCUENTA']"

        try:
            if ComponenteInteraccion.esperarElemento(page, selector_movimientos, timeout=5000, descripcion="enlace Movimientos de Cuenta"):
                if ComponenteInteraccion.clickComponente(page, selector_movimientos, descripcion="Movimientos de Cuenta"):
                    LogManager.escribir_log(
                        "SUCCESS", f"Clic exitoso en Movimientos de Cuenta con selector: {selector_movimientos}")

        except Exception as e:
            LogManager.escribir_log(
                "DEBUG", f"Selector {selector_movimientos} falló: {str(e)}")

            raise Exception("No se pudo hacer clic en 'Movimientos de Cuenta'")

        # Verificar que se cargó correctamente
        page.wait_for_load_state("networkidle", timeout=15000)

        LogManager.escribir_log(
            "SUCCESS", "Navegación a movimientos completada exitosamente")
        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error navegando a movimientos: {str(e)}")

        # Debug: screenshot de error
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"{RUTAS_CONFIG['descargas']}/error_navegacion_produbanco_{timestamp}.png"
            page.screenshot(path=screenshot_path)
            LogManager.escribir_log(
                "INFO", f"Screenshot de error guardado: {screenshot_path}")
        except:
            pass

        return False


@with_timeout_check
def iniciar_sesion(page):
    """Inicia sesión en la plataforma de Produbanco"""
    try:

        # Leer credenciales del banco
        credenciales_banco = LectorArchivos.leerCSV(
            RUTAS_CONFIG['credenciales_banco'],
            filtro_columna=0,
            valor_filtro=CONFIG_PRODUBANCO['banco_codigo']
        )

        if not credenciales_banco:
            LogManager.escribir_log(
                "ERROR", f"No se encontraron credenciales para {CONFIG_PRODUBANCO['banco_codigo']}")
            return False

        usuario = credenciales_banco[0][1]
        password = credenciales_banco[0][2]
        LogManager.escribir_log(
            "INFO", f"Credenciales cargadas para usuario: {usuario}")

        max_intentos = 5
        intento = 0

        while intento < max_intentos:
            intento += 1
            LogManager.escribir_log(
                "INFO", f"Intento de login {intento}/{max_intentos}")

            # Escribir credenciales
            ComponenteInteraccion.escribirComponente(
                page, "#username", usuario, descripcion="usuario")
            ComponenteInteraccion.escribirComponente(
                page, "#password", password, descripcion="password")

            # Hacer click en submit
            ComponenteInteraccion.clickComponente(
                page, "#submit", descripcion="botón login")
            esperarConLoader(2, "Esperando respuesta del login")

            ComponenteInteraccion.clickComponente(
                page, "//a[@data-ng-click='Confirmar(true)']", descripcion="botón aceptar login", intentos=2 )

            LogManager.escribir_log(
                "SUCCESS", f"Login exitoso para: {usuario}")
            return True

        LogManager.escribir_log(
            "ERROR", f"Login falló después de {max_intentos} intentos")
        return False

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error al iniciar sesión: {str(e)}")
        return False

# ==================== FUNCIONES DE CONSULTA ====================


@with_timeout_check
def obtener_y_procesar_movimientos(page, id_ejecucion):
    """Obtiene y procesa los movimientos de todas las cuentas disponibles"""
    try:
        LogManager.escribir_log(
            "INFO", "Iniciando obtención de movimientos...")

        # Navegar a movimientos
        if not navegar_a_movimientos(page):
            return False

        # Procesar todas las cuentas
        return obtener_y_seleccionar_empresas(page, id_ejecucion)

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error obteniendo movimientos: {str(e)}")
        return False


@with_timeout_check
def obtener_y_seleccionar_empresas(page, id_ejecucion):
    """Obtiene empresas disponibles y las procesa una por una (similar a Pichincha)"""
    try:
        LogManager.escribir_log("INFO", "Obteniendo y procesando empresas...")

        # Selector del dropdown de empresas (adaptado para Produbanco)
        selectores_empresas = "//form/fieldset/div[2]/div[1]/div/div/div[2]/select"

        selector_empresas = None
        if ComponenteInteraccion.esperarElemento(page, selectores_empresas, timeout=5000, descripcion=f"select empresas ({selectores_empresas})"):
            selector_empresas = selectores_empresas
            LogManager.escribir_log(
                "SUCCESS", f"Select de empresas encontrado: {selectores_empresas}")

        if not selector_empresas:
            LogManager.escribir_log(
                "ERROR", "No se encontró el selector de empresas")
            return False

        # Esperar que el select tenga opciones cargadas
        esperarConLoaderSimple(2, "Esperando carga de opciones de empresas")

        # Obtener todas las opciones del select - CORRECCIÓN AQUÍ
        try:

            # XPath, usar sintaxis XPath para las opciones
            opciones_data = ComponenteInteraccion.obtener_opciones_select(page, selector_empresas, "select empresas")
            empresas_procesadas = 0

            # Procesar cada empresa por índice
            for i, opcion_data in enumerate(opciones_data):
                try:
                    texto_empresa = opcion_data['text'].strip()
                    valor_empresa = opcion_data['value']

                    # Filtrar opciones vacías o de placeholder
                    if not texto_empresa or texto_empresa in ["Seleccione", "-- Seleccione --", "", "Seleccione una empresa"]:
                        LogManager.escribir_log(
                            "DEBUG", f"Saltando opción vacía: '{texto_empresa}'")
                        continue

                    tiempo_transcurrido = formatear_tiempo_ejecucion(
                        timeout_manager.get_elapsed_time())
                    print("=" * 125)
                    LogManager.escribir_log(
                        "INFO", f"======= Empresa {i+1}/{len(opciones_data)}: '{texto_empresa}' - Tiempo: {tiempo_transcurrido} =======")

                    # Seleccionar empresa
                    if ComponenteInteraccion.seleccionar_opcion_select(page, selector_empresas, texto_empresa, "selector empresas"):
                        LogManager.escribir_log(
                            "SUCCESS", f"Empresa seleccionada: {texto_empresa}")

                        # Procesar la empresa seleccionada
                        if procesar_empresa_individual(page, texto_empresa, id_ejecucion):
                            empresas_procesadas += 1
                            LogManager.escribir_log(
                                "SUCCESS", f"Empresa {texto_empresa} procesada exitosamente")
                        else:
                            LogManager.escribir_log(
                                "ERROR", f"Error procesando empresa: {texto_empresa}")
                    else:
                        LogManager.escribir_log(
                            "ERROR", f"No se pudo seleccionar empresa: {texto_empresa}")

                except Exception as e:
                    error_msg = f"Error procesando empresa {i+1}: {str(e)}"
                    LogManager.escribir_log("ERROR", error_msg)
                    continue

            LogManager.escribir_log(
                "SUCCESS", f"Procesadas {empresas_procesadas} empresas exitosamente")
            return empresas_procesadas > 0

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error obteniendo opciones del select: {str(e)}")

            return False

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error en obtener y seleccionar empresas: {str(e)}")
        return False


@with_timeout_check
def procesar_empresa_individual(page, nombre_empresa, id_ejecucion):
    """Procesa una empresa individual después de haberla seleccionado"""
    try:
        LogManager.escribir_log(
            "INFO", f"Procesando empresa individual: {nombre_empresa}")

        # PASO 1: Hacer clic en botón "Consultar" para desplegar formulario
        selector_consultar = "//button[@data-ng-click='easyfiltros.preBtnProcesarClick(false)']"

        ComponenteInteraccion.clickComponente(
            page, selector_consultar, descripcion=f"botón consultar 1", intentos=1, timeout=3000)

        # PASO 2: Configurar fechas de consulta
        if not configurar_fechas_consulta(page):
            LogManager.escribir_log(
                "ERROR", "No se pudieron configurar las fechas de consulta")
            return False

        # PASO 3: Hacer clic en botón "Consultar" para ejecutar consulta
        selector_ejecutar = "//button[@data-ng-click='inicializarValoresBusquedaMasDatos(); ejecutarClick()']"

        ComponenteInteraccion.clickComponente(
            page, selector_ejecutar, descripcion=f"botón ejecutar consulta", intentos=1, timeout=3000)

        esperarConLoader(6, f"Ejecutando consulta para {nombre_empresa}")

        # PASO 4: Verificar que hay resultados y descargar Excel
        selector_descarga = "//a[@data-ng-click=\"exportar('excel')\"]"

        if not ComponenteInteraccion.esperarElemento(page, selector_descarga, timeout=5000, descripcion=f"botón descargar"):
            LogManager.escribir_log(
                "WARNING", f"No se encontraron datos para descargar en empresa: {nombre_empresa}")
            # Actualizar fechas incluso cuando no hay datos, ya que es normal
            ConfiguracionManager.actualizar_configuraciones_fecha()
            return False

        # PASO 5: Descargar y procesar archivo
        return descargar_y_procesar_archivo_empresa(page, nombre_empresa, id_ejecucion)

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando empresa individual {nombre_empresa}: {str(e)}")
        return False


def configurar_fechas_consulta(page):
    """Configura las fechas de consulta y parámetros"""
    try:
        fecha_desde_config = ConfiguracionManager.leer_configuracion(
            RUTAS_CONFIG['configuraciones'],
            "Fecha desde"
        )
        fecha_hasta_config = ConfiguracionManager.leer_configuracion(
            RUTAS_CONFIG['configuraciones'],
            "Fecha hasta"
        )

        if not fecha_desde_config or not fecha_hasta_config:
            # Usar fechas por defecto (ayer y hoy)
            hoy = date.today()
            ayer = hoy - timedelta(days=1)
            fecha_desde = ayer.strftime("%d/%m/%Y")
            fecha_hasta = hoy.strftime("%d/%m/%Y")
        else:
            fecha_desde = fecha_desde_config[1]
            fecha_hasta = fecha_hasta_config[1]

        LogManager.escribir_log(
            "INFO", f"Configurando fechas: {fecha_desde} - {fecha_hasta}")

        # Configurar fecha desde
        selector_fecha_desde = "//input[@name='desde']"

        ComponenteInteraccion.escribirComponente(
            page, selector_fecha_desde, fecha_desde, descripcion=f"fecha desde")

        # Configurar fecha hasta
        selector_fecha_hasta = "//input[@name='hasta']"

        ComponenteInteraccion.escribirComponente(
            page, selector_fecha_hasta, fecha_hasta, descripcion=f"fecha hasta", intentos=1)

        # Configurar número de registros (300)
        selector_registros = "//input[@name='paginado']"

        ComponenteInteraccion.escribirComponente(
            page, selector_registros, "300", descripcion=f"número de registros", intentos=1)

        LogManager.escribir_log(
            "SUCCESS", f"Consulta configurada desde {fecha_desde} hasta {fecha_hasta} con 300 registros")
        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error configurando fechas de consulta: {str(e)}")
        return False


def descargar_y_procesar_archivo_empresa(page, nombre_empresa, id_ejecucion):
    """Descarga el archivo Excel de la empresa y lo procesa"""
    try:
        LogManager.escribir_log(
            "INFO", f"Descargando archivo para empresa: {nombre_empresa}")

        # Selectores para el botón de descarga
        selector_descarga = "//a[@data-ng-click=\"exportar('excel')\"]"

        # Generar adicional con fecha/hora y primeras letras de empresa
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefijo_empresa = nombre_empresa[:2].upper() if len(nombre_empresa) >= 2 else "XX"
        adicional_nombre = f"{prefijo_empresa}_{timestamp}"

        ruta_archivo = ComponenteInteraccion.esperarDescarga(
            page,
            selector_descarga,
            timeout=30000,
            descripcion=f"botón descargar",
            adicional=adicional_nombre
        )
        if not ruta_archivo:
            LogManager.escribir_log(
                "ERROR", f"No se pudo descargar archivo para empresa: {nombre_empresa}")
            return False

        # Procesar archivo descargado usando la función existente
        if not procesar_archivo_excel(ruta_archivo, id_ejecucion, nombre_empresa):
            LogManager.escribir_log(
                "ERROR", f"Error procesando archivo de empresa: {nombre_empresa}")
            return False

        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error descargando archivo para empresa {nombre_empresa}: {str(e)}")
        return False

# ==================== FUNCIONES DE PROCESAMIENTO DE ARCHIVOS ====================


def procesar_archivo_excel(ruta_archivo, id_ejecucion, nombre_empresa):
    """Procesa el archivo Excel descargado de Produbanco"""
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
        if len(contenido) < 14:
            LogManager.escribir_log(
                "WARNING", f"El archivo solo tiene {len(contenido)} filas, se esperaban al menos 14")
            return False

        # Extraer información del archivo según configuración Produbanco
        empresa_archivo = ""
        cuenta = ""

        # Extraer empresa (celda M9)
        if len(contenido) > 8 and len(contenido[8]) > 12:
            empresa_archivo = str(contenido[8][12]) if contenido[8][12] else ""

        # Extraer cuenta (celda F9)
        if len(contenido) > 8 and len(contenido[8]) > 5:
            cuenta = str(contenido[8][5]) if contenido[8][5] else ""
        
        # Usar nombre_empresa del parámetro si empresa_archivo está vacío
        empresa_final = empresa_archivo if empresa_archivo else (nombre_empresa if nombre_empresa else "SIN_EMPRESA")
        LogManager.escribir_log("INFO", f"Empresa: '{empresa_final}', Cuenta: '{cuenta}'")

        if not cuenta:
            LogManager.escribir_log(
                "WARNING", "No se pudo extraer número de cuenta")
            cuenta = "SIN_CUENTA"

        # Obtener rango de fechas del archivo para la consulta previa
        fechas_archivo = []

        # Los datos empiezan en la fila 14 (índice 13)
        for i in range(13, len(contenido)):
            fila = contenido[i]
            if fila and len(fila) > 0 and fila[3]:
                # Solo los primeros 10 caracteres (fecha)
                fecha_str = str(fila[3])[:10]
                if fecha_str and fecha_str not in fechas_archivo:
                    fechas_archivo.append(fecha_str)

        if not fechas_archivo:
            LogManager.escribir_log(
                "WARNING", "No se encontraron fechas válidas en el archivo")
            return False

        # Convertir fechas y obtener rango
        fechas_convertidas = []
        for fecha_str in fechas_archivo:
            fecha_sql = convertir_fecha_sql(fecha_str)
            if fecha_sql:
                fechas_convertidas.append(fecha_sql)

        if not fechas_convertidas:
            LogManager.escribir_log(
                "WARNING", "No se pudieron convertir las fechas")
            return False

        fecha_min = min(fechas_convertidas)
        fecha_max = max(fechas_convertidas)
        LogManager.escribir_log(
            "INFO", f"📅 Rango de fechas: {fecha_min} a {fecha_max}")

        # Consultar registros existentes en la BD
        sql_consulta = f"""
            SELECT numDocumento, fechaTransaccion, valor, tipo, conceptoTransaccion
            FROM {DATABASE}
            WHERE numCuenta = '{cuenta}' 
            AND banco = '{CONFIG_PRODUBANCO['banco_codigo']}' 
            AND empresa = '{empresa_final}' 
            AND fechaTransaccion BETWEEN '{fecha_min}' AND '{fecha_max}'
        """

        registros_existentes = BaseDatos.consultarBD(sql_consulta)
        combinaciones_existentes = set()
        documentos_existentes_en_bd = set()

        if registros_existentes:
            for registro in registros_existentes:
                doc_bd = str(registro[0]) if registro[0] else ""
                fecha_bd = str(registro[1])[:10] if registro[1] else ""
                valor_bd = float(registro[2]) if registro[2] else 0.0
                tipo_bd = str(registro[3]) if registro[3] else ""
                concepto_bd = str(registro[4]) if registro[4] else ""

                documentos_existentes_en_bd.add(doc_bd)
                clave_combinacion = f"{fecha_bd}|{valor_bd}|{tipo_bd}|{concepto_bd[:50]}"
                combinaciones_existentes.add(clave_combinacion)

        LogManager.escribir_log(
            "INFO", f"📋 Se encontraron {len(combinaciones_existentes)} combinaciones existentes")

        # Procesar movimientos del archivo
        movimientos_insertados = 0
        movimientos_omitidos = 0
        filas_procesadas = 0
        documentos_procesados_en_memoria = set()

        for i in range(13, len(contenido)):  # Empezar desde fila 14 (índice 13)
            fila = contenido[i]

            if not fila or len(fila) < 16:  # Asegurar que hay suficientes columnas
                continue

            # Extraer datos básicos según el formato de Produbanco
            fecha_str = str(fila[3]) if fila[3] else ""
            concepto = str(fila[7]) if fila[7] else ""
            signo = str(fila[8]) if fila[8] else ""
            valor_str = str(fila[10]) if fila[10] else ""
            saldo_str = str(fila[13]) if fila[13] else ""
            disponible_str = str(fila[14]) if fila[14] else ""
            oficina = str(fila[15]) if fila[15] else ""

            ref1 = str(fila[18]) if len(fila) > 8 and fila[18] else ""  # Referencia 1
            ref2 = str(fila[19]) if len(fila) > 9 and fila[19] else ""  # Referencia 2

            if not fecha_str or not valor_str:
                continue

            filas_procesadas += 1

            try:
                # Convertir fecha (solo la parte de fecha)
                fecha_solo = fecha_str[:10]  # YYYY-MM-DD
                fecha_convertida = convertir_fecha_sql(fecha_solo)
                if not fecha_convertida:
                    LogManager.escribir_log("WARNING", f"Fecha inválida en fila {i+1}: {fecha_str}")
                    continue

                # Filtrar por fecha (solo registros posteriores a 2024-02-28)
                if datetime.strptime(fecha_convertida, "%Y-%m-%d") <= datetime.strptime("2024-02-28", "%Y-%m-%d"):
                    continue

                # Determinar tipo basado en el signo
                tipo_trx = "D" if signo == "(-)" else "C"

                # Limpiar valores monetarios
                valor = limpiar_valor_monetario(valor_str)
                saldo = limpiar_valor_monetario(saldo_str)
                disponible = limpiar_valor_monetario(disponible_str)

                 # Generar número de documento
                prefijo_empresa = empresa_final[:2] if len(empresa_final) >= 2 else "XX"
                fecha_codigo = fecha_str.replace(
                    "-", "").replace(":", "").replace(" ", "")
                saldo_codigo = str(saldo).replace(
                    '$', '').replace(',', '').replace(' ', '')
                # valor_codigo = str(valor).replace(
                #     '$', '').replace(',', '').replace(' ', '')
                len_referencia = str(len(ref1))
                len_descripcion = str(len(ref2))

                # fecha_codigo_aux = fecha_solo.replace("-", "").replace(":", "").replace(" ", "")

                # num_documento_baseAux = f"{prefijo_empresa}{fecha_codigo_aux}{valor_codigo}{len_referencia}{len_descripcion}-n | {ref2}"
                
                num_documento_base = f"{prefijo_empresa}{fecha_codigo}{saldo_codigo}{len_referencia}{len_descripcion}-n | {ref2}"

                # Verificar si el documento ya existe en BD o en memoria
                if num_documento_base in documentos_existentes_en_bd or num_documento_base in documentos_procesados_en_memoria:
                    movimientos_omitidos += 1
                    LogManager.escribir_log("DEBUG", f"Documento duplicado omitido: {num_documento_base}")
                    continue


                # Obtener contador de fecha
                cont_fecha = obtener_contador_fecha(
                    cuenta, empresa_final, fecha_convertida)
                
                # Preparar descripción completa
                descripcion_completa = concepto.replace("'", "''")

                # Insertar en base de datos
                sql_insert = f"""
                    INSERT INTO {DATABASE} 
                    (numCuenta, banco, empresa, numDocumento, idEjecucion, fechaTransaccion, 
                     tipo, valor, saldoContable, disponible, oficina, referencia, contFecha, conceptoTransaccion)
                    VALUES ('{cuenta}', '{CONFIG_PRODUBANCO['banco_codigo']}', '{empresa_final.replace("'", "''")}', 
                            '{num_documento_base}', {id_ejecucion}, '{fecha_convertida}', 
                            '{tipo_trx}', {valor}, {saldo}, {disponible}, '{oficina.replace("'", "''")}', 
                            '{ref1.replace("'", "''")}', {cont_fecha}, '{descripcion_completa.replace("'", "''")}')
                """

                if datosEjecucion(sql_insert):
                    movimientos_insertados += 1
                    documentos_procesados_en_memoria.add(num_documento_base)
                else:
                    LogManager.escribir_log(
                        "ERROR", f"Error insertando movimiento: {num_documento_base}")

            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error procesando fila {i+1}: {str(e)}")
                continue

        # Resumen final
        LogManager.escribir_log("INFO", f"=== RESUMEN PROCESAMIENTO ===")
        LogManager.escribir_log("INFO", f"🏢 Empresa: {empresa_final}")
        LogManager.escribir_log("INFO", f"💳 Cuenta: {cuenta}")
        LogManager.escribir_log(
            "INFO", f"📊 Total filas procesadas: {filas_procesadas}")
        LogManager.escribir_log(
            "INFO", f"✅ Registros nuevos insertados: {movimientos_insertados}")
        LogManager.escribir_log(
            "INFO", f"⏭️ Registros omitidos: {movimientos_omitidos}")
        LogManager.escribir_log(
            "INFO", f"📅 Rango de fechas: {fecha_min} a {fecha_max}")

        if movimientos_insertados > 0:
            LogManager.escribir_log(
                "SUCCESS", f"✅ Procesamiento exitoso: {movimientos_insertados} nuevos movimientos")
        else:
            LogManager.escribir_log(
                "SUCCESS", f"✅ Procesamiento exitoso: No se encontraron registros nuevos")

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
        LogManager.escribir_log(
            "ERROR", f"Error procesando archivo Excel: {str(e)}")
        return False


def obtener_contador_fecha(cuenta, empresa, fecha):
    """Obtiene el siguiente contador de fecha para evitar duplicados"""
    try:
        sql = f"""
            SELECT COALESCE(MAX(contFecha), 0) + 1 AS maxCont 
            FROM {DATABASE} 
            WHERE numCuenta = '{cuenta}' 
            AND banco = '{CONFIG_PRODUBANCO['banco_codigo']}' 
            AND empresa = '{empresa}' 
            AND fechaTransaccion = '{fecha}'
        """
        resultado = BaseDatos.consultarBD(sql)
        return resultado[0][0] if resultado and resultado[0] else 1
    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Error obteniendo contador fecha: {str(e)}")
        return 1


def asegurar_numero_unico(num_documento_base, documentos_bd, documentos_memoria):
    """Asegura que el número de documento sea único"""
    try:
        if num_documento_base not in documentos_bd and num_documento_base not in documentos_memoria:
            return num_documento_base

        sufijo = 1
        while True:
            num_documento_con_sufijo = f"{num_documento_base}_{sufijo}"
            if num_documento_con_sufijo not in documentos_bd and num_documento_con_sufijo not in documentos_memoria:
                return num_documento_con_sufijo
            sufijo += 1

            if sufijo > 100:
                return f"{num_documento_base}_{int(time.time())}"

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error asegurando número único: {str(e)}")
        return f"{num_documento_base}_{int(time.time())}"

# ==================== FUNCIONES AUXILIARES ====================


def convertir_fecha_sql(fecha_str):
    """Convierte string de fecha a formato SQL Server"""
    try:
        if not fecha_str:
            return None

        # Intentar diferentes formatos de fecha
        formatos = ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y']

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

# ==================== FUNCIÓN PRINCIPAL ====================


@with_timeout_check
def main():
    """Función principal del robot Produbanco"""

    id_ejecucion = None
    inicio_ejecucion = datetime.now()

    try:
        # Obtener ID de ejecución
        id_ejecucion = obtenerIDEjecucion()

        LogManager.iniciar_proceso(NOMBRE_BANCO, id_ejecucion, f"Automatización Banco Produbanco - ID: {id_ejecucion}")
        # Iniciar timeout manager
        timeout_manager.start()

        # Registrar inicio de ejecución
        sql_inicio = f"""
            INSERT INTO {DATABASE_RUNS} (idAutomationRun, processName, startDate, finalizationStatus) 
            VALUES ({id_ejecucion}, 'Descarga comprobantes-{NOMBRE_BANCO}', SYSDATETIME(), 'Running')
        """
        datosEjecucion(sql_inicio)
        escribirLog(
            f"Iniciando automatización {NOMBRE_BANCO}", id_ejecucion, "INFO", "INICIO")

        # Inicializar Playwright
        manager = PlaywrightManager(
            headless=False, download_path=RUTAS_CONFIG['descargas'])
        playwright, browser, context, page = manager.iniciar_navegador()

        try:
            # Navegar a login
            if not navegar_a_login(page):
                return False

            # Iniciar sesión
            if not iniciar_sesion(page):
                return False

            # Obtener y procesar movimientos
            if not obtener_y_procesar_movimientos(page, id_ejecucion):
                return False

            # Registrar éxito
            tiempo_total = formatear_tiempo_ejecucion(
                datetime.now() - inicio_ejecucion)
            LogManager.escribir_log(
                "SUCCESS", f"✅ {NOMBRE_BANCO} completado exitosamente en {tiempo_total}")

            sql_exito = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = SYSDATETIME(), finalizationStatus = 'Exitoso'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_exito)
            escribirLog(
                f"Automatización {NOMBRE_BANCO} completada exitosamente", id_ejecucion, "SUCCESS", "FIN")
            
            # Actualizar configuraciones de fecha
            ConfiguracionManager.actualizar_configuraciones_fecha()

            # Ejecutar BAT final
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
            SubprocesoManager.ejecutar_bat_final()

            return True

        finally:
            if 'context' in locals():
                context.close()
            if 'browser' in locals():
                browser.close()
            if playwright:
                playwright.stop()

    except Exception as e:
        tiempo_total = formatear_tiempo_ejecucion(
            datetime.now() - inicio_ejecucion)
        LogManager.escribir_log(
            "ERROR", f"❌ Error en {NOMBRE_BANCO}: {str(e)} (Tiempo: {tiempo_total})")

        if id_ejecucion:
            sql_error = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = SYSDATETIME(), finalizationStatus = 'Error'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_error)
            escribirLog(
                f"Error en automatización {NOMBRE_BANCO}: {str(e)}", id_ejecucion, "ERROR", "FIN")

        # Ejecutar BAT final incluso si hubo error
        LogManager.escribir_log(
            "INFO", "🔧 Ejecutando proceso final de emergencia...")
        SubprocesoManager.ejecutar_bat_final()

        return False

    finally:
        # Detener timeout manager
        timeout_manager.stop()

        tiempo_total = formatear_tiempo_ejecucion(
            datetime.now() - inicio_ejecucion)
        LogManager.escribir_log(
            "INFO", f"Tiempo total de ejecución: {tiempo_total}")
        LogManager.escribir_log("INFO", "=" * 60)


if __name__ == "__main__":
    try:
        exito = main()
        if exito:
            LogManager.escribir_log(
                "SUCCESS", f"Robot {NOMBRE_BANCO} finalizado exitosamente")
            sys.exit(0)
        else:
            # Actualizar configuraciones de fecha
            ConfiguracionManager.actualizar_configuraciones_fecha()
            LogManager.escribir_log(
                "ERROR", f"Robot {NOMBRE_BANCO} finalizado con errores")
            sys.exit(1)
    except KeyboardInterrupt:
        LogManager.escribir_log(
            "WARNING", f"Robot {NOMBRE_BANCO} interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error fatal en robot {NOMBRE_BANCO}: {str(e)}")
        sys.exit(1)
