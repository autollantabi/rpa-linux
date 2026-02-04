# Flujos principales del sistema

Descripción paso a paso de los flujos principales. No hay sistema de usuarios ni permisos propios del proyecto; la autenticación es la de cada portal (usuario/contraseña + OTP cuando aplica).

---

## Flujo general (bancos con Playwright)

Aplicable a: Banco Guayaquil, Banco Produbanco, Banco Pichincha, Cooperativa JEP (modo automático). Cooperativa CREA sigue el mismo esquema pero está obsoleta.

1. **Inicio**
   - Obtener siguiente `idAutomationRun` desde BD (`SELECT MAX(idAutomationRun)...`).
   - Configurar `LogManager` con nombre del banco e ID.
   - Registrar en BD: `INSERT` en tabla de runs con estado `Running`.
   - (Opcional) Iniciar `TimeoutManager` (ej. 10 minutos).
   - Iniciar Playwright (Chromium), contexto y página; carpeta de descargas = `RUTAS_CONFIG['descargas']`.

2. **Login**
   - Leer credenciales de `credencialesBanco.csv` filtradas por nombre del banco.
   - Navegar a `URLS['login']`.
   - Rellenar usuario y contraseña con `ComponenteInteraccion.escribirComponente`.
   - Enviar formulario (clic en botón de login).

3. **Código de seguridad (OTP)**
   - Si el portal lo pide: guardar timestamp de inicio, llamar a `CorreoManager.obtener_codigo_correo(asunto=..., timestamp_inicio=...)`, recibir código de 6 dígitos e ingresarlo en la página (campo o teclado virtual según el banco).
   - **Banco Guayaquil:** tras el clic en login se busca primero el modal de “sesión guardada” (botón Aceptar en `p-dialog-footer`). Si aparece, se hace clic en Aceptar y se omite el OTP; si no aparece pero sí los inputs de código, se obtiene el código por correo y se rellenan los campos.
   - JEP usa teclado virtual en pantalla; otros suelen usar un input.

4. **Navegación a movimientos**
   - Cerrar modales/overlays si aparecen (cookies, avisos).
   - Navegar al menú de consulta de movimientos (clic en menú, opción “Movimientos” o equivalente).
   - En algunos bancos (ej. Guayaquil) se cierra un iframe/modal antes de elegir empresa.

5. **Procesamiento por empresas**
   - Obtener lista de empresas (desplegable o config fija según el banco).
   - Por cada empresa:
     - Seleccionar empresa en el combo/autocomplete.
     - Configurar rango de fechas si aplica (desde `configuraciones.csv` o cálculo por defecto).
     - Disparar descarga (Excel/CSV) con `ComponenteInteraccion.esperarDescarga` o similar.
     - Leer archivo descargado (openpyxl/pandas/CSV según formato).
     - Normalizar filas (fecha, valor, tipo C/D, cuenta, empresa, etc.).
     - Por cada movimiento: comprobar duplicados (opcional) e `INSERT` en tabla de movimientos en BD.
   - Los archivos descargados se guardan en `RUTAS_CONFIG['descargas']` y pueden ser sobrescritos en la siguiente descarga.

6. **Cierre**
   - Cerrar sesión en el portal si hay botón de salir.
   - Actualizar fechas en `configuraciones.csv` para la próxima ejecución (donde esté implementado).
   - Actualizar en BD el run: `UPDATE ... SET finalizationStatus = 'Completed'` (o `Failed`).
   - Llamar a `SubprocesoManager.ejecutar_bat_final()` (ejecuta `UNION_BANCOS_run.sh`).
   - Cerrar navegador y Playwright.
   - Detener `TimeoutManager` si se usa.

En caso de error en cualquier paso, se registra en log y en BD, se puede ejecutar igualmente el script final y se cierra el navegador.

---

## Flujo Banco Bolivariano (solo archivos)

1. Obtener ID de ejecución y registrar inicio en BD (igual que arriba).
2. Listar archivos `.txt` en `RUTAS_CONFIG['bolivariano']`.
3. Por cada archivo:
   - Leer contenido (líneas, columnas separadas por tabulador).
   - Extraer del encabezado: cuenta, empresa.
   - Desde la línea de datos (ej. línea 7 en adelante): fecha, oficina, referencia, numDocumento, signo, valor, disponible, saldo.
   - Normalizar fecha a `YYYY-MM-DD`; determinar tipo C/D por signo.
   - Obtener `contFecha` para evitar duplicados; comprobar duplicado por cuenta, banco, empresa, numDocumento, fecha, valor.
   - `INSERT` en tabla de movimientos; al terminar el archivo, eliminarlo del disco.
4. Actualizar estado del run en BD, ejecutar `UNION_BANCOS_run.sh`, finalizar logs.

No hay login ni navegador; no hay OTP.

---

## Flujo Cooperativa JEP — modo manual

1. Se invoca `CooperativaJEP_Final.py --manual` (o `bashJEP_manual.sh`).
2. No se abre navegador. Se buscan en la carpeta de descargas archivos con nombres como `jepAutollanta.xlsx`, `jepAutollantaT.xlsx`, `jepMaxximundo.xlsx` (o `.xls`).
3. Por cada archivo encontrado se identifica la empresa (por nombre o contenido; en código se referencia línea ~125 para Tecnicentro).
4. Se lee el Excel, se normalizan las filas y se insertan en BD (misma tabla que en modo automático).
5. Se registra fin en BD y se ejecuta el script de unión.

No hay login ni OTP en este modo.

---

## Auth, autorización y permisos

- **Proyecto:** No hay capa de autenticación ni roles propios. Quien ejecuta el script (cron o usuario) debe tener:
  - Acceso a la carpeta del proyecto y a `configBancos`.
  - Credenciales válidas en los CSV (bancos, correo, BD).
  - Permisos de red a portales y SQL Server.
- **Portales:** La autenticación es la del banco/cooperativa (usuario, contraseña, OTP por correo o por celular). Las credenciales se guardan en `credencialesBanco.csv`; el script las lee y las usa en el formulario de login.
- **Base de datos:** El usuario definido en `credencialesDB.csv` debe tener permisos de `INSERT`/`UPDATE`/`SELECT` en las tablas `AutomationRun`, `AutomationLog` y en la tabla de movimientos (ej. `RegistrosBancos`).

No hay gestión de sesiones ni tokens propios; la “sesión” es la del navegador Playwright hasta que se cierra.
