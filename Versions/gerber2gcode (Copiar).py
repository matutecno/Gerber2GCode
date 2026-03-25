"""
gerber2gcode.py — Gerber → G-code (isolation routing con iterative buffering)
Dependencias: pip install gerbonara shapely

Uso:
    python gerber2gcode.py input.gbr output.nc

El clearance se detecta automáticamente midiendo la distancia mínima entre
objetos de cobre individuales. Si no se puede detectar, se usa CLEARANCE_MM.
"""

import sys
from pathlib import Path
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.ops import unary_union
from gerbonara import GerberFile
from gerbonara.utils import MM
import math


def effective_tool_diameter() -> float:
    """
    Calcula el diámetro efectivo de corte de una V-bit en función
    de la profundidad de corte y el ángulo.

    Para una V-bit de ángulo total A y punta D, cortando a profundidad Z:
        d_efectivo = D + 2 × |Z| × tan(A/2)

    Ejemplo con los valores por defecto (tip=0.1, angle=60°, Z=-0.2):
        d_efectivo = 0.1 + 2 × 0.2 × tan(30°) = 0.331 mm
    """
    half_angle_rad = math.radians(VBIT_ANGLE_DEG / 2.0)
    d_eff = VBIT_TIP_MM + 2.0 * abs(CUT_DEPTH_MM) * math.tan(half_angle_rad)
    return d_eff

# ─────────────────────────────────────────────
# CONFIG — ajustá estos valores a tu máquina
# ─────────────────────────────────────────────
VBIT_TIP_MM       = 0.1     # diámetro de la punta de la V-bit (mm)
VBIT_ANGLE_DEG    = 60      # ángulo total de la V-bit (grados)
PASS_OVERLAP_FRAC = 0.1     # solapado entre pasadas (10% del diámetro efectivo)
CUT_DEPTH_MM      = -0.200  # profundidad de corte (Z negativo)
PLUNGE_RATE       = 750     # velocidad de bajada (mm/min)
FEED_RATE         = 400     # velocidad de corte (mm/min)
SAFE_Z_MM         = 3.000   # altura de viaje segura
CLEARANCE_MM      = None    # clearance manual en mm, o None para auto-detectar
# ─────────────────────────────────────────────


def load_gerber(path: str) -> GerberFile:
    """Carga el archivo Gerber y devuelve la capa."""
    print(f"[1/4] Cargando {path} ...")
    return GerberFile.open(path)


def _primitive_to_shapely(prim):
    """
    Convierte un GraphicPrimitive de gerbonara a geometría Shapely.
    Usa duck-typing para soportar distintas versiones de gerbonara.
    """
    cls = type(prim).__name__

    if cls == 'Line':
        ls = LineString([(prim.x1, prim.y1), (prim.x2, prim.y2)])
        return ls.buffer(prim.width / 2, cap_style=1)

    if cls == 'Circle':
        return Point(prim.x, prim.y).buffer(prim.r)

    if cls == 'Rectangle':
        x, y, w, h = prim.x, prim.y, prim.w, prim.h
        return Polygon([
            (x - w/2, y - h/2), (x + w/2, y - h/2),
            (x + w/2, y + h/2), (x - w/2, y + h/2),
        ])

    if hasattr(prim, 'outline'):
        pts = list(zip(prim.outline[0::2], prim.outline[1::2]))
        if len(pts) >= 3:
            return Polygon(pts)

    if hasattr(prim, 'coords'):
        try:
            pts = list(prim.coords)
            if len(pts) >= 3:
                return Polygon(pts)
        except Exception:
            pass

    return None


