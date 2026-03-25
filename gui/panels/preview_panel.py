"""Preview panel — embeds matplotlib for copper/path visualization."""

import tkinter as tk
import tkinter.ttk as ttk

try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MplPath
    import matplotlib.patches as mpatches
    import numpy as np
    _MPL_OK = True
except ImportError as e:
    _MPL_OK = False
    _MPL_ERR = str(e)

from shapely.geometry import MultiPolygon, Polygon


BG_DARK = '#1e1e1e'
COPPER_COLOR = '#DAA520'
PATH_COLOR = '#FF4444'
TICK_COLOR = '#888888'


def _polygon_to_patch(poly: Polygon, **kwargs):
    """Convert a shapely Polygon (with holes) to a matplotlib PathPatch."""
    def ring_codes(ring):
        coords = list(ring.coords)
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * (len(coords) - 2) + [MplPath.CLOSEPOLY]
        return coords, codes

    vertices = []
    codes = []

    ext_coords, ext_codes = ring_codes(poly.exterior)
    vertices.extend(ext_coords)
    codes.extend(ext_codes)

    for interior in poly.interiors:
        int_coords, int_codes = ring_codes(interior)
        vertices.extend(int_coords)
        codes.extend(int_codes)

    path = MplPath(vertices, codes)
    return PathPatch(path, **kwargs)


class PreviewPanel(ttk.Frame):
    """Embeds matplotlib figure for copper and path preview."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._build()

    def _build(self):
        if not _MPL_OK:
            lbl = ttk.Label(self, text=f"matplotlib not available:\n{_MPL_ERR}",
                            foreground='red', background=BG_DARK)
            lbl.pack(expand=True, fill='both')
            self._canvas = None
            return

        self.fig = Figure(figsize=(6, 5), dpi=96)
        self.fig.patch.set_facecolor(BG_DARK)

        self.ax = self.fig.add_subplot(111)
        self._style_axes()

        self._tk_canvas = FigureCanvasTkAgg(self.fig, master=self)
        self._tk_canvas.draw()
        widget = self._tk_canvas.get_tk_widget()
        widget.configure(background=BG_DARK)
        widget.pack(side='top', fill='both', expand=True)

        toolbar_frame = ttk.Frame(self)
        toolbar_frame.pack(side='bottom', fill='x')
        self._toolbar = NavigationToolbar2Tk(self._tk_canvas, toolbar_frame)
        self._toolbar.update()

    def _style_axes(self):
        self.ax.set_facecolor(BG_DARK)
        for spine in self.ax.spines.values():
            spine.set_color(TICK_COLOR)
        self.ax.tick_params(colors=TICK_COLOR)
        self.ax.xaxis.label.set_color(TICK_COLOR)
        self.ax.yaxis.label.set_color(TICK_COLOR)

    def clear(self):
        """Clear the axes."""
        if not _MPL_OK:
            return
        self.ax.cla()
        self._style_axes()
        self._tk_canvas.draw_idle()

    def show_copper(self, copper_geom, individuals):
        """Fill copper polygons in amber on dark background."""
        if not _MPL_OK:
            return
        self.ax.cla()
        self._style_axes()

        polys = list(copper_geom.geoms) if isinstance(copper_geom, MultiPolygon) else [copper_geom]
        for poly in polys:
            if not isinstance(poly, Polygon) or poly.is_empty:
                continue
            patch = _polygon_to_patch(poly, facecolor=COPPER_COLOR, edgecolor='#B8860B',
                                       linewidth=0.5, alpha=0.85)
            self.ax.add_patch(patch)

        self.ax.set_aspect('equal')
        self.ax.autoscale_view()
        self._tk_canvas.draw_idle()

    def show_paths(self, paths):
        """Overlay mill/laser paths in red."""
        if not _MPL_OK:
            return
        for path in paths:
            if len(path) < 2:
                continue
            xs = [p[0] for p in path]
            ys = [p[1] for p in path]
            self.ax.plot(xs, ys, color=PATH_COLOR, linewidth=0.7, alpha=0.8)
        self._tk_canvas.draw_idle()
