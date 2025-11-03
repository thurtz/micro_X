import argparse
import os
import subprocess

HELP_TEXT = "Generates a .desktop file for micro_X, allowing it to be launched from application menus."

def generate_desktop_entry(project_root, branch_name, app_name="micro_X"):
    local_apps_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(local_apps_dir, exist_ok=True)

    desktop_filename_base = "micro_x"
    final_display_name_for_instructions = app_name
    final_comment_for_desktop = f"Launch {app_name} AI Shell"

    if branch_name and branch_name != "unknown":
        final_desktop_filename = f"{desktop_filename_base}_{branch_name}.desktop"
        final_display_name_for_desktop = f"{app_name} ({branch_name})"
        final_display_name_for_instructions = final_display_name_for_desktop
        final_comment_for_desktop = f"Launch {app_name} AI Shell ({branch_name} instance)"
    else:
        final_desktop_filename = f"{desktop_filename_base}.desktop"
        final_display_name_for_desktop = app_name

    final_desktop_file_path = os.path.join(local_apps_dir, final_desktop_filename)
    micro_x_launcher_sh = os.path.join(project_root, "micro_X.sh")

    desktop_content = f"""[Desktop Entry]
Type=Application
Name={final_display_name_for_desktop}
Comment={final_comment_for_desktop}
Exec={micro_x_launcher_sh}
Terminal=true
Categories=Development;Utility;AI;
"""

    with open(final_desktop_file_path, "w") as f:
        f.write(desktop_content)

    print(f"Desktop entry '{final_display_name_for_desktop}' installed at {final_desktop_file_path}.")

    try:
        subprocess.run(["update-desktop-database", local_apps_dir], check=True, capture_output=True)
        print("Desktop database updated.")
    except subprocess.CalledProcessError as e:
        print(f"WARNING: Could not update desktop database: {e.stderr.decode().strip()}")
    except FileNotFoundError:
        print("WARNING: update-desktop-database command not found. Desktop entry might not appear immediately.")

    return final_display_name_for_instructions

def main():
    parser = argparse.ArgumentParser(description=HELP_TEXT)
    parser.add_argument("--project_root", required=True, help="The absolute path to the project root directory.")
    parser.add_argument("--branch_name", default="unknown", help="The current Git branch name (e.g., 'dev', 'main').")
    parser.add_argument("--app_name", default="micro_X", help="The display name of the application.")

    args = parser.parse_args()

    generate_desktop_entry(args.project_root, args.branch_name, args.app_name)

if __name__ == "__main__":
    main()
