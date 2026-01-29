# rpa-linux — Carpeta Bancos

Automatización bancaria multiplataforma para Linux usando **Python** y **Playwright**. Esta carpeta contiene los scripts que automatizan consultas, descargas de movimientos y procesamiento por empresa para varios bancos y cooperativas.

- **Repositorio:** el proyecto está vinculado al GitHub de **autollantabi** (`https://github.com/autollantabi/rpa-linux`).

---

## Bancos y cooperativas soportados

| Entidad              | Tipo        | Automatización                          |
|----------------------|------------|-----------------------------------------|
| **Banco Pichincha**  | Banco      | Playwright (login, movimientos, empresas) |
| **Banco Guayaquil**  | Banco      | Playwright (login, movimientos, empresas) |
| **Banco Produbanco** | Banco      | Playwright (login, movimientos, empresas) |
| **Banco Bolivariano**| Banco      | Solo procesamiento de archivos TXT (sin navegador) |
| **Cooperativa JEP**  | Cooperativa| Playwright + modo manual (archivos Excel) |
| **Cooperativa CREA** | Cooperativa| Playwright (login, movimientos, empresas) |

---

## Tecnologías utilizadas

- **Python 3.8+**
- **Playwright** (Chromium) para automatización del navegador
- **Xvfb** (X Virtual Framebuffer) en los bash para ejecución headless en Linux
- **Librerías estándar:** `os`, `sys`, `re`, `csv`, `json`, `time`, `datetime`, `threading`, `signal`, `functools`
- **Externas:** `playwright`, `pyodbc`, `openpyxl`, `imapclient`, `pandas` (vía componentes_comunes)

---

## Estructura del proyecto (carpeta `bancos`)

```
bancos/
├── componentes_comunes.py      # Módulo compartido: Playwright, logs, BD, correo, archivos
├── BancoPichincha_Final.py    # Automatización Banco Pichincha (este archivo esta sin funcionalidad por el momento por que el banco necesita el incio de sesion con código por celular)
├── BancoGuayaquil_Final.py    # Automatización Banco Guayaquil
├── BancoProdubanco_Final.py   # Automatización Banco Produbanco
├── BancoBolivariano_Final.py  # Solo procesamiento de TXT (sin navegador)
├── CooperativaJEP_Final.py    # Automatización Cooperativa JEP (+ modo manual)
├── CooperativaCREA_Final.py   # Automatización Cooperativa CREA (este ya no sirve ya que ya no existe la CooperativaCREA)
├── bashPichincha.sh           # Lanzador headless Pichincha
├── bashGuayaquil.sh           # Lanzador headless Guayaquil
├── bashProdubanco.sh          # Lanzador headless Produbanco
├── bashBolivariano.sh         # Lanzador Bolivariano (solo Python, sin Xvfb)
├── bashJEP.sh                 # Lanzador headless JEP
├── bashJEP_manual.sh          # Lanzador JEP en modo manual (solo archivos)
├── bashCREA.sh                # Lanzador headless CREA
└── README.md                  # Este archivo
```

---

## Cómo funciona cada banco / cooperativa

### Bancos con Playwright (Pichincha, Guayaquil, Produbanco)

1. **Inicio:** Se obtiene un ID de ejecución, se registra en BD y se inicia un navegador (Chromium) con `PlaywrightManager`.
2. **Login:** Se leen credenciales desde CSV (`credencialesBanco.csv`), se navega a la URL de login, se rellenan usuario y contraseña y se envía el formulario.
3. **Código de seguridad:** Tras el login, el banco envía un código por correo. El script usa `CorreoManager` (IMAP) para leer el último correo con el código y lo introduce en la página.
4. **Navegación a movimientos:** Se navega por el menú (por ejemplo “Cuentas” → “Consultar movimientos”) y se cierran modales/iframes si aparecen (p. ej. en Guayaquil).
5. **Procesamiento por empresas:** Se selecciona cada empresa en un desplegable/autocomplete, se configura rango de fechas si aplica, se descargan los movimientos (Excel/CSV) y se procesan (normalización, guardado, registro en BD).
6. **Cierre:** Se cierra sesión, se actualizan configuraciones de fecha si aplica, se registra fin en BD, se ejecuta el script final (`UNION_BANCOS_run.sh`) y se cierra el navegador.

**Particularidades:**
- **Guayaquil:** Cierre de iframe/modal de seguridad antes de elegir empresa; manejo de varios selectores para autocomplete de empresa.
- **Pichincha:** Flujo estándar con código por correo y descarga por empresa. Por la autenticación actual del banco (código por celular), la **subida manual** de movimientos se realiza en horarios fijos: **11:30 AM** y **5:00 PM** (hora Ecuador).

### Banco Bolivariano (solo archivos)

