# interface.py
# Responsibilities:
#   - Provide a user-friendly GUI for the SQL Query Annotator
#   - Allow user to connect to the PostgreSQL database
#   - Accept SQL query input (typed or pasted)
#   - Trigger annotation pipeline (preprocessing → annotation)
#   - Display annotated query output in a readable format
#   - Visualize the QEP as a tree structure
#   - Handle and display errors gracefully to the user

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
from preprocessing import get_connection, close_connection, get_qep, get_all_aqps, validate_query
from annotation import generate_annotations

# In _run_annotation() during development, replace pipeline with:
from dummy_data import get_dummy_qep, get_dummy_aqps, DUMMY_SQL

# =============================================================================
# SECTION 0: VISUAL TREE CONSTANTS
# =============================================================================

NODE_W   = 160   # width of each node rectangle
NODE_H   = 50    # height of each node rectangle
H_GAP    = 40    # horizontal gap between sibling subtrees
V_GAP    = 80    # vertical gap between tree levels
MARGIN_X = 20    # left/top canvas margin
MARGIN_Y = 20

NODE_COLORS = {
    "scan":  {"fill": "#D4EDDA", "outline": "#28A745", "text": "#155724"},
    "join":  {"fill": "#FFF3CD", "outline": "#FFC107", "text": "#856404"},
    "other": {"fill": "#D6E4F7", "outline": "#5B9BD5", "text": "#1a3a5c"},
}


# =============================================================================
# SECTION 1: MAIN APPLICATION CLASS
# =============================================================================

class TpcHAnnotatorApp:
    """
    Main GUI application class for the SC3020 Project 2 SQL Annotator.
    Built using Python's built-in Tkinter library.

    Layout (3-panel horizontal) (Tentative):
    ┌─────────────────┬──────────────────────┬─────────────────┐
    │   SQL Input     │  Annotated Output    │   QEP Tree      │
    │   (Left Panel)  │  (Middle Panel)      │  (Right Panel)  │
    └─────────────────┴──────────────────────┴─────────────────┘

    TODO:
        - Call self._build_top_bar() in __init__
        - Call self._build_panels() in __init__
        - Call self._build_status_bar() in __init__
        - Initialise self.conn = None in __init__
    """

    def __init__(self, root: tk.Tk):
        """
        Initialises the application window and builds all UI components.

        Args:
            root (tk.Tk): The root Tkinter window passed from project.py.

        TODO:
            - Set window title: "SC3020 Project 2 — SQL Query Annotator"
            - Set window size: root.geometry("1200x800")
            - Set minimum size: root.minsize(900, 600)
            - Initialise self.conn = None
            - Call _build_top_bar(), _build_panels(), _build_status_bar()
        """
        self.root = root
        self.conn = None
        self._build_top_bar()
        self._build_panels()
        self._build_status_bar()


