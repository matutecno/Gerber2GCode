"""
gerber2gcode.py — Gerber → G-code (isolation routing + laser + drills)
Dependencias: pip install gerbonara shapely

Uso:
    python gerber2gcode.py input.gbr output.nc [drill1.drl [drill2.drl ...]]

    Si se pasan archivos .drl, genera además:
        output-drill-0.80mm.nc   (uno por diámetro)
        output-slots.nc          (ranuras/ovalados)

Modos:
    MODE = "mill"   → fresa V-bit, isolation routing
    MODE = "laser"  → láser, quema pintura fuera de las pistas (transferencia)
"""

import sys
import re
import math
from pathlib import Path
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box
from shapely.ops import unary_union
from shapely.affinity import scale as shapely_scale, translate as shapely_translate
from gerbonara import GerberFile
from gerbonara.utils import MM

# ─────────────────────────────────────────────
# CONFIG GENERAL
# ─────────────────────────────────────────────
MODE          = "mill"  # "mill" o "laser"
SAFE_Z_MM     = 1.500   # altura de viaje segura (solo fresa)
CLEARANCE_MM  = None    # clearance manual en mm, o None para auto-detectar
MIRROR_X      = True    # True para B_Cu: espeja horizontalmente antes de generar G-code

# CONFIG FRESA
VBIT_TIP_MM       = 0.1     # diámetro de la punta de la V-bit (mm)
VBIT_ANGLE_DEG    = 20      # ángulo total de la V-bit (grados)
PASS_OVERLAP_FRAC = 0.3     # solapado entre pasadas
CUT_DEPTH_MM      = -0.1  # profundidad de corte (Z negativo)
PLUNGE_RATE       = 80    # velocidad de bajada (mm/min)
FEED_RATE         = 1300     # velocidad de corte (mm/min)
OVERSHOOT_MM      = 1.0     # sobreextensión al cierre de cada contorno (mm)

# CONFIG LÁSER (estándar GRBL)
LASER_POWER       = 800     # potencia (S value, 0-1000)
LASER_FEED_RATE   = 1000    # velocidad de grabado (mm/min)
LASER_PASS_MM     = 0.05    # distancia entre pasadas concéntricas (mm)

# CONFIG TALADRADO
DRILL_SIZES       = [0.8, 1.0, 1.25, 3.0]  # brocas disponibles (mm) — cada agujero se redondea a la inmediata superior
DRILL_SAFE_Z_MM   = 3.0     # altura de viaje segura
DRILL_DEPTH_MM    = -1.6    # profundidad de taladrado (Z negativo)
DRILL_FEED_RATE   = 50      # velocidad de taladrado (mm/min)

# CONFIG MARCAS DE REFERENCIA
REF_MARK_DEPTH_MM = -0.15   # profundidad de corte de la cruz (solo visible, no pasante)
REF_CROSS_MM      = 3.0     # longitud total del brazo de la cruz "+" (mm)
REF_OFFSET_MM     = 2.0     # distancia desde el borde del PCB al centro de la cruz (mm)

# CONFIG RANURAS
SLOT_TOOL_MM      = 0.8     # diámetro real de la fresa usada para ranuras
SLOT_DEPTH_MM     = -1.6    # profundidad de ranuras (Z negativo)
SLOT_PLUNGE_RATE  = 30      # velocidad de bajada en ranuras (mm/min)
SLOT_FEED_RATE    = 80      # velocidad de corte en ranuras (mm/min)
# ─────────────────────────────────────────────


def mirror_geometry(geom, cx: float):
    """Espeja la geometría shapely alrededor del eje vertical x=cx."""
    return shapely_scale(geom, xfact=-1, yfact=1, origin=(cx, 0))


def mirror_point(x: float, cx: float) -> float:
    """Espeja una coordenada X alrededor de cx."""
    return 2 * cx - x


def effective_tool_diameter() -> float:
    """Diámetro efectivo de corte de la V-bit según profundidad y ángulo."""
    half_angle_rad = math.radians(VBIT_ANGLE_DEG / 2.0)
    return VBIT_TIP_MM + 2.0 * abs(CUT_DEPTH_MM) * math.tan(half_angle_rad)


