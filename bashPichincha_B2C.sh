#!/bin/bash

# Configurar variables de entorno para headless
export DISPLAY=:99
export XVFB_WHD=${XVFB_WHD:-1920x1080x24}

# Función para verificar si xvfb está corriendo
check_xvfb() {
    if pgrep -f "Xvfb :99" > /dev/null; then
        echo "✅ Xvfb ya está corriendo en :99"
        return 0
    else
        echo "🚀 Iniciando Xvfb en :99"
        # Configuración mejorada para Xvfb
        Xvfb :99 -screen 0 $XVFB_WHD -ac +extension GLX +render -noreset -dpi 96 2>/dev/null &
        sleep 3
        
        if pgrep -f "Xvfb :99" > /dev/null; then
            echo "✅ Xvfb iniciado correctamente"
            return 0
        else
            echo "❌ Error iniciando Xvfb"
            return 1
        fi
    fi
}

# Función de limpieza
cleanup() {
    echo "🧹 Limpiando procesos..."
    pkill -f "Xvfb :99" 2>/dev/null
    pkill -f "python.*BancoPichincha_B2C" 2>/dev/null
}

# Configurar trap para limpieza
trap cleanup EXIT

# Cambiar al directorio
cd /home/administrador/Escritorio/bancos || exit 1

# Activar entorno virtual
source ../venv/bin/activate || exit 1

# Verificar/iniciar Xvfb
if ! check_xvfb; then
    echo "❌ No se pudo iniciar Xvfb"
    exit 1
fi

echo "🚀 Iniciando automatización B2C en modo headless..."

# Ejecutar el script con timeout de 20 minutos (B2C puede ser más lento)
timeout 1200 python BancoPichincha_B2C_Final.py

# Capturar código de salida
exit_code=$?

if [ $exit_code -eq 124 ]; then
    echo "⏰ ERROR: El proceso fue terminado por timeout (20 minutos)"
elif [ $exit_code -eq 0 ]; then
    echo "✅ Proceso completado exitosamente"
else
    echo "❌ Proceso terminó con código de error: $exit_code"
fi

exit $exit_code
