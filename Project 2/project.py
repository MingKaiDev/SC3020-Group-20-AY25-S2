# project.py
# Responsibilities:
#   - Serve as the single entry point to launch the application
#   - Initialise the Tkinter root window with correct settings
#   - Verify database connectivity before launching the GUI
#   - Instantiate the TpcHAnnotatorApp from interface.py
#   - Handle any top-level exceptions gracefully
#   - Start the Tkinter main event loop

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import sys
from interface import TpcHAnnotatorApp
from preprocessing import get_connection, close_connection

from dummy_data import DummyConnection

# =============================================================================
# SECTION 1: WINDOW CONFIGURATION
# =============================================================================

def configure_window(root: tk.Tk):
    """
    Applies global window settings to the root Tkinter window.

    Args:
        root (tk.Tk): The root Tkinter window.
    """
    root.title("SC3020 Project 2 — SQL Query Annotator")
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = (screen_w // 2) - (1600 // 2)
    y = (screen_h // 2) - (900 // 2)
    root.geometry(f"1600x900+{x}+{y}")
    root.minsize(900, 600)
    return root



# =============================================================================
# SECTION 2: PRE-LAUNCH CHECKS
# =============================================================================

def check_db_connection() -> bool:
    """
    Attempts a test connection to PostgreSQL before launching the GUI.
    Warns the user early if the database is unreachable.

    Returns:
        bool: True if connection succeeded, False otherwise.
    """
    try:
        conn = get_connection()
        close_connection(conn)
        return True
    except Exception:
        root = tk.Tk()
        root.withdraw()  # hide the empty root window
        response = messagebox.askokcancel(
            "Database Connection Failed",
            "Could not connect to PostgreSQL.\n"
            "Check your .env settings and ensure PostgreSQL is running.\n\n"
            "Launch anyway? (DB connect available inside the app)"
        )
        root.destroy()
        return response


def check_dependencies() -> bool:
    """
    Verifies that all required third-party Python packages are installed.
    Exits with a clear error message if any are missing.

    Returns:
        bool: True if all dependencies are present.
    """

    required = [
        ("psycopg", "psycopg"),
        ("dotenv", "python-dotenv"),
    ]

    for module, install_name in required:
        try:
            if module == "dotenv":
                from dotenv import load_dotenv
            else:
                __import__(module)
        except ImportError:
            msg = f"Missing dependency: {install_name}. Run: pip install {install_name}"
            print(msg)
            return False
    return True


# =============================================================================
# SECTION 3: APPLICATION LAUNCH
# =============================================================================

def launch_app():
    """
    Main launch function. Runs pre-checks then starts the GUI.
    """
    if not check_dependencies():
        sys.exit(1)
    if not check_db_connection():
        sys.exit(0)
    root = tk.Tk()
    root = configure_window(root)
    app = TpcHAnnotatorApp(root)
    try:
        root.mainloop()
    except:
        if app.conn:
            close_connection(app.conn)
        print("Application Closed")
        
    pass


# =============================================================================
# SECTION 4: ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Entry point when running:
        python project.py
        (or via PyCharm Run button)
    """
    try:
        launch_app()
    except Exception as e:
        print("Unexpected Error", str(e))
        sys.exit(1)
