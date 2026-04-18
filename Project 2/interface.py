# interface.py

import tkinter as tk
import re, datetime

from tkinter import ttk, scrolledtext, messagebox, font
from preprocessing import get_connection, close_connection, get_qep, get_all_aqps, validate_query, get_root_cost
from annotation import generate_annotations

# =============================================================================
# SECTION 0: CONSTANTS
# =============================================================================

NODE_W,NODE_H = 160,50 # width and height of each node rectangle
H_GAP, V_GAP = 40,80 # horizontal and vertical gap between sibling subtrees
MARGIN_X, MARGIN_Y = 20,20 # left/top canvas margin

NODE_COLORS = {
    "scan":  {"fill": "#D4EDDA", "outline": "#28A745", "text": "#155724"},
    "join":  {"fill": "#FFF3CD", "outline": "#FFC107", "text": "#856404"},
    "other": {"fill": "#D6E4F7", "outline": "#5B9BD5", "text": "#1a3a5c"},
}


_CHART_PROPERTIES = {
    "qep":          ["#28A745","QEP (chosen)"],
    "no_hashjoin":  ["#5B9BD5","No Hash Join"],
    "no_mergejoin": ["#FFC107","No Merge Join"],
    "no_nestloop":  ["#E74C3C","No Nested Loop"],
    "no_seqscan":   ["#9B59B6","No Seq Scan"],
    "no_indexscan": ["#E67E22","No Index Scan"],
}

_SQL_KEYWORDS = {
    'select','from','where','join','inner','outer','left','right','cross',
    'full','on','and','or','not','as','in','is','null','between','like',
    'exists','all','any','distinct','having','union','intersect','except',
    'with','by','asc','desc','case','when','then','else','end','true',
    'false','limit','offset','group','order','into','over','partition',
    'rows','range','unbounded','preceding','following','current','row',
    'filter','cast','date','interval','timestamp',
}
_SQL_FUNCTIONS = {
    'count','sum','avg','min','max','coalesce','nullif','cast','extract',
    'date_trunc','now','current_date','current_timestamp','substring',
    'trim','upper','lower','length','concat','replace','round','floor',
    'ceil','abs','mod','power','sqrt','to_date','to_char','isnull','nvl',
}
_SQL_TOKEN_RE = re.compile(
    r"(?P<string>'[^']*')"
    r"|(?P<number>\b\d+(?:\.\d+)?\b)"
    r"|(?P<operator>>=|<=|<>|!=|[=<>*])"
    r"|(?P<word>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<dot>\.)"
    r"|(?P<punct>[(),;])"
    r"|(?P<ws>\s+)"
    r"|(?P<other>.)"
)
NODE_TOOLTIPS = {
    # Scans
    "Seq Scan":          "Sequential Scan: Reads every row in the table from disk from top to bottom.\n It is used when no useful index exists or when most rows are needed.",
    "Index Scan":        "Index Scan: Uses a B-tree index to find matching rows directly.\nFaster than Seq Scan when only a small fraction of rows match.",
    "Index Only Scan":   "Index Only Scan: Like Index Scan but reads data directly from the index\nwithout touching the main table. Very fast for covered queries.",
    "Bitmap Heap Scan":  "Bitmap Heap Scan: First builds a bitmap of matching row locations,\nthen fetches those rows. Good for medium-selectivity conditions.",
    "Bitmap Index Scan": "Bitmap Index Scan: Scans the index to build a bitmap of row locations.\nAlways paired with a Bitmap Heap Scan above it.",
    "Tid Scan":          "TID Scan: Fetches rows by their physical tuple ID.\nOnly used when the query references ctid directly.",

    # Joins
    "Hash Join":         "Hash Join: Builds a hash table from the smaller input, then probes\nit with each row from the larger input. Best for large unsorted tables.",
    "Merge Join":        "Merge Join: Merges two pre-sorted inputs row by row.\nVery efficient when both sides are already sorted on the join key.",
    "Nested Loop":       "Nested Loop: For each row in the outer input, scans the inner input.\nFast when the inner side is small or accessed via index.",

    # Aggregation
    "Aggregate":         "Aggregate: Computes aggregate functions (COUNT, SUM, AVG etc.)\nover all input rows with no grouping.",
    "Hash Aggregate":    "Hash Aggregate: Groups rows using a hash table.\nGood for GROUP BY when the number of groups fits in memory.",
    "Group Aggregate":   "Group Aggregate: Groups pre-sorted rows sequentially.\nRequires input to be sorted on GROUP BY keys that often follows a Sort.",

    # Sorting / Limiting
    "Sort":              "Sort: Orders rows by the specified keys.\nExpensive for large inputs which may spill to disk if memory is limited.",
    "Limit":             "Limit: Stops execution after N rows are produced.\nEnables early termination that saves cost when combined with ORDER BY.",

    # Misc
    "Unique":            "Unique: Removes consecutive duplicate rows.\nUsed for DISTINCT or UNION when it requires sorted input.",
    "Hash":              "Hash: Builds a hash table from its input.\nAlways appears as the inner child of a Hash Join.",
    "Materialize":       "Materialize: Caches its input rows in memory (or disk).\nPrevents re-scanning the same subplan multiple times.",
    "Gather":            "Gather: Collects results from parallel worker processes\ninto a single stream for the main process.",
    "Gather Merge":      "Gather Merge: Like Gather, but preserves sort order\nwhen merging results from parallel workers.",
    "Subquery Scan":     "Subquery Scan: Wraps a subquery result so it can be\ntreated as a table by the outer query.",
    "Result":            "Result: Returns a constant or computed value directly\nwithout scanning any table.",
    "Append":            "Append: Concatenates results from multiple subplans.\nUsed for UNION ALL or partitioned table scans.",
    "Memoize":           "Memoize: Caches results of parameterized inner scans\nto avoid re-execution for repeated parameter values.",
}

