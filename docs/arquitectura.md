# Arquitectura del sistema

Arquitectura general, carpetas principales, responsabilidades y cómo añadir una nueva entidad o funcionalidad.

---

## Arquitectura general

El proyecto es un conjunto de **scripts RPA independientes** que comparten un único módulo común (`componentes_comunes.py`). No hay servidor ni API; cada script se ejecuta por separado (por cron o a mano) y:

1. Obtiene un ID de ejecución desde SQL Server.
2. Registra inicio en BD y en logs.
3. Según el tipo de entidad:
   - **Con navegador:** inicia Playwright → login → código por correo (si aplica) → navegación a movimientos → descarga por empresa → procesamiento de archivos.
   - **Solo archivos:** lista archivos en una carpeta → procesa cada uno (parseo, normalización, inserción en BD).
4. Al finalizar (éxito o fallo), actualiza el estado en BD, escribe en log y ejecuta el script de unión `UNION_BANCOS_run.sh`.

No hay colas ni orquestador central; la coordinación es por **cron** con horarios distintos por banco.

---

## Árbol de carpetas relevante

```
bancos/                          # Raíz del proyecto (carpeta bancos del repo)
├── componentes_comunes.py       # Módulo compartido: rutas, Playwright, BD, correo, logs, archivos
├── BancoPichincha_Final.py      # RPA Banco Pichincha (Playwright; 2FA por celular limita uso)
├── 2BancoPichincha_Final.py     # Variante: procesamiento de archivos CSV Pichincha (sin navegador)
├── BancoGuayaquil_Final.py      # RPA Banco Guayaquil
├── BancoProdubanco_Final.py    # RPA Banco Produbanco
├── BancoBolivariano_Final.py   # Solo procesamiento de archivos TXT
├── CooperativaJEP_Final.py     # RPA Cooperativa JEP + modo --manual (Excel)
├── CooperativaCREA_Final.py    # RPA Cooperativa CREA (obsoleto)
├── bashPichincha.sh            # Lanzador headless Pichincha (Xvfb + timeout)
├── bashGuayaquil.sh
├── bashProdubanco.sh
├── bashBolivariano.sh          # Sin Xvfb; solo Python
├── bashJEP.sh
├── bashJEP_manual.sh           # Solo Python, --manual
├── bashCREA.sh
├── 2bashPichincha.sh           # Lanzador para 2BancoPichincha_Final.py
├── docs/                       # Documentación técnica
│   ├── setup.md
│   ├── arquitectura.md
│   ├── apis.md
│   ├── flujo-funcional.md
│   ├── guia-proyecto.md
│   ├── decisiones-tecnicas.md
│   ├── despliegue.md
│   ├── pendientes.md
│   └── indice.md
└── README.md

# Fuera del repo (configuración por entorno)
/home/administrador/configBancos/
├── config/                     # CSV: credenciales, configuraciones, rutas
├── descargas/                  # Salida de Playwright; entrada JEP manual
├── logs/                       # Logs por banco y ejecución
└── Bolivariano/                # TXT para Banco Bolivariano
```

---

## Separación de responsabilidades

| Capa | Ubicación | Responsabilidad |
|------|-----------|------------------|
| **Configuración** | `RUTAS_CONFIG` en `componentes_comunes.py` + CSV en `configBancos` | Rutas, credenciales y parámetros por entorno. |
| **Navegador y RPA** | `PlaywrightManager`, `ComponenteInteraccion`, `EsperasInteligentes` en `componentes_comunes.py` | Inicio/cierre de Chromium, clics, escritura, esperas, descargas. |
| **Datos** | `LectorArchivos`, `BaseDatos`, `ConfiguracionManager` en `componentes_comunes.py` | Lectura de CSV/Excel/TXT; consultas e inserciones SQL; lectura/actualización de config. |
| **Correo** | `CorreoManager` en `componentes_comunes.py` | IMAP y obtención del código OTP desde el correo. |
| **Logs** | `LogManager` en `componentes_comunes.py` | Log por banco y ejecución en archivo y consola. |
| **Post-ejecución** | `SubprocesoManager` en `componentes_comunes.py` | Ejecución de `UNION_BANCOS_run.sh`. |
| **Lógica por entidad** | Cada `*_Final.py` | Flujo concreto: URLs, selectores, empresas, formato de archivos, inserción en BD. |
| **Orquestación externa** | Scripts `.sh` + cron | Entorno (Xvfb, venv), timeout y lanzamiento del Python correcto. |

