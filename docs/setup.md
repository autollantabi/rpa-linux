# Configuración y ejecución del proyecto

Requisitos del sistema, variables, pasos para ejecutar localmente y errores comunes.

---

## Requisitos del sistema

- **Sistema operativo:** Linux (probado en entornos con cron; los scripts Bash asumen rutas tipo `/home/administrador/...`).
- **Python:** 3.8 o superior (en el código se usa `componentes_comunes` con Python 3.12 según `__pycache__`).
- **Navegador:** Chromium instalado vía Playwright (`playwright install`).
- **Headless (opcional):** Xvfb para ejecución sin display (`sudo apt install xvfb` o equivalente).
- **Base de datos:** SQL Server accesible desde la máquina (ODBC Driver 18 for SQL Server).
- **Acceso de red:** A portales web de bancos/cooperativas y al servidor de correo IMAP (para códigos OTP).

---

## Variables de entorno necesarias

El proyecto **no usa archivos `.env`**. La configuración se lee desde:

1. **CSV en `configBancos`** (rutas definidas en `componentes_comunes.RUTAS_CONFIG`):
   - `credencialesBanco.csv` — usuario/contraseña por banco.
   - `credencialesCorreo.csv` — servidor, usuario y contraseña IMAP (por key, ej. `mail.maxximundo.com`).
   - `credencialesDB.csv` — servidor, base de datos, usuario y contraseña SQL Server.
   - `configuraciones.csv` — claves como "Fecha desde", "Fecha hasta".
   - `rutas.csv` — (si se usa) rutas adicionales.

2. **Para ejecución headless (scripts Bash):**
   - `DISPLAY=:99` — ya se exporta en los scripts que usan Xvfb.
   - `XVFB_WHD` (opcional) — resolución virtual, por defecto `1920x1080x24`.

No hay variables de entorno obligatorias que el desarrollador deba definir a mano para ejecución básica; todo depende de que exista la carpeta `configBancos` y los CSV con el formato esperado.

---

## Pasos para ejecutar el proyecto localmente

### 1. Clonar y ubicarse en la carpeta del proyecto

```bash
git clone https://github.com/autollantabi/rpa-linux.git
cd rpa-linux/bancos
```

### 2. Crear y activar entorno virtual

```bash
python3 -m venv /home/administrador/Escritorio/venv
source /home/administrador/Escritorio/venv/bin/activate
```

Si usas otra ruta, deberás ajustar los scripts `.sh` (líneas con `cd` y `source .../venv/bin/activate`).

### 3. Instalar dependencias Python

```bash
pip install playwright pyodbc openpyxl imapclient pandas
playwright install
```

No hay `requirements.txt` en el repositorio; las dependencias están documentadas en el README y en este documento.

### 4. Configurar `configBancos`

La ruta por defecto está en `componentes_comunes.RUTAS_CONFIG`: `/home/administrador/configBancos`.

Estructura esperada:

- `config/` — credencialesBanco.csv, credencialesCorreo.csv, credencialesDB.csv, configuraciones.csv, rutas.csv.
- `descargas/` — archivos descargados por Playwright; también aquí se buscan los Excel de JEP en modo manual.
- `logs/` — logs por banco y ejecución.
- `Bolivariano/` — archivos TXT para Banco Bolivariano (descargados manualmente).

Si instalas en otra máquina o usuario, crea esta estructura y ajusta `RUTAS_CONFIG` en `componentes_comunes.py`.

### 5. Permisos de ejecución en scripts Bash

```bash
chmod +x bash*.sh
```

### 6. Ejecutar por banco/cooperativa

**Con navegador (usar los Bash en Linux para headless):**

```bash
./bashGuayaquil.sh
./bashProdubanco.sh
./bashJEP.sh
```

**Solo procesamiento de archivos (sin Xvfb):**

```bash
./bashBolivariano.sh   # TXT en configBancos/Bolivariano
./bashJEP_manual.sh   # Excel JEP en configBancos/descargas (jepAutollanta.xlsx, etc.)
```

**Directamente con Python (desde la carpeta `bancos`):**

```bash
source /ruta/al/venv/bin/activate
python BancoGuayaquil_Final.py
python BancoBolivariano_Final.py
python CooperativaJEP_Final.py --manual
```

Para **Bolivariano** deben existir TXT en la carpeta configurada. Para **JEP manual**, los archivos deben estar en la carpeta de descargas con los nombres esperados (ver README o `CooperativaJEP_Final.py`).

---

## Errores comunes y cómo resolverlos

| Síntoma | Causa probable | Qué hacer |
|--------|-----------------|-----------|
| `FileNotFoundError` en credenciales o config | `configBancos` no existe o rutas incorrectas | Crear `/home/administrador/configBancos` y subcarpetas; o editar `RUTAS_CONFIG` en `componentes_comunes.py`. |
| `No se pudieron leer las credenciales de Banco X` | Falta fila en `credencialesBanco.csv` para ese banco (columna 0 = nombre) | Añadir fila con nombre exacto del banco (ej. "Banco Guayaquil", "Banco Produbanco"). |
| Error conectando a BD / pyodbc | Credenciales incorrectas o ODBC no instalado | Revisar `credencialesDB.csv`. En Linux instalar `msodbcsql18` y comprobar `odbcinst -q -d`. |
| Timeout en login o en página | Portal lento o bloqueado; red; cambio de diseño | Revisar logs en `configBancos/logs`. Aumentar timeouts en el script del banco si es necesario. |
| Código de seguridad no encontrado (correo) | Correo no llegó; asunto distinto; credenciales IMAP incorrectas | Verificar `credencialesCorreo.csv` y key usada (ej. `mail.maxximundo.com`). Revisar asuntos en `CorreoManager.obtener_codigo_correo`. |
| `Exit code 124` al usar los `.sh` | Timeout del comando `timeout` (900 s o 300 s) | Aumentar tiempo en el script (ej. `timeout 1200`) o revisar por qué el proceso tarda más. |
| Xvfb no inicia / Display :99 | Xvfb no instalado o puerto en uso | `sudo apt install xvfb`; comprobar que no haya otro Xvfb en :99. |
| No se encontraron archivos TXT/Excel | Ruta distinta o nombres incorrectos | Bolivariano: archivos en `RUTAS_CONFIG['bolivariano']`. JEP manual: nombres como `jepAutollanta.xlsx`, etc. (ver código JEP). |
| `UNION_BANCOS_run.sh` no encontrado | Ruta en `RUTAS_CONFIG['bat_final']` incorrecta | Ajustar `bat_final` en `componentes_comunes.py` a la ruta real del script de unión. |

Si algo no está claro en el código (por ejemplo formato exacto de un CSV), se debe revisar el script correspondiente y, si procede, anotarlo en [docs/pendientes.md](pendientes.md).