# =============================================================================
# SECTION 1: CANVAS CLASS
# =============================================================================

class _CanvasTooltip:
    def __init__(self, canvas: tk.Canvas):
        self._canvas = canvas
        self._texts = {}
        self._tip_win = None
        self._after = None

        canvas.bind("<Motion>", self._on_motion, add="+")
        canvas.bind("<Leave>", self._hide, add="+")

    def register(self, item_id: int, text: str):
        self._texts[item_id] = text
        self._canvas.tag_bind(item_id, "<Enter>",
            lambda e, t=text: self._schedule(t, e.x_root, e.y_root))
        self._canvas.tag_bind(item_id, "<Motion>",
            lambda e, t=text: self._schedule(t, e.x_root, e.y_root))
        self._canvas.tag_bind(item_id, "<Leave>",
            lambda e: self._hide())

    def _schedule(self, text, xr, yr):
        if self._after:
            self._canvas.after_cancel(self._after)
        self._after = self._canvas.after(300, lambda: self._show(text, xr, yr))

    def _on_motion(self, event):
        # Fires on canvas background — hide if not over a registered item
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        items = self._canvas.find_overlapping(cx-2, cy-2, cx+2, cy+2)
        if not any(i in self._texts for i in items):
            self._hide()

    def _show(self, text: str, rx: int, ry: int):
        self._hide()
        self._tip_win = tk.Toplevel(self._canvas)
        self._tip_win.wm_overrideredirect(True)
        self._tip_win.wm_attributes("-topmost", True)
        border = tk.Frame(self._tip_win, bg="#3A3A5C", padx=1, pady=1)
        border.pack()
        tk.Label(
            border, text=text, justify="left",
            bg="#FFFDE7", fg="#1a1a2e", font=("Arial", 8),
            padx=10, pady=6, wraplength=300,
        ).pack()
        self._tip_win.wm_geometry(f"+{rx + 14}+{ry + 10}")

    def _hide(self, event=None):
        if self._after:
            self._canvas.after_cancel(self._after)
            self._after = None
        if self._tip_win:
            self._tip_win.destroy()
            self._tip_win = None
# =============================================================================
# SECTION 2: MAIN APPLICATION CLASS
# =============================================================================

class TpcHAnnotatorApp:
    """
    Main GUI application class.

    Layout (3-panel horizontal) (Tentative):
    ┌─────────────────┬──────────────────────┬─────────────────┐
    │   SQL Input     │  Annotated Output    │   QEP Tree      │
    │   (Left Panel)  │  (Middle Panel)      │  (Right Panel)  │
    └─────────────────┴──────────────────────┴─────────────────┘
    """

    def __init__(self, root: tk.Tk):
        """
        Initialises the application window and builds all UI components.
        """
        self.root = root
        self.db_connected = False
        self.conn = None
        self._canvas_zoom = 1.0
        self._current_qep_plan = None
        self._loading_popup = None
        self._loading_bar = None
        self._build_top_bar()
        self._build_panels()
        self._build_status_bar()
        self._history = []


