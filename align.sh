#!/bin/bash
source venv/bin/activate

GERBER_DIR="Gerbers"

if [ "$#" -ne 4 ]; then
    echo "Uso: ./align.sh <X1> <Y1> <X2> <Y2>"
    echo ""
    echo "  X1 Y1 : posición real de la cruz inferior-izquierda"
    echo "  X2 Y2 : posición real de la cruz superior-derecha"
    echo ""
    echo "Ejemplo: ./align.sh 0.05 -0.02 96.28 79.61"
    exit 1
fi

REF_TXT=$(find "$GERBER_DIR" -maxdepth 1 -name "*-ref.txt" | sort | head -1)

if [ -z "$REF_TXT" ]; then
    echo "Error: no se encontró archivo -ref.txt en '$GERBER_DIR/'"
    exit 1
fi

echo "[align] Referencia : $REF_TXT"
echo "[align] Cruz 1     : ($1, $2)"
echo "[align] Cruz 2     : ($3, $4)"
echo ""

python3 fix_align.py "$REF_TXT" "$1" "$2" "$3" "$4"
