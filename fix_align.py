#!/usr/bin/env python3
"""
fix_align.py — Corrige offset y rotación en archivos de taladrado

Uso:
    python fix_align.py <ref.txt> <ax1> <ay1> <ax2> <ay2>

    ref.txt : archivo generado por gerber2gcode.py junto con el -ref.nc
    ax1,ay1 : posición REAL de la marca 1 (origen) leída en la máquina
    ax2,ay2 : posición REAL de la marca 2 (esquina superior derecha) leída en la máquina

Ejemplo:
    python fix_align.py output/case-B_Cu-ref.txt 0.05 -0.03 94.21 77.61

El script reescribe todos los archivos -drill-*.nc y -slots.nc del mismo directorio.
"""

import sys
import re
import math
from pathlib import Path


def load_ref(path: str):
    data = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if '=' in line:
                k, v = line.split('=', 1)
                data[k.strip()] = v.strip()
    return (float(data['EX1']), float(data['EY1']),
            float(data['EX2']), float(data['EY2']),
            data['STEM'])


def compute_transform(ex1, ey1, ex2, ey2, ax1, ay1, ax2, ay2):
    """Calcula rotación + traslación a partir de 2 pares de puntos."""
    angle = math.atan2(ay2 - ay1, ax2 - ax1) - math.atan2(ey2 - ey1, ex2 - ex1)
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    # Trasladar para que P1 esperado rote sobre sí mismo, luego ajustar a P1 real
    rx = ex1 * cos_a - ey1 * sin_a
    ry = ex1 * sin_a + ey1 * cos_a
    tx = ax1 - rx
    ty = ay1 - ry

    return cos_a, sin_a, tx, ty


def apply_transform(x, y, cos_a, sin_a, tx, ty):
    return (x * cos_a - y * sin_a + tx,
            x * sin_a + y * cos_a + ty)


def fix_nc_file(path: str, cos_a, sin_a, tx, ty):
    coord_re = re.compile(r'([XY])([+-]?\d+\.\d+)')

    with open(path) as f:
        lines = f.readlines()

    out = []
    for line in lines:
        if not any(tag in line for tag in ('G00', 'G01')):
            out.append(line)
            continue

        matches = {m.group(1): (m, float(m.group(2))) for m in coord_re.finditer(line)}
        if 'X' in matches and 'Y' in matches:
            x = matches['X'][1]
            y = matches['Y'][1]
            nx, ny = apply_transform(x, y, cos_a, sin_a, tx, ty)

            def replacer(m):
                if m.group(1) == 'X':
                    return f"X{nx:.3f}"
                if m.group(1) == 'Y':
                    return f"Y{ny:.3f}"
                return m.group(0)

            line = coord_re.sub(replacer, line)
        out.append(line)

    out_path = Path(path).stem + "_aligned.nc"
    out_path = str(Path(path).parent / out_path)
    with open(out_path, 'w') as f:
        f.writelines(out)
    print(f"  ✓ {out_path}")


def main():
    if len(sys.argv) != 6:
        print("Uso: python fix_align.py <ref.txt> <ax1> <ay1> <ax2> <ay2>")
        sys.exit(1)

    ref_path         = sys.argv[1]
    ax1, ay1         = float(sys.argv[2]), float(sys.argv[3])
    ax2, ay2         = float(sys.argv[4]), float(sys.argv[5])

    ex1, ey1, ex2, ey2, stem = load_ref(ref_path)

    print(f"[ref] Posiciones esperadas:  P1=({ex1:.3f}, {ey1:.3f})  P2=({ex2:.3f}, {ey2:.3f})")
    print(f"[ref] Posiciones reales:     P1=({ax1:.3f}, {ay1:.3f})  P2=({ax2:.3f}, {ay2:.3f})")

    cos_a, sin_a, tx, ty = compute_transform(ex1, ey1, ex2, ey2, ax1, ay1, ax2, ay2)
    angle_deg = math.degrees(math.atan2(sin_a, cos_a))

    print(f"\n[corrección]")
    print(f"  Rotación   : {angle_deg:.4f}°")
    print(f"  Traslación : X={tx:+.3f} mm  Y={ty:+.3f} mm\n")

    # Buscar todos los archivos de taladros y ranuras del mismo stem
    stem_path = Path(stem)
    targets = [p for p in
               list(stem_path.parent.glob(f"{stem_path.name}-drill-*.nc")) +
               list(stem_path.parent.glob(f"{stem_path.name}-slots.nc"))
               if not p.stem.endswith("_aligned")]

    if not targets:
        print(f"[!] No se encontraron archivos de taladros en '{stem_path.parent}'")
        sys.exit(1)

    print(f"[fix] Corrigiendo {len(targets)} archivo(s):")
    for path in sorted(targets):
        fix_nc_file(str(path), cos_a, sin_a, tx, ty)

    print("\n✓ Listo.")


if __name__ == "__main__":
    main()