# =============================================================================
# SECTION 3: UI BUILDER METHODS
# =============================================================================

    def _build_top_bar(self):
        """
        Builds the top control bar containing:
            - "Connect to DB" / "Disconnect from DB" button (toggles)
            - Connection status label → shows "Connected" or "Not connected"
            - "Clear All" button
        """
        top_bar = tk.Frame(self.root)
        top_bar.pack(fill="x", padx=10, pady=5)

        self.connect_btn = tk.Button(
            top_bar,
            text="Connect to DB",
            command=self._toggle_db_connection,
            bg="#4CAF50",
            fg="white"
        )
        self.connect_btn.pack(side="left")

        self.status_lbl = tk.Label(
            top_bar,
            text="Not connected",
            fg="red"
        )
        self.status_lbl.pack(side="left", padx=10)

        clear_btn = tk.Button(
            top_bar,
            text="Clear All",
            command=self._clear_all,
            bg="#E0E0E0"
        )
        clear_btn.pack(side="right")

    def _build_panels(self):
        """Create the top control bar with database and reset actions."""
        paned = tk.PanedWindow(self.root, orient="horizontal", sashrelief="raised")
        paned.pack(fill="both", expand=True, padx=10, pady=(0,10))

        left_panel = self._build_left_panel(paned)
        middle_panel = self._build_middle_panel(paned)
        right_panel = self._build_right_panel(paned)

        paned.add(left_panel, width=350)
        paned.add(middle_panel, width=450)
        paned.add(right_panel, width=350)

    def _build_left_panel(self, parent) -> tk.Frame:
        """Builds the LEFT panel: SQL query input area."""
        frame = tk.LabelFrame(parent, text="SQL Query Input")

        lbl = tk.Label(frame, text="Enter SQL query:")
        lbl.pack(anchor="w", padx=8, pady=(8, 4))

        self.query_input = scrolledtext.ScrolledText(frame, wrap="word", height=15)
        self.query_input.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        btn_row = tk.Frame(frame, bg=frame.cget("bg"))
        btn_row.pack(fill="x", padx=8, pady=(0, 8))
        btn_row.columnconfigure(0, weight=30)
        btn_row.columnconfigure(1, weight=70)

        history_btn = tk.Button(
            btn_row, text="History",
            command=self._open_history_window,
            bg="#6C757D", fg="white",
            font=("Arial", 9),
            relief="flat", padx=4, pady=7,
            cursor="hand2"
        )
        history_btn.grid(row=0, column=1, sticky="ew")

        annotate_btn = tk.Button(
            btn_row, text="  Annotate Query",
            command=self._run_annotation,
            bg="#2E86DE", fg="white",
            font=("Arial", 10, "bold"),
            relief="flat", padx=8, pady=7,
            cursor="hand2"
        )
        annotate_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        return frame

    def _build_middle_panel(self, parent) -> tk.Frame:
        """Builds the middle panel: Annotated query output display."""
        frame = tk.LabelFrame(parent, text="Annotated Output")
        self.annotation_output = scrolledtext.ScrolledText(frame, wrap="word", state="disabled", height=18)
        self.annotation_output.pack(fill="both", expand=True, padx=8, pady=8)

        self.annotation_output.tag_config("sql", foreground="navy")
        self.annotation_output.tag_config("scan", foreground="green")
        self.annotation_output.tag_config("join", foreground="darkorange")
        self.annotation_output.tag_config("other", foreground="grey")
        self.annotation_output.tag_config("header", foreground="black", font=("Arial", 10, "bold"))

        copy_btn = tk.Button(
            frame,
            text="Copy to Clipboard",
            command=self._copy_output_to_clipboard
        )
        copy_btn.pack(fill="x", padx=8, pady=(0, 8))

        return frame

    def _build_right_panel(self, parent) -> tk.Frame:
        """Builds the right panel: QEP + Cost Chart display."""
        frame = tk.LabelFrame(parent, text="Query Execution Plan (QEP)")

        zoom_bar = tk.Frame(frame)
        zoom_bar.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(zoom_bar, text="Zoom:").pack(side="left")
        tk.Button(zoom_bar, text="-", width=3, command=self._zoom_qep_out).pack(side="left", padx=(6, 4))
        tk.Button(zoom_bar, text="+", width=3, command=self._zoom_qep_in).pack(side="left")

        # ── Colour legend ────────────────────────────────────────────────────
        legend_bar = tk.Frame(frame, bg="#F0F0F0", relief="flat", bd=1)
        legend_bar.pack(fill="x", padx=8, pady=(6, 0))
        for label, color in [("Scan", "#28A745"), ("Join", "#FFC107"), ("Other", "#5B9BD5")]:
            box = tk.Frame(legend_bar, bg=color, width=12, height=12)
            box.pack(side="left", padx=(6, 2), pady=4)
            tk.Label(legend_bar, text=label, bg="#F0F0F0",
                    font=("Arial", 8)).pack(side="left", padx=(0, 8))

        # ── Notebook with 2 tabs ─────────────────────────────────────────────
        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # ── Tab 1: QEP Tree (your existing canvas code) ──────────────────────
        tree_tab = tk.Frame(notebook)
        notebook.add(tree_tab, text="  QEP Tree  ")

        canvas_frame = tk.Frame(tree_tab)
        canvas_frame.pack(fill="both", expand=True)
        self.qep_canvas = tk.Canvas(canvas_frame, bg="#EEF2F7", highlightthickness=0)
        self._canvas_tooltip = _CanvasTooltip(self.qep_canvas)
        vscroll = ttk.Scrollbar(canvas_frame, orient="vertical",
                                command=self.qep_canvas.yview)
        hscroll = ttk.Scrollbar(canvas_frame, orient="horizontal",
                                command=self.qep_canvas.xview)
        self.qep_canvas.configure(yscrollcommand=vscroll.set,
                                xscrollcommand=hscroll.set)
        hscroll.pack(side="bottom", fill="x")
        vscroll.pack(side="right",  fill="y")
        self.qep_canvas.pack(side="left", fill="both", expand=True)
        self.qep_canvas.config(cursor="fleur")
        self.qep_canvas.bind("<MouseWheel>",       self._on_canvas_mousewheel)
        self.qep_canvas.bind("<Shift-MouseWheel>", self._on_canvas_shift_mousewheel)
        self.qep_canvas.bind("<ButtonPress-1>",    self._on_canvas_drag_start)
        self.qep_canvas.bind("<B1-Motion>",        self._on_canvas_drag_move)

        # ── Tab 2: AQP Cost Chart ────────────────────────────────────────────
        chart_tab = tk.Frame(notebook, bg="white")
        notebook.add(chart_tab, text="  Cost Chart  ")

        self.cost_canvas = tk.Canvas(chart_tab, bg="white", highlightthickness=0)
        self.cost_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        # Redraw on resize so bars scale to available width
        self.cost_canvas.bind(
            "<Configure>",
            lambda e: self._redraw_chart_on_resize()
        )
        # Store latest chart data so resize can redraw
        self._last_chart_data = None

        return frame

    def _build_status_bar(self):
        """Builds a status bar at the very bottom of the window."""
        self.status_bar = tk.Label(
            self.root,
            text="Ready.",
            relief="sunken",
            anchor="w",
            padx=5
        )
        self.status_bar.pack(side="bottom", fill="x")