- **No usa navegador.** Solo procesa archivos **TXT** que deben estar descargados manualmente en la carpeta configurada (p. ej. `configBancos/Bolivariano` o la definida en `RUTAS_CONFIG`).
- **Flujo:** Obtiene lista de archivos TXT → por cada archivo ejecuta `procesar_archivo()` (lectura, parseo, normalización, inserción en BD) → al final ejecuta el mismo script de unión (`UNION_BANCOS_run.sh`).
- Se registra inicio/fin en BD y logs igual que el resto.

### Cooperativa JEP

- **Modo automático (por defecto):** Igual que los bancos con Playwright: login, código por correo si aplica, cierre de modal de cookies, navegación a movimientos, procesamiento por empresa (Autollanta, Autollanta Tecnicentro, Maxximundo), descarga y procesamiento de Excel.
- **Modo manual:** Si la automatización falla pero tienes los archivos ya descargados:
  - Ejecutar: `python CooperativaJEP_Final.py --manual` o `./bashJEP_manual.sh`.
  - El script busca en la carpeta de descargas archivos con nombres como `jepAutollanta.xlsx`, `jepAutollantaT.xlsx`, `jepMaxximundo.xlsx` (o `.xls`), identifica la empresa por nombre/contenido y procesa sin abrir el navegador.


---

## Scripts Bash — Qué hacen

Todos los `.sh` están pensados para ejecutarse desde Linux (por ejemplo desde cron o a mano). Asumen que el proyecto está en `/home/administrador/Escritorio/bancos` y el entorno virtual en `/home/administrador/Escritorio/venv` (o `../venv` según el script).

### Scripts con Xvfb (headless)

- **bashPichincha.sh**, **bashGuayaquil.sh**, **bashProdubanco.sh**, **bashJEP.sh**, **bashCREA.sh**:
  1. Exportan `DISPLAY=:99` y opcionalmente `XVFB_WHD` (p. ej. 1920x1080x24).
  2. Comprueban si **Xvfb** ya está corriendo en `:99`; si no, lo arrancan.
  3. Registran una función `cleanup` y un `trap` para al salir matar Xvfb y el proceso Python del banco correspondiente.
  4. Hacen `cd` a la carpeta `bancos` y activan el venv (`source ../venv/bin/activate` o ruta absoluta).
  5. Ejecutan el script Python con **timeout 900** (15 minutos).
  6. Interpretan el código de salida (124 = timeout, 0 = éxito, otro = error).

### Scripts sin Xvfb

- **bashBolivariano.sh:** Solo hace `cd` a `bancos`, activa el venv y ejecuta `BancoBolivariano_Final.py` con timeout 300 (5 minutos). No inicia Xvfb ni navegador.
- **bashJEP_manual.sh:** Solo activa el venv y ejecuta `CooperativaJEP_Final.py --manual` para procesar archivos JEP ya descargados; no usa Xvfb ni navegador.

Si cambias de ruta (por ejemplo otra carpeta o otro usuario), hay que editar las rutas dentro de cada `.sh` (`cd`, `source .../venv/bin/activate`).

---

## Carpeta configBancos (archivos necesarios)

Parte de los archivos que usan los scripts **no están en esta carpeta** sino en la carpeta de configuración:

- **Ruta:** `/home/administrador/configBancos`

Ahí se encuentran, entre otros:
- **config/:** credenciales de bancos (`credencialesBanco.csv`), correo (`credencialesCorreo.csv`), base de datos (`credencialesDB.csv`), configuraciones y rutas (`configuraciones.csv`, `rutas.csv`).
- **descargas/:** archivos descargados por Playwright (movimientos Excel/CSV) y usados por JEP en modo manual, estos archivos de la JEP si se quieren cargar manual, deben ser movidos aca con los siguientes nombres: jepAutollanta.xlsx, jepAutollantaT.xslx, jepMaxximundo.xlsx; para saber que cuenta pertenece el tecnicentro revisar el archivo de CooperativaJEP_final.py (linea 125).
- **logs/:** logs por banco y por ejecución.
- **Bolivariano/:** archivos TXT para Banco Bolivariano (descargados manualmente).

Las rutas exactas están definidas en `RUTAS_CONFIG` dentro de `componentes_comunes.py`. Si instalas en otra máquina, crea o copia la estructura de `configBancos` en la ruta que uses y ajusta `RUTAS_CONFIG`.

---

## Ejecución programada (cron)

Los bancos que **sí pueden ejecutarse solos** (Guayaquil, Produbanco, Bolivariano, JEP, etc.) están configurados en el **cron de Linux** con **horarios distintos** para cada uno, de modo que no se solapen y no dependan unos de otros. Los scripts bash correspondientes se invocan desde el crontab según esos horarios.

---

## Componentes comunes (`componentes_comunes.py`)

Módulo central usado por todos los scripts de la carpeta bancos:

