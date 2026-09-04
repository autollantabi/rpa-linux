# -*- coding: utf-8 -*-
"""
sesion_persistente.py

Mantiene UNA sola sesión de navegador abierta (login inicial con
usuario/contraseña + reCAPTCHA + 2FA, como ya lo teníamos) y permite
refrescar el token de acceso cuantas veces sea necesario SIN repetir el
login, aprovechando la renovación silenciosa de MSAL (usa la cookie de
sesión de Azure B2C, sin interacción del usuario).

Límite real: esto funciona mientras la sesión de B2C siga viva. Si el
usuario cierra sesión, o la sesión expira por completo (política de B2C,
usualmente horas/días de inactividad), sí va a hacer falta un login
interactivo nuevo — eso no se puede evitar, es la frontera de seguridad
real del banco.

Logging: igual que el resto de bancos (Produbanco, JEP, Guayaquil), este
script escribe a archivo vía LogManager (RUTAS_CONFIG['logs']) y registra
cada corrida en las tablas compartidas AutomationRun/AutomationLog.

IMPORTANTE: el procesamiento de los CSVs (2BancoPichincha_Final.py) se
llama DIRECTO en este mismo proceso (vía importlib, no subprocess) para
que reutilice el mismo id_ejecucion y el mismo archivo de log — antes,
lanzarlo como subprocess aparte generaba un id_ejecucion propio y un
segundo archivo de log para lo que en realidad es una sola corrida.
"""
import os
import sys
import time
import importlib
from datetime import datetime, timedelta

from componentes_comunes import (
    LectorArchivos,
    RUTAS_CONFIG,
    LogManager,
    BaseDatos,
)
from login_pichincha_selenium import crear_driver, login_pichincha
from download_by_api import obtener_sesion_api, descargar_todas_las_empresas_api

VIGENCIA_TOKEN_SEGUNDOS = 240  # el JWT dura ~300s; refrescamos con margen

# ==================== CONFIGURACIÓN GLOBAL (mismo patrón que Produbanco) ====================

DATABASE_RUNS = "AutomationRun"
DATABASE_LOGS = "AutomationLog"
NOMBRE_BANCO = "Banco Pichincha"

RUTA_DESCARGAS = RUTAS_CONFIG.get('pichincha', "/home/administrador/configBancos/Pichincha")

# "2BancoPichincha_Final" empieza con un número, así que no se puede hacer
# "import 2BancoPichincha_Final" directo (no es un identificador válido de
# Python) — se carga con importlib. Debe estar en el PYTHONPATH (ver
# bash_pichincha.sh, que ya agrega /home/administrador/Escritorio/bancos).
NOMBRE_MODULO_PROCESADOR = "2BancoPichincha_Final"



def formatear_tiempo_ejecucion(tiempo_delta):
    """Formatea un timedelta a string legible"""
    total_seconds = int(tiempo_delta.total_seconds())
    minutos = total_seconds // 60
    segundos = total_seconds % 60
    return f"{minutos}m {segundos}s"


def obtenerIDEjecucion():
    """Obtiene el siguiente ID de ejecución de la BD (misma tabla compartida
    AutomationRun que usan Produbanco/JEP/Guayaquil)."""
    try:
        sql = f"SELECT MAX(idAutomationRun) FROM {DATABASE_RUNS}"
        resultado = BaseDatos.consultarBD(sql)
        if resultado and resultado[0] and resultado[0][0]:
            return resultado[0][0] + 1
        return 1
    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error obteniendo ID ejecución: {str(e)}")
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
    """
    Escribe un log en la BD (tabla AutomationLog). Se trunca a 400
    caracteres porque el mensaje puede traer el stacktrace completo de
    Selenium/Playwright (varias líneas largas), y la columna processName
    no tiene espacio para eso — insertar sin truncar produce un error de
    SQL Server ("datos truncados") que enmascara el error real.
    """
    mensaje_una_linea = " ".join(mensaje.split())
    mensaje_truncado = mensaje_una_linea[:400]
    texto_limpio = mensaje_truncado.replace("'", "''")
    sql = f"""
        INSERT INTO {DATABASE_LOGS} (idAutomationRun, processName, dateLog, statusLog, action)
        VALUES ({id_ejecucion}, '{texto_limpio}', SYSDATETIME(), '{estado}', '{accion}')
    """
    datosEjecucion(sql)


