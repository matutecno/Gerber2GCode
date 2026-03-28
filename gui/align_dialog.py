"""Alignment dialog — wraps fix_align.py logic in a GUI form."""

import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import fix_align


class AlignDialog(tk.Toplevel):
    """
    Dialog to correct rotation/offset in drill and slot files using
    two reference marks measured on the machine.
    """

    def __init__(self, parent, ref_txt_path: str = ''):
        super().__init__(parent)
        self.title('Align Drills')
        self.resizable(False, False)
        self.grab_set()

        self._build(ref_txt_path)
        self.transient(parent)
        self.wait_visibility()
        self.lift()

    def _build(self, ref_txt_path: str):
        pad = {'padx': 8, 'pady': 4}

        # ── ref.txt ───────────────────────────────────────────────────────
        ref_frame = ttk.LabelFrame(self, text='Reference file (-ref.txt)')
        ref_frame.pack(fill='x', **pad)

        self._ref_var = tk.StringVar(value=ref_txt_path)
        ttk.Entry(ref_frame, textvariable=self._ref_var, width=50).pack(
            side='left', fill='x', expand=True, padx=(4, 2), pady=4)
        ttk.Button(ref_frame, text='Browse…', command=self._browse_ref).pack(
            side='right', padx=(0, 4), pady=4)

        # ── Expected positions (read-only, loaded from ref.txt) ───────────
        exp_frame = ttk.LabelFrame(self, text='Expected positions (from ref.txt)')
        exp_frame.pack(fill='x', **pad)

        self._exp_var = tk.StringVar(value='Load ref.txt to see expected positions')
        ttk.Label(exp_frame, textvariable=self._exp_var, foreground='gray').pack(
            anchor='w', padx=4, pady=4)

        ttk.Button(exp_frame, text='Load ref.txt', command=self._load_ref).pack(
            anchor='w', padx=4, pady=(0, 4))

        # ── Actual positions (measured on machine) ────────────────────────
        act_frame = ttk.LabelFrame(self, text='Actual positions (measured on machine)')
        act_frame.pack(fill='x', **pad)

        for col in range(4):
            act_frame.columnconfigure(col, weight=1)

        ttk.Label(act_frame, text='P1  X').grid(row=0, column=0, sticky='e', padx=(4, 2), pady=4)
        self._ax1 = tk.StringVar(value='0.000')
        ttk.Entry(act_frame, textvariable=self._ax1, width=10).grid(row=0, column=1, sticky='ew', padx=(0, 8))

        ttk.Label(act_frame, text='Y').grid(row=0, column=2, sticky='e', padx=(4, 2))
        self._ay1 = tk.StringVar(value='0.000')
        ttk.Entry(act_frame, textvariable=self._ay1, width=10).grid(row=0, column=3, sticky='ew', padx=(0, 4))

        ttk.Label(act_frame, text='P2  X').grid(row=1, column=0, sticky='e', padx=(4, 2), pady=4)
        self._ax2 = tk.StringVar()
        ttk.Entry(act_frame, textvariable=self._ax2, width=10).grid(row=1, column=1, sticky='ew', padx=(0, 8))

        ttk.Label(act_frame, text='Y').grid(row=1, column=2, sticky='e', padx=(4, 2))
        self._ay2 = tk.StringVar()
        ttk.Entry(act_frame, textvariable=self._ay2, width=10).grid(row=1, column=3, sticky='ew', padx=(0, 4))

        # ── Result display ────────────────────────────────────────────────
        res_frame = ttk.LabelFrame(self, text='Computed correction')
        res_frame.pack(fill='x', **pad)

        self._result_var = tk.StringVar(value='—')
        ttk.Label(res_frame, textvariable=self._result_var, foreground='#00BFFF').pack(
            anchor='w', padx=4, pady=4)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=8, pady=(4, 8))

        ttk.Button(btn_frame, text='Run Alignment', command=self._run).pack(side='left', padx=(0, 6))
        ttk.Button(btn_frame, text='Close', command=self.destroy).pack(side='left')

        if ref_txt_path:
            self._load_ref()

    def _browse_ref(self):
        p = filedialog.askopenfilename(
            title='Select reference file',
            filetypes=[('Reference files', '*-ref.txt'), ('All files', '*.*')]
        )
        if p:
            self._ref_var.set(p)
            self._load_ref()

    def _load_ref(self):
        path = self._ref_var.get().strip()
        if not path or not Path(path).exists():
            messagebox.showerror('Error', f'File not found:\n{path}', parent=self)
            return
        try:
            ex1, ey1, ex2, ey2, _ = fix_align.load_ref(path)
            self._exp_var.set(f'P1 = ({ex1:.3f}, {ey1:.3f})    P2 = ({ex2:.3f}, {ey2:.3f})')
            self._ax2.set(f'{ex2:.3f}')
            self._ay2.set(f'{ey2:.3f}')
        except Exception as e:
            messagebox.showerror('Error reading ref.txt', str(e), parent=self)

    def _run(self):
        path = self._ref_var.get().strip()
        if not path or not Path(path).exists():
            messagebox.showerror('Error', 'Select a valid -ref.txt file.', parent=self)
            return
        try:
            ax1 = float(self._ax1.get())
            ay1 = float(self._ay1.get())
            ax2 = float(self._ax2.get())
            ay2 = float(self._ay2.get())
        except ValueError:
            messagebox.showerror('Error', 'All position fields must be numeric.', parent=self)
            return

        try:
            ex1, ey1, ex2, ey2, stem = fix_align.load_ref(path)
            cos_a, sin_a, tx, ty = fix_align.compute_transform(ex1, ey1, ex2, ey2, ax1, ay1, ax2, ay2)
            angle_deg = math.degrees(math.atan2(sin_a, cos_a))

            stem_path = Path(stem)
            targets = [p for p in
                       list(stem_path.parent.glob(f"{stem_path.name}-drill-*.nc")) +
                       list(stem_path.parent.glob(f"{stem_path.name}-slots.nc"))
                       if not p.stem.endswith("_aligned")]

            if not targets:
                messagebox.showwarning('No files found',
                    f'No drill or slot files found for stem:\n{stem}', parent=self)
                return

            for p in sorted(targets):
                fix_align.fix_nc_file(str(p), cos_a, sin_a, tx, ty)

            self._result_var.set(
                f'Rotation: {angle_deg:.4f}°    '
                f'ΔX: {tx:+.3f} mm    ΔY: {ty:+.3f} mm\n'
                f'{len(targets)} file(s) written as *_aligned.nc'
            )
        except Exception as e:
            messagebox.showerror('Alignment error', str(e), parent=self)