def load_gerber(path: str) -> GerberFile:
    print(f"[1/4] Cargando {path} ...")
    return GerberFile.open(path)


def _primitive_to_shapely(prim):
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
    """Extrae geometría de cobre. Retorna (merged, individuals)."""
    print("[2/4] Extrayendo geometría de cobre ...")
    individuals = []
    all_shapes  = []

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


def detect_clearance(individuals: list):
    """Distancia mínima entre objetos de cobre individuales."""
    if len(individuals) < 2:
        return None
    min_dist = float('inf')
    sample = individuals[:80]
    for i in range(len(sample)):
        for j in range(i + 1, len(sample)):
            d = sample[i].distance(sample[j])
            if 0 < d < min_dist:
                min_dist = d
    return min_dist if min_dist != float('inf') else None


# ─────────────────────────────────────────────
# MODO FRESA
# ─────────────────────────────────────────────

def compute_mill_paths(copper_geom, tool_radius: float, clearance: float) -> list:
    """Iterative buffering hacia afuera del cobre."""
    d_eff = effective_tool_diameter()
    step  = d_eff * (1.0 - PASS_OVERLAP_FRAC)

    first_offset = tool_radius
    last_offset  = clearance - tool_radius
    if last_offset <= first_offset:
        last_offset = first_offset + step

    n_passes = max(2, math.ceil((last_offset - first_offset) / step) + 1)
    offsets  = [
        first_offset + i * (last_offset - first_offset) / (n_passes - 1)
        for i in range(n_passes)
    ]

    print(f"[3/4] Fresa — iterative buffering:")
    print(f"    clearance           = {clearance:.3f} mm")
    print(f"    diámetro efectivo   = {d_eff:.3f} mm")
    print(f"    pasadas             = {n_passes}")
    print(f"    offsets             = {[f'{o:.3f}' for o in offsets]}")

    paths = []
    polys = list(copper_geom.geoms) if isinstance(copper_geom, MultiPolygon) else [copper_geom]

    for poly in polys:
        if not isinstance(poly, Polygon) or poly.is_empty:
            continue
        for offset_dist in offsets:
            result = poly.buffer(offset_dist, join_style=2, cap_style=2)
            if result is None or result.is_empty:
                continue
            for sp in (list(result.geoms) if isinstance(result, MultiPolygon) else [result]):
                if isinstance(sp, Polygon) and not sp.is_empty:
                    paths.append(list(sp.exterior.coords))
            for interior in poly.interiors:
                hole_result = Polygon(interior).buffer(-offset_dist, join_style=2, cap_style=2)
                if hole_result is None or hole_result.is_empty:
                    continue
                for hp in (list(hole_result.geoms) if isinstance(hole_result, MultiPolygon) else [hole_result]):
                    if isinstance(hp, Polygon) and not hp.is_empty:
                        paths.append(list(hp.exterior.coords))

    print(f"    → {len(paths)} path(s) total")
    return paths


