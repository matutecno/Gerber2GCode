"""Main application window."""

import sys
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
from datetime import datetime, timezone
from queue import Queue, Empty
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui import theme
from gui import history as hist
from gui.worker import GenerationWorker
from gui.panels.preview_panel import PreviewPanel
from gui.panels.files_panel import FilesPanel
from gui.panels.params_panel import ParamsPanel
from gui.help_dialog import HelpDialog

BG_DARK = '#1e1e1e'
BG_PANEL = '#2d2d2d'


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('Gerber → G-code Converter')
        self.root.geometry('1400x820')
        self.root.configure(bg=BG_PANEL)

        theme.apply(root)

        self._worker = None
        self._queue = None
        self._poll_job = None
        self._paned = None

        self._build_toolbar()
        self._build_main()
        self._build_statusbar()

        self._refresh_history_list()
        self.root.after(50, self._init_sash_positions)

    def _init_sash_positions(self):
        self.root.update_idletasks()
        if self._paned.winfo_width() < 10:
            self.root.after(50, self._init_sash_positions)
            return
        self._paned.sash_place(0, 580, 1)

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = ttk.Frame(self.root)
        tb.pack(side='top', fill='x', padx=4, pady=4)

        self._gen_btn = ttk.Button(tb, text='Generate G-code',
                                   style='Generate.TButton',
                                   command=self._on_generate)
        self._gen_btn.pack(side='left', padx=(0, 6))

        ttk.Button(tb, text='Reset Defaults',
                   command=self._on_reset_defaults).pack(side='left', padx=(0, 6))

        ttk.Button(tb, text='Help',
                   command=self._on_help).pack(side='left')

    def _build_main(self):
        paned = tk.PanedWindow(self.root, orient='horizontal',
                               bg=BG_PANEL, sashwidth=5, sashrelief='flat')
        paned.pack(fill='both', expand=True, padx=4, pady=(0, 4))
        self._paned = paned  # stored for sash init

        # ── Left pane: files + params ──────────────────────────────────
        left = ttk.Frame(paned, width=300)
        left.pack_propagate(False)

        self.files_panel = FilesPanel(left)
        self.files_panel.pack(fill='x')

        # Scrollable params panel
        params_outer = ttk.Frame(left)
        params_outer.pack(fill='both', expand=True)

        canvas = tk.Canvas(params_outer, bg=BG_PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(params_outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        self.params_panel = ParamsPanel(canvas)
        canvas_window = canvas.create_window((0, 0), window=self.params_panel, anchor='nw')

        self.params_panel.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        canvas.bind(
            '<Configure>',
            lambda e: canvas.itemconfig(canvas_window, width=e.width)
        )
        canvas.bind('<Enter>',
                    lambda e: canvas.bind_all('<MouseWheel>',
                                              lambda ev: canvas.yview_scroll(-1*(ev.delta//120), 'units')))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))

        paned.add(left, minsize=280, stretch='never')

        # ── Center pane: preview ───────────────────────────────────────
        center = ttk.Frame(paned)
        self.preview_panel = PreviewPanel(center)
        self.preview_panel.pack(fill='both', expand=True)
        paned.add(center, minsize=400, stretch='always')

        # ── Right pane: history ────────────────────────────────────────
        right = ttk.Frame(paned, width=280)
        right.pack_propagate(False)
        self._build_history_pane(right)
        paned.add(right, minsize=200, stretch='never')

    def _build_history_pane(self, parent):
        ttk.Label(parent, text='Run history').pack(anchor='w', padx=6, pady=(6, 2))

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True, padx=4)

        cols = ('date', 'file', 'clearance', 'passes')
        self._hist_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=20)
        self._hist_tree.heading('date',      text='Date')
        self._hist_tree.heading('file',      text='GBR file')
        self._hist_tree.heading('clearance', text='Clearance')
        self._hist_tree.heading('passes',    text='Files')

        self._hist_tree.column('date',      width=90, minwidth=70)
        self._hist_tree.column('file',      width=100, minwidth=60)
        self._hist_tree.column('clearance', width=60, minwidth=50)
        self._hist_tree.column('passes',    width=40, minwidth=30)

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self._hist_tree.yview)
        self._hist_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self._hist_tree.pack(side='left', fill='both', expand=True)

        self._hist_tree.bind('<Double-1>', self._on_history_load)

        ttk.Button(parent, text='Load selected', command=self._on_history_load).pack(
            anchor='w', padx=6, pady=4)

    def _build_statusbar(self):
        sb = ttk.Frame(self.root)
        sb.pack(side='bottom', fill='x')

        self._status_var = tk.StringVar(value='Ready.')
        ttk.Label(sb, textvariable=self._status_var, anchor='w').pack(
            side='left', fill='x', expand=True, padx=6)

        self._progress = ttk.Progressbar(sb, mode='indeterminate', length=160)
        self._progress.pack(side='right', padx=6, pady=2)

    # ── Actions ───────────────────────────────────────────────────────────

    def _on_reset_defaults(self):
        self.params_panel.reset_defaults()

    def _on_help(self):
        HelpDialog(self.root)

    def _on_generate(self):
        gbr = self.files_panel.get_gbr_path()
        if not gbr:
            messagebox.showerror('Missing input', 'Please select a Gerber (.gbr) file.')
            return
        if not Path(gbr).exists():
            messagebox.showerror('File not found', f'Gerber file not found:\n{gbr}')
            return

        config = self.params_panel.get_config()
        drl_paths = self.files_panel.get_drl_paths()
        output_dir = self.files_panel.get_output_dir() or str(Path(gbr).parent)

        self._gen_btn.configure(state='disabled')
        self._status_var.set('Running…')
        self._progress.start(10)

        self._queue = Queue()
        self._worker = GenerationWorker(
            config=config,
            gbr_path=gbr,
            drl_paths=drl_paths,
            output_dir=output_dir,
            queue=self._queue,
        )
        self._worker.start()
        self._poll_job = self.root.after(100, self._poll_queue)

    def _poll_queue(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                mtype = msg.get('type')

                if mtype == 'status':
                    self._status_var.set(msg['text'])

                elif mtype == 'copper':
                    self.preview_panel.show_copper(msg['geom'], msg['individuals'])

                elif mtype == 'paths':
                    self.preview_panel.show_paths(msg['paths'])

                elif mtype == 'drills':
                    self.preview_panel.show_drills(msg['holes'], msg['slots'])

                elif mtype == 'done':
                    self._on_done(msg)
                    return

                elif mtype == 'error':
                    self._on_error(msg['text'])
                    return

        except Empty:
            pass

        # Reschedule while worker is alive
        if self._worker and self._worker.is_alive():
            self._poll_job = self.root.after(100, self._poll_queue)
        else:
            self._stop_worker_ui()

    def _on_done(self, msg):
        self._stop_worker_ui()
        result = msg.get('result', {})
        files = msg.get('files', [])

        n = len(files)
        clr = result.get('clearance')
        clr_str = f"{clr:.3f} mm" if clr else "n/a"
        self._status_var.set(f"Done — {n} file(s) generated, clearance {clr_str}")

        # Save to history
        entry = {
            'id': datetime.now(timezone.utc).isoformat(),
            'gbr_path': self.files_panel.get_gbr_path(),
            'drl_paths': self.files_panel.get_drl_paths(),
            'output_dir': self.files_panel.get_output_dir(),
            'output_files': files,
            'config': self.params_panel.get_config(),
            'clearance': clr,
            'board_w': result.get('board_w'),
            'board_h': result.get('board_h'),
        }
        hist.add(entry)
        self._refresh_history_list()

    def _on_error(self, tb_text: str):
        self._stop_worker_ui()
        self._status_var.set('Error — see dialog')
        messagebox.showerror('Generation error', tb_text)

    def _stop_worker_ui(self):
        self._progress.stop()
        self._gen_btn.configure(state='normal')
        if self._poll_job:
            self.root.after_cancel(self._poll_job)
            self._poll_job = None

    # ── History ───────────────────────────────────────────────────────────

    def _refresh_history_list(self):
        for row in self._hist_tree.get_children():
            self._hist_tree.delete(row)
        for entry in hist.load_all():
            raw_id = entry.get('id', '')
            # Pretty-print just date+time without timezone noise
            try:
                dt = datetime.fromisoformat(raw_id)
                date_str = dt.strftime('%m-%d %H:%M')
            except Exception:
                date_str = raw_id[:16]

            gbr = Path(entry.get('gbr_path', '')).name
            clr = entry.get('clearance')
            clr_str = f"{clr:.3f}" if clr else ''
            n_files = len(entry.get('output_files', []))

            self._hist_tree.insert('', 'end', iid=raw_id,
                                   values=(date_str, gbr, clr_str, n_files))

    def _on_history_load(self, event=None):
        sel = self._hist_tree.selection()
        if not sel:
            return
        iid = sel[0]
        for entry in hist.load_all():
            if entry.get('id') == iid:
                self.files_panel.load_config(entry)
                cfg = entry.get('config', {})
                if cfg:
                    self.params_panel.load_config(cfg)
                break