# =============================================================================
# SECTION 2: UI BUILDER METHODS
# =============================================================================

    def _build_top_bar(self):
        """
        Builds the top control bar containing:
            - "Connect to DB" button       → calls _connect_db()
            - Connection status label      → shows "Connected ✓" or "Not connected"
            - "Clear All" button           → calls _clear_all()
            - Optional: DB name label      → shows which DB is connected

        TODO:
            - Create a tk.Frame at the top of self.root
            - Add a "Connect to DB" button (green background)
            - Add self.status_lbl (tk.Label) — default text "● Not connected", red
            - Add a "Clear All" button (grey background) → calls _clear_all()
            - Pack frame with fill="x", padx=10, pady=5
        """
        top_bar = tk.Frame(self.root)
        top_bar.pack(fill="x", padx=10, pady=5)

        connect_btn = tk.Button(
            top_bar,
            text="Connect to DB",
            command= self._connect_db,
            bg="#4CAF50",
            fg="white"
        )
        connect_btn.pack(side="left")

        self.status_lbl = tk.Label(
            top_bar,
            text= "Not conected", #success state handled in _connect_db()
            fg="red"
        )
        self.status_lbl.pack(side="left", padx=10)

        clear_btn= tk.Button(
            top_bar,
            text= "Clear All",
            command= self._clear_all,
            bg="#E0E0E0"
        )
        clear_btn.pack(side="right")

    def _build_panels(self):
        """
        Builds the main 3-panel layout using a PanedWindow (resizable panels).

        Panels:
            Left   → SQL query input + Annotate button  (_build_left_panel)
            Middle → Annotated output display           (_build_middle_panel)
            Right  → QEP tree visualisation             (_build_right_panel)

        TODO:
            - Create a tk.PanedWindow with orient="horizontal"
            - Pack it to fill remaining space (fill="both", expand=True)
            - Call _build_left_panel(), _build_middle_panel(), _build_right_panel()
            - Add each returned frame to the PanedWindow with .add()
            - Set sensible default widths (e.g. 350, 450, 350)
        """
        paned = tk.PanedWindow(self.root, orient="horizontal", sashrelief="raised")
        paned.pack(fill="both", expand=True, padx=10, pady=(0,10))

        left_panel = self._build_left_panel(paned)
        middle_panel = self._build_middle_panel(paned)
        right_panel = self._build_right_panel(paned)

        paned.add(left_panel, width=350)
        paned.add(middle_panel, width=450)
        paned.add(right_panel, width=350)

    def _build_left_panel(self, parent) -> tk.Frame:
        """
        Builds the LEFT panel: SQL query input area.

        Contains:
            - Label: "SQL Query Input"
            - ScrolledText box for typing/pasting SQL
            - "▶ Annotate Query" button → calls _run_annotation()
            - Optional: dropdown to select dataset (TPC-H / IMDB) #note not implemented

        Args:
            parent: The PanedWindow to attach this panel to.

        Returns:
            tk.LabelFrame: The completed left panel frame.

        TODO:
            - Create a tk.LabelFrame with text="SQL Query Input"
            - Add self.query_input = scrolledtext.ScrolledText(...)
            - Add "▶ Annotate Query" button (blue background, bold font)
              that calls _run_annotation()
            - Optionally add a ttk.Combobox for dataset selection
              (values=["TPC-H", "IMDB"]) #not implemented

        """
        frame = tk.LabelFrame(parent, text="SQL Query Input")

        lbl = tk.Label(frame, text="Enter SQL query:")
        lbl.pack(anchor="w", padx=8, pady=(8, 4))

        self.query_input = scrolledtext.ScrolledText(frame, wrap="word", height=15)
        self.query_input.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        annotate_btn = tk.Button(
            frame,
            text="▶ Annotate Query",
            command=self._run_annotation,
            bg="#2E86DE",
            fg="white",
            font=("Arial", 10, "bold"),
        )
        annotate_btn.pack(fill="x", padx=8, pady=(0, 8))

        return frame

    def _build_middle_panel(self, parent) -> tk.Frame:
        """
        Builds the MIDDLE panel: Annotated query output display.

        Contains:
            - Label: "Annotated Output"
            - ScrolledText box (read-only) showing annotated SQL
            - Color-coded text tags:
                * SQL lines    → blue / dark
                * Scan notes   → green
                * Join notes   → orange
                * Other notes  → grey
            - Optional: "Copy to Clipboard" button

        Args:
            parent: The PanedWindow to attach this panel to.

        Returns:
            tk.LabelFrame: The completed middle panel frame.

        TODO:
            - Create a tk.LabelFrame with text="Annotated Output"
            - Add self.annotation_output = scrolledtext.ScrolledText(...)
            - Set state="disabled" so user cannot type in it
              (enable briefly when inserting text, then disable again)
            - Configure text tags for color coding:
                self.annotation_output.tag_config("sql",   foreground="navy")
                self.annotation_output.tag_config("scan",  foreground="green")
                self.annotation_output.tag_config("join",  foreground="darkorange")
                self.annotation_output.tag_config("other", foreground="grey")
                self.annotation_output.tag_config("header",foreground="black",
                                                  font=("Arial", 10, "bold"))
            - Optionally add a "Copy to Clipboard" button
        """
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
        """
        RIGHT panel: QEP visual canvas tree.
        Nodes are colour-coded rectangles connected by lines:
          - Scan  -> green
          - Join  -> amber
          - Other -> steel blue
        """
        
        frame = tk.LabelFrame(parent, text="Query Execution Plan (QEP)")

        # --- Colour legend ---
        legend_bar = tk.Frame(frame, bg="#F0F0F0", relief="flat", bd=1)
        legend_bar.pack(fill="x", padx=8, pady=(6, 0))

        for label, color in [("Scan", "#28A745"), ("Join", "#FFC107"), ("Other", "#5B9BD5")]:
            box = tk.Frame(legend_bar, bg=color, width=12, height=12)
            box.pack(side="left", padx=(6, 2), pady=4)
            tk.Label(legend_bar, text=label, bg="#F0F0F0", font=("Arial", 8)).pack(
                side="left", padx=(0, 8)
            )

        # --- Canvas + scrollbars ---
        canvas_frame = tk.Frame(frame)
        canvas_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self.qep_canvas = tk.Canvas(canvas_frame, bg="#EEF2F7", highlightthickness=0)

        v_scroll = ttk.Scrollbar(canvas_frame, orient="vertical",   command=self.qep_canvas.yview)
        h_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.qep_canvas.xview)

        self.qep_canvas.configure(
            yscrollcommand=v_scroll.set,
            xscrollcommand=h_scroll.set
        )

        h_scroll.pack(side="bottom", fill="x")
        v_scroll.pack(side="right",  fill="y")
        self.qep_canvas.pack(side="left", fill="both", expand=True)

        #Set cursor to be fleur
        self.qep_canvas.config(cursor="fleur")

        # Mouse-wheel scrolling
        self.qep_canvas.bind("<MouseWheel>",       self._on_canvas_mousewheel)
        self.qep_canvas.bind("<Shift-MouseWheel>", self._on_canvas_shift_mousewheel)
        self.qep_canvas.bind("<ButtonPress-1>",    self._on_canvas_drag_start)
        self.qep_canvas.bind("<B1-Motion>",        self._on_canvas_drag_move)

        return frame

    def _build_status_bar(self):
        self.status_bar = tk.Label(
            self.root,
            text="Ready.",
            relief="sunken",
            anchor="w",
            padx=5
        )
        self.status_bar.pack(side="bottom", fill="x")

    def _build_status_bar(self):
        """
        Builds a slim status bar at the very bottom of the window.
        Shows real-time status messages (e.g. "Fetching QEP...", "Done.").

        TODO:
            - Create a tk.Label anchored to the bottom (side="bottom", fill="x")
            - Set relief="sunken", anchor="w", padx=5
            - Store as self.status_bar
            - Default text: "Ready."
        """
        self.status_bar = tk.Label(
            self.root,
            text="Ready.",
            relief="sunken",
            anchor="w",
            padx=5
        )
        self.status_bar.pack(side="bottom", fill="x")


