"""Files panel — GBR, DRL, and output directory selectors."""

import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog
from pathlib import Path


class FilesPanel(ttk.Frame):
    """File selectors for GBR (single), DRL (multiple rows), and output directory."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._drl_rows = []   # list of (frame, var, entry, remove_btn)
        self._build()

    def _build(self):
        # ── GBR file ──────────────────────────────────────────────────────
        gbr_frame = ttk.LabelFrame(self, text='Gerber copper layer (.gbr)')
        gbr_frame.pack(fill='x', padx=6, pady=(6, 3))

        self._gbr_var = tk.StringVar()
        gbr_entry = ttk.Entry(gbr_frame, textvariable=self._gbr_var)
        gbr_entry.pack(side='left', fill='x', expand=True, padx=(4, 2), pady=4)

        ttk.Button(gbr_frame, text='Browse…', command=self._browse_gbr).pack(
            side='right', padx=(2, 4), pady=4)

        # ── DRL files ─────────────────────────────────────────────────────
        drl_outer = ttk.LabelFrame(self, text='Drill files (.drl) — optional')
        drl_outer.pack(fill='x', padx=6, pady=3)

        self._drl_container = ttk.Frame(drl_outer)
        self._drl_container.pack(fill='x', padx=4, pady=(2, 0))

        ttk.Button(drl_outer, text='+ Add drill file', command=self._add_drl_row).pack(
            anchor='w', padx=4, pady=(0, 4))

        # ── Output directory ──────────────────────────────────────────────
        out_frame = ttk.LabelFrame(self, text='Output directory')
        out_frame.pack(fill='x', padx=6, pady=(3, 6))

        self._out_var = tk.StringVar()
        out_entry = ttk.Entry(out_frame, textvariable=self._out_var)
        out_entry.pack(side='left', fill='x', expand=True, padx=(4, 2), pady=4)

        ttk.Button(out_frame, text='Browse…', command=self._browse_out).pack(
            side='right', padx=(2, 4), pady=4)

    # ── Internals ─────────────────────────────────────────────────────────

    def _browse_gbr(self):
        path = filedialog.askopenfilename(
            title='Select Gerber copper layer',
            filetypes=[('Gerber files', '*.gbr *.ger'), ('All files', '*.*')]
        )
        if path:
            self._gbr_var.set(path)
            if not self._out_var.get():
                self._out_var.set(str(Path(path).parent.parent / "Outputs"))

    def _browse_out(self):
        path = filedialog.askdirectory(title='Select output directory')
        if path:
            self._out_var.set(path)

    def _add_drl_row(self, path=''):
        row_frame = ttk.Frame(self._drl_container)
        row_frame.pack(fill='x', pady=1)

        var = tk.StringVar(value=path)
        entry = ttk.Entry(row_frame, textvariable=var)
        entry.pack(side='left', fill='x', expand=True, padx=(0, 2))

        def browse(v=var):
            p = filedialog.askopenfilename(
                title='Select drill file',
                filetypes=[('Drill files', '*.drl *.exc *.ncd'), ('All files', '*.*')]
            )
            if p:
                v.set(p)

        ttk.Button(row_frame, text='Browse…', command=browse).pack(side='left', padx=(0, 2))

        def remove(rf=row_frame, row_ref=None):
            # Find and remove this row from _drl_rows
            self._drl_rows[:] = [r for r in self._drl_rows if r[0] is not rf]
            rf.destroy()

        remove_btn = ttk.Button(row_frame, text='✕', width=3, command=remove)
        remove_btn.pack(side='left')

        self._drl_rows.append((row_frame, var, entry, remove_btn))

    # ── Public API ────────────────────────────────────────────────────────

    def get_gbr_path(self) -> str:
        return self._gbr_var.get().strip()

    def get_drl_paths(self) -> list:
        return [r[1].get().strip() for r in self._drl_rows if r[1].get().strip()]

    def get_output_dir(self) -> str:
        return self._out_var.get().strip()

    def load_config(self, d: dict):
        """Set paths from a history entry dict."""
        if d.get('gbr_path'):
            self._gbr_var.set(d['gbr_path'])
        if d.get('output_dir'):
            self._out_var.set(d['output_dir'])
        # Clear existing DRL rows
        for row_frame, *_ in self._drl_rows:
            row_frame.destroy()
        self._drl_rows.clear()
        for p in d.get('drl_paths', []):
            self._add_drl_row(p)
