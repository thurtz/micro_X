# utils/update_docs.py

import os
import subprocess

HELP_TEXT = """
micro_X Help: /update_docs Utility

This utility builds the Sphinx documentation.

Usage:
  /update_docs
"""

def main():
    """Builds the Sphinx documentation."""
    print("📚 Building documentation...")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_source_dir = os.path.join(project_root, 'docs', 'source')

    if not os.path.isdir(docs_source_dir):
        print(f"❌ Error: Documentation source directory not found at '{docs_source_dir}'")
        return

    try:
        subprocess.run(
            ['make', '-C', docs_source_dir, 'html'],
            check=True,
            encoding='utf-8',
            errors='replace'
        )
        print("\n✅ Documentation build complete.")
        print(f"   You can view it by running: /docs")
    except FileNotFoundError:
        print("❌ Error: 'make' command not found. Is it installed and in your PATH?")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error building documentation. The 'make' command failed with return code {e.returncode}.")
        if e.stdout:
            print(f"--- stdout ---\n{e.stdout}")
        if e.stderr:
            print(f"--- stderr ---\n{e.stderr}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