def generate_mill_gcode(paths: list, output_path: str, clearance: float,
                        board_w: float = None, board_h: float = None):
    """G-code para fresa, compatible con GRBL."""
    print(f"[4/4] Generando G-code (fresa) → {output_path} ...")
    d_eff = effective_tool_diameter()
    lines = [
        "( Generated by gerber2gcode.py — MODE: mill )",
        f"( V-bit tip      : {VBIT_TIP_MM} mm, angle: {VBIT_ANGLE_DEG} deg )",
        f"( Effective diam : {d_eff:.3f} mm at Z={CUT_DEPTH_MM} mm )",
        f"( Clearance      : {clearance:.3f} mm )",
        "G17", "G21", "G54", "G90",
        f"G00 Z{SAFE_Z_MM:.3f}",   # subir a altura segura antes de cualquier movimiento
    ]
    # Marcas de referencia en cruz — primero que se ejecuta
    if board_w is not None and board_h is not None:
        lines.append("( ── MARCAS DE REFERENCIA ── )")
        lines += _cross_gcode(-REF_OFFSET_MM, -REF_OFFSET_MM, "Ref 1 — inferior-izquierda")
        lines += _cross_gcode(board_w + REF_OFFSET_MM, board_h + REF_OFFSET_MM, "Ref 2 — superior-derecha")
        lines.append("( ── FRESADO ── )")
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
        # Sobreextender OVERSHOOT_MM siguiendo la geometría del contorno
        # (path es cerrado: path[-1]==path[0], continuamos por path[1], path[2]...)
        if OVERSHOOT_MM > 0 and len(path) >= 3:
            remaining = OVERSHOOT_MM
            px, py = path[-1]
            for nx, ny in path[1:]:
                seg = math.hypot(nx - px, ny - py)
                if seg >= remaining:
                    t = remaining / seg
                    lines.append(f"G01 F{FEED_RATE} X{px + t*(nx-px):.3f} Y{py + t*(ny-py):.3f}")
                    break
                lines.append(f"G01 F{FEED_RATE} X{nx:.3f} Y{ny:.3f}")
                remaining -= seg
                px, py = nx, ny
                if remaining <= 0:
                    break
        lines.append(f"G00 Z{SAFE_Z_MM:.3f}")
    lines += [f"G00 Z{SAFE_Z_MM:.3f}", "M05", "M30"]
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"    ✓ {len(lines)} líneas escritas")


# ─────────────────────────────────────────────
# MODO LÁSER
# ─────────────────────────────────────────────

def compute_laser_paths(copper_geom) -> list:
    """
    Contornos concéntricos hacia adentro del área libre (entre pistas).
    El láser quema la pintura en todo el espacio que NO es cobre.

    Estrategia:
    1. Calcular el bounding box de la placa como área total
    2. Restar el cobre → área libre
    3. Hacer shrink iterativo del área libre hacia adentro
       (equivale a offset interior de los polígonos libres)
    """
    bounds = copper_geom.buffer(1.0).bounds  # margen de 1mm alrededor
    board  = box(*bounds)
    free_area = board.difference(copper_geom)

    if free_area.is_empty:
        raise ValueError("No hay área libre entre las pistas.")

    step = LASER_PASS_MM
    paths = []
    current = free_area

    iteration = 0
    while not current.is_empty:
        polys = list(current.geoms) if isinstance(current, MultiPolygon) else [current]
        for poly in polys:
            if not isinstance(poly, Polygon) or poly.is_empty:
                continue
            coords = list(poly.exterior.coords)
            if len(coords) >= 2:
                paths.append(coords)
            # huecos internos (islas de cobre dentro del área libre)
            for interior in poly.interiors:
                paths.append(list(interior.coords))

        # Shrink del área libre (erosión)
        current = current.buffer(-step, join_style=2, cap_style=2)
        if current is None:
            break
        iteration += 1
        if iteration > 5000:  # safety cap
            break

    print(f"[3/4] Láser — contornos concéntricos:")
    print(f"    paso entre contornos = {step:.3f} mm")
    print(f"    contornos generados  = {iteration}")
    print(f"    → {len(paths)} path(s) total")
    return paths


def generate_laser_gcode(paths: list, output_path: str):
    """G-code para láser GRBL (M4 = potencia dinámica)."""
    print(f"[4/4] Generando G-code (láser) → {output_path} ...")
    lines = [
        "( Generated by gerber2gcode.py — MODE: laser )",
        f"( Laser power    : S{LASER_POWER} )",
        f"( Feed rate      : {LASER_FEED_RATE} mm/min )",
        f"( Pass step      : {LASER_PASS_MM} mm )",
        "G17", "G21", "G54", "G90",
        "M4",  # modo láser dinámico (GRBL estándar)
    ]
    for path in paths:
        if len(path) < 2:
            continue
        x0, y0 = path[0]
        lines += [
            f"G00 X{x0:.3f} Y{y0:.3f}",          # mover sin quemar
            f"G01 F{LASER_FEED_RATE} S{LASER_POWER}",  # encender láser
        ]
        for x, y in path[1:]:
            lines.append(f"G01 X{x:.3f} Y{y:.3f}")
        lines.append("S0")  # apagar láser entre contornos
    lines += ["M5", "M30"]
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"    ✓ {len(lines)} líneas escritas")


