#!/bin/bash
# bash_pichincha.sh
# Ejecuta la automatización de Banco Pichincha en modo "headless real"
# (navegador visible pero sin pantalla física, vía Xvfb) — necesario porque
# Chrome con reCAPTCHA/Akamai se comporta distinto en --headless real y
# puede ser detectado más fácil.

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
    pkill -f "python.*session.py" 2>/dev/null
}
trap cleanup EXIT

# --- AJUSTA ESTA RUTA a donde tengas el proyecto ---
cd /home/administrador/Escritorio/bancos/BancoPichincha || exit 1

# Activar entorno virtual (ajusta la ruta si tu venv está en otro lado)
source ../venv/bin/activate || exit 1

# Verificar/iniciar Xvfb
if ! check_xvfb; then
    echo "❌ No se pudo iniciar Xvfb"
    exit 1
fi

echo "🚀 Iniciando automatización (Banco Pichincha)..."

# Ejecutar el script principal con timeout de 15 minutos.
# El 2FA ahora se resuelve por Telegram — el bot te va a escribir al chat
# configurado en .env pidiendo el código, y tú le respondes ahí mismo.
timeout 900 python session.py

exit_code=$?

if [ $exit_code -eq 124 ]; then
    echo "⏰ ERROR: El proceso fue terminado por timeout (15 minutos)"
elif [ $exit_code -eq 0 ]; then
    echo "✅ Proceso completado exitosamente"
else
    echo "❌ Proceso terminó con código de error: $exit_code"
fi

exit $exit_code