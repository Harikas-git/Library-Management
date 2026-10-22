"""
run.py - Unified Launcher for Athenaeum Library Management & Simulation Platform.

Usage:
  python run.py          # Starts the interactive Web Dashboard & REST Server (default: http://127.0.0.1:5000)
  python run.py --cli    # Launches the interactive terminal CLI console
  python run.py --test   # Executes the automated unit & integration test suite
  python run.py --seed   # Resets and re-seeds the database with curated records
"""

import sys
import subprocess

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def print_banner():
    print("""
    +-------------------------------------------------------------------+
    |                                                                   |
    |   ATHENAEUM LIBRARY MANAGEMENT & SIMULATION PLATFORM              |
    |   Relational SQLite Database & Multi-Agent Behavioral Engine      |
    |                                                                   |
    +-------------------------------------------------------------------+
    """)

def main():
    print_banner()

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["--cli", "-c"]:
            import cli
            cli.main_menu()
            return
        elif arg in ["--test", "-t"]:
            import unittest
            import test_system
            suite = unittest.TestLoader().loadTestsFromModule(test_system)
            runner = unittest.TextTestRunner(verbosity=2)
            runner.run(suite)
            return
        elif arg in ["--seed", "-s"]:
            import seed_data
            seed_data.seed_database(reset=True)
            return
        elif arg in ["--help", "-h"]:
            print(__doc__)
            return

    # Default: launch web application
    from app import app
    print("  🌐 Starting Web Application...")
    print("  👉 Open your browser at: http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)

if __name__ == "__main__":
    main()
