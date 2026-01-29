#!/bin/bash

# Script para ejecutar Cooperativa JEP en modo manual
# Uso: ./bashJEP_manual.sh

# Cambiar al directorio del script
cd /home/administrador/Escritorio/bancos || exit 1

echo "🔧 Activando entorno virtual..."
# Activar entorno virtual
source /home/administrador/Escritorio/venv/bin/activate || exit 1

echo "📁 Modo manual: Procesando archivos desde carpeta de descargas"
echo "   Buscando archivos: jepAutollanta, jepAutollantaT, jepMaxximundo"
echo ""

# Ejecutar el script en modo manual
python3 CooperativaJEP_Final.py --manual

# Capturar código de salida
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ Proceso completado exitosamente"
else
    echo ""
    echo "❌ Proceso terminó con código de error: $exit_code"
fi

exit $exit_code