# =============================================================================
# SECTION 3: EVENT HANDLERS
# =============================================================================

    def _connect_db(self):
        """
        Handles the "Connect to DB" button click.
        Establishes a database connection and updates the status label.

        TODO:
            - Call get_connection() from preprocessing.py
            - Store result in self.conn
            - On success: update self.status_lbl text to "● Connected ✓", fg="green"
            - On failure: show messagebox.showerror() with the exception message
                          keep self.status_lbl as "● Not connected", fg="red"
        """
        
        #note editted mk's original method
        self._update_status("Connecting to database...")
        self.conn = get_connection()

        if self.conn:
            self.status_lbl.config(text="● Connected ✓", fg="green")
            self._update_status("Database connected.")
        else:
            self.status_lbl.config(text="● Not connected", fg="red")
            root = tk.Tk()
            root.withdraw()  # hide the empty root window
            response = messagebox.askokcancel(
                "Database Connection Failed",
                "Could not connect to PostgreSQL.\n"
                "Check your .env settings and ensure PostgreSQL is running.\n"
            )
            root.destroy()
            self._update_status("Ready.")

        #zl method
        # try:
        #     self._update_status("Connecting to database...")
        #     self.conn = get_connection()
        #     self.status_lbl.config(text = "● Connected ✓", fg = "green")
        #     self._update_status("Database connected.")
        # except Exception as e:
        #     self.conn = None
        #     self.status_lbl.config(text="● Not connected", fg = "red")
        #     messagebox.showerror("Database Connection Failed", str(e))
        #     self._update_status("Ready.")

        # Dev mode
        # self.conn = "DEV_MODE"
        # self.status_lbl.config(text="Connected (dev)", fg="green")
        # self._update_status("Dev mode: DB skipped.")

    def _run_annotation(self): #note done. Implemented the actual follow without dummy data
        """
        Handles the "▶ Annotate Query" button click.
        Orchestrates the full pipeline: validate → QEP → AQPs → annotate → display.

        TODO:
            - Check self.conn is not None, else warn user to connect first
            - Get SQL from self.query_input.get("1.0", "end").strip()
            - Call validate_query(sql) — show warning if invalid
            - Update status bar: "Fetching QEP from PostgreSQL..."
            - Call get_qep(self.conn, sql)
            - Update status bar: "Fetching Alternative Query Plans (AQPs)..."
            - Call get_all_aqps(self.conn, sql)
            - Update status bar: "Generating annotations..."
            - Call generate_annotations(qep, aqps)
            - Call _display_annotations(sql, result)
            - Call _populate_qep_tree(qep)
            - Update status bar: "Done."
            - On any exception: show messagebox.showerror(), reset status bar
        """
        # Dummydata
        # qep = get_dummy_qep()
        # aqps = get_dummy_aqps()
        # result = generate_annotations(qep, aqps)
        # self._display_annotations(DUMMY_SQL, result)
        # self._populate_qep_tree(qep)
        # self._update_status("Done.")
        # return

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

            self._update_status("Fetching QEP from PostgreSQL...")
            qep = get_qep(self.conn, sql)

            self._update_status("Fetching Alternative Query Plans (AQPs)...")
            aqps = get_all_aqps(self.conn, sql)

            self._update_status("Generating annotations...")
            result = generate_annotations(qep, aqps)

            self._display_annotations(sql, result)
            self._populate_qep_tree(qep)
            self._update_status("Done.")
        except Exception as e:
            messagebox.showerror("Annotation Failed", str(e))
            self._update_status("Ready.")

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