def extract_copper_polygons(layer: GerberFile):
    """
    Extrae geometría de cobre. Retorna:
      - merged: unary_union de todo el cobre (para calcular toolpaths)
      - individuals: lista de geometrías individuales por objeto (para detectar clearance)
    """
    print("[2/4] Extrayendo geometría de cobre ...")
    individuals = []  # una geometría por objeto (pad, pista, region)
    all_shapes  = []  # todos los primitivos planos

    for obj in layer.objects:
        if not getattr(obj, 'polarity_dark', True):
            continue
        try:
            obj_shapes = []
            for prim in obj.to_primitives(unit=MM):
                if not getattr(prim, 'polarity_dark', True):
                    continue
                geom = _primitive_to_shapely(prim)
                if geom is not None and not geom.is_empty and geom.is_valid:
                    obj_shapes.append(geom)
                    all_shapes.append(geom)
            if obj_shapes:
                merged_obj = unary_union(obj_shapes)
                if not merged_obj.is_empty:
                    individuals.append(merged_obj)
        except Exception:
            pass

    if not all_shapes:
        raise ValueError(
            "No se encontró geometría de cobre.\n"
            "Verificá que el archivo sea una capa de cobre (B_Cu / F_Cu)."
        )

    merged = unary_union(all_shapes)
    n = len(merged.geoms) if hasattr(merged, 'geoms') else 1
    print(f"    → {len(all_shapes)} primitivos, {len(individuals)} objetos → {n} polígono(s) fusionado(s)")
    return merged, individuals


def detect_clearance(individuals: list) -> float | None:
    """
    Mide la distancia mínima entre objetos de cobre individuales
    (antes del unary_union). Esto captura el clearance real entre
    pistas/pads incluso cuando son de la misma red.
    """
    if len(individuals) < 2:
        return None

    min_dist = float('inf')
    sample = individuals[:80]  # limitar para no tardar demasiado
    for i in range(len(sample)):
        for j in range(i + 1, len(sample)):
            d = sample[i].distance(sample[j])
            if 0 < d < min_dist:
                min_dist = d

    return min_dist if min_dist != float('inf') else None


def _extract_contours(geom) -> list:
    """Extrae todos los contornos (exterior + huecos) de una geometría."""
    contours = []
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    for poly in polys:
        if isinstance(poly, Polygon) and not poly.is_empty:
            contours.append(('exterior', poly))
            for interior in poly.interiors:
                contours.append(('hole', Polygon(interior)))
    return contours


def compute_isolation_paths(copper_geom, tool_radius: float, clearance: float) -> list:
    """
    Iterative buffering: genera múltiples pasadas concéntricas para cubrir
    el clearance completo.

    Las pasadas se distribuyen uniformemente entre tool_radius y
    clearance - tool_radius, garantizando al menos 2 pasadas.
    """
    import math as _math

    d_eff = effective_tool_diameter()
    step  = d_eff * (1.0 - PASS_OVERLAP_FRAC)

    first_offset = tool_radius
    last_offset  = clearance - tool_radius

    # Si el espacio es muy ajustado, forzar al menos 2 pasadas
    if last_offset <= first_offset:
        last_offset = first_offset + step

    n_passes = max(2, _math.ceil((last_offset - first_offset) / step) + 1)
    offsets  = [
        first_offset + i * (last_offset - first_offset) / (n_passes - 1)
        for i in range(n_passes)
    ]

    print(f"[3/4] Iterative buffering:")
    print(f"    clearance detectado  = {clearance:.3f} mm")
    print(f"    diámetro efectivo    = {d_eff:.3f} mm")
    print(f"    step entre pasadas   = {step:.3f} mm")
    print(f"    pasadas a generar    = {n_passes}")
    print(f"    offsets              = {[f'{o:.3f}' for o in offsets]}")

    paths = []
    polys = list(copper_geom.geoms) if isinstance(copper_geom, MultiPolygon) else [copper_geom]

    for poly in polys:
        if not isinstance(poly, Polygon) or poly.is_empty:
            continue

        for offset_dist in offsets:
            # Offset exterior
            result = poly.buffer(offset_dist, join_style=2, cap_style=2)
            if result is None or result.is_empty:
                continue
            sub_polys = list(result.geoms) if isinstance(result, MultiPolygon) else [result]
            for sp in sub_polys:
                if isinstance(sp, Polygon) and not sp.is_empty:
                    coords = list(sp.exterior.coords)
                    if len(coords) >= 2:
                        paths.append(coords)

            # Huecos internos
            for interior in poly.interiors:
                hole = Polygon(interior)
                hole_result = hole.buffer(-offset_dist, join_style=2, cap_style=2)
                if hole_result is None or hole_result.is_empty:
                    continue
                hole_polys = list(hole_result.geoms) if isinstance(hole_result, MultiPolygon) else [hole_result]
                for hp in hole_polys:
                    if isinstance(hp, Polygon) and not hp.is_empty:
                        coords = list(hp.exterior.coords)
                        if len(coords) >= 2:
                            paths.append(coords)

    print(f"    → {len(paths)} path(s) total")
    return paths


