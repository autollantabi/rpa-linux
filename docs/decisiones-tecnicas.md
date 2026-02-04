# Decisiones técnicas

Justificación de tecnologías elegidas, alternativas que se infieren del código y trade-offs importantes.

---

## Lenguaje y entorno

- **Python 3.8+:** Permite usar Playwright, pyodbc, openpyxl e imapclient de forma estándar; el código es procedural/por scripts, sin framework web.
- **Entorno virtual (venv):** Recomendado en README y en scripts Bash para aislar dependencias; no hay Docker ni contenedores en el repo.
- **Linux como objetivo:** Los Bash asumen rutas y Xvfb; no hay evidencia en el repo de soporte oficial para Windows/macOS, aunque Playwright y Python son multiplataforma.

---

## Automatización web: Playwright (Chromium)

- **Por qué Playwright:** Control del navegador (Chromium), soporte de descargas, timeouts y reintentos; adecuado para portales que no exponen API.
- **Alternativas típicas:** Selenium (más antiguo, mismo enfoque); requests + parsing (no viable si el portal depende de JavaScript y flujos multi-paso).
- **Trade-off:** Cualquier cambio en el HTML o en el flujo del portal obliga a actualizar selectores (XPath/CSS) en el script del banco; no hay abstracción de “API estable”.

---

## Base de datos: SQL Server + pyodbc

- **Por qué SQL Server:** Decisión de negocio/infraestructura; el proyecto asume que ya existe el servidor y las tablas (AutomationRun, AutomationLog, RegistrosBancos u equivalente).
- **Por qué pyodbc:** Driver estándar para SQL Server en Python; connection string con ODBC Driver 18 y `TrustServerCertificate=yes`.
- **Trade-off:** Credenciales en CSV; no hay variables de entorno ni vault. Quien despliegue debe asegurar que los CSV no se suban a repos públicos.

---

## Credenciales y configuración en CSV

- **Decisión:** Credenciales y rutas en archivos CSV bajo `configBancos`, fuera del repo; rutas por defecto en `RUTAS_CONFIG` dentro de `componentes_comunes.py`.
- **Ventaja:** Fácil de editar por entorno sin tocar código; mismo código sirve para varias instalaciones.
- **Trade-off:** No hay validación de esquema ni secretos cifrados; la seguridad depende de permisos de sistema de archivos y de no versionar `configBancos`.

---

## Módulo único compartido (componentes_comunes.py)

- **Decisión:** Un solo módulo con PlaywrightManager, ComponenteInteraccion, EsperasInteligentes, LectorArchivos, LogManager, BaseDatos, CorreoManager, ConfiguracionManager, SubprocesoManager y RUTAS_CONFIG.
- **Ventaja:** Evita duplicar lógica de clic, esperas, BD, correo y logs en cada banco.
- **Trade-off:** El archivo es grande; cambios en la interfaz afectan a todos los scripts. No hay paquetes por dominio (p. ej. `bancos.core`, `bancos.adapters`).

---

## Logs: archivo por banco y ejecución

- **Decisión:** LogManager (singleton) escribe en `configBancos/logs/` con nombre que incluye ID de ejecución y banco; además imprime en consola.
- **Trade-off:** No hay rotación ni nivel configurable desde fuera; el formato es fijo (timestamp, nivel, mensaje).

---

## Timeout global por script

- **Decisión:** En los scripts con Playwright hay una clase TimeoutManager (por script) que tras N minutos (ej. 10) llama a `os._exit(1)` para evitar procesos colgados.
- **Trade-off:** Salida brusca sin cleanup ordenado del navegador; evita que cron acumule procesos.

---

## Script final de unión (UNION_BANCOS_run.sh)

- **Decisión:** Tras cada ejecución (éxito o en algunos casos fallo) se ejecuta un script externo (`RUTAS_CONFIG['bat_final']`) con timeout de 5 minutos.
- **Ventaja:** Centraliza la lógica de “unión” de datos fuera de los scripts de banco.
- **Trade-off:** Dependencia de una ruta fija y de que ese script exista y funcione; no está versionado en este repo.

---

## Sin tests automatizados en el repo

- **Estado:** No hay carpetas `tests/` ni uso de pytest/unittest en el repositorio.
- **Inferencia:** Los flujos se validan manualmente o en entorno de producción; cambios en portales o en BD pueden romper sin detección automática.
- **Recomendación (pendientes):** Ver [docs/pendientes.md](pendientes.md) para sugerencias de pruebas y deuda técnica.
