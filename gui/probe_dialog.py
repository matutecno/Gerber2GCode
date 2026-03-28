"""Heightmap probing dialog — connects to GRBL via USB and runs a Z-probe grid."""

import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import threading
import time
import re
from datetime import datetime
from pathlib import Path


class ProbeDialog(tk.Toplevel):
    def __init__(self, parent, output_dir: str = '', on_done=None):
        super().__init__(parent)
        self.title('Probe Heightmap')
        self.resizable(True, True)
        self.grab_set()

        self._on_done = on_done   # callback(xyz_path: str)
        self._serial = None
        self._stop_flag = threading.Event()
        self._thread = None
        self._output_dir = output_dir or str(Path.home())

        self._build()
        self.transient(parent)
        self.wait_visibility()
        self.lift()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self._scan_ports()

    # ── UI construction ───────────────────────────────────────────────────

    def _build(self):
        pad = {'padx': 8, 'pady': 4}

        # Connection
        cf = ttk.LabelFrame(self, text='Connection')
        cf.pack(fill='x', **pad)
        cf.columnconfigure(1, weight=1)

        ttk.Label(cf, text='Port').grid(row=0, column=0, sticky='e', padx=(4, 2), pady=4)
        self._port_var = tk.StringVar()
        self._port_combo = ttk.Combobox(cf, textvariable=self._port_var, width=22)
        self._port_combo.grid(row=0, column=1, sticky='ew', padx=(0, 2), pady=4)
        ttk.Button(cf, text='Scan', command=self._scan_ports).grid(row=0, column=2, padx=2, pady=4)
        self._conn_btn = ttk.Button(cf, text='Connect', command=self._toggle_connect)
        self._conn_btn.grid(row=0, column=3, padx=(2, 4), pady=4)

        ttk.Label(cf, text='Baud').grid(row=1, column=0, sticky='e', padx=(4, 2), pady=(0, 4))
        self._baud_var = tk.StringVar(value='115200')
        ttk.Entry(cf, textvariable=self._baud_var, width=10).grid(row=1, column=1, sticky='w', pady=(0, 4))
        self._conn_status = tk.StringVar(value='Disconnected')
        ttk.Label(cf, textvariable=self._conn_status, foreground='gray').grid(
            row=1, column=2, columnspan=2, sticky='w', padx=4, pady=(0, 4))

        # Probe parameters
        pf = ttk.LabelFrame(self, text='Probe parameters')
        pf.pack(fill='x', **pad)

        ttk.Label(pf, text='Grid cols').grid(row=0, column=0, sticky='e', padx=(4, 2), pady=3)
        self._cols_var = tk.StringVar(value='14')
        ttk.Entry(pf, textvariable=self._cols_var, width=6).grid(row=0, column=1, sticky='w', padx=(0, 12))
        ttk.Label(pf, text='Rows').grid(row=0, column=2, sticky='e', padx=(4, 2))
        self._rows_var = tk.StringVar(value='14')
        ttk.Entry(pf, textvariable=self._rows_var, width=6).grid(row=0, column=3, sticky='w')

        ttk.Label(pf, text='X start (mm)').grid(row=1, column=0, sticky='e', padx=(4, 2), pady=3)
        self._x0_var = tk.StringVar(value='0')
        ttk.Entry(pf, textvariable=self._x0_var, width=8).grid(row=1, column=1, sticky='w', padx=(0, 12))
        ttk.Label(pf, text='X end (mm)').grid(row=1, column=2, sticky='e', padx=(4, 2))
        self._x1_var = tk.StringVar(value='100')
        ttk.Entry(pf, textvariable=self._x1_var, width=8).grid(row=1, column=3, sticky='w')

        ttk.Label(pf, text='Y start (mm)').grid(row=2, column=0, sticky='e', padx=(4, 2), pady=3)
        self._y0_var = tk.StringVar(value='0')
        ttk.Entry(pf, textvariable=self._y0_var, width=8).grid(row=2, column=1, sticky='w', padx=(0, 12))
        ttk.Label(pf, text='Y end (mm)').grid(row=2, column=2, sticky='e', padx=(4, 2))
        self._y1_var = tk.StringVar(value='100')
        ttk.Entry(pf, textvariable=self._y1_var, width=8).grid(row=2, column=3, sticky='w')

        ttk.Label(pf, text='Probe depth (mm)').grid(row=3, column=0, sticky='e', padx=(4, 2), pady=3)
        self._probe_z_var = tk.StringVar(value='-0.75')
        ttk.Entry(pf, textvariable=self._probe_z_var, width=8).grid(row=3, column=1, sticky='w', padx=(0, 12))
        ttk.Label(pf, text='Feed (mm/min)').grid(row=3, column=2, sticky='e', padx=(4, 2))
        self._feed_var = tk.StringVar(value='20')
        ttk.Entry(pf, textvariable=self._feed_var, width=8).grid(row=3, column=3, sticky='w')

        ttk.Label(pf, text='Retract Z (mm)').grid(row=4, column=0, sticky='e', padx=(4, 2), pady=3)
        self._retract_var = tk.StringVar(value='3')
        ttk.Entry(pf, textvariable=self._retract_var, width=8).grid(row=4, column=1, sticky='w', padx=(0, 12))

        # Output
        of = ttk.LabelFrame(self, text='Output file')
        of.pack(fill='x', **pad)
        of.columnconfigure(0, weight=1)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_out = str(Path(self._output_dir) / f'heightmap_{ts}.xyz')
        self._out_var = tk.StringVar(value=default_out)
        ttk.Entry(of, textvariable=self._out_var).grid(row=0, column=0, sticky='ew', padx=(4, 2), pady=4)
        ttk.Button(of, text='Browse…', command=self._browse_out).grid(row=0, column=1, padx=(0, 4), pady=4)

        self._auto_load_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(of, text='Auto-load when done', variable=self._auto_load_var).grid(
            row=1, column=0, columnspan=2, sticky='w', padx=4, pady=(0, 4))

        # Progress
        pgf = ttk.LabelFrame(self, text='Progress')
        pgf.pack(fill='both', expand=True, **pad)

        self._progress = ttk.Progressbar(pgf, mode='determinate', maximum=100)
        self._progress.pack(fill='x', padx=4, pady=(4, 2))

        self._log = tk.Text(pgf, height=8, state='disabled', wrap='word',
                            bg='#1e1e1e', fg='#cccccc', font=('Courier', 9))
        log_sb = ttk.Scrollbar(pgf, command=self._log.yview)
        self._log.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side='right', fill='y', padx=(0, 4), pady=(0, 4))
        self._log.pack(fill='both', expand=True, padx=(4, 0), pady=(0, 4))

        # Buttons
        bf = ttk.Frame(self)
        bf.pack(fill='x', padx=8, pady=(4, 8))

        self._probe_btn = ttk.Button(bf, text='Start Probe', command=self._start_probe, state='disabled')
        self._probe_btn.pack(side='left', padx=(0, 6))
        self._stop_btn = ttk.Button(bf, text='Stop', command=self._stop_probe, state='disabled')
        self._stop_btn.pack(side='left', padx=(0, 6))
        ttk.Button(bf, text='Close', command=self._on_close).pack(side='left')

    # ── Port scanning ─────────────────────────────────────────────────────

    def _scan_ports(self):
        try:
            import serial.tools.list_ports
            ports = [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            ports = []
        self._port_combo['values'] = ports
        if ports and not self._port_var.get():
            self._port_var.set(ports[0])

    # ── Connection ────────────────────────────────────────────────────────

    def _toggle_connect(self):
        if self._serial and self._serial.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        import serial
        port = self._port_var.get().strip()
        if not port:
            messagebox.showerror('Error', 'Select a serial port.', parent=self)
            return
        try:
            baud = int(self._baud_var.get())
        except ValueError:
            messagebox.showerror('Error', 'Invalid baud rate.', parent=self)
            return

        try:
            self._serial = serial.Serial(port, baud, timeout=1)
            time.sleep(0.1)
            self._serial.write(b'\x18')   # soft reset
            time.sleep(1.5)
            self._serial.flushInput()
            self._conn_status.set(f'Connected: {port}')
            self._conn_btn.configure(text='Disconnect')
            self._probe_btn.configure(state='normal')
            self._log_append(f'Connected to {port} @ {baud}\n')
        except Exception as e:
            messagebox.showerror('Connection error', str(e), parent=self)

    def _disconnect(self):
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._conn_status.set('Disconnected')
        self._conn_btn.configure(text='Connect')
        self._probe_btn.configure(state='disabled')
        self._log_append('Disconnected.\n')

    # ── Probing ───────────────────────────────────────────────────────────

    def _start_probe(self):
        try:
            ncols = int(self._cols_var.get())
            nrows = int(self._rows_var.get())
            x0 = float(self._x0_var.get())
            x1 = float(self._x1_var.get())
            y0 = float(self._y0_var.get())
            y1 = float(self._y1_var.get())
            probe_z = float(self._probe_z_var.get())
            feed = float(self._feed_var.get())
            retract = float(self._retract_var.get())
        except ValueError:
            messagebox.showerror('Error', 'All parameter fields must be numeric.', parent=self)
            return

        if ncols < 1 or nrows < 1:
            messagebox.showerror('Error', 'Grid must be at least 1x1.', parent=self)
            return
        if probe_z >= 0:
            messagebox.showerror('Error', 'Probe depth must be negative (e.g. -2).', parent=self)
            return
        if retract <= 0:
            messagebox.showerror('Error', 'Retract Z must be positive.', parent=self)
            return

        out_path = self._out_var.get().strip()
        if not out_path:
            messagebox.showerror('Error', 'Specify an output file path.', parent=self)
            return

        points = _make_grid(x0, x1, y0, y1, ncols, nrows)
        self._stop_flag.clear()
        self._probe_btn.configure(state='disabled')
        self._stop_btn.configure(state='normal')
        self._progress.configure(value=0)
        self._log_append(f'Starting probe: {ncols}×{nrows} grid ({len(points)} points)\n')

        self._thread = threading.Thread(
            target=self._probe_worker,
            args=(points, retract, probe_z, feed, out_path),
            daemon=True,
        )
        self._thread.start()

    def _stop_probe(self):
        self._stop_flag.set()
        self._stop_btn.configure(state='disabled')

    def _probe_worker(self, points, retract, probe_z, feed, out_path):
        results = []
        total = len(points)
        safe_z = max(retract, 5.0)
        try:
            self._grbl_cmd('G21 G90')
            self._grbl_cmd('G10 L20 P1 X0 Y0')   # current XY position = work (0,0)
            self._ui_log('Work origin set to current position.\n')
            wco = self._grbl_get_wco()
            self._ui_log(f'WCO G54: X={wco[0]:.3f} Y={wco[1]:.3f} Z={wco[2]:.3f}\n')

            self._ui_log('Checking probe connectivity... ')
            connected = self._check_probe_connected()
            self._grbl_cmd(f'G0 Z{safe_z:.3f}')
            self._grbl_cmd('G4 P0')
            if not connected:
                raise RuntimeError(
                    'Probe not connected — check crocodile clip and cable'
                )
            self._ui_log('OK\n')

            for i, (x, y) in enumerate(points):
                if self._stop_flag.is_set():
                    self._ui_log('Stopped by user.\n')
                    break

                self._grbl_cmd(f'G0 X{x:.3f} Y{y:.3f}')
                self._grbl_cmd('G4 P0')
                self._grbl_cmd(f'G0 Z{retract:.3f}')
                self._grbl_cmd('G4 P0')
                self._ui_log(f'Probing ({x:.2f}, {y:.2f})... ')

                mx, my, mz = self._grbl_probe(f'G38.2 Z{probe_z:.3f} F{feed:.0f}')
                wz = mz - wco[2]
                results.append((x, y, wz))
                self._ui_log(f'Z = {wz:.4f}\n')

                self._grbl_cmd(f'G0 Z{retract:.3f}')
                self._grbl_cmd('G4 P0')

                progress = (i + 1) / total * 100
                self.after(0, lambda p=progress: self._progress.configure(value=p))

            self._grbl_cmd(f'G0 Z{safe_z:.3f}')
            self._grbl_cmd('G4 P0')
            self._grbl_cmd('G0 X0 Y0')
            self._ui_log('Returned to origin.\n')

            if len(results) == total and not self._stop_flag.is_set():
                _save_xyz(out_path, results)
                self._ui_log(f'Saved {len(results)} points → {out_path}\n')
                self.after(0, lambda: self._on_probe_done(out_path))
            else:
                self._ui_log(f'Incomplete: {len(results)}/{total} points probed.\n')
                self.after(0, self._on_probe_stopped)

        except Exception as e:
            self._ui_log(f'Error: {e}\n')
            self.after(0, self._on_probe_stopped)

    # ── GRBL helpers ──────────────────────────────────────────────────────

    def _grbl_cmd(self, cmd, timeout=30):
        self._serial.write((cmd + '\n').encode())
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self._serial.readline().decode('ascii', errors='ignore').strip()
            if line == 'ok':
                return
            if line.startswith('error'):
                raise RuntimeError(f'GRBL: {line}  (cmd: {cmd})')
            if line.startswith('ALARM'):
                raise RuntimeError(f'GRBL ALARM (cmd: {cmd})')
        raise TimeoutError(f'Timeout waiting for ok (cmd: {cmd})')

    def _grbl_probe(self, cmd, timeout=60):
        self._serial.write((cmd + '\n').encode())
        deadline = time.time() + timeout
        prb = None
        while time.time() < deadline:
            line = self._serial.readline().decode('ascii', errors='ignore').strip()
            if line.startswith('[PRB:'):
                if ':0]' in line:
                    raise RuntimeError('Probe did not trigger (no contact)')
                m = re.search(r'\[PRB:([-\d.]+),([-\d.]+),([-\d.]+):', line)
                if m:
                    prb = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
            elif line == 'ok':
                if prb is None:
                    raise RuntimeError('No PRB coordinates in probe response')
                return prb
            elif line.startswith('error'):
                raise RuntimeError(f'Probe error: {line}')
            elif line.startswith('ALARM'):
                raise RuntimeError('GRBL ALARM during probe')
        raise TimeoutError('Timeout waiting for probe result')

    def _check_probe_connected(self, timeout=10):
        """Probes 0.02 mm down from Z=0 to verify circuit continuity.
        Returns True if triggered (:1), False if no contact (:0)."""
        self._serial.write(b'G38.2 Z-0.02 F5\n')
        deadline = time.time() + timeout
        triggered = None
        while time.time() < deadline:
            line = self._serial.readline().decode('ascii', errors='ignore').strip()
            if line.startswith('[PRB:'):
                triggered = ':1]' in line
            elif line == 'ok':
                if triggered is None:
                    raise RuntimeError('No PRB response during connectivity check')
                return triggered
            elif line.startswith('error'):
                raise RuntimeError(f'Probe error during connectivity check: {line}')
            elif line.startswith('ALARM'):
                raise RuntimeError('GRBL ALARM during connectivity check')
        raise TimeoutError('Timeout during probe connectivity check')

    def _grbl_get_wco(self, timeout=5):
        self._serial.write(b'$#\n')
        deadline = time.time() + timeout
        wco = None
        while time.time() < deadline:
            line = self._serial.readline().decode('ascii', errors='ignore').strip()
            if line.startswith('[G54:'):
                m = re.search(r'\[G54:([-\d.]+),([-\d.]+),([-\d.]+)\]', line)
                if m:
                    wco = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
            elif line == 'ok':
                if wco is not None:
                    return wco
                raise RuntimeError('G54 offset not found in $# response')
        raise TimeoutError('Timeout reading WCO ($#)')

    # ── UI helpers ────────────────────────────────────────────────────────

    def _log_append(self, text):
        self._log.configure(state='normal')
        self._log.insert('end', text)
        self._log.see('end')
        self._log.configure(state='disabled')

    def _ui_log(self, text):
        self.after(0, lambda t=text: self._log_append(t))

    def _on_probe_done(self, out_path):
        self._probe_btn.configure(state='normal')
        self._stop_btn.configure(state='disabled')
        if self._auto_load_var.get() and self._on_done:
            self._on_done(out_path)
            messagebox.showinfo('Done', f'Heightmap saved and loaded:\n{out_path}', parent=self)
        else:
            messagebox.showinfo('Done', f'Heightmap saved:\n{out_path}', parent=self)

    def _on_probe_stopped(self):
        self._probe_btn.configure(state='normal')
        self._stop_btn.configure(state='disabled')

    def _browse_out(self):
        p = filedialog.asksaveasfilename(
            title='Save heightmap as',
            defaultextension='.xyz',
            filetypes=[('XYZ heightmap', '*.xyz'), ('All files', '*.*')],
            initialdir=self._output_dir,
        )
        if p:
            self._out_var.set(p)

    def _on_close(self):
        if self._thread and self._thread.is_alive():
            self._stop_flag.set()
        self._disconnect()
        self.destroy()


# ── Module-level helpers ──────────────────────────────────────────────────

def _make_grid(x0, x1, y0, y1, ncols, nrows):
    xs = [x0 + (x1 - x0) * i / (ncols - 1) for i in range(ncols)] if ncols > 1 else [(x0 + x1) / 2]
    ys = [y0 + (y1 - y0) * j / (nrows - 1) for j in range(nrows)] if nrows > 1 else [(y0 + y1) / 2]
    points = []
    for j, y in enumerate(ys):
        row = xs if j % 2 == 0 else list(reversed(xs))
        for x in row:
            points.append((x, y))
    return points


def _save_xyz(path: str, points: list):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        for x, y, z in points:
            f.write(f'{x:.4f} {y:.4f} {z:.4f}\n')
