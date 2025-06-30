
# Cambiar al directorio
cd /home/administrador/Escritorio/bancos || exit 1

# Activar entorno virtual
source ../venv/bin/activate || exit 1

# Ejecutar el script con timeout de 15 minutos
timeout 300 python BancoBolivariano_Final.py