Los scripts de banco **no** implementan conexión a BD ni manejo de Playwright desde cero; importan y usan los componentes comunes.

---

## Módulos principales y cómo añadir una nueva pantalla o funcionalidad

### Añadir un nuevo banco o cooperativa con Playwright

1. Crear `BancoNuevo_Final.py` (o `CooperativaNueva_Final.py`).
2. Importar desde `componentes_comunes`: `PlaywrightManager`, `ComponenteInteraccion`, `EsperasInteligentes`, `LectorArchivos`, `LogManager`, `BaseDatos`, `CorreoManager` (si usa OTP por correo), `ConfiguracionManager`, `SubprocesoManager`, `RUTAS_CONFIG`, y helpers como `esperarConLoader` / `esperarConLoaderSimple`.
3. Definir constantes: `DATABASE`, `DATABASE_LOGS`, `DATABASE_RUNS`, `NOMBRE_BANCO`, `URLS` (p. ej. `{'login': '...'}`).
4. Implementar:
   - `obtenerIDEjecucion()`, `datosEjecucion()`, `escribirLog()` (patrón igual que en Guayaquil/Produbanco).
   - `main()`: obtener ID → registrar inicio en BD → iniciar timeout (opcional) → `PlaywrightManager` con `download_path=RUTAS_CONFIG['descargas']` → login → código por correo si aplica → navegación a movimientos → bucle por empresas (descargar, procesar archivo, insertar en BD) → cierre de sesión → actualizar estado en BD → `SubprocesoManager.ejecutar_bat_final()` → cerrar navegador.
5. Añadir credenciales en `configBancos/config/credencialesBanco.csv` (primera columna = nombre del banco/cooperativa).
6. Crear `bashNuevo.sh` siguiendo el patrón de `bashGuayaquil.sh` (Xvfb, venv, `timeout 900`, trap de limpieza).

### Añadir procesamiento solo de archivos (sin navegador)

1. Crear script similar a `BancoBolivariano_Final.py`.
2. En `main()`: obtener ID → registrar inicio → listar archivos desde una ruta (usar `RUTAS_CONFIG` o añadir clave nueva en `componentes_comunes` si hace falta) → por cada archivo llamar a una función `procesar_archivo()` que lea, parsee, normalice e inserte en la misma tabla/estructura que el resto.
3. Al final: actualizar estado en BD, `SubprocesoManager.ejecutar_bat_final()`.
4. Crear un `.sh` sin Xvfb (como `bashBolivariano.sh`).

### Añadir una nueva “pantalla” o paso dentro de un banco existente

- Añadir una función en el `*_Final.py` correspondiente (p. ej. nueva página o modal) usando `ComponenteInteraccion` y `EsperasInteligentes`.
- Llamar a esa función desde el flujo principal (p. ej. después del login o antes de la descarga), manteniendo el mismo patrón de logs y manejo de errores.

---

## Patrones de diseño utilizados

- **Singleton (implícito):** `LogManager` mantiene una única instancia y estado (`_banco_actual`, `_id_ejecucion`).
- **Módulo de utilidades:** `componentes_comunes` actúa como fachada de utilidades (clic, escritura, BD, correo, etc.) para evitar duplicar código.
- **Configuración centralizada:** `RUTAS_CONFIG` y CSV externos; los scripts no hardcodean rutas de credenciales.
- **Reintentos:** En `ComponenteInteraccion` (clic, escritura, lectura) con número de intentos y timeout configurables.
- **Timeout global:** En los scripts con Playwright, `TimeoutManager` (clase local en cada script) limita la duración total de la ejecución y fuerza salida con `os._exit(1)`.
- **Decorador:** `@with_timeout_check` en funciones críticas para comprobar el timeout antes de ejecutar.

No se usa inyección de dependencias ni frameworks de testing en el repositorio actual.
