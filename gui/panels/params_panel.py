"""Parameters panel — scrollable editor for all Config fields."""

import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import gerber2gcode


class ParamsPanel(ttk.Frame):
    """Scrollable parameter editor for gerber2gcode.Config fields."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._vars = {}
        self._build()
        self.reset_defaults()

    def _build(self):
        self._add_general_section()
        self._add_mill_section()
        self._add_laser_section()
        self._add_drill_section()
        self._add_slots_section()
        self._add_edge_section()
        self._add_ref_section()
        self._add_heightmap_section()

    def _labeled_entry(self, parent, label, key, row, col=0, width=12):
        ttk.Label(parent, text=label).grid(row=row, column=col*2, sticky='w', padx=(4, 2), pady=2)
        var = tk.StringVar()
        self._vars[key] = var
        entry = ttk.Entry(parent, textvariable=var, width=width)
        entry.grid(row=row, column=col*2+1, sticky='ew', padx=(0, 8), pady=2)
        return var

    def _labeled_check(self, parent, label, key, row, col=0):
        var = tk.BooleanVar()
        self._vars[key] = var
        cb = ttk.Checkbutton(parent, text=label, variable=var)
        cb.grid(row=row, column=col*2, columnspan=2, sticky='w', padx=(4, 2), pady=2)
        return var

    def _section(self, title):
        lf = ttk.LabelFrame(self, text=title)
        lf.pack(fill='x', padx=6, pady=4)
        lf.columnconfigure(1, weight=1)
        lf.columnconfigure(3, weight=1)
        return lf

    def _add_general_section(self):
        lf = self._section('General')

        ttk.Label(lf, text='MODE').grid(row=0, column=0, sticky='w', padx=(4, 2), pady=2)
        mode_var = tk.StringVar()
        self._vars['MODE'] = mode_var
        cb = ttk.Combobox(lf, textvariable=mode_var, values=['mill', 'laser'],
                          width=10, state='readonly')
        cb.grid(row=0, column=1, sticky='ew', padx=(0, 8), pady=2)

        self._labeled_check(lf, 'MIRROR_X', 'MIRROR_X', row=0, col=1)

        self._labeled_entry(lf, 'SAFE_Z_MM', 'SAFE_Z_MM', row=1, col=0)
        self._labeled_entry(lf, 'CLEARANCE_MM (blank=auto)', 'CLEARANCE_MM', row=1, col=1)

        self._labeled_check(lf, 'Spindle on start', 'SPINDLE_ON', row=2, col=0)

    def _add_mill_section(self):
        lf = self._section('Mill (V-bit)')
        pairs = [
            ('VBIT_TIP_MM',       'VBIT_TIP_MM',       0, 0),
            ('VBIT_ANGLE_DEG',    'VBIT_ANGLE_DEG',     0, 1),
            ('CUT_DEPTH_MM',      'CUT_DEPTH_MM',       1, 0),
            ('FEED_RATE',         'FEED_RATE',          1, 1),
            ('PLUNGE_RATE',       'PLUNGE_RATE',        2, 0),
            ('PASS_OVERLAP_FRAC', 'PASS_OVERLAP_FRAC',  2, 1),
            ('OVERSHOOT_MM',      'OVERSHOOT_MM',       3, 0),
        ]
        for label, key, row, col in pairs:
            self._labeled_entry(lf, label, key, row=row, col=col)

    def _add_laser_section(self):
        lf = self._section('Laser')
        pairs = [
            ('LASER_POWER',     'LASER_POWER',     0, 0),
            ('LASER_FEED_RATE', 'LASER_FEED_RATE', 0, 1),
            ('LASER_PASS_MM',   'LASER_PASS_MM',   1, 0),
        ]
        for label, key, row, col in pairs:
            self._labeled_entry(lf, label, key, row=row, col=col)

    def _add_drill_section(self):
        lf = self._section('Drill')
        ttk.Label(lf, text='DRILL_SIZES (comma-sep)').grid(
            row=0, column=0, sticky='w', padx=(4, 2), pady=2)
        var = tk.StringVar()
        self._vars['DRILL_SIZES'] = var
        ttk.Entry(lf, textvariable=var, width=24).grid(
            row=0, column=1, columnspan=3, sticky='ew', padx=(0, 8), pady=2)

        pairs = [
            ('DRILL_SAFE_Z_MM',  'DRILL_SAFE_Z_MM',  1, 0),
            ('DRILL_DEPTH_MM',   'DRILL_DEPTH_MM',   1, 1),
            ('DRILL_FEED_RATE',  'DRILL_FEED_RATE',  2, 0),
        ]
        for label, key, row, col in pairs:
            self._labeled_entry(lf, label, key, row=row, col=col)

    def _add_slots_section(self):
        lf = self._section('Slots')
        pairs = [
            ('SLOT_TOOL_MM',    'SLOT_TOOL_MM',    0, 0),
            ('SLOT_DEPTH_MM',   'SLOT_DEPTH_MM',   0, 1),
            ('SLOT_PLUNGE_RATE','SLOT_PLUNGE_RATE', 1, 0),
            ('SLOT_FEED_RATE',  'SLOT_FEED_RATE',  1, 1),
        ]
        for label, key, row, col in pairs:
            self._labeled_entry(lf, label, key, row=row, col=col)

    def _add_edge_section(self):
        lf = self._section('Edge Cut (troquelado)')
        pairs = [
            ('EDGE_TOOL_MM',      'EDGE_TOOL_MM',      0, 0),
            ('EDGE_DEPTH_MM',     'EDGE_DEPTH_MM',     0, 1),
            ('EDGE_PASS_DEPTH_MM','EDGE_PASS_DEPTH_MM', 1, 0),
            ('EDGE_FEED_RATE',    'EDGE_FEED_RATE',    1, 1),
            ('EDGE_PLUNGE_RATE',  'EDGE_PLUNGE_RATE',  2, 0),
            ('EDGE_SAFE_Z_MM',    'EDGE_SAFE_Z_MM',    2, 1),
        ]
        for label, key, row, col in pairs:
            self._labeled_entry(lf, label, key, row=row, col=col)

    def _add_ref_section(self):
        lf = self._section('Reference Marks')
        pairs = [
            ('REF_MARK_DEPTH_MM', 'REF_MARK_DEPTH_MM', 0, 0),
            ('REF_CROSS_MM',      'REF_CROSS_MM',       0, 1),
            ('REF_OFFSET_MM',     'REF_OFFSET_MM',      1, 0),
        ]
        for label, key, row, col in pairs:
            self._labeled_entry(lf, label, key, row=row, col=col)

    def _add_heightmap_section(self):
        lf = self._section('Height Map (autoleveling)')
        var = tk.StringVar()
        self._vars['HEIGHTMAP_FILE'] = var
        ttk.Entry(lf, textvariable=var).grid(
            row=0, column=0, columnspan=3, sticky='ew', padx=(4, 2), pady=2)
        lf.columnconfigure(0, weight=1)
        def browse():
            p = filedialog.askopenfilename(
                title='Select height map file',
                filetypes=[('Height map', '*.xyz *.gcode'), ('All files', '*.*')]
            )
            if p:
                var.set(p)
        def clear():
            var.set('')
        ttk.Button(lf, text='Browse…', command=browse).grid(row=0, column=3, padx=(2, 2), pady=2)
        ttk.Button(lf, text='✕', width=3, command=clear).grid(row=0, column=4, padx=(0, 4), pady=2)

    def set_heightmap(self, path: str):
        self._vars['HEIGHTMAP_FILE'].set(path)

    # ── Public API ────────────────────────────────────────────────────────

    def get_config(self) -> dict:
        """Returns all values as a dict matching Config field names."""
        cfg = {}
        for key, var in self._vars.items():
            if key == 'MODE':
                cfg[key] = var.get()
            elif key in ('MIRROR_X', 'SPINDLE_ON'):
                cfg[key] = bool(var.get())
            elif key == 'CLEARANCE_MM':
                raw = var.get().strip()
                if not raw or raw.lower() == 'auto':
                    cfg[key] = None
                else:
                    try:
                        cfg[key] = float(raw)
                    except ValueError:
                        cfg[key] = None
            elif key == 'DRILL_SIZES':
                raw = var.get().strip()
                try:
                    cfg[key] = [float(x.strip()) for x in raw.split(',') if x.strip()]
                except ValueError:
                    cfg[key] = gerber2gcode.Config().DRILL_SIZES
            elif key == 'HEIGHTMAP_FILE':
                raw = var.get().strip()
                cfg[key] = raw if raw else None
            else:
                raw = var.get().strip()
                try:
                    # Try int first for integer-like fields
                    if '.' in raw:
                        cfg[key] = float(raw)
                    else:
                        cfg[key] = int(raw)
                except ValueError:
                    try:
                        cfg[key] = float(raw)
                    except ValueError:
                        cfg[key] = raw
        return cfg

    def load_config(self, d: dict):
        """Set all variables from a dict."""
        for key, var in self._vars.items():
            if key not in d:
                continue
            val = d[key]
            if key in ('MIRROR_X', 'SPINDLE_ON'):
                var.set(bool(val))
            elif key == 'CLEARANCE_MM':
                if val is None:
                    var.set('')
                else:
                    var.set(str(val))
            elif key == 'DRILL_SIZES':
                if isinstance(val, list):
                    var.set(', '.join(str(v) for v in val))
                else:
                    var.set(str(val))
            else:
                var.set(str(val) if val is not None else '')

    def reset_defaults(self):
        """Reset all variables to Config() defaults."""
        defaults = gerber2gcode.Config()
        d = {
            'MODE':             defaults.MODE,
            'MIRROR_X':         defaults.MIRROR_X,
            'SPINDLE_ON':       defaults.SPINDLE_ON,
            'SAFE_Z_MM':        defaults.SAFE_Z_MM,
            'CLEARANCE_MM':     defaults.CLEARANCE_MM,
            'VBIT_TIP_MM':      defaults.VBIT_TIP_MM,
            'VBIT_ANGLE_DEG':   defaults.VBIT_ANGLE_DEG,
            'CUT_DEPTH_MM':     defaults.CUT_DEPTH_MM,
            'FEED_RATE':        defaults.FEED_RATE,
            'PLUNGE_RATE':      defaults.PLUNGE_RATE,
            'PASS_OVERLAP_FRAC':defaults.PASS_OVERLAP_FRAC,
            'OVERSHOOT_MM':     defaults.OVERSHOOT_MM,
            'LASER_POWER':      defaults.LASER_POWER,
            'LASER_FEED_RATE':  defaults.LASER_FEED_RATE,
            'LASER_PASS_MM':    defaults.LASER_PASS_MM,
            'DRILL_SIZES':      defaults.DRILL_SIZES,
            'DRILL_SAFE_Z_MM':  defaults.DRILL_SAFE_Z_MM,
            'DRILL_DEPTH_MM':   defaults.DRILL_DEPTH_MM,
            'DRILL_FEED_RATE':  defaults.DRILL_FEED_RATE,
            'SLOT_TOOL_MM':     defaults.SLOT_TOOL_MM,
            'SLOT_DEPTH_MM':    defaults.SLOT_DEPTH_MM,
            'SLOT_PLUNGE_RATE': defaults.SLOT_PLUNGE_RATE,
            'SLOT_FEED_RATE':   defaults.SLOT_FEED_RATE,
            'REF_MARK_DEPTH_MM':defaults.REF_MARK_DEPTH_MM,
            'REF_CROSS_MM':     defaults.REF_CROSS_MM,
            'REF_OFFSET_MM':    defaults.REF_OFFSET_MM,
            'EDGE_TOOL_MM':      defaults.EDGE_TOOL_MM,
            'EDGE_DEPTH_MM':     defaults.EDGE_DEPTH_MM,
            'EDGE_PASS_DEPTH_MM':defaults.EDGE_PASS_DEPTH_MM,
            'EDGE_FEED_RATE':    defaults.EDGE_FEED_RATE,
            'EDGE_PLUNGE_RATE':  defaults.EDGE_PLUNGE_RATE,
            'EDGE_SAFE_Z_MM':    defaults.EDGE_SAFE_Z_MM,
            'HEIGHTMAP_FILE':   defaults.HEIGHTMAP_FILE,
        }
        self.load_config(d)
