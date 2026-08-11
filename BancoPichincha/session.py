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

Uso típico (recomendado — download_by_api maneja su propio refresh):
    from sesion_persistente import SesionPichincha
    from download_by_api import descargar_todas_las_empresas_api

    sesion = SesionPichincha(usuario, password, ruta_descargas="./reportes")
    sesion.iniciar()                                      # login una sola vez
    descargar_todas_las_empresas_api(sesion.driver, "./reportes")
    sesion.cerrar()

Uso alterno (si necesitas el token/uuid crudo para llamadas con `requests`
fuera del navegador, ej. a los endpoints de /companies o /accounts que NO
están detrás de Akamai — ver descargar_reportes_bancarios.py):
    token, uuid = sesion.token_vigente()   # se refresca solo si hace falta
"""
import time
from datetime import datetime, timedelta

from componentes_comunes import (LectorArchivos, RUTAS_CONFIG)
from login_pichincha_selenium import crear_driver, login_pichincha
from download_by_api import obtener_sesion_api

VIGENCIA_TOKEN_SEGUNDOS = 240  # el JWT dura ~300s; refrescamos con margen


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
        print("=== Iniciando sesión persistente (login completo, una sola vez) ===")
        self.driver = crear_driver(headless=self.headless, ruta_descargas=self.ruta_descargas)
        login_pichincha(self.driver, self.usuario, self.password, id_ejecucion=id_ejecucion)

        # Justo tras el login, MSAL todavía no guarda el access token en
        # sessionStorage — solo lo cachea cuando la SPA hace su primera
        # llamada real a la API protegida. Navegamos a la home para que
        # Angular bootstraree y dispare esa llamada (ej. a /companies),
        # y ahí sí queda cacheado el token.
        self._refrescar_token(forzar_renovacion_silenciosa=True)
        print("=== Sesión lista. El navegador queda abierto en segundo plano. ===")

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
                print(f"  Token actualizado (uuid de sesión: {self._uuid})")
                return
            except Exception as e:
                ultimo_error = e
                print(f"  Token todavía no disponible (intento {intento}/{intentos}), reintentando...")
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


if __name__ == "__main__":
    import os
    import sys
    import subprocess
    from download_by_api import descargar_todas_las_empresas_api

    # TODO: en producción, lee estas credenciales de un lugar seguro
    # (variable de entorno, secreto de Windows Credential Manager, etc.)
    # — no las dejes hardcodeadas como aquí en el archivo final.
    credenciales_banco = LectorArchivos.leerCSV(
        RUTAS_CONFIG['credenciales_banco'],
        filtro_columna=0,
        valor_filtro="Banco Pichincha"
    )

    USUARIO = credenciales_banco[0][1]
    PASSWORD = credenciales_banco[0][2]

    print(USUARIO, PASSWORD)

    # Misma carpeta que usa tu script de procesamiento (RUTAS_CONFIG['pichincha'])
    # — los nombres autollanta.csv/ikonix.csv/maxximundo.csv/stox.csv ya
    # coinciden con los prefijos que busca obtener_empresa_desde_nombre_archivo().
    RUTA_DESCARGAS = "/home/administrador/configBancos/Pichincha"
    os.makedirs(RUTA_DESCARGAS, exist_ok=True)

    # Script que procesa los CSVs descargados (inserta en RegistrosBancos y
    # sube el BAT final vía SubprocesoManager.ejecutar_bat_final()).
    RUTA_SCRIPT_PROCESAMIENTO = "/home/administrador/Escritorio/bancos/2BancoPichincha_Final.py"

    sesion = SesionPichincha(USUARIO, PASSWORD, ruta_descargas=RUTA_DESCARGAS)
    try:
        sesion.iniciar()  # login completo: usuario/contraseña + reCAPTCHA + 2FA

        # Descarga los 4 CSVs directo en la carpeta que espera el procesador.
        resultados = descargar_todas_las_empresas_api(sesion.driver, RUTA_DESCARGAS)

        # Si al menos un archivo se descargó bien, dispara el procesamiento
        # (inserta en la BD y sube el BAT final) usando el MISMO intérprete
        # de Python (venv) con el que está corriendo este script.
        algun_archivo_ok = any(resultados.values())
        if algun_archivo_ok:
            print(f"\nDisparando procesamiento: {RUTA_SCRIPT_PROCESAMIENTO}")
            proceso = subprocess.run(
                [sys.executable, RUTA_SCRIPT_PROCESAMIENTO],
                capture_output=True, text=True
            )
            print(proceso.stdout)
            if proceso.returncode != 0:
                print(f"  Aviso: el procesamiento terminó con código {proceso.returncode}")
                print(proceso.stderr)
        else:
            print("\nNinguna empresa se descargó correctamente — no se dispara el procesamiento.")

    finally:
        sesion.cerrar()