# =============================================================================
# SECTION 4: DATABASE AND ANNOTATION
# =============================================================================

    def _toggle_db_connection(self):
        """Toggles between connecting and disconnecting from the DB."""
        if self.db_connected:
            self._disconnect_db()
        else:
            self._connect_db()

    def _connect_db(self):
        """Handles the "Connect to DB" button click."""
        
        self._update_status("Connecting to database...")

        try:
            self.conn = get_connection()
            self.db_connected = True
            self.connect_btn.config(text="Disconnect from DB", bg="#F44336")
            self.status_lbl.config(text="Connected", fg="green")
            self._update_status("Database connected.")
        except:
            self.status_lbl.config(text="Not connected", fg="red")
            root = tk.Tk()
            root.withdraw()  # hide the empty root window
            response = messagebox.askokcancel(
                "Database Connection Failed",
                "Could not connect to PostgreSQL.\n"
                "Check your .env settings and ensure PostgreSQL is running.\n"
            )
            root.destroy()
            self._update_status("Ready.")

    def _disconnect_db(self):
        """Handles DB disconnection logic."""
        close_connection(self.conn)
        self.db_connected = False
        self.connect_btn.config(text="Connect to DB", bg="#4CAF50")
        self.status_lbl.config(text="Not connected", fg="red")

    def _run_annotation(self): 
        """Orchestrates the full pipeline: validate → QEP → AQPs → annotate → display."""
        try:
            if not self.conn:
                messagebox.showwarning("Not Connected", "Please connect to the database first.")
                self._update_status("Ready.")
                return

            sql = self.query_input.get("1.0", "end").strip()
            if not validate_query(sql):
                messagebox.showwarning(
                    "Invalid Query",
                    "Please enter a valid query.",
                )
                self._update_status("Ready.")
                return

            self._show_loading_popup()

            self._update_status("Fetching QEP from PostgreSQL...")
            qep = get_qep(self.conn, sql)

            self._update_status("Fetching Alternative Query Plans (AQPs)...")
            aqps = get_all_aqps(self.conn, sql)

            self._update_status("Generating annotations...")
            result = generate_annotations(qep, aqps, sql)

            self._display_annotations(sql, result)
            self._populate_qep_tree(qep)
            qep_cost = get_root_cost(qep)
            self._last_chart_data = (qep_cost, aqps)
            self._draw_cost_chart(qep_cost, aqps)
            self._update_status("Done.")
            self._history.append({
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sql":       sql,
                "scans":     result.get("scans", []),
                "joins":     result.get("joins", []),
                "others":    result.get("others", []),
            })
        except Exception as e:
            messagebox.showerror("Annotation Failed", str(e))
            self._update_status("Ready.")
        finally:
            self._hide_loading_popup()

# =============================================================================
# SECTION 5: GENERAL UI STATE HELPERS
# =============================================================================

    def _clear_all(self):
        if hasattr(self, "query_input"):
            self.query_input.delete("1.0", "end")

        if hasattr(self, "annotation_output"):
            self.annotation_output.config(state="normal")
            self.annotation_output.delete("1.0", "end")
            self.annotation_output.config(state="disabled")

        if hasattr(self, "qep_canvas"):
            self.qep_canvas.delete("all")
            self.qep_canvas.configure(scrollregion=(0, 0, 0, 0))
            self._canvas_zoom = 1.0
            self._current_qep_plan = None

        self._update_status("Ready.")

    def _on_canvas_mousewheel(self, event):
        self.qep_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_shift_mousewheel(self, event):
        self.qep_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_drag_start(self, event):
        """Record the starting position when mouse button is pressed."""
        self.qep_canvas.scan_mark(event.x, event.y)

    def _on_canvas_drag_move(self, event):
        """Drag the canvas as the mouse moves."""
        self.qep_canvas.scan_dragto(event.x, event.y, gain=1)

    def _zoom_qep_in(self):
        self._zoom_qep_canvas(1.15)

    def _zoom_qep_out(self):
        self._zoom_qep_canvas(1 / 1.15)

    def _zoom_qep_canvas(self, factor: float):
        if not hasattr(self, "qep_canvas"):
            return
        if self._current_qep_plan is None:
            return

        new_zoom = self._canvas_zoom * factor
        if new_zoom < 0.15 or new_zoom > 3.0:
            return

        self._canvas_zoom = new_zoom
        # Redraw entire tree at new zoom level
        self._populate_qep_tree(self._current_qep_plan)
        self._update_status(f"QEP zoom: {int(self._canvas_zoom * 100)}%")

    def _show_loading_popup(self):
        if self._loading_popup and self._loading_popup.winfo_exists():
            return

        popup = tk.Toplevel(self.root)
        popup.title("Working...")
        popup.geometry("380x180")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        # Center over parent window.
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - 380) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - 180) // 2
        popup.geometry(f"380x180+{x}+{y}")

        container = tk.Frame(popup, padx=16, pady=14)
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            text="Please Wait",
            font=("Arial", 16, "bold"),
            fg="#1f2d3d",
        ).pack(pady=(18, 14))

        self._loading_bar = ttk.Progressbar(container, mode="indeterminate", length=240)
        self._loading_bar.pack(pady=(0, 8))
        self._loading_bar.start(10)

        popup.protocol("WM_DELETE_WINDOW", lambda: None)
        self._loading_popup = popup
        popup.update_idletasks()

    def _hide_loading_popup(self):
        if self._loading_bar:
            self._loading_bar.stop()
        if self._loading_popup and self._loading_popup.winfo_exists():
            self._loading_popup.grab_release()
            self._loading_popup.destroy()
        self._loading_popup = None
        self._loading_bar = None