- **RUTAS_CONFIG:** Diccionario con rutas de credenciales, config, descargas, logs, carpetas por banco y script final (`bat_final` / `UNION_BANCOS_run.sh`).
- **PlaywrightManager:** Inicia/cierra Chromium, contexto y página; configurable headless, carpeta de descargas y timeouts.
- **ComponenteInteraccion:** Clic, escritura, lectura de elementos e inputs en la página (con reintentos y timeouts).
- **EsperasInteligentes:** Esperas a carga de página y elementos.
- **LectorArchivos:** Lectura de CSV, Excel y TXT (usado para credenciales, config y archivos descargados).
- **LogManager:** Logs por banco y ejecución en `logs/`.
- **BaseDatos:** Conexión a SQL Server (pyodbc), ejecución de consultas e inserciones (registro de ejecuciones, movimientos, etc.).
- **CorreoManager:** Conexión IMAP y obtención del código de seguridad desde el correo.
- **ConfiguracionManager:** Lectura y actualización de configuraciones (p. ej. fechas) en CSV.
- **SubprocesoManager:** Ejecución del script final de unión de bancos (`UNION_BANCOS_run.sh`).

Además se exportan funciones de conveniencia (`clickComponente`, `escribirComponente`, `leerCSV`, `leerExcel`, `escribirLog`, etc.) para no cambiar el resto del código.

---

## Requisitos

- Python 3.8 o superior.
- Playwright y navegador Chromium:
  ```bash
  pip install playwright
  playwright install
  ```
- Dependencias Python del proyecto:
  ```bash
  pip install playwright pyodbc openpyxl imapclient
  playwright install
  ```
- Acceso a los portales web de cada banco/cooperativa (credenciales válidas).
- Para ejecución headless en Linux: Xvfb instalado (`sudo apt install xvfb` o equivalente).
- Permisos de ejecución en los scripts: `chmod +x bash*.sh`.
- Credenciales y rutas configuradas en `configBancos` (CSV de credenciales, BD, correo, rutas); las rutas por defecto están en `RUTAS_CONFIG` dentro de `componentes_comunes.py`.

---

## Uso

1. **Clonar y entrar en la carpeta:**
   ```bash
   git clone https://github.com/autollantabi/rpa-linux.git
   cd rpa-linux/bancos
   ```

2. **Crear y activar entorno virtual (recomendado):**
   ```bash
   python3 -m venv /home/administrador/Escritorio/venv
   source /home/administrador/Escritorio/venv/bin/activate
   pip install playwright pyodbc openpyxl imapclient
   playwright install
   ```

3. **Ejecutar por banco/cooperativa:**
   - Con navegador (recomendado usar los bash para headless):
     ```bash
     ./bashPichincha.sh
     ./bashGuayaquil.sh
     ./bashProdubanco.sh
     ./bashJEP.sh
     ```
   - Solo procesamiento de archivos:
     ```bash
     ./bashBolivariano.sh   # TXT ya descargados
     ./bashJEP_manual.sh    # Excel JEP ya descargados (modo manual)
     ```
   - Directamente con Python (sin bash):
     ```bash
     python BancoPichincha_Final.py
     python BancoGuayaquil_Final.py
     python CooperativaJEP_Final.py --manual
     python BancoBolivariano_Final.py
     ```

Para **Bolivariano** hay que tener los TXT en la carpeta configurada antes de ejecutar. Para **JEP en modo manual**, los archivos deben estar en la carpeta de descargas con los nombres esperados (`jepAutollanta.xlsx`, etc.).

---

## Configuración y logs

- **Credenciales y rutas:** En la carpeta **configBancos**, subcarpeta `config/` — ruta completa `/home/administrador/configBancos/config/` (credencialesBanco.csv, credencialesCorreo.csv, credencialesDB.csv, configuraciones.csv, rutas.csv). Las rutas por defecto se definen en `componentes_comunes.py` (`RUTAS_CONFIG`).
- **Logs:** Se guardan por banco y por ejecución en la carpeta `logs/` indicada en `RUTAS_CONFIG` (por defecto `/home/administrador/configBancos/logs`).
- **Descargas:** Los archivos descargados por Playwright van a la carpeta `descargas` de `RUTAS_CONFIG`; Bolivariano y JEP manual leen desde sus rutas configuradas.

---

## Resumen de librerías

- **Externas:** `playwright`, `pyodbc`, `openpyxl`, `imapclient`
- **Estándar:** `os`, `sys`, `re`, `csv`, `json`, `time`, `datetime`, `threading`, `signal`, `functools`, `email`, `subprocess`

Instalación:
```bash
pip install playwright pyodbc openpyxl imapclient
playwright install
```

---

## Notas

- **Bolivariano** no abre navegador; solo procesa TXT ya descargados.
- **JEP** puede ejecutarse en modo automático (Playwright) o manual (`--manual` o `bashJEP_manual.sh`) cuando los archivos ya están en la carpeta de descargas.
- En entorno gráfico, algunos scripts pueden usarse con `headless=False` dentro del Python para ver el navegador; en servidor/cron se usan los bash con Xvfb y timeout.
- Si cambias de máquina o usuario, revisa rutas en los `.sh` y en `RUTAS_CONFIG` en `componentes_comunes.py`.

---

## Licencia

MIT

---

**Desarrollado por Diego Barbecho**  
**GitProfile: https://github.com/diegobarpdev**
