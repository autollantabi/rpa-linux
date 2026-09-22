#!/bin/bash
# bashBolivariano.sh
# Ejecuta la automatización de Banco Bolivariano en modo "headless real"
# (navegador visible pero sin pantalla física, vía Xvfb) — necesario porque
# el banco detecta Chrome en --headless=new real y responde con la pantalla
# "Navegador no soportado" en vez del login. Mismo patrón ya usado en
# BancoPichincha/bashPichincha.sh.
#
# DISPLAY propio (:98, no :99): los demás bash*.sh de este proyecto
# (Pichincha, CREA, Guayaquil, Produbanco, JEP) comparten DISPLAY=:99 y cada
# uno mata ese Xvfb al salir (pkill -f "Xvfb :99" en su propio cleanup). Si
# dos de esos scripts corren solapados, el que termina primero le mata la
# pantalla al que sigue corriendo, y Chrome se cae con un crash nativo sin
# mensaje legible (visto en un run real de Bolivariano). Usar :98 aquí saca
# a Bolivariano de esa colisión sin tocar los otros scripts.

# Configurar variables de entorno para "headless real"
export DISPLAY=:98
export XVFB_WHD=${XVFB_WHD:-1920x1080x24}
export BOLIVARIANO_HEADLESS=false

# Función para verificar si Xvfb está corriendo
check_xvfb() {
    if pgrep -f "Xvfb :98" > /dev/null; then
        echo "✅ Xvfb ya está corriendo en :98"
        return 0
    else
        echo "🚀 Iniciando Xvfb en :98"
        Xvfb :98 -screen 0 $XVFB_WHD -ac +extension GLX +render -noreset -dpi 96 2>/dev/null &
        sleep 3

        if pgrep -f "Xvfb :98" > /dev/null; then
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
    pkill -f "Xvfb :98" 2>/dev/null
    pkill -f "python.*BancoBolivariano_Final.py" 2>/dev/null
}
trap cleanup EXIT

cd /home/administrador/Escritorio/bancos/BancoBolivariano || exit 1

# Activar entorno virtual (ajustar la ruta si el venv de este proyecto vive
# en otro lugar, ej. uno propio en vez del compartido con los otros bancos).
source ../venv/bin/activate || exit 1

# componentes_comunes.py vive un nivel arriba (compartido con los otros
# bancos: Pichincha, Guayaquil, Produbanco, JEP) — lo agregamos al
# PYTHONPATH para que sea importable desde aquí sin duplicar el archivo.
export PYTHONPATH="/home/administrador/Escritorio/bancos:$PYTHONPATH"

# Verificar/iniciar Xvfb
if ! check_xvfb; then
    echo "❌ No se pudo iniciar Xvfb"
    exit 1
fi

echo "🚀 Iniciando automatización (Banco Bolivariano)..."

# Ejecutar el script principal con timeout de 15 minutos.
timeout 900 python BancoBolivariano_Final.py

exit_code=$?

if [ $exit_code -eq 124 ]; then
    echo "⏰ ERROR: El proceso fue terminado por timeout (15 minutos)"
elif [ $exit_code -eq 0 ]; then
    echo "✅ Proceso completado exitosamente"
else
    echo "❌ Proceso terminó con código de error: $exit_code"
fi

exit $exit_code
