# -*- coding: utf-8 -*-
"""
COOPERATIVA CREA - AUTOMATIZACIÓN COMPLETA MODERNIZADA
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
    SubprocesoManager,
    ConfiguracionManager,
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
    """Formatea la duración de tiempo en formato legible"""
    total_seconds = int(tiempo_delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


# ==================== CONFIGURACIÓN GLOBAL ====================

# DATABASE = "RegistrosBancosPRUEBA"
# DATABASE_LOGS = "AutomationLogPRUEBA"
# DATABASE_RUNS = "AutomationRunPRUEBA"
DATABASE = "RegistrosBancos"
DATABASE_LOGS = "AutomationLog"
DATABASE_RUNS = "AutomationRun"
NOMBRE_BANCO = "Cooperativa CREA"

URLS = {
    'login': "https://ws.crea.fin.ec/PaginaWeb/?_ga=2.170749536.1786221678.1709744334-878577525.1709744333&_gl=1*746s7d*_gcl_au*Njc3Nzg3MzEuMTcwOTc0NDMzNA..*_ga*ODc4NTc3NTI1LjE3MDk3NDQzMzM.*_ga_NP0ZEFS6DM*MTcwOTgxOTQyOS44LjAuMTcwOTgxOTQyOS4wLjAuMA.."
}

# Configuración específica de CREA
CONFIG_CREA = {
    'banco_codigo': "CREA",
    'mes_default': "actual"
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


def escribirLog(estado, mensaje, id_ejecucion, accion):
    """
    Escribe un log en la BD

    Args:
        estado: Estado del log (SUCCESS, ERROR, INFO, etc.)
        mensaje: Mensaje del log
        id_ejecucion: ID de ejecución (opcional)
        accion: Acción realizada (opcional)
    """
    try:
        if not id_ejecucion:
            id_ejecucion = obtenerIDEjecucion()

        texto_limpio = mensaje.replace("'", "''")
        sql = f"""
            INSERT INTO {DATABASE_LOGS} (idAutomationRun, processName, dateLog, statusLog, action)
            VALUES ({id_ejecucion}, '{texto_limpio}', SYSDATETIME(), '{estado}', '{accion}')
        """
        datosEjecucion(sql)
    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Error escribiendo log en BD: {str(e)}")

# ==================== FUNCIONES DE GENERACIÓN DE IDENTIFICADORES ====================


def generar_num_documento(fecha, valor, tipo, numero_base=None):
    """
    Genera un número de documento único para CREA
    Args:
        fecha: Fecha de la transacción (datetime o string)
        valor: Valor de la transacción (float)
        tipo: Tipo de transacción (C o D)
        numero_base: Número base del archivo Excel (si existe)
    """
    try:
        # Convertir fecha a string si es datetime
        if isinstance(fecha, datetime):
            fecha_str = fecha.strftime("%Y%m%d")
        elif isinstance(fecha, str):
            # Intentar parsear la fecha
            try:
                fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
                fecha_str = fecha_obj.strftime("%Y%m%d")
            except:
                fecha_str = fecha.replace("-", "").replace("/", "")[:8]
        else:
            fecha_str = str(fecha).replace("-", "").replace("/", "")[:8]

        # Convertir valor a entero (sin decimales)
        if isinstance(valor, (int, float)):
            valor_str = str(int(abs(valor)))
        else:
            valor_str = str(valor).replace(".", "").replace(",", "")

        # Usar número base si está disponible, sino generar uno
        if numero_base:
            base_str = str(numero_base)
        else:
            # Generar número basado en timestamp
            timestamp = int(datetime.now().timestamp())
            base_str = str(timestamp)[-6:]

        # Formato: FECHA + TIPO + VALOR + BASE
        num_documento = f"{fecha_str}{tipo}{valor_str}{base_str}"

        # Limitar longitud y asegurar unicidad
        if len(num_documento) > 20:
            num_documento = num_documento[:20]

        LogManager.escribir_log(
            "DEBUG", f"Número documento generado: {num_documento}")
        return num_documento

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error generando número documento: {e}")
        # Fallback: timestamp + tipo
        timestamp = int(datetime.now().timestamp())
        return f"{timestamp}{tipo}"


def verificar_duplicado(num_documento, credenciales_db):
    """Verifica si el número de documento ya existe en la base de datos"""
    try:
        sql = f"SELECT COUNT(*) FROM {DATABASE} WHERE numDocumento = '{num_documento}'"
        resultado = BaseDatos.consultarBD(sql)

        existe = resultado[0][0] > 0 if resultado and resultado[0] else False

        if existe:
            LogManager.escribir_log(
                "WARNING", f"Número documento duplicado detectado: {num_documento}")

        return existe

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error verificando duplicado: {e}")
        return False


# ==================== FUNCIONES DE NAVEGACIÓN ====================

@with_timeout_check
def inicializar_navegacion():
    """Inicializa el navegador y va a la página de CREA"""
    try:
        LogManager.escribir_log("INFO", "Inicializando navegación CREA...")

        # Inicializar Playwright
        manager = PlaywrightManager(
            headless=False, download_path=RUTAS_CONFIG['descargas'])
        playwright, browser, context, page = manager.iniciar_navegador()

        LogManager.escribir_log("INFO", f"Navegando a: {URLS['login']}")
        page.goto(URLS['login'], timeout=60000)
        page.wait_for_load_state('networkidle', timeout=30000)

        LogManager.escribir_log("INFO", "Página CREA cargada correctamente")
        return playwright, browser, context, page

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error inicializando navegación: {e}")
        return None, None, None, None


@with_timeout_check
def realizar_login(page, usuario, clave):
    """Realiza el proceso de login en CREA usando componentes modernos"""
    try:
        LogManager.escribir_log("INFO", "Iniciando proceso de login...")

        # ✅ USAR ComponenteInteraccion existente
        if not ComponenteInteraccion.escribirComponente(page, "#identificacionLogin", usuario, descripcion="Usuario"):
            raise Exception("No se pudo llenar el campo de usuario")

        if not ComponenteInteraccion.escribirComponente(page, "#password", clave, descripcion="Contraseña"):
            raise Exception("No se pudo llenar el campo de contraseña")

        # ✅ USAR ComponenteInteraccion existente
        if not ComponenteInteraccion.clickComponente(page, "#login", descripcion="Botón Login"):
            raise Exception("No se pudo hacer clic en el botón de login")

        LogManager.escribir_log("INFO", "Credenciales enviadas")

        # ✅ USAR ComponenteInteraccion existente
        if not ComponenteInteraccion.esperarElemento(page, "#txtPing", descripcion="Campo de token"):
            raise Exception("No apareció el campo de token")

        LogManager.escribir_log("INFO", "Campo de token detectado")
        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error en login: {e}")
        return False


@with_timeout_check
def procesar_token_correo(page):
    """Obtiene el token del correo y lo ingresa usando componentes modernos"""
    try:
        LogManager.escribir_log("INFO", "Obteniendo token del correo...")

        # Obtener código del correo usando configuración automática
        codigo = CorreoManager.obtener_codigo_correo(
            asunto="Nuevo token", intentos=15, espera=4
        )

        if not codigo:
            raise Exception("No se pudo obtener el token del correo")

        LogManager.escribir_log("INFO", f"Token obtenido: {codigo}")

        # ✅ USAR ComponenteInteraccion existente
        if not ComponenteInteraccion.escribirComponente(page, "#txtPing", codigo, descripcion="Token"):
            raise Exception("No se pudo llenar el campo de token")

        # ✅ USAR ComponenteInteraccion existente
        if not ComponenteInteraccion.clickComponente(page, "#btnValidaPing", descripcion="Validar Token"):
            raise Exception("No se pudo hacer clic en validar token")

        LogManager.escribir_log("INFO", "Token validado correctamente")
        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error procesando token: {e}")
        return False


@with_timeout_check
def navegar_a_estado_cuenta(page):
    """Navega a la sección de estado de cuenta usando componentes modernos"""
    try:
        LogManager.escribir_log("INFO", "Navegando a estado de cuenta...")

        # ✅ USAR ComponenteInteraccion existente
        if not ComponenteInteraccion.esperarElemento(page, "#MainContent_grdCuenAhoSocios", descripcion="Tabla de cuentas"):
            raise Exception("No se encontró la tabla de cuentas")

        # ✅ USAR ComponenteInteraccion existente
        enlace_selector = "#MainContent_grdCuenAhoSocios a:has-text('Est. Cuenta')"

        if not ComponenteInteraccion.esperarElemento(page, enlace_selector, descripcion="Enlace Estado Cuenta"):
            raise Exception("No se encontró el enlace 'Est. Cuenta'")

        if not ComponenteInteraccion.clickComponente(page, enlace_selector, descripcion="Est. Cuenta"):
            raise Exception("No se pudo hacer clic en 'Est. Cuenta'")

        LogManager.escribir_log("INFO", "Haciendo clic en 'Est. Cuenta'")

        # ✅ CORRECCIÓN: Esperar un momento antes de buscar el iframe
        LogManager.escribir_log("INFO", "Esperando carga del iframe...")
        time.sleep(2)  # Dar tiempo para que aparezca el iframe
        # ✅ El iframe puede estar presente inmediatamente, usar múltiples selectores
        iframe_selector = "iframe#MainContent_Iframe1"

        iframe = None
       
        if ComponenteInteraccion.esperarElemento(page, iframe_selector, descripcion=f"Iframe con selector {iframe_selector}"):
            iframe = page.frame_locator(iframe_selector)
            LogManager.escribir_log(
                "INFO", f"✅ Iframe encontrado con selector: {iframe_selector}")
        else:
            LogManager.escribir_log(
                "ERROR", f"No se encontró el iframe con selector: {iframe_selector}")
            return None

        try:
            # Esperar que aparezca el dropdown de meses dentro del iframe
            dropdown_locator = iframe.locator(
                "select[name='ctl00$MainContent$DropDownMeses']")
            dropdown_locator.wait_for(timeout=15000)
            LogManager.escribir_log(
                "INFO", "✅ Contenido del iframe cargado correctamente")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"El iframe se encontró pero su contenido no se cargó completamente: {e}")
            # Intentar esperar un poco más
            time.sleep(3)

        LogManager.escribir_log(
            "INFO", "Navegación a estado de cuenta completada")
        return iframe

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error navegando a estado cuenta: {e}")
        return None


@with_timeout_check
def seleccionar_mes_y_consultar(page, iframe):
    """Selecciona el mes disponible y ejecuta la consulta usando componentes modernos"""
    try:
        # El dropdown ya está cargado según el HTML del iframe
        select_selector = "select[name='ctl00$MainContent$DropDownMeses']"

        # ✅ Esperar elemento en iframe usando wait_for
        dropdown_locator = iframe.locator(select_selector)
        dropdown_locator.wait_for(timeout=30000)

        # Obtener todas las opciones disponibles
        opciones = iframe.locator(f"{select_selector} option").all()

        if not opciones:
            raise Exception("No se encontraron opciones en el dropdown")

        # Seleccionar la primera opción disponible (mes más reciente)
        primera_opcion = opciones[0]
        mes_texto = primera_opcion.inner_text().strip()

        LogManager.escribir_log("INFO", f"Seleccionando mes: {mes_texto}")

        # ✅ Seleccionar opción usando locator (primer mes de la lista)
        iframe.locator(select_selector).select_option(index=0)

        # ✅ Hacer clic en "Buscar" - Usando el ID exacto del HTML
        boton_buscar = "#MainContent_lnkbtnBuscarMovimientos"

        LogManager.escribir_log(
            "INFO", "Haciendo clic en 'Buscar movimientos'")
        iframe.locator(boton_buscar).click()

        # ✅ Esperar a que se carguen los resultados
        LogManager.escribir_log("INFO", "Esperando carga de movimientos...")
        page.wait_for_load_state('networkidle', timeout=30000)

        return mes_texto

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error seleccionando mes: {e}")
        return None


@with_timeout_check
def descargar_excel(page, iframe, adicional=""):
    """Descarga el archivo Excel con los movimientos usando componentes modernos"""
    try:
        LogManager.escribir_log("INFO", "Iniciando descarga de Excel...")

        # ✅ Esperar botón de descarga en iframe - Usando el ID exacto del HTML
        boton_excel = "#MainContent_lnkBtnExcel"

        # Verificar que el botón existe
        excel_locator = iframe.locator(boton_excel)
        excel_locator.wait_for(timeout=30000)

        # Configurar la escucha de descargas
        download_path = RUTAS_CONFIG['descargas']

        with page.expect_download() as download_info:
            # ✅ Hacer clic en descarga usando locator
            excel_locator.click()

            # Esperar a que se complete la descarga
            download = download_info.value

        # Generar nombre único para el archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_base = f"CREA_{adicional}.xlsx" if adicional else f"CREA_{timestamp}.xlsx"
        nombre_base = nombre_base.replace(" ", "_")

        # Ruta de destino
        archivo_destino = os.path.join(download_path, nombre_base)

        # ✅ Obtener la ruta del archivo temporal antes de moverlo
        try:
            ruta_temporal = download.path()
            LogManager.escribir_log("DEBUG", f"Archivo temporal creado en: {ruta_temporal}")
        except Exception as e:
            LogManager.escribir_log("WARNING", f"No se pudo obtener ruta temporal: {e}")
            ruta_temporal = None

        # Mover el archivo descargado
        download.save_as(archivo_destino)
        
        # ✅ Eliminar archivo temporal si existe
        if ruta_temporal and os.path.exists(ruta_temporal):
            try:
                os.remove(ruta_temporal)
                LogManager.escribir_log("DEBUG", f"Archivo temporal eliminado: {ruta_temporal}")
            except Exception as e:
                LogManager.escribir_log("WARNING", f"No se pudo eliminar archivo temporal: {e}")
        else:
            LogManager.escribir_log("DEBUG", "No se encontró archivo temporal para eliminar")

        return archivo_destino

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error descargando Excel: {e}")
        return None


@with_timeout_check
def cerrar_sesion(page, iframe):
    """Cierra la sesión correctamente usando componentes modernos"""
    try:
        LogManager.escribir_log("INFO", "Cerrando sesión...")

        # ✅ Hacer clic para salir del módulo usando locator
        boton_cancelar = "#MainContent_brnCancelar"

        try:
            iframe.locator(boton_cancelar).click()
            LogManager.escribir_log("INFO", "Clic exitoso en Cancelar/Salir")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"No se pudo hacer clic en Cancelar: {e}")

        # ✅ USAR esperas existentes
        esperarConLoaderSimple(2, "Esperando navegación")

        # ✅ USAR ComponenteInteraccion existente para cerrar sesión
        boton_logout = "#LinkButton1"

        if ComponenteInteraccion.esperarElemento(page, boton_logout, descripcion="Botón Cerrar Sesión"):
            if ComponenteInteraccion.clickComponente(page, boton_logout, descripcion="Cerrar Sesión"):
                LogManager.escribir_log("INFO", "Sesión cerrada correctamente")
            else:
                LogManager.escribir_log(
                    "WARNING", "No se pudo cerrar sesión completamente")
        else:
            LogManager.escribir_log(
                "WARNING", "No se encontró el botón de cerrar sesión")

        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error cerrando sesión: {e}")
        return False


# ==================== FUNCIONES DE PROCESAMIENTO DE ARCHIVOS ====================

def procesar_archivo_excel(ruta_archivo, id_ejecucion):
    """Procesa el archivo Excel descargado de CREA"""
    try:
        LogManager.escribir_log(
            "INFO", f"Procesando archivo: {os.path.basename(ruta_archivo)}")

        # Leer el archivo Excel usando componentes comunes
        contenido = LectorArchivos.leerExcel(ruta_archivo)
        if contenido is None:
            LogManager.escribir_log(
                "ERROR", f"No se pudo leer el archivo: {ruta_archivo}")
            return False

        # ✅ Extraer información del encabezado según formato CREA
        try:
            # Fila 2 (índice 1), Columna G (índice 6) = Número de cuenta
            num_cuenta = contenido[1][6] if len(contenido) > 1 and len(contenido[1]) > 6 else "CUENTA_NO_ENCONTRADA"
            
            # Fila 3 (índice 2), Columna C (índice 2) = Empresa
            empresa_raw = contenido[2][2] if len(contenido) > 2 and len(contenido[2]) > 2 else "EMPRESA_NO_ENCONTRADA"
            
            LogManager.escribir_log("INFO", f"Datos del encabezado - Cuenta: {num_cuenta}, Empresa: {empresa_raw}")
        except Exception as e:
            LogManager.escribir_log("WARNING", f"Error leyendo encabezado: {e}")
            num_cuenta = "CUENTA_NO_ENCONTRADA"
            empresa_raw = "EMPRESA_NO_ENCONTRADA"

        # Procesar nombre de empresa según lógica original
        if empresa_raw and "-" in str(empresa_raw):
            empresa = str(empresa_raw).split("-", 1)[-1].strip()
        else:
            empresa = str(empresa_raw) if empresa_raw else "N/A"

        LogManager.escribir_log(
            "INFO", f"Procesando datos para cuenta: {num_cuenta}, empresa: {empresa}")

        # Obtener rango de fechas del archivo para la consulta previa
        fechas_archivo = []
        movimientos_datos = []

        # Los datos empiezan en la fila 9 según formato CREA
        for row_num, row in enumerate(contenido[8:], start=9):
            try:
                # ✅ Verificar que la fila tiene suficientes columnas
                if not row or len(row) < 10:
                    LogManager.escribir_log("DEBUG", f"Fila {row_num}: Insuficientes columnas ({len(row) if row else 0})")
                    continue

                 # ✅ Extraer datos de la fila según formato CREA (usando índices de lista)
                fecha = row[1] if len(row) > 1 else None
                tipo_raw = row[2] if len(row) > 2 else None
                valor_credito = row[3] if len(row) > 3 else None
                valor_debito = row[4] if len(row) > 4 else None
                saldo = row[6] if len(row) > 6 else None
                observaciones = row[7] if len(row) > 7 else None
                num_doc_original = row[8] if len(row) > 8 else None
                ordenante = row[9] if len(row) > 9 else None
                
                concepto = f"{tipo_raw} || {observaciones}" if observaciones else str(tipo_raw) if tipo_raw else ""


                 # Validar datos obligatorios
                if not fecha or not tipo_raw or saldo is None:
                    LogManager.escribir_log("DEBUG", f"Fila {row_num}: Datos obligatorios faltantes - fecha: {fecha}, tipo: {tipo_raw}, saldo: {saldo}")
                    continue

                # Extraer tipo de transacción
                import re
                match = re.search(r"N/([CD])", str(tipo_raw).upper())
                tipo = match.group(1) if match else ""

                if not tipo:
                    LogManager.escribir_log("DEBUG", f"Fila {row_num}: No se pudo determinar tipo de transacción para '{tipo_raw}'")
                    continue

                # Determinar valor según tipo
                if tipo == "C":
                    valor = float(valor_credito) if valor_credito and str(valor_credito).strip() not in ['', 'None', '0'] else 0.0
                elif tipo == "D":
                    valor = float(valor_debito) if valor_debito and str(valor_debito).strip() not in ['', 'None', '0'] else 0.0
                else:
                    valor = 0.0

                
                # ✅ Formatear fecha - manejo mejorado para lista de listas
                fecha_obj = None
                fecha_fmt = None

                if hasattr(fecha, 'strftime'):
                    # Es un objeto datetime
                    fecha_fmt = fecha.strftime("%Y-%m-%d")
                    fecha_obj = fecha
                elif isinstance(fecha, str) and fecha.strip():
                    # Es un string, intentar parsearlo
                    try:
                        formatos_fecha = ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y', '%Y-%m-%d %H:%M:%S']
                        
                        for formato in formatos_fecha:
                            try:
                                fecha_obj = datetime.strptime(fecha.strip(), formato)
                                fecha_fmt = fecha_obj.strftime("%Y-%m-%d")
                                break
                            except ValueError:
                                continue
                        
                        if not fecha_obj:
                            LogManager.escribir_log("WARNING", f"No se pudo parsear fecha '{fecha}' en fila {row_num}")
                            continue
                    except Exception as e:
                        LogManager.escribir_log("WARNING", f"Error procesando fecha '{fecha}' en fila {row_num}: {e}")
                        continue
                elif isinstance(fecha, (int, float)):
                    # Puede ser un número de Excel (fecha serial)
                    try:
                        # Excel epoch: 1900-01-01 (con corrección del bug de 1900)
                        if fecha > 25569:  # Después de 1970-01-01
                            fecha_obj = datetime(1970, 1, 1) + timedelta(days=fecha - 25569)
                            fecha_fmt = fecha_obj.strftime("%Y-%m-%d")
                        else:
                            LogManager.escribir_log("WARNING", f"Fecha numérica inválida en fila {row_num}: {fecha}")
                            continue
                    except Exception as e:
                        LogManager.escribir_log("WARNING", f"Error convirtiendo fecha numérica en fila {row_num}: {e}")
                        continue
                else:
                    LogManager.escribir_log("WARNING", f"Formato de fecha no reconocido en fila {row_num}: {fecha} (tipo: {type(fecha)})")
                    continue

                # Agregar fecha al listado
                if fecha_fmt and fecha_fmt not in fechas_archivo:
                    fechas_archivo.append(fecha_fmt)

                # ✅ Convertir saldo a float de manera segura
                try:
                    saldo_float = float(saldo) if saldo and str(saldo).strip() not in ['', 'None'] else 0.0
                except (ValueError, TypeError):
                    saldo_float = 0.0

                # Guardar datos del movimiento
                movimientos_datos.append({
                    'fecha': fecha_fmt,
                    'fecha_obj': fecha_obj,
                    'tipo': tipo,
                    'valor': valor,
                    'saldo': saldo_float,
                    'num_doc_original': str(num_doc_original) if num_doc_original and str(num_doc_original).strip() not in ['', 'None'] else "",
                    'ordenante': str(ordenante) if ordenante and str(ordenante).strip() not in ['', 'None'] else "",
                    'concepto': concepto,
                    'row_num': row_num
                })

                LogManager.escribir_log("DEBUG", f"Fila {row_num} procesada: {fecha_fmt}, {tipo}, {valor}")

            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error procesando fila {row_num}: {e}")
                continue

        if not fechas_archivo:
            LogManager.escribir_log(
                "WARNING", "No se encontraron fechas válidas en el archivo")
            return False

        LogManager.escribir_log("INFO", f"📊 Total de movimientos válidos encontrados: {len(movimientos_datos)}")

        # Obtener rango de fechas
        fecha_min = min(fechas_archivo)
        fecha_max = max(fechas_archivo)
        LogManager.escribir_log(
            "INFO", f"📅 Rango de fechas: {fecha_min} a {fecha_max}")

        # Consultar registros existentes en la BD
        sql_consulta = f"""
            SELECT numDocumento, fechaTransaccion, valor, tipo, conceptoTransaccion
            FROM {DATABASE}
            WHERE numCuenta = '{num_cuenta}' 
            AND banco = '{CONFIG_CREA['banco_codigo']}' 
            AND empresa = '{empresa}' 
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
            "INFO", f"📋 Se encontraron {len(combinaciones_existentes)} combinaciones existentes en BD")

        # Procesar movimientos del archivo
        movimientos_insertados = 0
        movimientos_omitidos = 0
        documentos_procesados_en_memoria = set()

        for movimiento in movimientos_datos:
            try:
                # Filtrar por fecha (solo registros posteriores a 2024-02-28)
                if datetime.strptime(movimiento['fecha'], "%Y-%m-%d") <= datetime.strptime("2024-02-28", "%Y-%m-%d"):
                    LogManager.escribir_log("DEBUG", f"Movimiento anterior a 2024-03-01, omitido: {movimiento['fecha']}")
                    continue

                # Generar número de documento único
                num_documento = generar_num_documento(
                    movimiento['fecha_obj'], movimiento['valor'],
                    movimiento['tipo'], movimiento['num_doc_original']
                )

                # Verificar duplicados en BD
                if verificar_duplicado(num_documento, None):
                    LogManager.escribir_log(
                        "WARNING", f"Movimiento duplicado omitido (BD): {num_documento}")
                    movimientos_omitidos += 1
                    continue

                # Verificar duplicados en memoria
                if num_documento in documentos_procesados_en_memoria:
                    num_documento = asegurar_numero_unico(
                        num_documento, documentos_existentes_en_bd, documentos_procesados_en_memoria)

                # Verificar duplicado por combinación
                clave_combinacion = f"{movimiento['fecha']}|{movimiento['valor']}|{movimiento['tipo']}|{movimiento['concepto'][:50]}"
                if clave_combinacion in combinaciones_existentes:
                    LogManager.escribir_log(
                        "WARNING", f"Movimiento duplicado por combinación omitido")
                    movimientos_omitidos += 1
                    continue

                # Agregar a memoria
                documentos_procesados_en_memoria.add(num_documento)
                combinaciones_existentes.add(clave_combinacion)

                # Limpiar strings para SQL
                concepto_limpio = movimiento['concepto'].replace("'", "''") if movimiento['concepto'] else ""
                ordenante_limpio = movimiento['ordenante'].replace("'", "''") if movimiento['ordenante'] else ""
                empresa_limpio = str(empresa).replace("'", "''")

                # Insertar en base de datos
                sql_insert = f"""
                    INSERT INTO {DATABASE} (
                        numCuenta, banco, empresa, numDocumento,
                        fechaTransaccion, tipo, valor, saldoContable,
                        conceptoTransaccion, ordenante, idEjecucion
                    )
                    VALUES (
                        '{num_cuenta}', '{CONFIG_CREA['banco_codigo']}', '{empresa_limpio}', '{num_documento}',
                        '{movimiento['fecha']}', '{movimiento['tipo']}', {movimiento['valor']}, {movimiento['saldo']},
                        '{concepto_limpio}', '{ordenante_limpio}', {id_ejecucion}
                    )
                """

                if BaseDatos.ejecutarSQL(sql_insert):
                    movimientos_insertados += 1
                    LogManager.escribir_log(
                        "DEBUG", f"Movimiento insertado: {num_documento} - {movimiento['valor']} - {movimiento['tipo']}")
                else:
                    LogManager.escribir_log(
                        "WARNING", f"Error insertando movimiento: {num_documento}")
                    movimientos_omitidos += 1

            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error procesando movimiento fila {movimiento['row_num']}: {str(e)}")
                movimientos_omitidos += 1
                continue

        # Resumen final
        LogManager.escribir_log("INFO", f"=== RESUMEN PROCESAMIENTO ===")
        LogManager.escribir_log("INFO", f"🏢 Empresa: {empresa}")
        LogManager.escribir_log("INFO", f"💳 Cuenta: {num_cuenta}")
        LogManager.escribir_log(
            "INFO", f"📊 Total movimientos procesados: {len(movimientos_datos)}")
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
                "INFO", f"Archivo eliminado: {os.path.basename(ruta_archivo)}")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"No se pudo eliminar el archivo: {e}")

        return movimientos_insertados, movimientos_omitidos

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando archivo Excel: {e}")
        return 0, 0


