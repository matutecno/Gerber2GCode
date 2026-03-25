#!/bin/bash
source venv/bin/activate

GERBER_DIR="Gerbers"

# Sin argumentos → modo automático: busca en la carpeta Gerbers/
if [ -z "$1" ]; then
    # Buscar archivos .gbr (excluir .gbrjob)
    mapfile -t GBR_FILES < <(find "$GERBER_DIR" -maxdepth 1 -name "*.gbr" | sort)
    mapfile -t DRL_FILES < <(find "$GERBER_DIR" -maxdepth 1 -name "*.drl" | sort)

    if [ ${#GBR_FILES[@]} -eq 0 ] && [ ${#DRL_FILES[@]} -eq 0 ]; then
        echo "Error: no se encontraron archivos .gbr ni .drl en '$GERBER_DIR/'"
        exit 1
    fi

    if [ ${#GBR_FILES[@]} -eq 0 ]; then
        # Solo taladros
        echo "[auto] Modo solo-taladros: ${DRL_FILES[*]}"
        python3 gerber2gcode.py "${DRL_FILES[@]}"
    else
        GBR="${GBR_FILES[0]}"
        if [ ${#GBR_FILES[@]} -gt 1 ]; then
            echo "[auto] Múltiples .gbr encontrados, usando: $GBR"
        fi
        echo "[auto] Gerber : $GBR"
        [ ${#DRL_FILES[@]} -gt 0 ] && echo "[auto] Drills  : ${DRL_FILES[*]}"
        python3 gerber2gcode.py "$GBR" "${GBR%.gbr}.nc" "${DRL_FILES[@]}"
    fi
    exit 0
fi

# Con argumentos → comportamiento original
if [[ "$1" == *.drl ]]; then
    python3 gerber2gcode.py "$@"
else
    python3 gerber2gcode.py "$1" "${1%.gbr}.nc" "${@:2}"
fi
