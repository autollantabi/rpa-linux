# Despliegue y producción

Proceso de “build”, configuración de ambientes y consideraciones para producción. El proyecto no tiene un pipeline de build clásico; el despliegue consiste en instalar dependencias y configurar el entorno y cron.

---

## Proceso de “build”

No hay compilación ni artefacto empaquetado. El “build” es:

1. **Clonar o actualizar el repositorio** en la máquina objetivo (por ejemplo `/home/administrador/Escritorio/bancos` o la ruta que se use).
2. **Crear y activar el entorno virtual:**
   ```bash
   python3 -m venv /ruta/al/venv
   source /ruta/al/venv/bin/activate
   ```
3. **Instalar dependencias Python:**
   ```bash
   pip install playwright pyodbc openpyxl imapclient pandas
   playwright install
   ```
4. **Ajustar rutas** en `componentes_comunes.RUTAS_CONFIG` y en los scripts `.sh` si la instalación no está en `/home/administrador/...`.
5. **Crear y rellenar** la carpeta `configBancos` (config/, descargas/, logs/, Bolivariano/ según corresponda) y los CSV de credenciales y configuraciones.
6. **Dar permisos de ejecución** a los Bash: `chmod +x bash*.sh`.

No hay `requirements.txt` en el repo; las dependencias están listadas en [docs/setup.md](setup.md).

---

## Configuración de ambientes

- **Desarrollo / pruebas:** Misma estructura; se puede usar `headless=False` en los scripts Python para ver el navegador. Opcionalmente usar bases de datos o tablas de prueba (en el código hay constantes comentadas como `RegistrosBancosPRUEBA`, `AutomationLogPRUEBA`).
- **Producción:** Ejecución por cron con los scripts Bash; Xvfb para headless; timeouts (900 s para bancos con navegador, 300 s para Bolivariano/JEP manual). Las credenciales en `configBancos` deben ser las de producción (BD, correo, bancos).
- **Variables de entorno:** No se usan para configuración de negocio; solo `DISPLAY` y opcionalmente `XVFB_WHD` en los Bash que usan Xvfb.

---

## Consideraciones para producción

1. **Rutas:** Revisar que `RUTAS_CONFIG` en `componentes_comunes.py` y las rutas dentro de cada `.sh` (cd, source venv) coincidan con la máquina donde se ejecuta.
2. **Cron:** Programar cada banco en horarios distintos para evitar solapamientos y contención de recursos (navegador, BD, correo). Los timeouts de los Bash (900/300 s) limitan la duración máxima por ejecución.
3. **Espacio y logs:** La carpeta `configBancos/logs` crece con el tiempo; no hay rotación automática en el código. Valorar limpieza o rotación externa (logrotate, cron).
4. **Credenciales:** Los CSV en `configBancos` contienen datos sensibles; permisos de lectura restringidos y no versionar esa carpeta.
5. **Script de unión:** Verificar que `RUTAS_CONFIG['bat_final']` apunte al script correcto y que tenga permisos de ejecución; el timeout interno es 5 minutos.
6. **ODBC:** En el servidor Linux debe estar instalado el driver (ODBC Driver 18 for SQL Server) y configurado para conectar al SQL Server de producción.
7. **Red y cortafuegos:** Permitir acceso a los dominios de los portales bancarios y al servidor IMAP y al SQL Server.
8. **Pichincha / 2FA:** Si el banco exige código por celular, la automatización completa puede no ser viable; se documenta subida manual en horarios fijos.
9. **CREA:** La cooperativa ya no existe; no ejecutar `CooperativaCREA_Final.py` ni `bashCREA.sh` en producción.

No hay documentación en el repo sobre el contenido exacto del script `UNION_BANCOS_run.sh` ni sobre el esquema de BD; eso debe documentarse o mantenerse en el equipo que administra el sistema.