# ─────────────────────────────────────────────
# MARCAS DE REFERENCIA
# ─────────────────────────────────────────────

def _cross_gcode(cx: float, cy: float, label: str) -> list:
    """Genera las líneas G-code para una cruz '+' centrada en (cx, cy)."""
    arm = REF_CROSS_MM / 2.0
    return [
        f"( {label} — cruz en ({cx:.3f}, {cy:.3f}) )",
        # brazo horizontal
        f"G00 X{cx - arm:.3f} Y{cy:.3f}",
        f"G01 F{PLUNGE_RATE} Z{REF_MARK_DEPTH_MM:.3f}",
        f"G01 F{FEED_RATE} X{cx + arm:.3f} Y{cy:.3f}",
        f"G00 Z{SAFE_Z_MM:.3f}",
        # brazo vertical
        f"G00 X{cx:.3f} Y{cy - arm:.3f}",
        f"G01 F{PLUNGE_RATE} Z{REF_MARK_DEPTH_MM:.3f}",
        f"G01 F{FEED_RATE} X{cx:.3f} Y{cy + arm:.3f}",
        f"G00 Z{SAFE_Z_MM:.3f}",
    ]


def generate_ref_marks(board_w: float, board_h: float, output_stem: str):
    """
    Genera dos marcas de referencia en cruz '+' (REF_CROSS_MM) con V-bit:
      P1 = inferior-izquierda: centro a REF_OFFSET_MM fuera del origen
      P2 = superior-derecha:   centro a REF_OFFSET_MM fuera de (board_w, board_h)
    Produce:
      <stem>-ref.nc   → G-code para fresar las dos cruces
      <stem>-ref.txt  → posiciones esperadas para fix_align.py
    """
    nc_path  = f"{output_stem}-ref.nc"
    txt_path = f"{output_stem}-ref.txt"

    o   = REF_OFFSET_MM
    c1x, c1y = -o,           -o
    c2x, c2y =  board_w + o,  board_h + o

    lines = [
        "( Generated by gerber2gcode.py — REFERENCE MARKS )",
        f"( Cruz '+' de {REF_CROSS_MM:.1f} mm, offset {REF_OFFSET_MM:.1f} mm desde bordes del PCB )",
        f"( P1 = ({c1x:.3f}, {c1y:.3f})  —  inferior-izquierda )",
        f"( P2 = ({c2x:.3f}, {c2y:.3f})  —  superior-derecha )",
        "G17", "G21", "G54", "G90",
        f"G00 Z{SAFE_Z_MM:.3f}",
    ]
    lines += _cross_gcode(c1x, c1y, "Marca 1 — inferior-izquierda")
    lines += _cross_gcode(c2x, c2y, "Marca 2 — superior-derecha")
    lines += ["M05", "M30"]

    with open(nc_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    with open(txt_path, 'w') as f:
        f.write(f"EX1={c1x:.3f}\n")
        f.write(f"EY1={c1y:.3f}\n")
        f.write(f"EX2={c2x:.3f}\n")
        f.write(f"EY2={c2y:.3f}\n")
        f.write(f"STEM={output_stem}\n")

    print(f"[ref] {nc_path}")
    print(f"      P1=({c1x:.3f}, {c1y:.3f})  P2=({c2x:.3f}, {c2y:.3f})")
    print(f"[ref] {txt_path}  (usar con fix_align.py)")


# ─────────────────────────────────────────────
# TALADRADO (Excellon .drl)
# ─────────────────────────────────────────────

def map_drill_size(diam: float) -> float:
    """Asigna el diámetro a la broca disponible inmediata superior en DRILL_SIZES."""
    for size in sorted(DRILL_SIZES):
        if diam <= size + 1e-6:
            return size
    return sorted(DRILL_SIZES)[-1]


def parse_excellon(path: str) -> dict:
    """
    Parsea un archivo Excellon de KiCad (METRIC decimal).
    Retorna:
        {
          'holes': {0.75: [(x,y), ...], ...},      # agujeros redondos por diámetro
          'slots': [(x1,y1, x2,y2, diam), ...]     # ranuras
        }
    """
    print(f"[drill] Parseando {path} ...")

    tools        = {}    # T number → diameter mm
    holes        = {}    # diam → [(x, y), ...]
    slots        = []    # [(x1, y1, x2, y2, diam)]
    current_diam = None
    slot_start   = None
    in_slot      = False
    in_header    = True

    coord_re    = re.compile(r'X([+-]?\d+\.?\d*)Y([+-]?\d+\.?\d*)')
    tool_def_re = re.compile(r'^T(\d+)C([\d.]+)')
    tool_sel_re = re.compile(r'^T(\d+)\s*$')

    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(';'):
                continue

            if line == 'M48':
                in_header = True
                continue
            if line == '%':
                in_header = False
                continue

            # Definición de herramienta (en cabecera)
            m = tool_def_re.match(line)
            if m:
                tools[int(m.group(1))] = float(m.group(2))
                continue

            if in_header:
                continue

            if line == 'M30':
                break
            if line in ('G90', 'G05', 'FMAT,2', 'METRIC'):
                continue

            # Selección de herramienta
            m = tool_sel_re.match(line)
            if m:
                current_diam = tools.get(int(m.group(1)))
                in_slot      = False
                slot_start   = None
                continue

            # Ranura — G00: rápido al inicio
            if line.startswith('G00'):
                m = coord_re.search(line)
                if m:
                    slot_start = (float(m.group(1)), float(m.group(2)))
                    in_slot    = True
                continue

            # Ranura — G01: corte hasta el final
            if line.startswith('G01') and in_slot and slot_start is not None:
                m = coord_re.search(line)
                if m and current_diam is not None:
                    slots.append((slot_start[0], slot_start[1],
                                  float(m.group(1)), float(m.group(2)),
                                  current_diam))
                    slot_start = None
                    in_slot    = False
                continue

            if line in ('M15', 'M16', 'G05'):
                continue

            # Agujero redondo: coordenada XY simple
            m = coord_re.match(line)
            if m and current_diam is not None:
                holes.setdefault(current_diam, []).append(
                    (float(m.group(1)), float(m.group(2)))
                )

    total = sum(len(v) for v in holes.values())
    diams = sorted(holes.keys())
    print(f"    → diámetros: {[f'{d:.3f}mm' for d in diams]}")
    print(f"    → agujeros: {total}  ranuras: {len(slots)}")
    return {'holes': holes, 'slots': slots}


def generate_drill_gcode(diameter_mm: float, holes: list, output_path: str):
    """G-code para taladrar agujeros de un diámetro."""
    print(f"[drill] {output_path}  ({len(holes)} agujeros, ø{diameter_mm:.3f} mm) ...")
    lines = [
        f"( Generated by gerber2gcode.py — DRILLS {diameter_mm:.3f} mm )",
        f"( Tool: {diameter_mm:.3f} mm drill bit )",
        f"( Holes: {len(holes)} )",
        "G17", "G21", "G54", "G90",
        f"G00 Z{DRILL_SAFE_Z_MM:.3f}",
    ]
    for x, y in holes:
        lines += [
            f"G00 X{x:.3f} Y{y:.3f}",
            f"G01 F{DRILL_FEED_RATE} Z{DRILL_DEPTH_MM:.3f}",
            f"G00 Z{DRILL_SAFE_Z_MM:.3f}",
        ]
    lines += ["M05", "M30"]
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"    ✓ {len(lines)} líneas escritas")


