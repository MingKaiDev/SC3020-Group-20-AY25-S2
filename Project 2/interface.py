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
        Builds the RIGHT panel: QEP tree visualisation.

        Contains:
            - Label: "Query Execution Plan"
            - ttk.Treeview widget showing plan nodes as a collapsible tree
            - Each tree node shows: Node Type + Total Cost
            - Optional: colour nodes differently by type
              (scan = green, join = orange, other = grey) 

        Args:
            parent: The PanedWindow to attach this panel to.

        Returns:
            tk.LabelFrame: The completed right panel frame.

        TODO:
            - Create a tk.LabelFrame with text="Query Execution Plan (QEP)"
            - Add self.qep_tree = ttk.Treeview(...)
            - Set self.qep_tree.heading("#0", text="Plan Nodes")
            - Add a vertical scrollbar linked to the Treeview
            - Leave population to _populate_qep_tree()
        """
        frame = tk.LabelFrame(parent, text="Query Execution Plan (QEP)")

        self.qep_tree = ttk.Treeview(frame)
        self.qep_tree.heading("#0", text="Plan Nodes")
        self.qep_tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        self.qep_tree.tag_configure("scan", foreground="green")
        self.qep_tree.tag_configure("join", foreground="darkorange")
        self.qep_tree.tag_configure("other", foreground="grey")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.qep_tree.yview)
        scrollbar.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.qep_tree.configure(yscrollcommand=scrollbar.set)

        return frame

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
        """
        Clears all three panels and resets the status bar.

        TODO:
            - Clear self.query_input (delete "1.0", "end")
            - Clear self.annotation_output (enable → delete → disable)
            - Clear self.qep_tree (delete all children)
            - Reset self.status_bar to "Ready."
        """
        if hasattr(self, "query_input"):
            self.query_input.delete("1.0", "end")

        if hasattr(self, "annotation_output"):
            self.annotation_output.config(state="normal")
            self.annotation_output.delete("1.0", "end")
            self.annotation_output.config(state="disabled")

        if hasattr(self, "qep_tree"):
            self.qep_tree.delete(*self.qep_tree.get_children())

        self._update_status("Ready.")
    


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

    def _populate_qep_tree(self, plan: dict):
        """
        Recursively populates the QEP Treeview widget with plan nodes.

        Args:
            plan (dict): The full QEP plan dict (output of get_qep).

        TODO:
            - Clear existing tree nodes: self.qep_tree.delete(*self.qep_tree.get_children())
            - Call the recursive helper _insert_tree_node("", plan.get("Plan", plan))
        """
        if not hasattr(self, "qep_tree"):
            return

        self.qep_tree.delete(*self.qep_tree.get_children())
        self._insert_tree_node("", plan.get("Plan", plan))

    def _insert_tree_node(self, parent_id: str, node: dict):
        """
        Recursive helper to insert a single plan node and its children
        into the QEP Treeview.

        Args:
            parent_id (str): Treeview item ID of the parent node ("" for root).
            node (dict): A single plan node dict.

        TODO:
            - Build label string:
              "<Node Type>  |  cost: <Total Cost>  |  rows: <Plan Rows>"
            - Insert into tree:
              item_id = self.qep_tree.insert(parent_id, "end", text=label, open=True)
            - Recurse for each child in node.get("Plans", []):
              self._insert_tree_node(item_id, child)
        """
        node_type = node.get("Node Type", "Unknown")
        total_cost = node.get("Total Cost", "N/A")
        plan_rows = node.get("Plan Rows", "N/A")

        label = f"{node_type}  |  cost: {total_cost}  |  rows: {plan_rows}"

        if "Scan" in node_type:
            tag = "scan"
        elif "Join" in node_type:
            tag = "join"
        else:
            tag = "other"

        item_id = self.qep_tree.insert(parent_id, "end", text=label, open=True, tags=(tag,))

        for child in node.get("Plans", []):
            self._insert_tree_node(item_id, child)

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
