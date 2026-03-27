"""Help dialog — parameter reference for gerber2gcode."""

import tkinter as tk
import tkinter.ttk as ttk

# ---------------------------------------------------------------------------
# Help content
# Each section is (title, [(param_name, description), ...])
# ---------------------------------------------------------------------------
HELP_SECTIONS = [
    ("General", [
        ("MODE",
         "Operation mode.\n"
         "  • mill   — V-bit isolation routing. The tool cuts channels in the\n"
         "             copper-clad board to isolate traces from each other.\n"
         "  • laser  — Laser engraving. The laser burns paint off the board\n"
         "             in areas where there is no copper (toner-transfer method).\n"
         "  • pocket — Endmill pocket milling. Each copper pad is milled out\n"
         "             with a flat end-mill using raster zigzag passes followed\n"
         "             by a slow perimeter finish pass. Useful for connector\n"
         "             cavities and rectangular through-hole pads."),

        ("MIRROR_X",
         "Mirror the design horizontally before generating G-code.\n"
         "Must be enabled for back-copper layers (B_Cu) so the physical\n"
         "result matches the original design when the board is flipped.\n"
         "Leave disabled for front-copper layers (F_Cu)."),

        ("SAFE_Z_MM",
         "Height (mm) the tool retracts to when traveling between paths.\n"
         "Must be high enough to clear all clamps, board edges, and surface\n"
         "irregularities. Typical value: 1.0 – 2.0 mm.\n"
         "Too low risks dragging the tool across copper; too high wastes time."),

        ("CLEARANCE_MM",
         "Isolation gap (mm) between adjacent copper regions.\n"
         "Leave blank (auto) to let the script detect the minimum gap present\n"
         "in the Gerber file. Set a manual value if auto-detection is wrong\n"
         "or if you want a wider isolation margin than the design minimum.\n"
         "The outermost mill pass is placed at CLEARANCE_MM from the copper edge."),

        ("SPINDLE_ON",
         "Emit S10000 M03 (spindle start) at the beginning of each G-code file.\n"
         "Enable if your controller requires an explicit spindle command.\n"
         "Leave disabled if spindle is started manually or controlled separately."),
    ]),

    ("Mill — V-bit", [
        ("VBIT_TIP_MM",
         "Diameter of the flat tip of the V-bit engraving tool (mm).\n"
         "A sharp bit has a tip near 0.1 mm. Wider tips remove more copper\n"
         "per pass but produce wider isolation channels.\n"
         "Used together with VBIT_ANGLE_DEG and CUT_DEPTH_MM to compute the\n"
         "effective cutting diameter at depth."),

        ("VBIT_ANGLE_DEG",
         "Total included angle of the V-bit (degrees).\n"
         "Common values: 20°, 30°, 45°, 60°, 90°.\n"
         "A narrower angle (e.g. 20°) gives finer cuts at the same depth;\n"
         "a wider angle cuts a broader channel per pass.\n"
         "Formula: effective_diam = tip + 2 × |depth| × tan(angle/2)."),

        ("CUT_DEPTH_MM",
         "Depth the tool plunges below the board surface (mm, negative).\n"
         "Typical range: −0.05 to −0.15 mm for copper isolation.\n"
         "Too shallow → incomplete copper removal; too deep → risk of cutting\n"
         "through the substrate or breaking thin bits.\n"
         "Start conservative (−0.05) and increase until isolation is clean."),

        ("FEED_RATE",
         "Horizontal cutting speed (mm/min) during G01 moves.\n"
         "Typical range: 200 – 600 mm/min for PCB copper on a rigid machine.\n"
         "Too fast → chatter, poor cut quality; too slow → unnecessary wear.\n"
         "Adjust based on your machine rigidity and bit quality."),

        ("PLUNGE_RATE",
         "Vertical plunge speed (mm/min) when the tool descends into the board.\n"
         "Should be slower than FEED_RATE to avoid snapping the bit on entry.\n"
         "Typical range: 50 – 100 mm/min."),

        ("PASS_OVERLAP_FRAC",
         "Fraction of tool diameter that successive passes overlap (0.0 – 1.0).\n"
         "0.3 means each pass overlaps 30% of the previous one.\n"
         "Higher overlap → smoother, more complete copper removal but more passes.\n"
         "Lower overlap → fewer passes but possible ridges between them."),

        ("OVERSHOOT_MM",
         "Extra distance (mm) the tool continues past the closed end of each\n"
         "contour path before lifting. Ensures the start/end junction of a\n"
         "closed loop is fully cut rather than leaving a small uncut tab.\n"
         "Typical value: 0.5 – 1.5 mm."),
    ]),

    ("Laser", [
        ("LASER_POWER",
         "Laser power level (S value, 0 – 1000, GRBL standard).\n"
         "The correct value depends on your laser module and the paint/toner\n"
         "being engraved. Start low and increase until paint is fully removed\n"
         "without burning the substrate."),

        ("LASER_FEED_RATE",
         "Laser engraving speed (mm/min).\n"
         "Slower speeds increase the energy delivered per mm², removing more\n"
         "material. Balance with LASER_POWER to achieve clean removal without\n"
         "scorching the board."),

        ("LASER_PASS_MM",
         "Distance between adjacent concentric laser passes (mm).\n"
         "Should be ≤ the laser spot diameter for complete coverage.\n"
         "Typical values: 0.05 – 0.15 mm depending on laser optics."),
    ]),

    ("Drill", [
        ("DRILL_SIZES",
         "Comma-separated list of available drill bit diameters (mm).\n"
         "Each hole in the Excellon file is rounded up to the nearest size\n"
         "in this list. A hole requiring 0.9 mm with list [0.8, 1.0, 1.25, 3.0]\n"
         "would be drilled with the 1.0 mm bit.\n"
         "Add or remove sizes to match your actual bit set."),

        ("DRILL_SAFE_Z_MM",
         "Travel height (mm) between drill holes.\n"
         "Analogous to SAFE_Z_MM but used only during drilling operations.\n"
         "Typically 1.0 – 2.0 mm."),

        ("DRILL_DEPTH_MM",
         "Depth to drill each hole (mm, negative).\n"
         "Must be deep enough to fully penetrate the board and backing material.\n"
         "For a standard 1.6 mm PCB: −1.8 to −2.2 mm is typical."),

        ("DRILL_FEED_RATE",
         "Plunge speed during drilling (mm/min).\n"
         "Slower than milling feed rates to avoid breaking drill bits.\n"
         "Typical range: 30 – 80 mm/min depending on bit diameter and material."),
    ]),

    ("Slots", [
        ("SLOT_TOOL_MM",
         "Diameter of the end-mill used to cut slots/oblong holes (mm).\n"
         "Must be ≤ the narrowest slot width in the design.\n"
         "The script calculates lateral offsets automatically if the tool is\n"
         "narrower than the slot, making multiple side-by-side passes."),

        ("SLOT_DEPTH_MM",
         "Depth to cut slots (mm, negative).\n"
         "Usually equal to DRILL_DEPTH_MM since slots are through-holes.\n"
         "Typical: −1.8 to −2.2 mm for a 1.6 mm board."),

        ("SLOT_PLUNGE_RATE",
         "Vertical plunge speed for slot entry (mm/min).\n"
         "Keep slow to protect the end-mill on initial engagement.\n"
         "Typical: 20 – 40 mm/min."),

        ("SLOT_FEED_RATE",
         "Horizontal cutting speed inside slots (mm/min).\n"
         "Slower than isolation routing due to full-width chip load.\n"
         "Typical: 60 – 120 mm/min."),
    ]),

    ("Pocket — Endmill", [
        ("POCKET_TOOL_MM",
         "Diameter of the flat end-mill used for pocket milling (mm).\n"
         "Pads narrower than this diameter are skipped automatically.\n"
         "The tool center is confined to a region inset by POCKET_TOOL_MM/2\n"
         "from each pad edge, so the tool never cuts outside the pad boundary."),

        ("POCKET_DEPTH_MM",
         "Depth to mill each pocket (mm, negative).\n"
         "Set to the board thickness plus a small margin to cut fully through.\n"
         "Typical: −1.6 to −2.0 mm for a standard 1.6 mm PCB."),

        ("POCKET_STEPOVER_FRAC",
         "Raster pass overlap as a fraction of POCKET_TOOL_MM (0.0 – 1.0).\n"
         "0.65 means each pass overlaps 65% of the tool diameter, leaving\n"
         "35% as fresh material per pass — a good balance between speed and\n"
         "surface finish. Lower values leave ridges; higher values add passes."),

        ("POCKET_PLUNGE_RATE",
         "Vertical plunge speed when descending into the pocket (mm/min).\n"
         "Keep slow to protect the end-mill on entry, especially for deep cuts.\n"
         "Typical: 20 – 40 mm/min."),

        ("POCKET_FEED_RATE",
         "Horizontal cutting speed during raster fill passes (mm/min).\n"
         "Full-width engagement puts more load on the tool than isolation routing,\n"
         "so use a conservative value.\n"
         "Typical: 60 – 150 mm/min depending on tool diameter and material."),

        ("POCKET_FINISH_FEED_RATE",
         "Speed for the perimeter finish pass that runs after the raster fill (mm/min).\n"
         "Should be slower than POCKET_FEED_RATE for a cleaner wall finish.\n"
         "Typical: 40 – 80 mm/min."),
    ]),

    ("Reference Marks", [
        ("REF_MARK_DEPTH_MM",
         "Depth of the alignment cross marks (mm, negative).\n"
         "These are shallow visual marks engraved outside the board outline\n"
         "to help realign the board for double-sided work or drilling.\n"
         "Typical: −0.10 to −0.20 mm (just enough to be visible)."),

        ("REF_CROSS_MM",
         "Total arm length of each '+' reference cross (mm).\n"
         "A value of 3.0 mm produces a cross with 1.5 mm arms in each direction.\n"
         "Make it large enough to be visible and measurable with calipers."),

        ("REF_OFFSET_MM",
         "Distance (mm) from the PCB edge to the center of each cross.\n"
         "0.0 places the crosses exactly at the board corner.\n"
         "A positive value moves them outside the board boundary, keeping\n"
         "them clear of the copper area."),
    ]),
]