# =============================================================================
# SECTION 4: DISPLAY HELPERS
# =============================================================================

    def _display_annotations(self, sql: str, annotation_result: dict):
        """
        Writes the annotated output to the middle panel with color-coded tags.

        Args:
            sql (str): The original SQL query string.
            annotation_result (dict): Output of generate_annotations()
                                      Keys: "scans", "joins", "others", "full_text"

        TODO:
            - Enable self.annotation_output (config state="normal")
            - Clear existing content
            - Insert original SQL with "sql" tag
            - Insert "--- Scan Operations ---" header with "header" tag
            - Insert each item from annotation_result["scans"] with "scan" tag
            - Insert "--- Join Operations ---" header with "header" tag
            - Insert each item from annotation_result["joins"] with "join" tag
            - Insert "--- Other Operations ---" header with "header" tag
            - Insert each item from annotation_result["others"] with "other" tag
            - Disable self.annotation_output again (config state="disabled")
        """

        self.annotation_output.config(state="normal")
        self.annotation_output.delete("1.0", "end")

        self.annotation_output.insert("end", "Original SQL Query\n", "header")
        self.annotation_output.insert("end", f"{sql}\n\n", "sql")

        self.annotation_output.insert("end", "--- Scan Operations ---\n", "header")
        for item in annotation_result.get("scans", []):
            self.annotation_output.insert("end", f"- {item}\n", "scan")
        self.annotation_output.insert("end", "\n")

        self.annotation_output.insert("end", "--- Join Operations ---\n", "header")
        for item in annotation_result.get("joins", []):
            self.annotation_output.insert("end", f"- {item}\n", "join")
        self.annotation_output.insert("end", "\n")

        self.annotation_output.insert("end", "--- Other Operations ---\n", "header")
        for item in annotation_result.get("others", []):
            self.annotation_output.insert("end", f"- {item}\n", "other")

        self.annotation_output.config(state="disabled")

    # ------------------------------------------------------------------
    # QEP Visual Tree (Canvas-based)
    # ------------------------------------------------------------------

    def _populate_qep_tree(self, plan: dict):
        """Entry point: clears canvas, computes layout, draws edges then nodes."""
        if not hasattr(self, "qep_canvas"):
            return

        self.qep_canvas.delete("all")
        root_node = plan.get("Plan", plan)

        nodes_pos, edges = self._layout_tree(root_node)

        # Draw edges first so nodes appear on top
        for (x1, y1, x2, y2) in edges:
            self.qep_canvas.create_line(
                x1, y1, x2, y2,
                fill="#999999", width=2, smooth=True
            )

        for (node, cx, cy) in nodes_pos:
            self._draw_canvas_node(node, cx, cy)

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

    def _subtree_width(self, node: dict) -> float:
        """Returns the pixel width required to lay out this node's full subtree."""
        children = node.get("Plans", [])
        if not children:
            return NODE_W
        total = sum(self._subtree_width(c) for c in children)
        total += H_GAP * (len(children) - 1)
        return max(NODE_W, total)

    def _layout_tree(self, root_node: dict):
        """
        Two-pass top-down layout.
        Returns:
            nodes_pos : list of (node_dict, cx, cy)
            edges     : list of (x1, y1, x2, y2)
        """
        nodes_pos = []
        edges     = []

        def recurse(node, left_x, top_y):
            sw = self._subtree_width(node)
            cx = left_x + sw / 2
            cy = top_y + NODE_H / 2
            nodes_pos.append((node, cx, cy))

            children  = node.get("Plans", [])
            child_left = left_x
            for child in children:
                cw       = self._subtree_width(child)
                child_cx = child_left + cw / 2
                child_cy = top_y + NODE_H + V_GAP + NODE_H / 2
                # parent bottom-centre -> child top-centre
                edges.append((cx, cy + NODE_H / 2, child_cx, child_cy - NODE_H / 2))
                recurse(child, child_left, top_y + NODE_H + V_GAP)
                child_left += cw + H_GAP

        recurse(root_node, MARGIN_X, MARGIN_Y)
        return nodes_pos, edges

    def _draw_canvas_node(self, node: dict, cx: float, cy: float):
        """Draws a single rounded-rectangle node centred at (cx, cy)."""
        node_type  = node.get("Node Type", "Unknown")
        total_cost = node.get("Total Cost", "N/A")
        plan_rows  = node.get("Plan Rows",  "N/A")

        if "Scan" in node_type:
            scheme = NODE_COLORS["scan"]
        elif "Join" in node_type:
            scheme = NODE_COLORS["join"]
        else:
            scheme = NODE_COLORS["other"]

        x0 = cx - NODE_W / 2
        y0 = cy - NODE_H / 2
        x1 = cx + NODE_W / 2
        y1 = cy + NODE_H / 2
        r  = 8  # corner radius

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

        # Node type (bold, upper line)
        self.qep_canvas.create_text(
            cx, cy - 9,
            text=node_type,
            font=("Arial", 9, "bold"),
            fill=scheme["text"],
            width=NODE_W - 10
        )

        # Cost + rows (smaller, lower line)
        self.qep_canvas.create_text(
            cx, cy + 10,
            text=f"cost: {total_cost}  rows: {plan_rows}",
            font=("Arial", 7),
            fill=scheme["text"],
            width=NODE_W - 10
        )

    def _update_status(self, message: str):
        """
        Updates the bottom status bar with a new message.

        Args:
            message (str): Status message to display.

        TODO:
            - self.status_bar.config(text=message)
            - Call self.root.update_idletasks() to force immediate UI refresh
              (important so status updates show during long operations)
        """
        self.status_bar.config(text=message)
        self.root.update_idletasks()

    def _copy_output_to_clipboard(self):
        text = self.annotation_output.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._update_status("Annotated output copied to clipboard.")