def generate_slots_gcode(slots: list, output_path: str):
    """G-code para ranuras/ovalados con múltiples pasadas si la fresa es menor al ancho."""
    print(f"[slots] {output_path}  ({len(slots)} ranuras) ...")
    lines = [
        "( Generated by gerber2gcode.py — SLOTS )",
        f"( Tool diameter  : {SLOT_TOOL_MM:.3f} mm )",
        f"( Slots: {len(slots)} )",
        "G17", "G21", "G54", "G90",
        f"G00 Z{DRILL_SAFE_Z_MM:.3f}",
    ]

    for x1, y1, x2, y2, diam in slots:
        offset = (diam - SLOT_TOOL_MM) / 2.0

        # Vector unitario perpendicular al slot
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        # perpendicular: rotar 90°
        px, py = -dy / length, dx / length

        # Pasadas: izquierda, centro, derecha (solo centro si offset=0)
        offsets = [-offset, 0.0, offset] if offset > 1e-6 else [0.0]

        lines.append(f"( slot ø{diam:.3f}mm — fresa {SLOT_TOOL_MM:.3f}mm — {len(offsets)} pasada(s) )")
        for o in offsets:
            ax = x1 + px * o
            ay = y1 + py * o
            bx = x2 + px * o
            by = y2 + py * o
            lines += [
                f"G00 X{ax:.3f} Y{ay:.3f}",
                f"G01 F{SLOT_PLUNGE_RATE} Z{SLOT_DEPTH_MM:.3f}",
                f"G01 F{SLOT_FEED_RATE} X{bx:.3f} Y{by:.3f}",
                f"G00 Z{DRILL_SAFE_Z_MM:.3f}",
            ]

    lines += ["M05", "M30"]
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"    ✓ {len(lines)} líneas escritas")