def asegurar_numero_unico(num_documento_base, documentos_bd, documentos_memoria):
    """Asegura que el número de documento sea único"""
    try:
        if num_documento_base not in documentos_bd and num_documento_base not in documentos_memoria:
            return num_documento_base

        sufijo = 1
        while True:
            num_documento_con_sufijo = f"{num_documento_base}_{sufijo}"
            if num_documento_con_sufijo not in documentos_bd and num_documento_con_sufijo not in documentos_memoria:
                LogManager.escribir_log(
                    "DEBUG", f"Número único generado: {num_documento_con_sufijo}")
                return num_documento_con_sufijo
            sufijo += 1

            if sufijo > 100:
                timestamp = int(time.time())
                return f"{num_documento_base}_{timestamp}"

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error asegurando número único: {str(e)}")
        return f"{num_documento_base}_{int(time.time())}"


# ==================== FUNCIÓN PRINCIPAL ====================

@with_timeout_check
def ejecutar_proceso_crea():
    """Función principal que ejecuta todo el proceso de CREA"""
    id_ejecucion = obtenerIDEjecucion()

    LogManager.iniciar_proceso(NOMBRE_BANCO, id_ejecucion, f"Automatización {NOMBRE_BANCO} - Id de ejecución: {id_ejecucion}")
    # Inicializar timeout
    timeout_manager.start()
    tiempo_inicio = datetime.now()

    playwright = None
    browser = None
    context = None
    page = None

    try:
        # ===== 1. CONFIGURACIONES =====
        LogManager.escribir_log("INFO", "📋 Cargando configuraciones...")

        # Leer credenciales del banco
        credenciales_banco = LectorArchivos.leerCSV(
            RUTAS_CONFIG['credenciales_banco'],
            filtro_columna=0,
            valor_filtro=CONFIG_CREA['banco_codigo']
        )

        if not credenciales_banco:
            raise Exception(
                f"No se encontraron credenciales para {CONFIG_CREA['banco_codigo']}")

        # Extraer datos de configuración del banco
        USUARIO = credenciales_banco[0][1]
        CLAVE = credenciales_banco[0][2]

        LogManager.escribir_log("INFO", f"Usuario configurado: {USUARIO}")
        LogManager.escribir_log(
            "INFO", "✅ Configuraciones cargadas correctamente")

        # ===== 2. ID DE EJECUCIÓN =====

        # Registrar inicio de ejecución (si la tabla existe)
        try:
            sql_inicio = f"""
                INSERT INTO {DATABASE_RUNS} (idAutomationRun, processName, startDate, finalizationStatus) 
                VALUES ('{id_ejecucion}', 'Descarga Transacciones-{NOMBRE_BANCO}', GETDATE(), 'Running')
            """
            BaseDatos.insertarBD(sql_inicio)
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"No se pudo registrar en tabla de ejecuciones: {e}")
            LogManager.escribir_log(
                "INFO", f"Continuando con ejecución local: {id_ejecucion}")

        # ===== 3. INICIALIZACIÓN =====
        LogManager.escribir_log("INFO", "🚀 Inicializando componentes...")

        playwright, browser, context, page = inicializar_navegacion()
        if not page:
            raise Exception("Error inicializando navegación")

        # ===== 4. PROCESO DE LOGIN =====
        LogManager.escribir_log("INFO", "🔐 Ejecutando proceso de login...")

        if not realizar_login(page, USUARIO, CLAVE):
            raise Exception("Error en el proceso de login")

        if not procesar_token_correo(page):
            raise Exception("Error procesando token del correo")

        LogManager.escribir_log("INFO", "✅ Login completado exitosamente")

        # ===== 5. NAVEGACIÓN A ESTADO DE CUENTA =====
        LogManager.escribir_log("INFO", "📊 Navegando a estado de cuenta...")

        iframe = navegar_a_estado_cuenta(page)
        if not iframe:
            raise Exception("Error navegando a estado de cuenta")

        # ===== 6. CONSULTA Y DESCARGA =====
        LogManager.escribir_log("INFO", "🔍 Ejecutando consulta y descarga...")

        # ✅ CORRECCIÓN: Pasar el iframe a la función
        mes_seleccionado = seleccionar_mes_y_consultar(page, iframe)
        if not mes_seleccionado:
            raise Exception("Error en la consulta de movimientos")

         # Generar adicional para nombre de archivo
        adicional = f"{mes_seleccionado}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        archivo_descargado = descargar_excel(page, iframe, adicional=adicional)
        if not archivo_descargado:
            raise Exception("Error descargando archivo Excel")

        LogManager.escribir_log(
            "INFO", f"✅ Archivo descargado: {os.path.basename(archivo_descargado)}")

        # ===== 7. PROCESAMIENTO DE DATOS =====

        movimientos_procesados, movimientos_omitidos = procesar_archivo_excel(
            archivo_descargado, id_ejecucion)

        LogManager.escribir_log(
            "INFO", f"✅ Movimientos procesados: {movimientos_procesados}")
        if movimientos_omitidos > 0:
            LogManager.escribir_log(
                "WARNING", f"⚠️ Movimientos omitidos (duplicados): {movimientos_omitidos}")

        # ===== 8. CIERRE DE SESIÓN =====
        LogManager.escribir_log("INFO", "🔒 Cerrando sesión...")

        cerrar_sesion(page, iframe)

        # ===== 9. FINALIZACIÓN EXITOSA =====
        tiempo_fin = datetime.now()
        tiempo_total = formatear_tiempo_ejecucion(tiempo_fin - tiempo_inicio)

        # Finalizar ejecución con éxito
        try:
            sql_fin = f"""
                UPDATE {DATABASE_RUNS} 
                SET finalizationStatus = 'Success', endDate = GETDATE()
                WHERE idAutomationRun = '{id_ejecucion}'
            """
            BaseDatos.ejecutarSQL(sql_fin)
            LogManager.escribir_log(
                "INFO", "Estado de ejecución actualizado a Success en BD")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"No se pudo actualizar estado en BD: {e}")

        # Log final de éxito
        mensaje_exito = f"Proceso {NOMBRE_BANCO} completado exitosamente"
        escribirLog("SUCCESS", mensaje_exito, id_ejecucion, "PROCESS_COMPLETE")

        LogManager.escribir_log("INFO", "=" * 80)
        LogManager.escribir_log("INFO", "✅ PROCESO COMPLETADO EXITOSAMENTE")
        LogManager.escribir_log(
            "INFO", f"Movimientos procesados: {movimientos_procesados}")
        LogManager.escribir_log(
            "INFO", f"Tiempo total de ejecución: {tiempo_total}")
        LogManager.escribir_log("INFO", f"ID de ejecución: {id_ejecucion}")
        LogManager.escribir_log("INFO", "=" * 80)

        return True

    except Exception as e:
        # ===== MANEJO DE ERRORES =====
        tiempo_fin = datetime.now()
        tiempo_total = formatear_tiempo_ejecucion(tiempo_fin - tiempo_inicio)

        error_msg = f"Error en proceso CREA: {str(e)}"
        LogManager.escribir_log("ERROR", "=" * 80)
        LogManager.escribir_log("ERROR", "❌ PROCESO FINALIZADO CON ERRORES")
        LogManager.escribir_log("ERROR", error_msg)
        LogManager.escribir_log(
            "ERROR", f"Tiempo de ejecución: {tiempo_total}")
        LogManager.escribir_log("ERROR", "=" * 80)

        # Finalizar ejecución con error
        if id_ejecucion:
            try:
                sql_error = f"""
                    UPDATE {DATABASE_RUNS} 
                    SET finalizationStatus = 'Error', endDate = GETDATE()
                    WHERE idAutomationRun = '{id_ejecucion}'
                """
                BaseDatos.ejecutarSQL(sql_error)
                LogManager.escribir_log(
                    "INFO", "Estado de ejecución actualizado a Error en BD")
            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"No se pudo actualizar estado de error en BD: {e}")

            # Log final de error
            escribirLog("ERROR", error_msg, id_ejecucion, "PROCESS_ERROR")

        return False

    finally:
        # ===== LIMPIEZA FINAL =====
        timeout_manager.stop()

        if browser:
            try:
                browser.close()
                LogManager.escribir_log(
                    "INFO", "🧹 Navegador cerrado correctamente")
            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error cerrando navegador: {e}")

        if playwright:
            try:
                playwright.stop()
                LogManager.escribir_log(
                    "INFO", "🧹 Playwright cerrado correctamente")
            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error cerrando playwright: {e}")

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
    """Función principal del robot CREA"""

    id_ejecucion = None
    inicio_ejecucion = datetime.now()

    try:
        # Ejecutar proceso principal
        exito = ejecutar_proceso_crea()

        if exito:
            tiempo_total = formatear_tiempo_ejecucion(
                datetime.now() - inicio_ejecucion)
            LogManager.finalizar_proceso(
                NOMBRE_BANCO, True, f"Proceso completado exitosamente (Tiempo: {tiempo_total})")
            
            # Ejecutar BAT final en caso de error
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final de emergencia...")
            SubprocesoManager.ejecutar_bat_final()
            return True
        else:
            tiempo_total = formatear_tiempo_ejecucion(
                datetime.now() - inicio_ejecucion)
            LogManager.finalizar_proceso(
                NOMBRE_BANCO, False, f"Proceso finalizado con errores (Tiempo: {tiempo_total})")
            # Ejecutar BAT final en caso de error
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final de emergencia...")
            SubprocesoManager.ejecutar_bat_final()
            return False

    except Exception as e:
        tiempo_total = formatear_tiempo_ejecucion(
            datetime.now() - inicio_ejecucion)
        LogManager.escribir_log(
            "ERROR", f"❌ Error en {NOMBRE_BANCO}: {str(e)} (Tiempo: {tiempo_total})")

        LogManager.finalizar_proceso(
            NOMBRE_BANCO, False, f"Error crítico: {str(e)}")
        # Ejecutar BAT final en caso de error
        LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final de emergencia...")
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

# ==================== SCRIPT PRINCIPAL ====================


if __name__ == "__main__":
    try:
        exito = main()
        if exito:
            LogManager.escribir_log(
                "SUCCESS", f"Robot {NOMBRE_BANCO} finalizado exitosamente")
            sys.exit(0)
        else:
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
