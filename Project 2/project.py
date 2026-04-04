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

    TODO:
        - Set window title:
          root.title("SC3020 Project 2 — SQL Query Annotator")
        - Set window size:
          root.geometry("1200x800")
        - Set minimum resize limit:
          root.minsize(900, 600)
        - Set window to open centered on screen:
            screen_w = root.winfo_screenwidth()
            screen_h = root.winfo_screenheight()
            x = (screen_w // 2) - (1200 // 2)
            y = (screen_h // 2) - (800 // 2)
            root.geometry(f"1200x800+{x}+{y}")
        - Optional: set a window icon using root.iconbitmap("icon.ico")
          (skip if no icon file is available)
    """
    root.title("SC3020 Project 2 — SQL Query Annotator")
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = (screen_w // 2) - (1200 // 2)
    y = (screen_h // 2) - (800 // 2)
    root.geometry(f"1200x800+{x}+{y}")
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

    TODO:
        - Call get_connection() from preprocessing.py inside a try/except
        - If successful:
            - Immediately call close_connection() (just a test ping)
            - Return True
        - If exception:
            - Show a messagebox.askokcancel() warning:
              Title:   "Database Connection Failed"
              Message: "Could not connect to PostgreSQL.\n
                        Check your .env settings and ensure PostgreSQL is running.\n\n
                        Launch anyway? (DB connect available inside the app)"
            - Return True if user clicks OK (launch anyway)
            - Return False if user clicks Cancel (exit)
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

    TODO:
        - Attempt to import each required package inside a try/except ImportError:
            * psycopg
            * dotenv  (from dotenv import load_dotenv)
        - If any import fails:
            - Print a clear error to console:
              "Missing dependency: <package>. Run: pip install <package>"
            - Show a messagebox.showerror() with the same message
            - Return False
        - Return True if all imports succeed
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

    TODO:
        - Call check_dependencies() → if False, call sys.exit(1)
        - Call check_db_connection() → if False, call sys.exit(0)
        - Create root = tk.Tk()
        - Call configure_window(root)
        - Instantiate app = TpcHAnnotatorApp(root)
        - Wrap root.mainloop() in try/except KeyboardInterrupt:
            - On interrupt: call close_connection(app.conn) if app.conn exists
            - Print "Application closed."
    """
    if not check_dependencies():
        sys.exit(1)
    if not check_db_connection():
        sys.exit(0)
    conn = get_connection()
    root = tk.Tk()
    configure_window(root)
    TpcHAnnotatorApp(root)
    try:
        root.mainloop()
    except:
        if conn:
            close_connection(conn)
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

    TODO:
        - Wrap launch_app() in a try/except Exception as e:
            - On unexpected error: print full traceback using traceback.print_exc()
            - Show messagebox.showerror("Unexpected Error", str(e))
            - sys.exit(1)
    """
    launch_app()
