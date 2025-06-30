# -*- coding: utf-8 -*-
"""
BANCO PICHINCHA - AUTOMATIZACIÓN COMPLETA OPTIMIZADA
"""
from datetime import datetime, date, timedelta
import email
import json
import csv
import re
import time
import threading
import signal
from functools import wraps
import sys
import os
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
    clickComponenteOpcional
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
        os._exit(1)  # Salida forzada sin cleanup

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
# 12 minutos 30 seg (12.5 * 60 = 750 segundos)
timeout_manager = TimeoutManager(750)


def with_timeout_check(func):
    """Decorator que verifica timeout antes de ejecutar funciones críticas"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        timeout_manager.check()
        return func(*args, **kwargs)
    return wrapper

# ==================== CONFIGURACIÓN GLOBAL ====================

# DATABASE = "RegistrosBancosPRUEBA"
# DATABASE_LOGS = "AutomationLogPRUEBA"
# DATABASE_RUNS = "AutomationRunPRUEBA"
DATABASE = "RegistrosBancos"
DATABASE_LOGS = "AutomationLog"
DATABASE_RUNS = "AutomationRun"
NOMBRE_BANCO = "Banco Pichincha"

URLS = {
    'login': "https://cashmanagement.pichincha.com/loginNR/#/loginNR/auth/login",
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
    """Realiza el login completo en Banco Pichincha"""
    try:
        LogManager.escribir_log("INFO", "Iniciando proceso de login")

        # Leer credenciales
        credenciales = LectorArchivos.leerCSV(
            RUTAS_CONFIG['credenciales_banco'],
            filtro_columna=0,
            valor_filtro="Banco Pichincha"
        )
        credenciales = credenciales[0]

        if not credenciales:
            raise Exception(
                "No se pudieron leer las credenciales de Banco Pichincha")

        usuario = credenciales[1]
        password = credenciales[2]

        # Navegar a la página
        page.goto(URLS['login'])
        EsperasInteligentes.esperar_carga_pagina(page)

        # Escribir credenciales
        ComponenteInteraccion.escribirComponente(
            page,
            "input[formcontrolname='username']",
            usuario,
            descripcion="usuario"
        )
        ComponenteInteraccion.escribirComponente(
            page,
            "input[formcontrolname='password']",
            password,
            descripcion="password"
        )
        ComponenteInteraccion.clickComponente(
            page,
            "#kt_login_signin_submit",
            descripcion="botón login"
        )

        # Manejar código de seguridad
        LogManager.escribir_log("INFO", "Esperando código de seguridad...")

        # Obtener código del correo usando la función simplificada
        codigo = CorreoManager.obtener_codigo_correo(
            asunto="Codigo de Seguridad",  # Asunto específico de Pichincha
        )

        if not codigo:
            raise Exception(
                "No se pudo obtener el código de seguridad del correo")

        if codigo and re.fullmatch(r"^\d{6}$", codigo):
            LogManager.escribir_log(
                "SUCCESS", f"Código válido recibido: {codigo}")

            ComponenteInteraccion.escribirComponente(
                page,
                "input[formcontrolname='userCode']",
                codigo,
                descripcion="código seguridad"
            )
            ComponenteInteraccion.clickComponente(
                page,
                "#kt_login_signin_submit1",
                descripcion="validar código"
            )

            # Manejar diálogos posteriores
            esperarConLoaderSimple(2, "Procesando código de seguridad")

            # Manejo de diálogos opcionales con selectores robustos
            clickComponenteOpcional(
                page,
                "//button[contains(text(), 'OK')] | //button[.//span[contains(text(), 'OK')]] | //button[@mat-dialog-close and contains(., 'OK')]",
                descripcion="botón OK",
                intentos=1,
                timeout=2000
            )

            esperarConLoaderSimple(1, "Esperando diálogos")

            ComponenteInteraccion.clickComponente(
                page,
                "//button[.//span[contains(text(), 'No')]]",
                descripcion="botón No guardar sesión",
            )

            LogManager.escribir_log(
                "SUCCESS", "Login completado exitosamente")
            return True

        raise Exception("No se pudo completar el proceso de login")

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error en login: {str(e)}")
        return False

# ==================== FUNCIONES DE NAVEGACIÓN ====================


def navegar_a_movimientos(page):
    """Navega a la página de movimientos/consulta de cuentas a través del menú"""
    try:
        LogManager.escribir_log(
            "INFO", "Navegando a página de movimientos a través del menú...")

        EsperasInteligentes.esperar_carga_pagina(page)
        esperarConLoaderSimple(5, "Esperando carga de página principal")

        ComponenteInteraccion.clickComponenteOpcional(
            page,
            "//a[contains(text(), 'Aceptar')]",
            descripcion="botón Aceptar mensaje",
            intentos=2,
            timeout=2000
        )

        # PASO 1: Hacer clic en "Banca Empresas"
        LogManager.escribir_log(
            "INFO", "Paso 1: Haciendo clic en 'Banca Empresas'")

        selector_banca_empresas = "//span[contains(text(), 'Banca Empresas')]"
        banca_empresas_encontrado = False

        if ComponenteInteraccion.esperarElemento(page, selector_banca_empresas, timeout=5000, descripcion=f"Botón Banca Empresas)"):
            if ComponenteInteraccion.clickComponente(page, selector_banca_empresas, descripcion="Banca Empresas"):
                banca_empresas_encontrado = True

        if not banca_empresas_encontrado:
            raise Exception("No se encontró el menú 'Banca Empresas'")

        # Esperar que se expanda el menú de Banca Empresas
        esperarConLoaderSimple(1, "Esperando expansión de menú Banca Empresas")

        # PASO 2: Hacer clic en "Cuentas"
        LogManager.escribir_log("INFO", "Paso 2: Haciendo clic en 'Cuentas'")

        selector_cuentas = "//a[contains(@ng-click, 'AbrirModuloClick')][contains(., 'Cuentas')]"

        cuentas_encontrado = False

        if ComponenteInteraccion.esperarElemento(page, selector_cuentas, timeout=5000, descripcion=f"Botón Cuentas"):
            if ComponenteInteraccion.clickComponente(page, selector_cuentas, descripcion="módulo Cuentas"):
                cuentas_encontrado = True

        if not cuentas_encontrado:
            raise Exception("No se encontró el módulo 'Cuentas'")

        # Esperar que se expanda el submenú de Cuentas
        esperarConLoaderSimple(1, "Esperando expansión de submenú Cuentas")

        # PASO 3: Hacer clic en "Movimientos"
        LogManager.escribir_log(
            "INFO", "Paso 3: Haciendo clic en 'Movimientos'")

        selector_movimientos = "//a[@href='#/trans/BVE/Cuentas/ESTADOCUENTA']"

        movimientos_encontrado = False

        if ComponenteInteraccion.esperarElemento(page, selector_movimientos, timeout=5000, descripcion=f"Botón Movimientos"):
            if ComponenteInteraccion.clickComponente(page, selector_movimientos, descripcion="Movimientos"):
                movimientos_encontrado = True

        if not movimientos_encontrado:
            raise Exception("No se encontró la opción 'Movimientos'")
        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error navegando a movimientos: {str(e)}")

        # Debug: screenshot de error
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"{RUTAS_CONFIG['descargas']}/error_navegacion_{timestamp}.png"
            page.screenshot(path=screenshot_path)
            LogManager.escribir_log(
                "INFO", f"Screenshot de error guardado: {screenshot_path}")
        except:
            pass

        return False


# ==================== FUNCIONES DE SELECCIÓN DE EMPRESA ====================
@with_timeout_check
def obtener_y_seleccionar_empresas(page, id_ejecucion):
    """
    Función combinada que obtiene empresas disponibles y las procesa una por una
    Simplifica el código eliminando funciones redundantes
    """
    try:
        LogManager.escribir_log("INFO", "Obteniendo y procesando empresas...")

        # Esperar carga de página
        EsperasInteligentes.esperar_carga_pagina(page)

        # Selector específico del select de empresas
        selector_empresas = "//div[@data-ng-show='!easyfiltros.busquedaEmpresaHabilitada']//select[@id='seleccionEmpresaCombo']"

        # Usar la función genérica para obtener opciones
        opciones_data = ComponenteInteraccion.obtener_opciones_select(
            page, selector_empresas, "select empresas")

        if not opciones_data:
            LogManager.escribir_log(
                "ERROR", "No se pudieron obtener las opciones de empresas")
            return False

        empresas_procesadas = 0

        # Procesar cada empresa
        for i, opcion_data in enumerate(opciones_data):
            texto_empresa = opcion_data['text']
            valor_empresa = opcion_data['value']

            # Filtrar opciones vacías o de placeholder
            if not texto_empresa or texto_empresa in ["Seleccione", "-- Seleccione --", ""]:
                LogManager.escribir_log(
                    "DEBUG", f"Saltando opción vacía: '{texto_empresa}'")
                continue

            tiempo_transcurrido = formatear_tiempo_ejecucion(
                timeout_manager.get_elapsed_time())
            print("=" * 125)
            LogManager.escribir_log(
                "INFO", f"======= Empresa {i+1}/{len(opciones_data)} - Tiempo: {tiempo_transcurrido} =======")
            escribirLog(
                f"Iniciando consulta para empresa: {texto_empresa}", id_ejecucion, "Information", "Consulta Empresa")

            try:
                # Seleccionar empresa usando la función común
                if ComponenteInteraccion.seleccionar_opcion_select(page, selector_empresas, texto_empresa, "selector empresas"):
                    # Procesar la empresa seleccionada
                    if procesar_empresa_individual(page, texto_empresa, id_ejecucion):
                        empresas_procesadas += 1
                        LogManager.escribir_log(
                            "SUCCESS", f"{texto_empresa} procesada exitosamente")
                        escribirLog(f"Empresa {texto_empresa} completada",
                                    id_ejecucion, "Information", "Empresa Completada")
                    else:
                        LogManager.escribir_log(
                            "ERROR", f"Error procesando empresa: {texto_empresa}")
                        escribirLog(
                            f"Error procesando empresa: {texto_empresa}", id_ejecucion, "Error", "Error Empresa")
                else:
                    LogManager.escribir_log(
                        "ERROR", f"No se pudo seleccionar empresa: {texto_empresa}")
                    escribirLog(
                        f"Error seleccionando empresa: {texto_empresa}", id_ejecucion, "Error", "Error Selección")

            except Exception as e:
                error_msg = f"Error procesando empresa {texto_empresa}: {str(e)}"
                LogManager.escribir_log("ERROR", error_msg)
                escribirLog(error_msg, id_ejecucion, "Error", "Error Empresa")
                continue

        LogManager.escribir_log(
            "SUCCESS", f"Procesadas {empresas_procesadas} empresas exitosamente")
        return empresas_procesadas > 0

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

        # Hacer clic en botón procesar cambio empresa
        ComponenteInteraccion.clickComponente(
            page,
            "//button[.//span[contains(text(),' Consultar ')]]",
            descripcion="botón procesar cambio empresa",
            intentos=1,
            timeout=5000
        )
        esperarConLoaderSimple(
            1, f"Esperando formulario de empresa: {nombre_empresa}")

        # Configurar fechas de consulta (que incluye tipo de consulta y registros por página)
        # Leer fechas desde configuración
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

        if not configurar_tipo_consulta(page):
            LogManager.escribir_log(
                "ERROR", "No se pudo configurar el tipo de consulta a 'Movimientos por rango de fecha'")
            return False

        LogManager.escribir_log(
            "INFO", f"Configurando fechas: {fecha_desde} - {fecha_hasta}")

        # Escribir fecha desde
        ComponenteInteraccion.escribirComponente(
            page,
            "//input[@name='desde']",
            fecha_desde,
            descripcion="fecha desde"
        )

        # Escribir fecha hasta
        ComponenteInteraccion.escribirComponente(
            page,
            "//input[@name='hasta']",
            fecha_hasta,
            descripcion="fecha hasta"
        )

        # Escribir paginado, Banco Pichincha max 100
        ComponenteInteraccion.escribirComponente(
            page,
            "//input[@name='paginado']",
            "100",
            descripcion="paginado hasta"
        )

        # Hacer clic en botón consultar movimientos
        ComponenteInteraccion.clickComponente(
            page,
            "//button[@data-ng-click='inicializarValoresBusquedaMasDatos(); ejecutarClick()']",
            descripcion="botón procesar consulta movimientos empresa",
            intentos=2,
            timeout=3000
        )

        # Procesar registros encontrados
        return procesar_registros_empresa(
            page, nombre_empresa, id_ejecucion, fecha_desde, fecha_hasta)

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando empresa individual {nombre_empresa}: {str(e)}")
        return False


def configurar_tipo_consulta(page):
    """Configura el tipo de consulta a 'Movimientos por rango de fecha' - SOLO XPATH"""
    try:
        # Selector XPath específico para el tipo de consulta
        selector_tipo_consulta = "//select[@data-ng-model='frmItem.tipoConsulta']"

        # Usar la función común para seleccionar la opción
        if ComponenteInteraccion.seleccionar_opcion_select(
            page,
            selector_tipo_consulta,
            "Movimientos por rango de fecha",
            "tipo de consulta"
        ):
            return True
        else:
            LogManager.escribir_log(
                "ERROR", "No se pudo configurar el tipo de consulta")
            return False

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error configurando tipo de consulta: {str(e)}")
        return False

# ==================== FUNCIONES DE CONSULTA POR EMPRESA ====================

def procesar_movimientos_descargados(movimientos_descargados, nombre_banco, empresa=None):
    """
    Procesa los movimientos descargados (lista de listas) y los compara con la BD
    """
    try:
        if not movimientos_descargados or len(movimientos_descargados) <= 1:
            LogManager.escribir_log(
                "WARNING", "No hay movimientos para procesar (solo headers o lista vacía)")
            return []

        # Verificar que la primera fila sean headers
        headers = movimientos_descargados[0]

        # Validar que tenemos las columnas necesarias
        expected_columns = ['Fecha', 'Documento', 'Tipo', 'Monto', 'Saldo']
        if not all(col in headers for col in expected_columns):
            LogManager.escribir_log(
                "ERROR", f"Headers no contienen las columnas necesarias: {expected_columns}")
            return []

        # Obtener índices de columnas
        try:
            idx_fecha = headers.index('Fecha')           # Columna 0
            idx_concepto = headers.index('Concepto')     # Columna 2
            idx_tipo = headers.index('Tipo')             # Columna 3
            idx_documento = headers.index('Documento')   # Columna 4
            idx_monto = headers.index('Monto')           # Columna 6
            idx_saldo = headers.index('Saldo')           # Columna 7
        except ValueError as e:
            LogManager.escribir_log(
                "ERROR", f"Error encontrando índices de columnas: {str(e)}")
            return []

        # Procesar datos (saltando la fila de headers)
        documentos_extraidos = []
        documentos_procesados_count = 0

        # Empezar desde índice 1
        for idx, row in enumerate(movimientos_descargados[1:], 1):
            try:
                documentos_procesados_count += 1

                # Extraer datos de la fila
                fecha_str = row[idx_fecha].strip()
                documento = row[idx_documento].strip()
                tipo = row[idx_tipo].strip()
                monto_str = row[idx_monto].strip()
                saldo_str = row[idx_saldo].strip()
                concepto = row[idx_concepto].strip(
                ) if idx_concepto < len(row) else ""

                # Convertir fecha al formato SQL
                try:
                    fecha_sql = datetime.strptime(
                        fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    LogManager.escribir_log(
                        "WARNING", f"Fecha inválida en fila {idx}: {fecha_str}")
                    continue

                # Convertir monto y saldo
                def convertir_a_float_csv(valor_str):
                    """Convierte string con comas a float"""
                    if not valor_str or valor_str.strip() == "":
                        return 0.0
                    try:
                        # Remover comas y convertir
                        valor_limpio = valor_str.replace(
                            ",", "").replace("$", "").strip()
                        return float(valor_limpio)
                    except ValueError:
                        LogManager.escribir_log(
                            "WARNING", f"Error convirtiendo valor: {valor_str}")
                        return 0.0

                valor_float = convertir_a_float_csv(monto_str)
                saldo_float = convertir_a_float_csv(saldo_str)

                # Crear documento faltante
                documento_excel = {
                    "numDocumento": documento,
                    "banco": nombre_banco,
                    "fechaTransaccion": fecha_sql,
                    "valor": valor_float,
                    "saldoContable": saldo_float,
                    "tipo": tipo,
                    "concepto": concepto
                }

                documentos_extraidos.append(documento_excel)

            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error procesando fila {idx}: {str(e)}")
                continue

        return documentos_extraidos

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando movimientos descargados: {str(e)}")
        return []

def obtenerDocumentosExcel(page, fecha_desde, fecha_hasta, empresa=None):
    """
    Descarga el archivo CSV/XLSX, compara con la base de datos y asigna sufijos si hay diferencias en valor o saldo.
    """
    try:
        # Selector para el botón de exportar Excel
        selector_excel = "//a[@data-ng-click=\"exportar('excel')\"]"

        # Esperar un momento para que la página cargue
        esperarConLoaderSimple(4, f"Esperando datos para {empresa}")

        ruta_archivo = ComponenteInteraccion.esperarDescarga(
            page,
            selector_excel,
            timeout=10000,
            descripcion="descarga de movimientos"
        )

        if not ruta_archivo:
            LogManager.escribir_log(
                "ERROR", "No se pudo descargar el archivo de movimientos")
            return []
        # Leer archivo descargado
        try:
            movimientos_descargados = LectorArchivos.leerCSV(ruta_archivo)

            # Procesar movimientos descargados
            documentos_extraidos = procesar_movimientos_descargados(
                movimientos_descargados,
                "Banco Pichincha",
                empresa
            )

            # Verificar que el archivo existe y tiene contenido
            if os.path.exists(ruta_archivo):
                # Eliminar archivo después de procesarlo
                try:
                    os.remove(ruta_archivo)
                except:
                    LogManager.escribir_log(
                        "WARNING", f"No se pudo eliminar archivo temporal: {ruta_archivo}")

            return documentos_extraidos

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error procesando archivo descargado: {str(e)}")
            return []

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error obteniendo documentos faltantes: {str(e)}")
        return False


@with_timeout_check
def procesar_documentos_faltantes_con_html(page, documentos_excel, nombre_empresa, id_ejecucion, fecha_desde, fecha_hasta):
    """
    Procesa documentos del Excel comparándolos con BD y luego busca solo los faltantes en HTML
    """
    try:
        LogManager.escribir_log(
            "INFO", f"Procesando {len(documentos_excel)} documentos faltantes con HTML...")

        # PASO 1: OBTENER DOCUMENTOS EXISTENTES EN BD UNA SOLA VEZ
        def obtener_documentos_existentes_bd(empresa):
            """Obtiene todos los documentos existentes en BD para la empresa"""
            try:
                # Convertir fechas al formato SQL
                fecha_desde_sql = datetime.strptime(
                    fecha_desde, "%d/%m/%Y").strftime("%Y-%m-%d")
                fecha_hasta_sql = datetime.strptime(
                    fecha_hasta, "%d/%m/%Y").strftime("%Y-%m-%d")

                sql = f"""
                    SELECT numDocumento, fechaTransaccion, valor, saldoContable, tipo
                    FROM {DATABASE}
                    WHERE banco = '{NOMBRE_BANCO}'
                    AND empresa = '{empresa}'
                    AND fechaTransaccion BETWEEN '{fecha_desde_sql}' AND '{fecha_hasta_sql}';
                """
                resultado = BaseDatos.consultarBD(sql)

                documentos_bd = []
                for row in resultado:
                    doc_bd = {
                        "numDocumento": row[0],
                        "fechaTransaccion": row[1],
                        "valor": float(row[2]) if row[2] is not None else 0.0,
                        "saldoContable": float(row[3]) if row[3] is not None else 0.0,
                        "tipo": row[4]
                    }
                    documentos_bd.append(doc_bd)
                return documentos_bd
            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error obteniendo documentos de BD: {str(e)}")
                return []

        # PASO 2: FUNCIÓN PARA COMPARAR SI UN DOCUMENTO DEL EXCEL EXISTE EN BD
        def documento_existe_en_bd(doc_excel, documentos_bd):
            """Verifica si un documento del Excel existe en BD considerando sufijos"""
            num_base_excel = doc_excel["numDocumento"].strip()
            fecha_excel = doc_excel["fechaTransaccion"]
            valor_excel = doc_excel["valor"]
            saldo_excel = doc_excel["saldoContable"]
            tipo_excel = doc_excel["tipo"]

            for doc_bd in documentos_bd:
                # Extraer número base del documento en BD (remover sufijo si existe)
                num_doc_bd_completo = doc_bd["numDocumento"].strip()
                num_base_bd = num_doc_bd_completo.split(' - ')[0].strip()

                # Comparar número base + otros campos
                if (num_base_bd == num_base_excel and
                    doc_bd["fechaTransaccion"] == fecha_excel and
                    abs(doc_bd["valor"] - valor_excel) < 0.01 and
                    abs(doc_bd["saldoContable"] - saldo_excel) < 0.01 and
                        doc_bd["tipo"] == tipo_excel):

                    return True

            return False

        # PASO 3: OBTENER DOCUMENTOS DE BD
        documentos_bd = obtener_documentos_existentes_bd(nombre_empresa)

        # PASO 4: COMPARAR EXCEL VS BD - OBTENER SOLO LOS FALTANTES
        documentos_realmente_faltantes = []
        documentos_existentes_count = 0

        for doc_excel in documentos_excel:
            if documento_existe_en_bd(doc_excel, documentos_bd):
                documentos_existentes_count += 1
            else:
                documentos_realmente_faltantes.append(doc_excel)

        # LOGS DE COMPARACIÓN
        LogManager.escribir_log("INFO", f"=== RESULTADO COMPARACIÓN ===")
        LogManager.escribir_log(
            "INFO", f"Total documentos en Excel: {len(documentos_excel)}")
        LogManager.escribir_log(
            "INFO", f"Documentos ya existentes en BD: {documentos_existentes_count}")
        LogManager.escribir_log(
            "INFO", f"Documentos realmente faltantes: {len(documentos_realmente_faltantes)}")
        
        # Si no hay documentos faltantes, terminar aquí
        if not documentos_realmente_faltantes:
            LogManager.escribir_log(
                "INFO", "No hay documentos nuevos para procesar")
            return []

        # PASO 5: PROCESAR SOLO LOS DOCUMENTOS REALMENTE FALTANTES EN HTML
        LogManager.escribir_log(
            "INFO", f"=== PROCESANDO {len(documentos_realmente_faltantes)} DOCUMENTOS FALTANTES EN HTML ===")
        print("")

        registros = []
        filas_procesadas = set()

        # FUNCIONES AUXILIARES PARA SUFIJOS (usando documentos_bd ya obtenidos)
        def obtener_documentos_con_mismo_numero_base(num_base, documentos_bd):
            """Obtiene documentos existentes con el mismo número base"""
            documentos_encontrados = []
            for doc_bd in documentos_bd:
                num_doc_bd_completo = doc_bd["numDocumento"].strip()
                num_base_bd = num_doc_bd_completo.split(' - ')[0].strip()
                if num_base_bd == num_base:
                    documentos_encontrados.append(num_doc_bd_completo)
            return documentos_encontrados

        def existe_en_memoria(doc):
            """Verifica si el documento ya está en memoria"""
            return any(r["numDocumento"] == doc for r in registros)

        # Contadores
        documentos_procesados_html = 0
        documentos_no_encontrados_html = 0

        # PROCESAR CADA DOCUMENTO FALTANTE
        for idx, doc in enumerate(documentos_realmente_faltantes):
            numDocumento_base = doc["numDocumento"]
            fecha = doc["fechaTransaccion"]
            valor = doc["valor"]
            saldo = doc["saldoContable"]
            tipo = doc["tipo"]
            concepto = doc["concepto"]

            tiempo_transcurrido = formatear_tiempo_ejecucion(
                timeout_manager.get_elapsed_time())

            LogManager.escribir_log(
                "INFO", f"================ Procesando documento {idx+1}/{len(documentos_realmente_faltantes)}: {numDocumento_base} - Tiempo: {tiempo_transcurrido} ================")

            # Buscar fila en HTML
            indice_fila_encontrada = buscar_fila_en_html_playwright(
                page, numDocumento_base, valor, saldo, filas_procesadas, pagina_actual=1)

            if indice_fila_encontrada is not None:
                # Marcar fila como procesada
                filas_procesadas.add(indice_fila_encontrada)

                # Obtener detalles adicionales
                detalles_extra = obtener_detalles_registros_playwright(
                    page, numDocumento_base, indice_fila_encontrada)

                if not detalles_extra:
                    LogManager.escribir_log(
                        "WARNING", f"No se pudieron obtener detalles para {numDocumento_base}")
                    documentos_no_encontrados_html += 1
                    continue

                # Procesar fecha
                fecha_transaccion = doc["fechaTransaccion"]
                if isinstance(fecha_transaccion, str):
                    if '/' in fecha_transaccion:
                        try:
                            fecha_transaccion = datetime.strptime(
                                fecha_transaccion, "%d/%m/%Y").strftime("%Y-%m-%d")
                        except ValueError:
                            LogManager.escribir_log(
                                "WARNING", f"Formato de fecha inválido: {fecha_transaccion}")
                            fecha_transaccion = datetime.now().strftime("%Y-%m-%d")
                    elif '-' in fecha_transaccion and len(fecha_transaccion) == 10:
                        pass  # Ya está en formato correcto
                    else:
                        LogManager.escribir_log(
                            "WARNING", f"Formato de fecha desconocido: {fecha_transaccion}")
                        fecha_transaccion = datetime.now().strftime("%Y-%m-%d")
                else:
                    fecha_transaccion = fecha_transaccion.strftime("%Y-%m-%d")

                detalles = {
                    "fechaTransaccion": fecha_transaccion,
                    "valor": doc["valor"],
                    "saldoContable": doc["saldoContable"],
                    "tipo": doc["tipo"],
                    **detalles_extra
                }

                # Combinar conceptos
                concepto_csv = concepto.strip() if concepto else ""
                concepto_html = detalles_extra.get(
                    "conceptoTransaccion", "").strip()

                if concepto_csv and concepto_html and concepto_csv == concepto_html:
                    concepto_final = concepto_csv
                elif concepto_csv and concepto_html and concepto_csv != concepto_html:
                    concepto_final = f"{concepto_csv} - {concepto_html}"
                elif concepto_csv and not concepto_html:
                    concepto_final = concepto_csv
                elif not concepto_csv and concepto_html:
                    concepto_final = concepto_html
                else:
                    concepto_final = ""

                detalles["conceptoTransaccion"] = concepto_final

                # LÓGICA DE SUFIJOS (usando documentos_bd ya obtenidos)
                documentos_existentes = obtener_documentos_con_mismo_numero_base(
                    numDocumento_base, documentos_bd)
                sufijo = 0
                numDocumento_final = numDocumento_base

                if documentos_existentes:
                    LogManager.escribir_log(
                        "DEBUG", f"Encontrados documentos existentes para {numDocumento_base}: {documentos_existentes}")

                    # Encontrar el mayor sufijo existente
                    mayor_sufijo = 0
                    for doc_existente in documentos_existentes:
                        if ' - ' in doc_existente:
                            try:
                                sufijo_existente = int(
                                    doc_existente.split(' - ')[1])
                                mayor_sufijo = max(
                                    mayor_sufijo, sufijo_existente)
                            except (ValueError, IndexError):
                                pass

                    # Asignar el siguiente sufijo disponible
                    sufijo = mayor_sufijo + 1
                    numDocumento_final = f"{numDocumento_base} - {sufijo}"
                    LogManager.escribir_log(
                        "INFO", f"Asignando sufijo {sufijo} al documento {numDocumento_base} -> {numDocumento_final}")

                # Verificar que no esté duplicado en memoria (registros del lote actual)
                while existe_en_memoria(numDocumento_final):
                    sufijo += 1
                    numDocumento_final = f"{numDocumento_base} - {sufijo}"
                    LogManager.escribir_log(
                        "DEBUG", f"Documento duplicado en memoria, incrementando sufijo: {numDocumento_final}")

                # Crear registro completo
                detalle_completo = {
                    "numDocumento": numDocumento_final,
                    "empresa": nombre_empresa,
                    **detalles
                }
                registros.append(detalle_completo)
                documentos_procesados_html += 1

                LogManager.escribir_log(
                    "INFO", f" ---------- Movimiento {numDocumento_base} guardado como: {numDocumento_final} ----------")
                LogManager.escribir_log(
                    "INFO", f"=======================================================================================")
                print("")
            else:
                documentos_no_encontrados_html += 1
                LogManager.escribir_log(
                    "WARNING", f"No se encontró el documento {numDocumento_base} en HTML")
                continue

        # LOGS FINALES
        LogManager.escribir_log("INFO", f"{"=" * 25} RESUMEN FINAL {nombre_empresa} {"=" * 25}")
        LogManager.escribir_log(
            "INFO", f"Documentos del Excel: {len(documentos_excel)}")
        LogManager.escribir_log(
            "INFO", f"Ya existentes en BD (saltados en comparación): {documentos_existentes_count}")
        LogManager.escribir_log(
            "INFO", f"Documentos para procesar en HTML: {len(documentos_realmente_faltantes)}")
        LogManager.escribir_log(
            "INFO", f"Procesados exitosamente en HTML: {documentos_procesados_html}")
        LogManager.escribir_log(
            "INFO", f"No encontrados en HTML: {documentos_no_encontrados_html}")
        LogManager.escribir_log(
            "INFO", f"Total registros preparados para insertar: {len(registros)}")

        # Mostrar detalles de sufijos
        registros_con_sufijo = [
            r for r in registros if ' - ' in r["numDocumento"]]
        registros_sin_sufijo = [
            r for r in registros if ' - ' not in r["numDocumento"]]

        LogManager.escribir_log(
            "INFO", f"Registros sin sufijo (nuevos): {len(registros_sin_sufijo)}")
        LogManager.escribir_log(
            "INFO", f"Registros con sufijo (duplicados del lote): {len(registros_con_sufijo)}")

        if registros_con_sufijo:
            sufijos_asignados = [r["numDocumento"]
                                 for r in registros_con_sufijo]
            LogManager.escribir_log(
                "DEBUG", f"Sufijos asignados: {sufijos_asignados}")

        if len(registros) > 0:
            LogManager.escribir_log(
                "SUCCESS", f"Procesamiento completado: {len(registros)} registros preparados para insertar")
        else:
            LogManager.escribir_log(
                "INFO", "No se generaron registros nuevos para insertar")

        return registros

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando documentos: {str(e)}")
        return []


def buscar_fila_en_html_playwright(page, numDocumento, valor, saldoContable, filas_procesadas, pagina_actual=1):
    """
    Busca una fila específica en la tabla HTML usando Playwright
    """
    try:
        # Obtener todas las filas de datos usando el selector correcto
        selector_filas = "//tbody//tr[@data-ng-repeat and contains(@class, 'filaGrid')]"

        # Esperar que existan filas
        if not ComponenteInteraccion.esperarElemento(page, selector_filas, timeout=5000, descripcion="filas de datos"):
            LogManager.escribir_log(
                "WARNING", "No se encontraron filas de datos en la tabla")
            return None

        # Obtener todas las filas
        filas_locator = page.locator(selector_filas)
        total_filas = filas_locator.count()

        for i in range(total_filas):
            # Crear un ID único para la fila que incluya la página actual
            fila_id = f"pagina_{pagina_actual}_fila_{i}"

            # Verificar si esta fila ya fue procesada
            if fila_id in filas_procesadas:
                LogManager.escribir_log(
                    "DEBUG", f"Saltando fila ya procesada: {fila_id}")
                continue

            try:
                fila_actual = filas_locator.nth(i)

                # Extraer datos usando selectores relativos dentro de cada fila
                # Basándome en el HTML: td[0]=fecha, td[1]=concepto, td[2]=tipo, td[3]=documento, td[4]=oficina, td[5]=monto, td[6]=saldo, td[7]=ver detalle
                documento_elem = fila_actual.locator(
                    "td:nth-child(4) span")  # Columna Documento
                valor_elem = fila_actual.locator(
                    "td:nth-child(6)")           # Columna Monto
                saldo_elem = fila_actual.locator(
                    "td:nth-child(7)")           # Columna Saldo contable

                # Verificar que los elementos existen
                if not documento_elem.count() or not valor_elem.count() or not saldo_elem.count():
                    LogManager.escribir_log(
                        "DEBUG", f"Fila {i} no tiene todos los elementos necesarios")
                    continue

                # Obtener textos
                num_doc_html = documento_elem.text_content().strip()
                valor_html_str = valor_elem.text_content().strip()
                saldo_html_str = saldo_elem.text_content().strip()

                # Convertir valores (remover &nbsp; y comas)
                def convertir_valor_html(valor_str):
                    if not valor_str:
                        return 0.0
                    try:
                        # Limpiar &nbsp; y otros caracteres HTML
                        valor_limpio = valor_str.replace("&nbsp;", "").replace(
                            ",", "").replace("$", "").strip()
                        return float(valor_limpio) if valor_limpio else 0.0
                    except:
                        return 0.0

                valor_html = convertir_valor_html(valor_html_str)
                saldo_html = convertir_valor_html(saldo_html_str)

                # Verificar coincidencia
                if (num_doc_html == numDocumento and
                    abs(valor_html - valor) < 0.01 and
                        abs(saldo_html - saldoContable) < 0.01):
                    return i  # Retornar índice basado en 0

            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error procesando fila {i}: {str(e)}")
                continue

        # Si no se encontró en la página actual, intentar ir a la siguiente
        selector_siguiente = "//a[@data-ng-click=\"ObtenerMasDatos(1)\"]"

        if ComponenteInteraccion.clickComponente(page, selector_siguiente, descripcion="siguiente página", intentos=1):
            LogManager.escribir_log("INFO", "Avanzando a siguiente página...")
            esperarConLoaderSimple(3, "Cargando siguiente página")

            # Llamada recursiva para buscar en la siguiente página
            return buscar_fila_en_html_playwright(page, numDocumento, valor, saldoContable, filas_procesadas, pagina_actual + 1)

        LogManager.escribir_log(
            "INFO", f"Documento {numDocumento} no encontrado en ninguna página")
        return None

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error buscando fila en HTML: {str(e)}")
        return None


def obtener_detalles_registros_playwright(page, numDocumento, indice_fila):
    """
    Extrae detalles adicionales del registro usando Playwright
    """
    try:
        # Selector actualizado para el botón de detalle usando el índice
        selector_filas = "//tbody//tr[@data-ng-repeat and contains(@class, 'filaGrid')]"
        filas_locator = page.locator(selector_filas)

        if indice_fila >= filas_locator.count():
            LogManager.escribir_log(
                "ERROR", f"Índice de fila {indice_fila} fuera de rango")
            return {}

        fila_actual = filas_locator.nth(indice_fila)

        boton_detalle = fila_actual.locator(
            "button[data-ng-click='consultaVerDetalle(item)']")

        if not boton_detalle.count():
            LogManager.escribir_log(
                "WARNING", f"No se encontró botón de detalle para {numDocumento}")
            return {}

        # Hacer clic en el botón de detalle
        boton_detalle.click()

        esperarConLoaderSimple(2, f"Obteniendo detalles de {numDocumento}...")
        # Extraer detalles usando los selectores correctos del formulario
        detalles = {
            # Número de cuenta del titular (siempre visible)
            "numCuenta": extraer_texto_seguro(page, "//span[@data-ng-bind='frmItem.cta.Texto']").split(";")[0].strip(),

            # Fecha transacción (siempre visible)
            # "fechaTransaccion": extraer_texto_seguro(page, "//span[@data-ng-bind='dtEstadoCuentaDetOUT.Fec_Mov | date']"),

            # Hora transacción (puede estar oculta con ng-hide)
            "horaTransaccion": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'showDetalleHoraTrans')]//span[@data-ng-bind='dtEstadoCuentaDetOUT.Hora_Mov']"),

            # Concepto transacción (siempre visible)
            "conceptoTransaccion": extraer_texto_seguro(page, "//span[@data-ng-bind='dtEstadoCuentaDetOUT.Desc_Mot']"),

            # Tipo (siempre visible)
            # "tipo": extraer_texto_seguro(page, "//span[@data-ng-bind='dtEstadoCuentaDetOUT.Tip_Mov']"),

            # Oficina (visible con showOficinaTransaccion)
            "oficina": extraer_texto_seguro(page, "//div[@data-ng-show='showOficinaTransaccion']//span[@data-ng-bind='dtEstadoCuentaDetOUT.Oficina']"),

            # Moneda (siempre visible)
            "moneda": extraer_texto_seguro(page, "//span[@data-ng-bind='monedaCuentaSelected']"),

            # Valor (siempre visible)
            # "valor": extraer_texto_seguro(page, "//span[@data-ng-bind=\"dtEstadoCuentaDetOUT.Valor_Mov | currency:''\"]"),

            # Canal de pago (puede estar oculto con showCanalDetalle)
            "canal": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'showCanalDetalle')]//span[@data-ng-bind='dtEstadoCuentaDetOUT.Canal']"),

            # Cuenta ordenante (visible con showCuentaOrigen)
            "cuentaOrigen": extraer_texto_seguro(page, "//div[@data-ng-show='showCuentaOrigen']//span[@data-ng-bind='dtEstadoCuentaDetOUT.cuentaOrigen']"),

            # Ordenante (visible con showOrdenante)
            "ordenante": extraer_texto_seguro(page, "//div[@data-ng-show='showOrdenante']//span[@data-ng-bind='dtEstadoCuentaDetOUT.ordenante']"),

            # Banco ordenante (puede estar oculto con showBancoOrdenante)
            "bancoOrdenante": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'showBancoOrdenante')]//span[@data-ng-bind='dtEstadoCuentaDetOUT.BancoOrdenante']"),

            # Cuenta destino (puede estar oculta con showCuentaDestino)
            "cuentaDestino": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'showCuentaDestino')]//span[@data-ng-bind='dtEstadoCuentaDetOUT.cuentaDestino']"),

            # Referencias adicionales (pueden estar ocultas)
            "ref1": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'mostrarBeneficiario')]//span[@data-ng-bind='dtEstadoCuentaDetOUT.Ref1']"),
            "ref2": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'mostrarBanco')]//span[@data-ng-bind='dtEstadoCuentaDetOUT.Ref2']"),
            "ref3": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'mostrarDescripcion')]//span[@data-ng-bind='dtEstadoCuentaDetOUT.Ref3']"),

            # Info adicional (puede estar oculta con showInfoAdicional)
            "infoAdicional": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'showInfoAdicional')]//span[@data-ng-bind='dtEstadoCuentaDetOUT.ReferenciaTransaccion']"),

            # Reference (puede estar oculta con showReference)
            "referencia": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'showReference')]//span[@data-ng-bind='dtEstadoCuentaDetOUT.Referencia']"),

            # Referencia adicional (puede estar oculta con mostrarReferencia)
            "referenciaAdicional": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'mostrarReferencia')]//span[@data-ng-bind='textoReferencia']"),

            # Proveedor (puede estar oculto con mostrarProveedor)
            "proveedor": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'mostrarProveedor')]//span[@data-ng-bind='dtEstadoCuentaDetOUT.Ref2']"),

            # Nombre del titular (puede estar oculto con showTitular)
            "nombreTitular": extraer_texto_seguro(page, "//div[contains(@data-ng-show, 'showTitular')]//span[@data-ng-bind='dtEstadoCuentaA.Oficial']"),

            # Inicializar como no cheque
            "escheque": False
        }

        # Verificar si es cheque basándose en el concepto
        concepto = detalles.get("conceptoTransaccion", "")
        if "CHEQUE" in concepto.upper():
            detalles["escheque"] = True
            LogManager.escribir_log(
                "INFO", f"Documento {numDocumento} identificado como cheque")

        # Limpiar datos extraídos
        detalles_limpios = {}
        for clave, valor in detalles.items():
            if isinstance(valor, str) and valor.strip():
                # Limpiar espacios y caracteres especiales
                valor_limpio = valor.strip()

                # Para valores monetarios, limpiar el formato
                if clave == "valor" and valor_limpio.startswith("&nbsp;"):
                    valor_limpio = valor_limpio.replace("&nbsp;", "").strip()

                detalles_limpios[clave] = valor_limpio
            elif isinstance(valor, bool):
                detalles_limpios[clave] = valor
            else:
                detalles_limpios[clave] = ""

        # Registrar información útil extraída
        campos_con_datos = [
            k for k, v in detalles_limpios.items() if v and v != ""]

        # Cerrar detalle
        selector_cerrar = "//button[@data-ng-click=\"btnRegresarClick()\"]"
        ComponenteInteraccion.clickComponente(
            page, selector_cerrar, descripcion="cerrar detalle", intentos=1)
        # esperarConLoaderSimple(1, "Cerrando detalles")

        return detalles_limpios

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error obteniendo detalles para {numDocumento}: {str(e)}")
        return {}


def extraer_texto_seguro(page, selector):
    """Extrae texto de manera segura con timeout corto"""
    try:
        # Buscar elementos que no tengan la clase ng-hide (que los oculta)
        elemento_locator = page.locator(selector).filter(
            has_not=page.locator(".ng-hide"))

        if elemento_locator.count() > 0:
            texto = elemento_locator.first.text_content()
            if texto and texto.strip():
                return texto.strip()
    except Exception as e:
        # Si falla el filtro, intentar sin filtro
        try:
            elemento_locator = page.locator(selector)
            if elemento_locator.count() > 0:
                # Verificar si el elemento está visible
                elemento = elemento_locator.first
                if elemento.is_visible():
                    texto = elemento.text_content()
                    if texto and texto.strip():
                        return texto.strip()
        except:
            pass

    return ""


def insertar_registros_bd(registros, id_ejecucion):
    """Inserta los registros procesados en la base de datos"""
    try:
        LogManager.escribir_log(
            "INFO", f"Insertando {len(registros)} registros en BD...")

        for registro in registros:
            try:
                # Limpiar textos para evitar errores de SQL
                def limpiar_texto_sql(texto):
                    if not texto:
                        return ""
                    return str(texto).replace("'", "''").strip()

                # Preparar valores
                num_cuenta = limpiar_texto_sql(registro.get("numCuenta", ""))
                num_documento = limpiar_texto_sql(registro["numDocumento"])
                empresa = limpiar_texto_sql(registro.get("empresa", ""))
                concepto = limpiar_texto_sql(
                    registro.get("conceptoTransaccion", ""))
                tipo = limpiar_texto_sql(registro["tipo"])
                oficina = limpiar_texto_sql(registro.get("oficina", ""))
                ordenante = limpiar_texto_sql(registro.get("ordenante", ""))
                cuenta_origen = limpiar_texto_sql(
                    registro.get("cuentaOrigen", ""))
                fecha_transaccion = registro["fechaTransaccion"]

                # Construir SQL de inserción con más campos
                sql = f"""
                    INSERT INTO {DATABASE} 
                    (numCuenta, banco, numDocumento, empresa, idEjecucion, fechaTransaccion, 
                     conceptoTransaccion, tipo, saldoContable, valor, oficina, ordenante, cuentaOrdenante) 
                    VALUES 
                    ('{num_cuenta}', 
                     '{NOMBRE_BANCO}', 
                     '{num_documento}', 
                     '{empresa}', 
                     {id_ejecucion}, 
                     '{fecha_transaccion}', 
                     '{concepto}', 
                     '{tipo}', 
                     {registro["saldoContable"]}, 
                     {registro["valor"]}, 
                     '{oficina}',
                     '{ordenante}',
                     '{cuenta_origen}');
                """

                BaseDatos.insertarBD(sql)

            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error insertando registro {registro.get('numDocumento', 'unknown')}: {str(e)}")

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error general insertando registros: {str(e)}")


def procesar_registros_empresa(page, nombre_empresa, id_ejecucion, fecha_desde, fecha_hasta):
    """Procesa los registros encontrados para una empresa"""
    try:
        LogManager.escribir_log(
            "INFO", f"Procesando registros para empresa: {nombre_empresa}")

        # Procesar los registros
        documentos_excel = obtenerDocumentosExcel(
            page, fecha_desde, fecha_hasta, nombre_empresa)

        if not documentos_excel:
            LogManager.escribir_log(
                "INFO", f"No se encontraron movimientos en Excel para {nombre_empresa}")
            return True

        # AQUÍ VA LA NUEVA LÓGICA DE PROCESAMIENTO
        registros = procesar_documentos_faltantes_con_html(
            page, documentos_excel, nombre_empresa, id_ejecucion, fecha_desde, fecha_hasta)

        if registros:
            # Insertar registros en BD
            insertar_registros_bd(registros, id_ejecucion)
            LogManager.escribir_log(
                "SUCCESS", f"{len(registros)} registros insertados para {nombre_empresa}")

        # Por ahora, solo registrar que se procesó
        escribirLog(f"Registros procesados para {nombre_empresa}",
                    id_ejecucion, "Information", "Proceso Registros")

        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando registros para {nombre_empresa}: {str(e)}")
        return False


# ==================== FUNCIONES AUXILIARES ====================

def formatear_tiempo_ejecucion(tiempo_delta):
    """Formatea un objeto timedelta en un string legible"""
    try:
        total_segundos = int(tiempo_delta.total_seconds())
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        segundos = total_segundos % 60

        if horas > 0:
            return f"{horas}h {minutos}m {segundos}s"
        elif minutos > 0:
            return f"{minutos}m {segundos}s"
        else:
            return f"{segundos}s"
    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Error formateando tiempo: {str(e)}")
        return "Tiempo no disponible"


def esperar_carga_completa_pagina(page, timeout=15000):
    """Espera que la página cargue completamente"""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
        esperarConLoaderSimple(2, "Esperando carga completa")
        return True
    except:
        return True  # Continuar aunque no se complete la espera


def cerrar_sesion(page):
    """Cierra la sesión del usuario"""
    try:
        LogManager.escribir_log("INFO", "Cerrando ventana...")

        # ComponenteInteraccion.clickComponente(
        #     page,
        #     "//img[class=\"botonMenu\"]",
        #     descripcion="cerrar sesión",
        # )
        # # Intentar hacer clic en el botón de cerrar sesión
        # if ComponenteInteraccion.clickComponente(
        #     page,
        #     "//li[data-ng-click=\"CerrarAplicacion()\"]",
        #     descripcion="cerrar sesión",
        # ):
        #     LogManager.escribir_log("SUCCESS", "Sesión cerrada exitosamente")
        # else:
        #     LogManager.escribir_log(
        #         "WARNING", "No se pudo cerrar sesión de manera explícita")

        return True

    except Exception as e:
        LogManager.escribir_log("WARNING", f"Error cerrando sesión: {str(e)}")
        return True  # No es crítico


# ==================== FUNCIÓN PRINCIPAL ====================


def main():
    """Función principal que ejecuta todo el proceso de automatización"""
    id_ejecucion = None
    manager = None

    try:
        # Iniciar timeout manager
        timeout_manager.start()

        # Obtener ID de ejecución
        id_ejecucion = obtenerIDEjecucion()

        LogManager.iniciar_proceso(NOMBRE_BANCO, id_ejecucion, f"Automatización Banco Pichincha - ID: {id_ejecucion}")

        # Registrar inicio en BD
        sql_inicio = f"""
            INSERT INTO {DATABASE_RUNS} (idAutomationRun, processName, startDate, finalizationStatus) VALUES ({id_ejecucion}, 'Descarga comprobantes-Banco Pichincha', SYSDATETIME(), 'Running')
        """
        datosEjecucion(sql_inicio)
        escribirLog(f"Inicio del proceso", id_ejecucion,
                    "Information", "Inicio")

        # Crear manager de navegador
        manager = PlaywrightManager(
            headless=False,  # Cambiar a True para modo headless
            download_path=RUTAS_CONFIG['descargas'],
            timeout=30000
        )

        # Iniciar navegador
        playwright, browser, context, page = manager.iniciar_navegador()
        LogManager.escribir_log("INFO", "Navegador iniciado correctamente")
        escribirLog("Navegador iniciado", id_ejecucion,
                    "Information", "Navegador")

        # Realizar login
        if not realizar_login_completo(page):
            raise Exception("Error en el proceso de login")

        escribirLog("Login completado exitosamente",
                    id_ejecucion, "Information", "Login")

        # Navegar a movimientos
        if not navegar_a_movimientos(page):
            raise Exception("Error navegando a la página de movimientos")

        escribirLog("Navegación a movimientos exitosa",
                    id_ejecucion, "Information", "Navegación")

        # Obtener y procesar todas las empresas

        if not obtener_y_seleccionar_empresas(page, id_ejecucion):
            raise Exception("Error obteniendo y procesando empresas")

        # Cerrar sesión

        cerrar_sesion(page)

        # Actualizar configuraciones de fecha
        ConfiguracionManager.actualizar_configuraciones_fecha()

        # Calcular tiempo total y registrar en BD
        tiempo_total = timeout_manager.get_elapsed_time()

        # Marcar como completado
        sql_fin = f"""
            UPDATE {DATABASE_RUNS} 
            SET endDate = SYSDATETIME(), finalizationStatus = 'Completed' 
            WHERE idAutomationRun = {id_ejecucion}
        """
        datosEjecucion(sql_fin)

        # Log final con tiempo total
        tiempo_total_str = formatear_tiempo_ejecucion(tiempo_total)
        mensaje_final = f"Proceso completado exitosamente - Tiempo total de ejecución: {tiempo_total_str}"

        # Ejecutar BAT para subir moviemientos al portal
        LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
        SubprocesoManager.ejecutar_bat_final()

        escribirLog(mensaje_final, id_ejecucion, "Information", "Fin")

        LogManager.finalizar_proceso(
            NOMBRE_BANCO, exito=True, descripcion="Proceso completado exitosamente")
        return True

    except Exception as e:
        error_msg = f"Error en proceso principal: {str(e)}"
        LogManager.escribir_log("ERROR", error_msg)

        # Calcular tiempo hasta el error
        tiempo_error = timeout_manager.get_elapsed_time()
        tiempo_error_str = formatear_tiempo_ejecucion(tiempo_error)
        error_msg += f" - Tiempo transcurrido hasta el error: {tiempo_error_str}"

        if id_ejecucion:
            # Determinar tipo de error
            status = 'Timeout' if isinstance(e, TimeoutError) else 'Failed'

            sql_error = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = SYSDATETIME(), finalizationStatus = '{status}' 
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_error)
            escribirLog(error_msg, id_ejecucion, "Error", "Error Fatal")

            # Ejecutar BAT para subir moviemientos al portal
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
            SubprocesoManager.ejecutar_bat_final()

        LogManager.finalizar_proceso(
            NOMBRE_BANCO, exito=False, descripcion=error_msg)
        return False

    finally:
        # Detener timeout manager
        timeout_manager.stop()
        if manager:
            try:
                manager.cerrar_navegador()
                LogManager.escribir_log(
                    "INFO", "Navegador cerrado correctamente")
            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error cerrando navegador: {str(e)}")


if __name__ == "__main__":
    try:
        
        resultado = main()
        if resultado:
            LogManager.escribir_log(
                "SUCCESS", "=== AUTOMATIZACIÓN COMPLETADA EXITOSAMENTE ===")
        else:
            LogManager.escribir_log("ERROR", "=== AUTOMATIZACIÓN FALLÓ ===")
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error crítico en ejecución: {str(e)}")
    finally:
        LogManager.escribir_log("INFO", "=== FIN DE EJECUCIÓN ===")