class HelpDialog(tk.Toplevel):
    """Scrollable parameter reference dialog."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Parameter Reference — gerber2gcode")
        self.geometry("720x600")
        self.minsize(500, 400)
        self.configure(bg='#2d2d2d')
        self.resizable(True, True)
        self._build()
        self.transient(parent)
        self.focus_set()

    def _build(self):
        # Search bar
        search_frame = ttk.Frame(self)
        search_frame.pack(fill='x', padx=10, pady=(10, 4))
        ttk.Label(search_frame, text='Search:').pack(side='left', padx=(0, 6))
        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', self._on_search)
        ttk.Entry(search_frame, textvariable=self._search_var, width=30).pack(side='left')
        ttk.Button(search_frame, text='✕', width=3,
                   command=lambda: self._search_var.set('')).pack(side='left', padx=4)

        ttk.Separator(self, orient='horizontal').pack(fill='x', padx=10, pady=4)

        # Scrollable text area
        frame = ttk.Frame(self)
        frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        self._text = tk.Text(
            frame,
            bg='#1e1e1e', fg='#e0e0e0',
            font=('monospace', 10),
            wrap='word',
            relief='flat',
            state='disabled',
            cursor='arrow',
            spacing1=2, spacing3=4,
        )
        sb = ttk.Scrollbar(frame, orient='vertical', command=self._text.yview)
        self._text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._text.pack(side='left', fill='both', expand=True)

        # Tags for styling
        self._text.tag_configure('section',
                                 font=('sans-serif', 11, 'bold'),
                                 foreground='#4a9eff',
                                 spacing1=12, spacing3=4)
        self._text.tag_configure('param',
                                 font=('monospace', 10, 'bold'),
                                 foreground='#DAA520',
                                 spacing1=6)
        self._text.tag_configure('desc',
                                 font=('monospace', 10),
                                 foreground='#cccccc',
                                 lmargin1=20, lmargin2=20)
        self._text.tag_configure('highlight',
                                 background='#3a5a3a',
                                 foreground='#ffffff')

        self._render(HELP_SECTIONS)

        # Mouse wheel
        self._text.bind('<MouseWheel>',
                        lambda e: self._text.yview_scroll(-1 * (e.delta // 120), 'units'))
        self._text.bind('<Button-4>',
                        lambda e: self._text.yview_scroll(-1, 'units'))
        self._text.bind('<Button-5>',
                        lambda e: self._text.yview_scroll(1, 'units'))

    def _render(self, sections):
        self._text.configure(state='normal')
        self._text.delete('1.0', 'end')
        for section_title, params in sections:
            self._text.insert('end', f'\n{section_title}\n', 'section')
            for name, desc in params:
                self._text.insert('end', f'  {name}\n', 'param')
                self._text.insert('end', f'{desc}\n', 'desc')
        self._text.configure(state='disabled')

    def _on_search(self, *_):
        query = self._search_var.get().strip().lower()
        if not query:
            self._render(HELP_SECTIONS)
            return

        filtered = []
        for section_title, params in HELP_SECTIONS:
            matched = [
                (name, desc) for name, desc in params
                if query in name.lower() or query in desc.lower()
            ]
            if matched:
                filtered.append((section_title, matched))

        self._render(filtered if filtered else [('No results', [('—', f'No parameters match "{query}".')])])

        # Highlight matching text
        self._text.configure(state='normal')
        start = '1.0'
        while True:
            pos = self._text.search(query, start, nocase=True, stopindex='end')
            if not pos:
                break
            end = f'{pos}+{len(query)}c'
            self._text.tag_add('highlight', pos, end)
            start = end
        self._text.configure(state='disabled')
