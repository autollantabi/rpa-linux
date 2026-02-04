# Guía de proyecto (onboarding)

Resumen para incorporarse al proyecto: qué es, cómo empezar, dónde está cada cosa, flujo típico para añadir funcionalidad y decisiones o código legado relevante.

---

## Qué es el proyecto

- **Nombre / contexto:** Carpeta `bancos` del repo **rpa-linux** (GitHub: autollantabi/rpa-linux).
- **Objetivo:** Automatizar la descarga de movimientos bancarios de varios bancos y cooperativas en Ecuador, normalizarlos e insertarlos en SQL Server, y ejecutar al final un script de unión de datos (`UNION_BANCOS_run.sh`).
- **Tipo:** RPA (automatización de procesos) con Python y Playwright; algunos bancos solo procesan archivos TXT o Excel ya descargados.
- **Ejecución:** Scripts Python lanzados por scripts Bash (con Xvfb en Linux cuando hay navegador) o por cron; no hay servidor ni API expuesta.

---

## Cómo empezar

1. Leer el [README.md](../README.md) y [docs/indice.md](indice.md) para tener la visión general y el orden de lectura.
2. Seguir [docs/setup.md](setup.md): requisitos, entorno virtual, dependencias, carpeta `configBancos` y ejecución de un banco (por ejemplo Guayaquil o Bolivariano).
3. Revisar [docs/arquitectura.md](arquitectura.md) para entender la estructura y el módulo `componentes_comunes.py`.
4. Revisar [docs/flujo-funcional.md](flujo-funcional.md) para el flujo de login, OTP, descarga por empresa y cierre.
5. Para integraciones externas (portales, correo, BD, script final): [docs/apis.md](apis.md).
6. Para decisiones técnicas y trade-offs: [docs/decisiones-tecnicas.md](decisiones-tecnicas.md).
7. Para mejoras y deuda técnica: [docs/pendientes.md](pendientes.md).

---

## Dónde está cada cosa

| Necesito… | Dónde está |
|-----------|-------------|
| Rutas y configuración por defecto | `componentes_comunes.py` → `RUTAS_CONFIG` |
| Credenciales y config (CSV) | Carpeta externa `configBancos/config/` (ruta en `RUTAS_CONFIG`) |
| Lógica de navegador, clic, esperas, descargas | `componentes_comunes.py` → `PlaywrightManager`, `ComponenteInteraccion`, `EsperasInteligentes` |
| Lectura de CSV/Excel/TXT | `componentes_comunes.py` → `LectorArchivos` |
| Logs por banco y ejecución | `componentes_comunes.py` → `LogManager`; archivos en `configBancos/logs/` |
| Conexión y consultas SQL | `componentes_comunes.py` → `BaseDatos` |
| Código OTP desde correo | `componentes_comunes.py` → `CorreoManager` |
| Configuraciones (fechas, etc.) | `componentes_comunes.py` → `ConfiguracionManager` |
| Script final de unión | `componentes_comunes.py` → `SubprocesoManager`; ruta en `RUTAS_CONFIG['bat_final']` |
| Flujo concreto de un banco | `Banco*_Final.py` o `Cooperativa*_Final.py` |
| Lanzadores headless / manual | `bash*.sh` en la raíz del proyecto |
| Documentación técnica | Carpeta `docs/` (este archivo y el resto) |

---

## APIs e integraciones (resumen)

- **Portales web:** Playwright (Chromium); no hay cliente HTTP manual. URLs en cada `*_Final.py` en `URLS`.
- **Correo:** IMAP (SSL) para OTP; credenciales en `credencialesCorreo.csv`; key por servidor (ej. `mail.maxximundo.com`).
- **Base de datos:** SQL Server vía pyodbc; credenciales en `credencialesDB.csv`.
- **Script final:** `UNION_BANCOS_run.sh` ejecutado por `SubprocesoManager`; ruta en `RUTAS_CONFIG['bat_final']`.

Detalle en [docs/apis.md](apis.md).

---

## Flujo típico para añadir una pantalla o funcionalidad

- **Nuevo banco/cooperativa con navegador:** Crear `*_Final.py` importando componentes comunes; implementar login, OTP si aplica, navegación a movimientos, bucle por empresas (descarga → procesar → insertar); registrar inicio/fin en BD y llamar a `SubprocesoManager.ejecutar_bat_final()`. Añadir credenciales en CSV y un `bash*.sh` siguiendo el patrón de los existentes. Ver [docs/arquitectura.md](arquitectura.md) sección “Cómo añadir una nueva pantalla o funcionalidad”.
- **Nuevo banco solo archivos:** Crear script similar a `BancoBolivariano_Final.py` (listar archivos, procesar cada uno, insertar en BD, script final). Añadir ruta en `RUTAS_CONFIG` si hace falta.
- **Nuevo paso dentro de un banco existente:** Añadir función en el `*_Final.py` correspondiente usando `ComponenteInteraccion` y `EsperasInteligentes`, e invocarla desde el flujo principal.

---

## Decisiones históricas o código legado relevante

- **Pichincha:** El banco exige 2FA por celular; la automatización completa está limitada. Existe subida manual de movimientos en horarios fijos (11:30 y 17:00, hora Ecuador). `BancoPichincha_Final.py` existe pero puede estar sin uso activo; `2BancoPichincha_Final.py` procesa archivos CSV.
- **Cooperativa CREA:** Ya no existe la cooperativa; `CooperativaCREA_Final.py` y `bashCREA.sh` están obsoletos.
- **JEP:** Tiene modo automático (Playwright) y modo manual (`--manual` / `bashJEP_manual.sh`) cuando los archivos Excel ya están en la carpeta de descargas con nombres concretos (jepAutollanta.xlsx, etc.). La cuenta del Tecnicentro se identifica en el código (línea ~125 en `CooperativaJEP_Final.py`).
- **Rutas fijas:** Los scripts Bash y `RUTAS_CONFIG` usan rutas como `/home/administrador/Escritorio/bancos` y `/home/administrador/configBancos`. En otra máquina o usuario hay que editar los `.sh` y/o `RUTAS_CONFIG`.
- **Sin requirements.txt:** Las dependencias están documentadas en README y en [docs/setup.md](setup.md): playwright, pyodbc, openpyxl, imapclient, pandas.
- **Tabla de runs:** En algunos scripts el `processName` del INSERT en `AutomationRun` sigue diciendo "Banco Guayaquil" (ej. JEP); es un copy-paste sin corregir, no afecta la lógica si el nombre del banco se usa en otros sitios desde `NOMBRE_BANCO`.

---

## Contacto o autor

- **Desarrollador original:** Diego Barbecho.  
- **GitHub:** [diegobarpdev](https://github.com/diegobarpdev).  
- **Repositorio del proyecto:** [autollantabi/rpa-linux](https://github.com/autollantabi/rpa-linux) (carpeta `bancos`).

Para dudas sobre negocio o convenios con bancos/cooperativas, contactar al equipo o titular del repo según corresponda.
