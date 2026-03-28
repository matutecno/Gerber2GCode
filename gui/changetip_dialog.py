"""Change Tip dialog — guided workflow to swap the milling bit safely."""

import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as messagebox
import time
from pathlib import Path


_STEPS = [
    "1. Connect the machine and click  \"Raise & Lock\".",
    "2. Change the tip. Motors are locked — machine won't drift.",
    "3. Click  \"Return to Origin\"  (X0 Y0).",
    "4. Use the Z jog buttons to lower the tip until it just touches the surface.",
    "5. Click  \"Set Z=0\"  to register the new tool height.",
]


class ChangeTipDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Change Tip')
        self.resizable(False, False)
        self.grab_set()

        self._serial = None
        self._build()
        self.transient(parent)
        self.wait_visibility()
        self.lift()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self._scan_ports()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build(self):
        pad = {'padx': 10, 'pady': 5}

        # Guide
        guide = ttk.LabelFrame(self, text='Steps')
        guide.pack(fill='x', **pad)
        for step in _STEPS:
            ttk.Label(guide, text=step, anchor='w').pack(fill='x', padx=6, pady=1)

        # Connection
        cf = ttk.LabelFrame(self, text='Connection')
        cf.pack(fill='x', **pad)
        cf.columnconfigure(1, weight=1)

        ttk.Label(cf, text='Port').grid(row=0, column=0, sticky='e', padx=(6, 2), pady=4)
        self._port_var = tk.StringVar()
        self._port_combo = ttk.Combobox(cf, textvariable=self._port_var, width=20)
        self._port_combo.grid(row=0, column=1, sticky='ew', padx=(0, 2), pady=4)
        ttk.Button(cf, text='Scan', command=self._scan_ports).grid(row=0, column=2, padx=2)
        self._conn_btn = ttk.Button(cf, text='Connect', command=self._toggle_connect)
        self._conn_btn.grid(row=0, column=3, padx=(2, 6), pady=4)

        ttk.Label(cf, text='Baud').grid(row=1, column=0, sticky='e', padx=(6, 2), pady=(0, 4))
        self._baud_var = tk.StringVar(value='115200')
        ttk.Entry(cf, textvariable=self._baud_var, width=10).grid(row=1, column=1, sticky='w', pady=(0, 4))
        self._conn_status = tk.StringVar(value='Disconnected')
        ttk.Label(cf, textvariable=self._conn_status, foreground='gray').grid(
            row=1, column=2, columnspan=2, sticky='w', padx=4, pady=(0, 4))

        # Raise parameters
        pf = ttk.LabelFrame(self, text='Raise height')
        pf.pack(fill='x', **pad)
        ttk.Label(pf, text='Z raise (mm)').grid(row=0, column=0, sticky='e', padx=(6, 2), pady=4)
        self._raise_var = tk.StringVar(value='60')
        ttk.Entry(pf, textvariable=self._raise_var, width=8).grid(row=0, column=1, sticky='w', pady=4)

        # Step 1 & 2 buttons
        s12 = ttk.Frame(self)
        s12.pack(fill='x', **pad)
        self._raise_btn = ttk.Button(s12, text='① Raise & Lock', command=self._raise_and_lock, state='disabled')
        self._raise_btn.pack(side='left', padx=(0, 6))
        self._origin_btn = ttk.Button(s12, text='③ Return to Origin', command=self._return_to_origin, state='disabled')
        self._origin_btn.pack(side='left')

        # Step 4: Z jog
        jf = ttk.LabelFrame(self, text='④  Z jog')
        jf.pack(fill='x', **pad)

        up_frame = ttk.Frame(jf)
        up_frame.pack(pady=(4, 1))
        for text, step in [('▲ 10 mm', 10.0), ('▲ 1 mm', 1.0), ('▲ 0.1 mm', 0.1), ('▲ 0.01 mm', 0.01)]:
            ttk.Button(up_frame, text=text, width=10,
                       command=lambda s=step: self._jog_z(s)).pack(side='left', padx=3)

        dn_frame = ttk.Frame(jf)
        dn_frame.pack(pady=(1, 4))
        for text, step in [('▼ 0.01 mm', -0.01), ('▼ 0.1 mm', -0.1), ('▼ 1 mm', -1.0), ('▼ 10 mm', -10.0)]:
            ttk.Button(dn_frame, text=text, width=10,
                       command=lambda s=step: self._jog_z(s)).pack(side='left', padx=3)

        # Step 5: Set Z=0
        s5 = ttk.Frame(self)
        s5.pack(fill='x', **pad)
        self._setz_btn = ttk.Button(s5, text='⑤ Set Z=0', command=self._set_z0, state='disabled')
        self._setz_btn.pack(side='left', padx=(0, 6))
        ttk.Button(s5, text='Close', command=self._on_close).pack(side='left')

        # Status
        self._status_var = tk.StringVar(value='Connect the machine to start.')
        ttk.Label(self, textvariable=self._status_var, foreground='#aaaaaa',
                  anchor='w').pack(fill='x', padx=10, pady=(2, 8))

    # ── Connection ────────────────────────────────────────────────────────

    def _scan_ports(self):
        try:
            import serial.tools.list_ports
            ports = [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            ports = []
        self._port_combo['values'] = ports
        if ports and not self._port_var.get():
            self._port_var.set(ports[0])

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
            self._serial = serial.Serial(port, baud, timeout=1)
            time.sleep(0.1)
            self._serial.write(b'\x18')
            time.sleep(1.5)
            self._serial.flushInput()
            self._conn_status.set(f'Connected: {port}')
            self._conn_btn.configure(text='Disconnect')
            self._raise_btn.configure(state='normal')
            self._status_var.set('Ready. Click  "Raise & Lock".')
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
        for btn in (self._raise_btn, self._origin_btn, self._setz_btn):
            btn.configure(state='disabled')
        self._status_var.set('Connect the machine to start.')

    # ── Actions ───────────────────────────────────────────────────────────

    def _raise_and_lock(self):
        try:
            raise_mm = float(self._raise_var.get())
        except ValueError:
            messagebox.showerror('Error', 'Z raise must be numeric.', parent=self)
            return
        try:
            self._cmd('G21')
            self._cmd('G90')
            self._cmd(f'G0 Z{raise_mm:.3f}')
            self._cmd('G4 P0')
            self._origin_btn.configure(state='normal')
            self._setz_btn.configure(state='normal')
            self._status_var.set('Z raised. Change the tip, then click  "Return to Origin".')
        except Exception as e:
            messagebox.showerror('Error', str(e), parent=self)

    def _return_to_origin(self):
        try:
            raise_mm = float(self._raise_var.get())
            self._cmd(f'G0 Z{raise_mm:.3f}')
            self._cmd('G4 P0')
            self._cmd('G0 X0 Y0')
            self._cmd('G4 P0')
            self._status_var.set('At origin. Jog Z down until tip touches surface, then Set Z=0.')
        except Exception as e:
            messagebox.showerror('Error', str(e), parent=self)

    def _jog_z(self, step: float):
        if not self._serial or not self._serial.is_open:
            return
        try:
            feed = 100 if abs(step) >= 1.0 else 20
            self._serial.write(f'$J=G21 G91 Z{step:.3f} F{feed}\n'.encode())
            time.sleep(abs(step) / feed * 60 + 0.3)
            self._serial.flushInput()
        except Exception as e:
            messagebox.showerror('Jog error', str(e), parent=self)

    def _set_z0(self):
        try:
            self._cmd('G10 L20 P1 Z0')
            self._status_var.set('Z=0 set. Tip change complete.')
            messagebox.showinfo('Done', 'Z=0 registered at current position.', parent=self)
        except Exception as e:
            messagebox.showerror('Error', str(e), parent=self)

    # ── GRBL helper ───────────────────────────────────────────────────────

    def _cmd(self, cmd, timeout=30):
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
        raise TimeoutError(f'Timeout (cmd: {cmd})')

    def _on_close(self):
        self._disconnect()
        self.destroy()