def process_drill_files(drl_paths: list, output_stem: str,
                        cx: float = None, offset: tuple = (0.0, 0.0)):
    """Procesa uno o más .drl y genera los .nc por diámetro + slots."""
    all_holes = {}
    all_slots = []

    for drl_path in drl_paths:
        result = parse_excellon(drl_path)
        for diam, pts in result['holes'].items():
            all_holes.setdefault(diam, []).extend(pts)
        all_slots.extend(result['slots'])

    # Reasignar a brocas disponibles
    mapped_holes = {}
    for diam, pts in all_holes.items():
        target = map_drill_size(diam)
        if diam != target:
            print(f"    [map] ø{diam:.3f}mm → ø{target:.3f}mm  ({len(pts)} agujeros)")
        mapped_holes.setdefault(target, []).extend(pts)
    all_holes = mapped_holes

    if MIRROR_X and cx is not None:
        all_holes = {
            diam: [(mirror_point(x, cx), y) for x, y in pts]
            for diam, pts in all_holes.items()
        }
        all_slots = [
            (mirror_point(x1, cx), y1, mirror_point(x2, cx), y2, diam)
            for x1, y1, x2, y2, diam in all_slots
        ]

    ox, oy = offset
    all_holes = {
        diam: [(x + ox, y + oy) for x, y in pts]
        for diam, pts in all_holes.items()
    }
    all_slots = [
        (x1 + ox, y1 + oy, x2 + ox, y2 + oy, diam)
        for x1, y1, x2, y2, diam in all_slots
    ]

    for diam in sorted(all_holes.keys()):
        fname = f"{output_stem}-drill-{diam:.2f}mm.nc"
        generate_drill_gcode(diam, all_holes[diam], fname)

    if all_slots:
        generate_slots_gcode(all_slots, f"{output_stem}-slots.nc")
    else:
        print("[slots] No se encontraron ranuras.")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python gerber2gcode.py <input.gbr> <output.nc> [drill.drl ...]")
        print("  python gerber2gcode.py <input.drl> [more.drl ...]")
        sys.exit(1)

    # Modo solo-taladros: todos los argumentos son .drl
    if all(Path(a).suffix.lower() == '.drl' for a in sys.argv[1:]):
        drl_paths = sys.argv[1:]
        for drl in drl_paths:
            if not Path(drl).exists():
                print(f"Error: no existe el archivo '{drl}'")
                sys.exit(1)
        # Stem de salida desde el primer .drl, sin extensión
        output_stem = str(Path(drl_paths[0]).with_suffix(''))
        print("[✓] Modo: SOLO TALADROS")
        if MIRROR_X:
            print("[✓] MIRROR_X activo")
        print()
        process_drill_files(drl_paths, output_stem)
        print("\n✓ Listo.")
        return

    if len(sys.argv) < 3:
        print("Uso: python gerber2gcode.py <input.gbr> <output.nc> [drill.drl ...]")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]
    drl_paths = sys.argv[3:]

    if not Path(input_path).exists():
        print(f"Error: no existe el archivo '{input_path}'")
        sys.exit(1)

    for drl in drl_paths:
        if not Path(drl).exists():
            print(f"Error: no existe el archivo '{drl}'")
            sys.exit(1)

    print(f"[✓] Modo: {MODE.upper()}")
    if MIRROR_X:
        print("[✓] MIRROR_X activo — espejado horizontal (B_Cu)")

    layer          = load_gerber(input_path)
    copper, indivs = extract_copper_polygons(layer)

    # Calcular centro X antes de espejo (usado también para los taladros)
    bounds = copper.bounds  # (minx, miny, maxx, maxy)
    cx = (bounds[0] + bounds[2]) / 2.0

    if MIRROR_X:
        print(f"    → Centro X del tablero: {cx:.3f} mm")
        copper  = mirror_geometry(copper, cx)
        indivs  = [mirror_geometry(g, cx) for g in indivs]

    # Trasladar esquina inferior-izquierda al origen (cuadrante I)
    minx, miny, _, _ = copper.bounds
    copper = shapely_translate(copper, xoff=-minx, yoff=-miny)
    indivs = [shapely_translate(g, xoff=-minx, yoff=-miny) for g in indivs]
    print(f"[✓] Traslación al origen: offset X={-minx:.3f} mm  Y={-miny:.3f} mm")

    if MODE == "mill":
        d_eff = effective_tool_diameter()
        tool_radius = d_eff / 2.0
        print(f"[✓] V-bit: punta={VBIT_TIP_MM} mm, ángulo={VBIT_ANGLE_DEG}°, profundidad={CUT_DEPTH_MM} mm")
        print(f"    → Diámetro efectivo de corte: {d_eff:.3f} mm")

        if CLEARANCE_MM is not None:
            clearance = CLEARANCE_MM
            print(f"[✓] Clearance manual: {clearance:.3f} mm")
        else:
            clearance = detect_clearance(indivs)
            if clearance is None:
                clearance = d_eff
                print(f"[!] No se pudo detectar clearance, usando {clearance:.3f} mm")
            else:
                print(f"[✓] Clearance detectado automáticamente: {clearance:.3f} mm")

        paths = compute_mill_paths(copper, tool_radius, clearance)
        _, _, board_w, board_h = copper.bounds
        generate_mill_gcode(paths, output_path, clearance, board_w, board_h)

    elif MODE == "laser":
        print(f"[✓] Láser: potencia=S{LASER_POWER}, feed={LASER_FEED_RATE} mm/min, paso={LASER_PASS_MM} mm")
        paths = compute_laser_paths(copper)
        generate_laser_gcode(paths, output_path)

    else:
        print(f"Error: MODE '{MODE}' desconocido. Usá 'mill' o 'laser'.")
        sys.exit(1)

    if drl_paths:
        output_stem = str(Path(output_path).with_suffix(''))
        print()
        process_drill_files(drl_paths, output_stem,
                            cx=cx if MIRROR_X else None,
                            offset=(-minx, -miny))

    _, _, board_w, board_h = copper.bounds
    print(f"\n┌─ Dimensiones del PCB ──────────────────")
    print(f"│  Ancho  (X): {board_w:.3f} mm")
    print(f"│  Alto   (Y): {board_h:.3f} mm")
    print(f"└────────────────────────────────────────\n")

    # Guardar posiciones de referencia para fix_align.py
    output_stem = str(Path(output_path).with_suffix(''))
    o = REF_OFFSET_MM
    txt_path = f"{output_stem}-ref.txt"
    with open(txt_path, 'w') as f:
        f.write(f"EX1={-o:.3f}\nEY1={-o:.3f}\n")
        f.write(f"EX2={board_w + o:.3f}\nEY2={board_h + o:.3f}\n")
        f.write(f"STEM={output_stem}\n")
    print(f"[ref] {txt_path}  (posiciones de cruces para fix_align.py)")

    print("\n✓ Listo.")


if __name__ == "__main__":
    main()