# =============================================================================
# SECTION 6: ANNOTATED OUTPUT RENDERING
# =============================================================================

    def _insert_highlighted_sql(self, widget, line: str):
        """Inserts one SQL line into `widget` with token-level syntax highlighting."""
        for m in _SQL_TOKEN_RE.finditer(line):
            kind = m.lastgroup
            text = m.group()

            if kind == 'string':
                tag = 'sql_str'
            elif kind == 'number':
                tag = 'sql_num'
            elif kind == 'operator':
                tag = 'sql_op'
            elif kind == 'word':
                lower = text.lower()
                if lower in _SQL_KEYWORDS:
                    tag = 'sql_kw'
                elif lower in _SQL_FUNCTIONS:
                    tag = 'sql_fn'
                else:
                    tag = 'sql_ident'
            elif kind in ('dot', 'punct'):
                tag = 'sql_punct'
            else:
                tag = 'sql_ws'

            widget.insert("end", text, tag)
        widget.insert("end", "\n")


    def _configure_tags(self, out):
        CONSOLAS = ("Consolas", 10)
        ARIAL9I  = ("Arial", 9, "italic")
        ARIAL9   = ("Arial", 9)
        ARIAL10B = ("Arial", 10, "bold")
        LM10 = dict(lmargin1=10, lmargin2=10)

        tags = {
            "section_header": dict(foreground="#FFFFFF", background="#3A3A5C",
                                font=("Arial", 10, "bold"), spacing1=6, spacing3=6,
                                lmargin1=0, lmargin2=0),
            "sql_kw":    dict(foreground="#0000CC", font=(*CONSOLAS, "bold"),
                            spacing1=1, spacing3=1, **LM10),
            "sql_fn":    dict(foreground="#7B2FBE", font=(*CONSOLAS, "bold"), **LM10),
            "sql_ident": dict(foreground="#1a1a1a", font=CONSOLAS, **LM10),
            "sql_str":   dict(foreground="#2E7D32", font=CONSOLAS, **LM10),
            "sql_num":   dict(foreground="#E65100", font=CONSOLAS, **LM10),
            "sql_op":    dict(foreground="#00838F", font=(*CONSOLAS, "bold"), **LM10),
            "sql_punct": dict(foreground="#555555", font=CONSOLAS, **LM10),
            "sql_ws":    dict(font=CONSOLAS, **LM10),
            "clause_note": dict(foreground="#8B4513", font=ARIAL9I,
                                spacing1=0, spacing3=4, lmargin1=24, lmargin2=30),
            "scan_header":  dict(foreground="#1a7a2e", font=ARIAL10B, spacing1=10, spacing3=4),
            "join_header":  dict(foreground="#b35900", font=ARIAL10B, spacing1=10, spacing3=4),
            "other_header": dict(foreground="#4a4aaa", font=ARIAL10B, spacing1=10, spacing3=4),
            "scan":  dict(foreground="#1a7a2e", font=ARIAL9, spacing1=2, spacing3=4,
                        lmargin1=14, lmargin2=22),
            "join":  dict(foreground="#b35900", font=ARIAL9, spacing1=2, spacing3=4,
                        lmargin1=14, lmargin2=22),
            "other": dict(foreground="#4a4aaa", font=ARIAL9, spacing1=2, spacing3=4,
                        lmargin1=14, lmargin2=22),
            "divider": dict(foreground="#CCCCCC", spacing1=4, spacing3=4),
        }
        for tag, cfg in tags.items():
            out.tag_config(tag, **cfg)


    def _insert_section(self, out, title, items, tag):
        if not items:
            return
        out.insert("end", "\n")
        out.insert("end", f"  {title}  \n", "section_header")
        out.insert("end", "\n")
        for item in items:
            out.insert("end", f"• {item}\n", tag)

    def _display_annotations(self, sql: str, annotation_result: dict):
        """Render annotated SQL and grouped operator notes in the output panel."""
        out = self.annotation_output
        out.config(state="normal")
        out.delete("1.0", "end")
        self._configure_tags(out)

        out.insert("end", "  Annotated SQL  \n", "section_header")
        out.insert("end", "\n")

        clause_map = annotation_result.get("clause_map", [])
        if clause_map:
            for sql_line, note in clause_map:
                if not sql_line.strip():
                    continue
                self._insert_highlighted_sql(out, sql_line)
                if note:
                    for part in note.split(" | "):
                        out.insert("end", f"    - {part.strip()}\n", "clause_note")
        else:
            out.insert("end", sql + "\n", "sql")

        self._insert_section(out, "Scan Operations",  annotation_result.get("scans",  []), "scan")
        self._insert_section(out, "Join Operations",  annotation_result.get("joins",  []), "join")
        self._insert_section(out, "Other Operations", annotation_result.get("others", []), "other")

        out.config(state="disabled")

