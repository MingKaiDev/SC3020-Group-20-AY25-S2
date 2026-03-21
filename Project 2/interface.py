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
        pass


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
        pass

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
        pass

    def _build_left_panel(self, parent) -> tk.Frame:
        """
        Builds the LEFT panel: SQL query input area.

        Contains:
            - Label: "SQL Query Input"
            - ScrolledText box for typing/pasting SQL
            - "▶ Annotate Query" button → calls _run_annotation()
            - Optional: dropdown to select dataset (TPC-H / IMDB)

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
              (values=["TPC-H", "IMDB"])
        """
        pass

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
        pass

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
        pass

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
        pass


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
        pass

    def _run_annotation(self):
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
        qep    = get_dummy_qep()
        aqps   = get_dummy_aqps()
        result = generate_annotations(qep, aqps)
        self._display_annotations(DUMMY_SQL, result)
        self._populate_qep_tree(qep)
        pass

    def _clear_all(self):
        """
        Clears all three panels and resets the status bar.

        TODO:
            - Clear self.query_input (delete "1.0", "end")
            - Clear self.annotation_output (enable → delete → disable)
            - Clear self.qep_tree (delete all children)
            - Reset self.status_bar to "Ready."
        """
        pass


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
        pass

    def _populate_qep_tree(self, plan: dict):
        """
        Recursively populates the QEP Treeview widget with plan nodes.

        Args:
            plan (dict): The full QEP plan dict (output of get_qep).

        TODO:
            - Clear existing tree nodes: self.qep_tree.delete(*self.qep_tree.get_children())
            - Call the recursive helper _insert_tree_node("", plan.get("Plan", plan))
        """
        pass

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
        pass

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
        pass
