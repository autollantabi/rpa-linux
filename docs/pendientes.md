# Pendientes y mejoras

Mejoras técnicas sugeridas, deuda técnica detectada y suposiciones o partes no claras del proyecto. Sirve como lista de tareas para quien mantenga o amplíe el sistema.

---

## Mejoras técnicas sugeridas

1. **Añadir `requirements.txt`** con versiones fijas (playwright, pyodbc, openpyxl, imapclient, pandas) para reproducibilidad de entornos.
2. **Extraer credenciales sensibles** a variables de entorno o a un mecanismo seguro (vault, secretos del SO) en lugar de CSV en disco, sobre todo en producción.
3. **Tests automatizados:** al menos tests unitarios para `componentes_comunes` (lectura CSV, normalización de fechas, parsing de movimientos) y, si es posible, tests de integración con BD de prueba.
4. **Rotación o límite de logs:** definir política para `configBancos/logs` (antigüedad, tamaño) o integrar con logrotate.
5. **Unificar nombres en BD:** corregir en los scripts donde el `processName` del INSERT en AutomationRun no coincide con el banco (ej. JEP que inserta "Descarga comprobantes-Banco Guayaquil").
6. **Documentar esquema de BD:** tablas AutomationRun, AutomationLog y tabla de movimientos (columnas, tipos) para facilitar mantenimiento y onboarding.
7. **Documentar o versionar `UNION_BANCOS_run.sh`:** si es posible, incluir su lógica o una copia en el repo o en docs para no depender solo de una ruta externa.
8. **Refactorizar `componentes_comunes.py`:** dividir en módulos (p. ej. navegador, bd, correo, logs, config) para reducir tamaño y acoplamiento.
9. **TimeoutManager:** actualmente duplicado en cada script con Playwright; podría moverse a `componentes_comunes` o a un módulo compartido.

---

## Deuda técnica detectada

- **Duplicación de TimeoutManager y helpers:** La clase TimeoutManager y funciones como `formatear_tiempo_ejecucion` y el decorador `@with_timeout_check` se repiten en BancoGuayaquil_Final.py, BancoProdubanco_Final.py, BancoPichincha_Final.py, CooperativaJEP_Final.py y CooperativaCREA_Final.py. Cualquier cambio hay que replicarlo en todos.
- **Rutas absolutas:** Los Bash y `RUTAS_CONFIG` usan `/home/administrador/...`; en otra máquina o usuario requiere edición manual en varios sitios. Valorar un único punto de configuración (env, archivo de config) para la raíz del proyecto y de configBancos.
- **Sin tipo de datos explícito para credenciales:** Los CSV se leen como listas de filas sin validación de columnas; errores de formato se detectan en tiempo de ejecución.
- **Manejo de errores:** En varios puntos se hace `except Exception` genérico; podría afinarse para distinguir errores recuperables de fallos fatales y registrar mejor el contexto.
- **Constantes de BD en cada script:** DATABASE, DATABASE_LOGS, DATABASE_RUNS se repiten en cada `*_Final.py`; podrían centralizarse o leerse de config.

---

## Suposiciones o partes no claras

- **Formato exacto de credencialesBanco.csv:** Se infiere que la primera columna es el nombre del banco (para filtrar) y que hay al menos usuario y contraseña en columnas siguientes; no está documentado el número de columnas ni el orden en el repo. Conviene documentarlo en setup.md o en un ejemplo.
- **Formato de credencialesCorreo.csv:** Se usa filtro por “key” (primera columna, ej. mail.maxximundo.com) y se asume servidor, usuario, contraseña en las siguientes; no hay documento que describa el esquema.
- **Estructura de la tabla de movimientos:** Los INSERT usan columnas como numCuenta, banco, empresa, numDocumento, fechaTransaccion, tipo, valor, saldoContable, disponible, oficina, referencia, contFecha, idEjecucion; no hay script de creación de tablas ni documentación del esquema en el repo.
- **Horarios de cron:** El README indica que cada banco tiene horarios distintos en cron pero no se documentan los valores exactos (por política o por estar en el crontab del servidor).
- **Nombre de cuenta Tecnicentro JEP:** Se referencia en comentarios la línea ~125 de CooperativaJEP_Final.py para saber qué cuenta es el Tecnicentro; la lógica podría documentarse en guia-proyecto o en el propio script.
- **Estado real de Banco Pichincha y 2BancoPichincha:** No está claro si en producción se usa solo el procesamiento de archivos (2BancoPichincha_Final.py) o si en algún entorno se sigue usando el flujo con navegador; el README indica que Pichincha está limitado por 2FA por celular.
- **Uso actual de CooperativaCREA:** Se documenta como obsoleta (la cooperativa ya no existe); no está claro si los archivos se mantienen “por si acaso” o se pueden eliminar/deprecar formalmente.

Cuando se aclare cualquiera de estos puntos, se recomienda actualizar este documento o la documentación correspondiente (setup, guia-proyecto, arquitectura) y marcar el ítem como resuelto.
