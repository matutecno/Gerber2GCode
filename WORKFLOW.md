# Flujo de trabajo: PCB en CNC con gerber2gcode

Guía completa desde el diseño en KiCad hasta la ejecución en la máquina.

---

## 1. KiCad — Exportar archivos

### Origen de coordenadas

1. Ir a **Place → Drill/Place File Origin**.
2. Colocar el origen en la **esquina inferior izquierda** de la placa.

### Plotear la capa de cobre

1. Ir a **File → Plot**.
2. Seleccionar la capa **B.Cu**.
3. En "Include Layers on All Plots", agregar **Edge.Cuts**.
4. Formato de salida: **Gerber**.
5. Unidades: **mm** (preferido).
6. Click en **Plot**.

### Generar archivos de taladro

1. En la misma ventana de Plot, click en **Generate Drill Files**.
2. Configurar:
   - **Drill origin:** activar *Drill/Place File Origin* (el que se colocó en el paso anterior).
   - **Formato:** Gerber X2.
   - **Unidades:** mm.
   - **Formato de números:** Decimal.
3. Click en **Generate Drill Files**.

Los archivos resultantes (`.gbr` y `.drl`) son los que se usarán en el paso siguiente.

---

## 2. gerber2gcode — Generar G-code inicial

### Iniciar la GUI

En la terminal, ejecutar el script `./gcode.sh --gui` desde la carpeta del proyecto.

### Primera pasada (sin mapa de alturas)

1. Cargar el archivo `.gbr` de B.Cu en el campo **Gerber copper layer**.
2. Agregar los archivos `.drl` (PTH y NPTH si corresponde) en **Drill files**.
3. Configurar los parámetros:
   - **DRILL_SIZES:** ingresar solo los diámetros de las mechas disponibles, separados por coma. Por ejemplo: `1, 3` si solo se dispone de mechas de 1 mm y 3 mm. El script asignará cada taladro a la mecha más cercana.
   - Resto de parámetros según el trabajo.
4. Dejar el campo **Height Map** vacío por ahora.
5. Click en **Generate**.

Los archivos se guardarán en la carpeta `Outputs/`. El `.nc` generado en este paso se usará para calcular el mapa de alturas.

---

## 3. Universal G-code Sender — Mapa de alturas

### Home de la máquina

Antes de cualquier operación, hacer home con la fresa apenas tocando el metal en la **esquina inferior izquierda** de la placa. Si se dispone de una sonda, el paso mínimo anterior al contacto. Ese punto es el origen absoluto (X0, Y0, Z0).

### Generar el mapa de alturas

1. Abrir el `.nc` generado en el paso anterior en Universal G-code Sender.
2. Ir a **Window → Plugins → Auto Leveler**.
3. Click en **Use Loaded File** — esto cargará la previsualización del área de trabajo.
4. Ajustar los parámetros del mapa (resolución, área, rango Z).

> **Importante:** Luego de hacer click en *Use Loaded File*, modificar cualquier parámetro y devolverlo a su valor original antes de continuar. Si no se hace esto, el Auto Leveler modificará el G-code original en lugar de solo generar el mapa.

5. Verificar que **Apply to G-code** **no** esté seleccionado. Solo se necesita el mapa, no el G-code corregido por UGS.
6. Click en **Scan Surface** para sondear la superficie.
7. Una vez completado, exportar el mapa y guardarlo en la carpeta `Extern/` del proyecto con extensión `.xyz`.

---

## 4. gerber2gcode — Generar G-code final

1. Volver a la GUI (`./gcode.sh --gui`).
2. Recargar los mismos archivos Gerber y drill del paso 2.
3. En el campo **Height Map**, cargar el archivo `.xyz` guardado en `Extern/`.
4. Verificar todos los parámetros.
5. Click en **Generate**.

Se generarán versiones `-leveled` de todos los archivos:
- `case-B_Cu-leveled.nc` — Fresado de cobre con corrección de alturas. **Este es el archivo a usar en la máquina.**
- `case-B_Cu-drill-Xmm-leveled.nc` — Taladros con corrección de alturas.
- `case-B_Cu-slots-leveled.nc` — Ranuras con corrección (si las hay).

Los archivos sin `-leveled` se conservan como referencia pero no deben usarse en la máquina.

---

## 5. Alineación de taladros (opcional)

Si la placa tiene marcas de referencia y se detecta un offset o rotación al colocarla en la máquina, usar el botón **Align Drills** en la barra de herramientas de la GUI.

1. El diálogo carga automáticamente el archivo `-ref.txt` del último run.
2. Mover la fresa manualmente hasta cada marca de referencia en la máquina y anotar las coordenadas reales (X, Y).
3. Ingresar las posiciones reales de P1 y P2 en el diálogo.
4. Click en **Run Alignment**.

Se generarán versiones `_aligned.nc` de todos los archivos de taladros y ranuras con la corrección aplicada.

---

## 6. Ejecución en la máquina

### Orden de operaciones

Ejecutar los archivos en el siguiente orden:

1. **`case-B_Cu-leveled.nc`** — Fresado de aislamiento de cobre (V-bit).
2. **`case-B_Cu-drill-Xmm-leveled.nc`** — Taladros, uno por diámetro, en orden creciente.
3. **`case-B_Cu-slots-leveled.nc`** — Ranuras (si las hay).

### Consideraciones

- De ser necesario, hacer home antes de cada sesión: fresa tocando el metal en la esquina inferior izquierda (X0, Y0, Z0).
- Cambiar la herramienta entre el fresado de cobre (V-bit) y los taladros.
- Re-hacer home después de cada cambio de herramienta, de ser necesario.