# =============================================================================
# SECTION 7: QEP TREE VISUALISATION
# =============================================================================

    def _populate_qep_tree(self, plan: dict):
        """Entry point: clears canvas, computes layout, draws edges then nodes."""
        if not hasattr(self, "qep_canvas"):
            return

        self._current_qep_plan = plan  # Cache for zoom redraws
        self.qep_canvas.delete("all")
        root_node = plan.get("Plan", plan)

        nodes_pos, edges = self._layout_tree(root_node, self._canvas_zoom)

        # Draw edges first so nodes appear on top
        for (x1, y1, x2, y2) in edges:
            self.qep_canvas.create_line(
                x1, y1, x2, y2,
                fill="#999999", width=2, smooth=True
            )

        for (node, cx, cy) in nodes_pos:
            self._draw_canvas_node(node, cx, cy, self._canvas_zoom)

        # Fit scroll region to content
        self.qep_canvas.update_idletasks()
        bbox = self.qep_canvas.bbox("all")
        if bbox:
            pad = 20
            self.qep_canvas.configure(
                scrollregion=(
                    bbox[0] - pad, bbox[1] - pad,
                    bbox[2] + pad, bbox[3] + pad
                )
            )

    def _subtree_width(self, node: dict, zoom: float) -> float:
        """Returns the pixel width required to lay out this node's full subtree."""
        children = node.get("Plans", [])
        node_w = NODE_W * zoom
        if not children:
            return node_w
        total = sum(self._subtree_width(c, zoom) for c in children)
        total += H_GAP * zoom * (len(children) - 1)
        return max(node_w, total)

    def _layout_tree(self, root_node: dict, zoom: float):
        """
        Two-pass top-down layout with zoom factor.
        Returns:
            nodes_pos : list of (node_dict, cx, cy)
            edges     : list of (x1, y1, x2, y2)
        """
        nodes_pos = []
        edges     = []
        
        node_h = NODE_H * zoom
        h_gap = H_GAP * zoom
        v_gap = V_GAP * zoom
        margin_x = MARGIN_X * zoom
        margin_y = MARGIN_Y * zoom

        def recurse(node, left_x, top_y):
            sw = self._subtree_width(node, zoom)
            cx = left_x + sw / 2
            cy = top_y + node_h / 2
            nodes_pos.append((node, cx, cy))

            children  = node.get("Plans", [])
            child_left = left_x
            for child in children:
                cw       = self._subtree_width(child, zoom)
                child_cx = child_left + cw / 2
                child_cy = top_y + node_h + v_gap + node_h / 2
                # parent bottom-centre -> child top-centre
                edges.append((cx, cy + node_h / 2, child_cx, child_cy - node_h / 2))
                recurse(child, child_left, top_y + node_h + v_gap)
                child_left += cw + h_gap

        recurse(root_node, margin_x, margin_y)
        return nodes_pos, edges

