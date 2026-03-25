# Gerber2gcode — Historial de versiones

## v7 — `gerber2gcode_v7_fix_drill_coords.py` (2026-03-24)
**Archivo activo:** `gerber2gcode.py`

### Cambios
- **Bug fix crítico en taladros:** Los archivos Excellon de KiCad usan coordenadas relativas al PCB (origen = esquina inferior-izquierda), mientras que el Gerber usa coordenadas absolutas del sheet. El código aplicaba incorrectamente el offset del Gerber a los drills, generando coordenadas fuera de límites que enviaban la máquina a los finales de carrera.
- El offset para drills ahora es siempre `(0, 0)`.
- El centro de espejo para drills ahora es `board_w / 2` (en coordenadas del PCB), no `cx` del sheet.

---

## v6 — `gerber2gcode_v6_ref_in_mill.py` (2026-03-24)
**Archivo activo:** `gerber2gcode.py`

### Cambios
- **Marcas de referencia integradas en el mill:** las cruces "+" ya no se generan en un `-ref.nc` separado, sino que son lo primero que se ejecuta dentro del archivo principal de fresado.
- Se elimina la generación de `-ref.nc`. Se conserva `-ref.txt` para `fix_align.py`.

---

## v5 — `gerber2gcode_v5_cross_ref_marks.py` (2026-03-24)
**Archivo activo:** `gerber2gcode.py`

### Cambios
- **Marcas de referencia rediseñadas:** reemplaza el punto V-bit por una cruz "+" de `REF_CROSS_MM` (default: 3.0 mm), fresada en dos pasadas (brazo horizontal + vertical).
- Las cruces se ubican a `REF_OFFSET_MM` (default: 2.0 mm) fuera de las esquinas del PCB: inferior-izquierda `(-2, -2)` y superior-derecha `(board_w+2, board_h+2)`.
- Nuevas constantes de config: `REF_CROSS_MM` y `REF_OFFSET_MM`.
- El archivo `-ref.txt` ahora guarda las coordenadas reales de los centros de las cruces.

---

## v4 — `gerber2gcode_v4_safe_z_overshoot.py` (2026-03-24)
**Archivo activo:** `gerber2gcode.py`

### Cambios
- **Bug fix crítico:** Al iniciar el G-code de fresado, el cabezal ahora sube a `SAFE_Z_MM` antes de cualquier movimiento XY. Antes rayaba la placa al desplazarse al primer punto de corte.
- **Nueva función — Overshoot:** Al cerrar cada contorno, la fresa se sobreextiende `OVERSHOOT_MM` (default: 1.0 mm) siguiendo la geometría real del path, garantizando limpieza completa en el punto de inicio sin riesgo de cortar cobre adyacente.
- **Nueva config:** `OVERSHOOT_MM = 1.0` en sección CONFIG FRESA.
- **gcode.sh — modo automático:** Sin argumentos, el script detecta automáticamente el `.gbr` y los `.drl` dentro de la carpeta `Gerbers/`. El comportamiento con argumentos explícitos se mantiene.

---

## v3 — `gerber2gcode_v3_slots_multipass_dimensions.py`
### Cambios
- Soporte para ranuras/ovalados (slots) en archivos Excellon.
- Múltiples pasadas en ranuras cuando la fresa es menor al ancho del slot.
- Dimensiones del PCB al finalizar.

---

## v2 — `gerber2gcode_v2_drills_mirror.py`
### Cambios
- Soporte para taladros (archivos `.drl` Excellon).
- Espejado horizontal (`MIRROR_X`) para capas B_Cu.
- Marcas de referencia (`-ref.nc`, `-ref.txt`) para alineación.

---

## v1 — `gerber2gcode (Copiar).py`
### Cambios
- Versión inicial: isolation routing básico (fresado, modo láser).
- Soporte para G-code fresa (V-bit) y láser.