# ==================== SESIÓN PERSISTENTE ====================


class SesionPichincha:
    def __init__(self, usuario, password, ruta_descargas=None, headless=False):
        self.usuario = usuario
        self.password = password
        self.ruta_descargas = ruta_descargas
        self.headless = headless
        self.driver = None
        self._token = None
        self._uuid = None
        self._token_obtenido_en = None

    def iniciar(self, id_ejecucion=1):
        """Login inicial completo (usuario/contraseña + reCAPTCHA + 2FA)."""
        LogManager.escribir_log("INFO", "Iniciando sesión persistente (login completo, una sola vez)...")
        self.driver = crear_driver(headless=self.headless, ruta_descargas=self.ruta_descargas)
        login_pichincha(self.driver, self.usuario, self.password, id_ejecucion=id_ejecucion)

        # Justo tras el login, MSAL todavía no guarda el access token en
        # sessionStorage — solo lo cachea cuando la SPA hace su primera
        # llamada real a la API protegida. Navegamos a la home para que
        # Angular bootstraree y dispare esa llamada (ej. a /companies),
        # y ahí sí queda cacheado el token.
        self._refrescar_token(forzar_renovacion_silenciosa=True)
        LogManager.escribir_log("SUCCESS", "Sesión lista. El navegador queda abierto en segundo plano.")

    def _token_esta_vigente(self):
        if not self._token or not self._token_obtenido_en:
            return False
        return (datetime.now() - self._token_obtenido_en) < timedelta(seconds=VIGENCIA_TOKEN_SEGUNDOS)

    def _refrescar_token(self, forzar_renovacion_silenciosa=True, intentos=5, espera_entre_intentos=2):
        """
        obtener_sesion_api() ya se encarga de navegar/recargar la página
        antes de leer los logs de red (necesario porque get_log() vacía el
        buffer en cada llamada) — aquí solo reintentamos varias veces por
        si la SPA tarda un poco más de lo esperado en disparar su llamada
        a la API tras cada intento de navegación.
        """
        ultimo_error = None
        for intento in range(1, intentos + 1):
            try:
                self._token, self._uuid = obtener_sesion_api(
                    self.driver, forzar_navegacion=forzar_renovacion_silenciosa
                )
                self._token_obtenido_en = datetime.now()
                LogManager.escribir_log("SUCCESS", f"Token actualizado (uuid de sesión: {self._uuid})")
                return
            except Exception as e:
                ultimo_error = e
                LogManager.escribir_log(
                    "WARNING", f"Token todavía no disponible (intento {intento}/{intentos}), reintentando...")
                time.sleep(espera_entre_intentos)

        raise Exception(f"No se pudo obtener el token tras {intentos} intentos: {ultimo_error}")

    def token_vigente(self):
        """
        Devuelve (token, uuid) listos para usar. Si el token está por vencer
        o ya venció, lo refresca automáticamente antes de devolverlo.
        """
        if not self.driver:
            raise Exception("Llama a iniciar() antes de pedir un token.")
        if not self._token_esta_vigente():
            self._refrescar_token(forzar_renovacion_silenciosa=True)
        return self._token, self._uuid

    def cerrar(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


# ==================== FUNCIÓN PRINCIPAL ====================


def main():
    """Función principal del robot Pichincha"""

    id_ejecucion = None
    inicio_ejecucion = datetime.now()
    sesion = None

    try:
        # Obtener ID de ejecución (misma tabla compartida que los demás bancos)
        id_ejecucion = obtenerIDEjecucion()

        LogManager.iniciar_proceso(
            NOMBRE_BANCO, id_ejecucion, f"Automatización {NOMBRE_BANCO} - ID: {id_ejecucion}")

        sql_inicio = f"""
            INSERT INTO {DATABASE_RUNS} (idAutomationRun, processName, startDate, finalizationStatus)
            VALUES ({id_ejecucion}, 'Descarga comprobantes-{NOMBRE_BANCO}', SYSDATETIME(), 'Running')
        """
        datosEjecucion(sql_inicio)
        escribirLog(f"Iniciando automatización {NOMBRE_BANCO}", id_ejecucion, "INFO", "INICIO")

        # Credenciales desde el archivo compartido de credenciales de bancos
        credenciales_banco = LectorArchivos.leerCSV(
            RUTAS_CONFIG['credenciales_banco'],
            filtro_columna=0,
            valor_filtro=NOMBRE_BANCO
        )
        usuario = credenciales_banco[0][1]
        password = credenciales_banco[0][2]

        os.makedirs(RUTA_DESCARGAS, exist_ok=True)

        sesion = SesionPichincha(usuario, password, ruta_descargas=RUTA_DESCARGAS)
        sesion.iniciar(id_ejecucion=id_ejecucion)  # login: usuario/contraseña + reCAPTCHA + 2FA

        # Descarga los 4 CSVs directo en la carpeta que espera el procesador.
        resultados = descargar_todas_las_empresas_api(sesion.driver, RUTA_DESCARGAS)

        algun_archivo_ok = any(resultados.values())
        if algun_archivo_ok:
            LogManager.escribir_log(
                "INFO", f"Llamando al procesador ({NOMBRE_MODULO_PROCESADOR}) en el mismo proceso, "
                f"reutilizando id_ejecucion={id_ejecucion}...")
            procesador = importlib.import_module(NOMBRE_MODULO_PROCESADOR)
            resultado_procesamiento = procesador.procesar_todos_los_archivos(id_ejecucion)
            LogManager.escribir_log(
                "SUCCESS",
                f"Procesamiento: {resultado_procesamiento['archivos_procesados']} archivos procesados, "
                f"{resultado_procesamiento['archivos_exitosos']} exitosos"
            )
        else:
            LogManager.escribir_log(
                "WARNING", "Ninguna empresa se descargó correctamente — no se dispara el procesamiento.")

        tiempo_total = formatear_tiempo_ejecucion(datetime.now() - inicio_ejecucion)
        LogManager.escribir_log("SUCCESS", f"✅ {NOMBRE_BANCO} completado exitosamente en {tiempo_total}")

        sql_exito = f"""
            UPDATE {DATABASE_RUNS}
            SET endDate = SYSDATETIME(), finalizationStatus = 'Exitoso'
            WHERE idAutomationRun = {id_ejecucion}
        """
        datosEjecucion(sql_exito)
        escribirLog(f"Automatización {NOMBRE_BANCO} completada exitosamente", id_ejecucion, "SUCCESS", "FIN")

        return True

    except Exception as e:
        tiempo_total = formatear_tiempo_ejecucion(datetime.now() - inicio_ejecucion)
        LogManager.escribir_log("ERROR", f"❌ Error en {NOMBRE_BANCO}: {str(e)} (Tiempo: {tiempo_total})")

        if id_ejecucion:
            sql_error = f"""
                UPDATE {DATABASE_RUNS}
                SET endDate = SYSDATETIME(), finalizationStatus = 'Error'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_error)
            escribirLog(f"Error en automatización {NOMBRE_BANCO}: {str(e)}", id_ejecucion, "ERROR", "FIN")

        return False

    finally:
        if sesion:
            sesion.cerrar()

        tiempo_total = formatear_tiempo_ejecucion(datetime.now() - inicio_ejecucion)
        LogManager.escribir_log("INFO", f"Tiempo total de ejecución: {tiempo_total}")
        LogManager.escribir_log("INFO", "=" * 60)


if __name__ == "__main__":
    try:
        exito = main()
        if exito:
            LogManager.escribir_log("SUCCESS", f"Robot {NOMBRE_BANCO} finalizado exitosamente")
            sys.exit(0)
        else:
            LogManager.escribir_log("ERROR", f"Robot {NOMBRE_BANCO} finalizado con errores")
            sys.exit(1)
    except KeyboardInterrupt:
        LogManager.escribir_log("WARNING", f"Robot {NOMBRE_BANCO} interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error fatal en robot {NOMBRE_BANCO}: {str(e)}")
        sys.exit(1)