# =============================================================================
# SECTION 8: COST CHART VISUALISATION
# =============================================================================

    def _draw_cost_chart(self, qep_cost: float, aqps: dict):
        """Draws a horizontal bar chart of QEP vs AQP costs on self.cost_canvas."""
        c = self.cost_canvas
        c.delete("all")
        c.update_idletasks()
        W = c.winfo_width()  or 380
        H = c.winfo_height() or 300

        rows = [("qep", _CHART_PROPERTIES["qep"][1], qep_cost,
                _CHART_PROPERTIES["qep"][0])]
        for key, plan in aqps.items():
            cost  = get_root_cost(plan) if plan else float("inf")
            label = _CHART_PROPERTIES.get(key, key)[1]
            color = _CHART_PROPERTIES.get(key, "#888888")[0] \
                    if cost != float("inf") else "#CCCCCC"
            rows.append((key, label, cost, color))

        PAD_L, PAD_R = 130, 70
        PAD_T, PAD_B = 38, 28
        chart_w = W - PAD_L - PAD_R
        n       = len(rows)
        bar_h   = max(14, min(30, (H - PAD_T - PAD_B) // n - 8))
        row_h   = bar_h + 10

        finite  = [r[2] for r in rows if r[2] != float("inf")]
        max_val = max(finite) * 1.1 if finite else 1.0

        # Title
        c.create_text(W // 2, 14,
            text="QEP vs AQP  —  Total Cost",
            font=("Arial", 9, "bold"), fill="#1a1a2e")

        # Grid lines + x-axis labels
        NUM_GRID = 4
        for i in range(NUM_GRID + 1):
            gx  = PAD_L + int(chart_w * i / NUM_GRID)
            gy1 = PAD_T - 4
            gy2 = PAD_T + row_h * n + 4
            c.create_line(gx, gy1, gx, gy2, fill="#E0E0E0", dash=(3, 3))
            c.create_text(gx, gy2 + 10, text=f"{max_val * i / NUM_GRID:,.0f}",
                        font=("Arial", 7), fill="#AAAAAA", anchor="n")

        # Bars
        for idx, (key, label, cost, color) in enumerate(rows):
            yt  = PAD_T + idx * row_h
            ym  = yt + bar_h // 2
            fw  = "bold" if key == "qep" else "normal"

            # Row label
            c.create_text(PAD_L - 6, ym, text=label,
                        font=("Arial", 8, fw), fill="#222222", anchor="e")

            if cost == float("inf"):
                c.create_rectangle(PAD_L, yt + 2, PAD_L + 50, yt + bar_h - 2,
                                    fill="#E0E0E0", outline="")
                c.create_text(PAD_L + 56, ym,
                            text="N/A", font=("Arial", 7, "italic"),
                            fill="#AAAAAA", anchor="w")
            else:
                bar_w = max(4, int(chart_w * cost / max_val))
                # Bar body
                c.create_rectangle(PAD_L, yt + 2, PAD_L + bar_w, yt + bar_h - 2,
                                    fill=color, outline="")
                # Left accent stripe (darker)
                r, g, b = (int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
                dark = f"#{int(r*.65):02x}{int(g*.65):02x}{int(b*.65):02x}"
                c.create_rectangle(PAD_L, yt + 2, PAD_L + 4, yt + bar_h - 2,
                                    fill=dark, outline="")
                # Cost value label
                c.create_text(PAD_L + bar_w + 5, ym - 4,
                            text=f"{cost:,.1f}",
                            font=("Arial", 7, "bold" if key == "qep" else "normal"),
                            fill="#333333", anchor="w")
                # Ratio label (for AQPs only)
                if key != "qep" and qep_cost > 0 and cost != float("inf"):
                    ratio = cost / qep_cost
                    rtxt  = f"+{(ratio-1)*100:.0f}%" if ratio >= 1 else f"-{(1-ratio)*100:.0f}%"
                    rcol  = "#CC0000" if ratio > 1.005 else "#28A745"
                    c.create_text(PAD_L + bar_w + 5, ym + 6,
                                text=rtxt, font=("Arial", 7, "italic"),
                                fill=rcol, anchor="w")

    def _draw_canvas_node(self, node: dict, cx: float, cy: float, zoom: float):
        """Draws a single rounded-rectangle node centred at (cx, cy) with zoom applied."""
        node_type  = node.get("Node Type", "Unknown")
        total_cost = node.get("Total Cost", "N/A")
        plan_rows  = node.get("Plan Rows",  "N/A")

        if "Scan" in node_type:
            scheme = NODE_COLORS["scan"]
        elif "Join" in node_type:
            scheme = NODE_COLORS["join"]
        else:
            scheme = NODE_COLORS["other"]

        node_w = NODE_W * zoom
        node_h = NODE_H * zoom
        x0 = cx - node_w / 2
        y0 = cy - node_h / 2
        x1 = cx + node_w / 2
        y1 = cy + node_h / 2
        r  = max(4, int(8 * zoom))  # corner radius scales with zoom

        # Rounded rectangle via smooth polygon
        self.qep_canvas.create_polygon(
            x0 + r, y0,
            x1 - r, y0,
            x1,     y0 + r,
            x1,     y1 - r,
            x1 - r, y1,
            x0 + r, y1,
            x0,     y1 - r,
            x0,     y0 + r,
            fill=scheme["fill"],
            outline=scheme["outline"],
            width=2,
            smooth=True
        )

        # Node type (bold, upper line) - scale font with zoom
        title_font_size = max(1, int(9 * zoom))
        self.qep_canvas.create_text(
            cx, cy - 9 * zoom,
            text=node_type,
            font=("Arial", title_font_size, "bold"),
            fill=scheme["text"],
            width=max(60, node_w - 10)
        )

        # Cost + rows (smaller, lower line) - scale font with zoom
        detail_font_size = max(1, int(7 * zoom))
        self.qep_canvas.create_text(
            cx, cy + 10 * zoom,
            text=f"cost: {total_cost}  rows: {plan_rows}",
            font=("Arial", detail_font_size),
            fill=scheme["text"],
            width=max(60, node_w - 10)
        )
        # Register all shapes of this node with the tooltip
        tip_text = NODE_TOOLTIPS.get(node_type, f"{node_type}: No description available.")
        tip_text += f"\n\nEstimated cost : {total_cost}"
        tip_text += f"\nEstimated rows : {plan_rows}"

        for item_id in self.qep_canvas.find_overlapping(x0, y0, x1, y1):
            self._canvas_tooltip.register(item_id, tip_text)

    def _update_status(self, message: str):
        """Updates the bottom status bar with a new message."""
        self.status_bar.config(text=message)
        self.root.update_idletasks()

    def _redraw_chart_on_resize(self):
        """Redraws the cost chart when the canvas is resized."""
        if self._last_chart_data:
            qep_cost, aqps = self._last_chart_data
            self._draw_cost_chart(qep_cost, aqps)

    def _copy_output_to_clipboard(self):
        text = self.annotation_output.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._update_status("Annotated output copied to clipboard.")

# =============================================================================
# SECTION 10: HISTORY WINDOW
# =============================================================================

    def _open_history_window(self):
        """Opens a popup window showing all past annotation runs."""
        win = tk.Toplevel(self.root)
        win.title("Annotation History")
        win.geometry("700x500")
        win.minsize(500, 350)
        win.grab_set()   # modal — blocks interaction with main window until closed

        # ── Top label ────────────────────────────────────────────────────────
        header = tk.Frame(win, bg="#3A3A5C", pady=6)
        header.pack(fill="x")
        tk.Label(header, text=f"Annotation History  ({len(self._history)} runs)",
                bg="#3A3A5C", fg="white",
                font=("Arial", 10, "bold")).pack(side="left", padx=12)

        if not self._history:
            tk.Label(win, text="No queries have been annotated yet.",
                    fg="#888888", font=("Arial", 10, "italic")).pack(
                        expand=True)
            return

        # ── Left: scrollable list of runs ────────────────────────────────────
        pane = tk.PanedWindow(win, orient="horizontal", sashwidth=4,
                            sashrelief="flat", bg="#CCCCCC")
        pane.pack(fill="both", expand=True, padx=0, pady=0)

        list_frame = tk.Frame(pane, bg="#F5F5F5")
        pane.add(list_frame, width=220)

        tk.Label(list_frame, text="Runs", bg="#F5F5F5",
                font=("Arial", 9, "bold"), fg="#555555",
                pady=4).pack(fill="x", padx=8)

        list_canvas = tk.Canvas(list_frame, bg="#F5F5F5",
                                highlightthickness=0)
        list_scroll = ttk.Scrollbar(list_frame, orient="vertical",
                                    command=list_canvas.yview)
        list_canvas.configure(yscrollcommand=list_scroll.set)
        list_scroll.pack(side="right", fill="y")
        list_canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(list_canvas, bg="#F5F5F5")
        list_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                lambda e: list_canvas.configure(
                    scrollregion=list_canvas.bbox("all")))

        # ── Right: detail panel ───────────────────────────────────────────────
        detail_frame = tk.Frame(pane, bg="white")
        pane.add(detail_frame)

        detail_text = scrolledtext.ScrolledText(
            detail_frame, wrap="word", state="disabled",
            font=("Arial", 9), bg="white", relief="flat",
            padx=10, pady=8
        )
        detail_text.pack(fill="both", expand=True)

        # Tags for detail panel
        detail_text.tag_config("ts",
            foreground="#888888", font=("Arial", 8, "italic"))
        detail_text.tag_config("sql_block",
            foreground="#1a1aff", font=("Consolas", 9),
            lmargin1=10, lmargin2=10, spacing3=2)
        detail_text.tag_config("sec",
            foreground="white", background="#3A3A5C",
            font=("Arial", 9, "bold"),
            spacing1=6, spacing3=4)
        detail_text.tag_config("scan", foreground="#1a7a2e",
            font=("Arial", 9), lmargin1=12, lmargin2=20, spacing3=3)
        detail_text.tag_config("join", foreground="#b35900",
            font=("Arial", 9), lmargin1=12, lmargin2=20, spacing3=3)
        detail_text.tag_config("other", foreground="#4a4aaa",
            font=("Arial", 9), lmargin1=12, lmargin2=20, spacing3=3)

        selected_btn = [None]   # mutable ref for currently highlighted button

        def show_entry(idx):
            """Populate the right panel with history entry [idx]."""
            entry = self._history[idx]

            # Highlight selected run button
            if selected_btn[0]:
                selected_btn[0].config(bg="#F5F5F5", fg="#222222")
            selected_btn[0] = run_buttons[idx]
            run_buttons[idx].config(bg="#3A3A5C", fg="white")

            detail_text.config(state="normal")
            detail_text.delete("1.0", "end")

            # Timestamp
            detail_text.insert("end",
                f"Run {idx + 1}  —  {entry['timestamp']}\n", "ts")
            detail_text.insert("end", "\n")

            # SQL block
            detail_text.insert("end", "  SQL Query  \n", "sec")
            detail_text.insert("end", "\n")
            detail_text.insert("end",
                entry["sql"].strip() + "\n", "sql_block")

            # Scans
            if entry["scans"]:
                detail_text.insert("end", "\n")
                detail_text.insert("end", "  Scan Operations  \n", "sec")
                detail_text.insert("end", "\n")
                for s in entry["scans"]:
                    detail_text.insert("end", f"• {s}\n", "scan")

            # Joins
            if entry["joins"]:
                detail_text.insert("end", "\n")
                detail_text.insert("end", "  Join Operations  \n", "sec")
                detail_text.insert("end", "\n")
                for j in entry["joins"]:
                    detail_text.insert("end", f"• {j}\n", "join")

            # Others
            if entry["others"]:
                detail_text.insert("end", "\n")
                detail_text.insert("end", "  Other Operations  \n", "sec")
                detail_text.insert("end", "\n")
                for o in entry["others"]:
                    detail_text.insert("end", f"• {o}\n", "other")

            detail_text.config(state="disabled")

        def restore_entry(idx):
            """Load the SQL of this history entry back into the query input."""
            sql = self._history[idx]["sql"]
            self.query_input.delete("1.0", "end")
            self.query_input.insert("1.0", sql)
            win.destroy()
            self._update_status(f"Restored query from history run {idx + 1}.")

        # ── Build run buttons in list panel ──────────────────────────────────
        run_buttons = []
        for i, entry in enumerate(reversed(self._history)):
            real_idx = len(self._history) - 1 - i   # newest first
            sql_preview = entry["sql"].strip()
            sql_preview = (sql_preview[:38] + "...") \
                        if len(sql_preview) > 38 else sql_preview

            btn_frame = tk.Frame(inner, bg="#F5F5F5")
            btn_frame.pack(fill="x", padx=4, pady=2)

            run_btn = tk.Button(
                btn_frame,
                text=f"#{real_idx + 1}  {sql_preview}",
                anchor="w",
                wraplength=180,
                justify="left",
                bg="#F5F5F5", fg="#222222",
                font=("Arial", 8),
                relief="flat", pady=4, padx=6,
                cursor="hand2",
                command=lambda idx=real_idx: show_entry(idx)
            )
            run_btn.pack(side="left", fill="x", expand=True)

            # Small "restore" button
            restore_btn = tk.Button(
                btn_frame, text="<<",
                bg="#F5F5F5", fg="#2E86DE",
                font=("Arial", 7), relief="flat",
                cursor="hand2", padx=2,
                command=lambda idx=real_idx: restore_entry(idx)
            )
            restore_btn.pack(side="right")

            run_buttons.insert(0, run_btn)   # keep index aligned

        # ── Footer: clear history button ─────────────────────────────────────
        footer = tk.Frame(win, bg="#F0F0F0", pady=4)
        footer.pack(fill="x", side="bottom")
        tk.Button(
            footer, text="Clear All History",
            command=lambda: [self._history.clear(), win.destroy()],
            bg="#E74C3C", fg="white",
            font=("Arial", 8), relief="flat",
            padx=8, pady=4, cursor="hand2"
        ).pack(side="right", padx=10)
        tk.Button(
            footer, text="Close",
            command=win.destroy,
            bg="#6C757D", fg="white",
            font=("Arial", 8), relief="flat",
            padx=8, pady=4, cursor="hand2"
        ).pack(side="right", padx=(0, 4))

        # Auto-select the most recent entry
        if self._history:
            show_entry(len(self._history) - 1)