def generate_gcode(paths: list, output_path: str, clearance: float):
    """Escribe el archivo G-code compatible con GRBL."""
    print(f"[4/4] Generando G-code → {output_path} ...")
    lines = []

    d_eff = effective_tool_diameter()
    lines += [
        "( Generated by gerber2gcode.py )",
        f"( V-bit tip      : {VBIT_TIP_MM} mm, angle: {VBIT_ANGLE_DEG} deg )",
        f"( Effective diam : {d_eff:.3f} mm at Z={CUT_DEPTH_MM} mm )",
        f"( Clearance      : {clearance:.3f} mm )",
        f"( Cut depth      : {CUT_DEPTH_MM} mm )",
        "G17", "G21", "G54", "G90",
    ]

    for path in paths:
        if len(path) < 2:
            continue
        x0, y0 = path[0]
        lines += [
            f"G00  X{x0:.3f} Y{y0:.3f}",
            f"G01 F{PLUNGE_RATE} Z0",
            f"G01 F{PLUNGE_RATE} Z{CUT_DEPTH_MM}",
        ]
        for x, y in path[1:]:
            lines.append(f"G01 F{FEED_RATE} X{x:.3f} Y{y:.3f}")
        lines.append(f"G00 Z{SAFE_Z_MM:.3f}")

    lines += [f"G00 Z{SAFE_Z_MM:.3f}", "M05", "M30"]

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"    ✓ {len(lines)} líneas escritas")


def main():
    if len(sys.argv) < 3:
        print("Uso: python gerber2gcode.py <input.gbr> <output.nc>")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    if not Path(input_path).exists():
        print(f"Error: no existe el archivo '{input_path}'")
        sys.exit(1)

    # Calcular diámetro efectivo de la V-bit
    d_eff = effective_tool_diameter()
    tool_radius = d_eff / 2.0
    print(f"[✓] V-bit: punta={VBIT_TIP_MM} mm, ángulo={VBIT_ANGLE_DEG}°, "
          f"profundidad={CUT_DEPTH_MM} mm")
    print(f"    → Diámetro efectivo de corte: {d_eff:.3f} mm")

    layer          = load_gerber(input_path)
    copper, indivs = extract_copper_polygons(layer)

    # Clearance: manual > auto-detectado > fallback
    if CLEARANCE_MM is not None:
        clearance = CLEARANCE_MM
        print(f"[✓] Clearance manual: {clearance:.3f} mm")
    else:
        clearance = detect_clearance(indivs)
        if clearance is None:
            clearance = d_eff
            print(f"[!] No se pudo detectar clearance, usando {clearance:.3f} mm")
            print(f"    → Definí CLEARANCE_MM en CONFIG para forzar un valor")
        else:
            print(f"[✓] Clearance detectado automáticamente: {clearance:.3f} mm")

    paths = compute_isolation_paths(copper, tool_radius, clearance)
    generate_gcode(paths, output_path, clearance)
    print("\n✓ Listo.")


if __name__ == "__main__":
    main()
