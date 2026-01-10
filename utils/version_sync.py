# utils/version_sync.py

import os
import json
import re
import sys
import argparse

HELP_TEXT = """
micro_X Utility: Version Sync

Synchronizes the application version number across the project.
It reads the "master" version from 'config/default_config.json' and updates:
1. 'micro_X.desktop'
2. 'docs/source/conf.py'
3. 'micro_X-A_Technical_Whitepaper.md'

Usage:
  /utils version_sync [--check]

Arguments:
  --check    Only check if versions are in sync, do not modify files.
             Returns exit code 0 if synced, 1 if not.
"""

def get_project_root():
    """Finds the project root relative to this script."""
    # Script is in utils/version_sync.py
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_master_version(root_dir):
    config_path = os.path.join(root_dir, "config", "default_config.json")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            # Simple JSON load - we assume default_config.json is valid standard JSON here
            # For robustness we could use the comment-stripping loader, but let's keep it simple for now
            data = json.load(f)
            version = data.get("application", {}).get("version")
            if not version:
                print(f"❌ Error: 'application.version' not found in {config_path}")
                return None
            return version
    except Exception as e:
        print(f"❌ Error loading master version: {e}")
        return None

def update_file(filepath, pattern, replacement_template, current_version, dry_run=False):
    if not os.path.exists(filepath):
        print(f"⚠️  File not found: {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = re.sub(pattern, replacement_template.format(version=current_version), content)

    if content != new_content:
        if dry_run:
            print(f"🔸 Would update {filepath}")
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ Updated {filepath}")
        return True # Change needed/made
    else:
        print(f"   {filepath} is up to date.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Sync micro_X version number.")
    parser.add_argument("--check", action="store_true", help="Only check for sync status.")
    args = parser.parse_args()

    root_dir = get_project_root()
    master_version = load_master_version(root_dir)

    if not master_version:
        sys.exit(1)

    print(f"ℹ️  Master Version (config/default_config.json): {master_version}")

    changes_detected = False

    # 1. Update micro_X.desktop
    # Pattern: Version=X.X.X
    changes_detected |= update_file(
        os.path.join(root_dir, "micro_X.desktop"),
        r"Version=[\d\.]+",
        "Version={version}",
        master_version,
        args.check
    )

    # 2. Update docs/source/conf.py
    # Pattern: version = 'X.X.X'
    changes_detected |= update_file(
        os.path.join(root_dir, "docs", "source", "conf.py"),
        r"version = '[\d\.]+'",
        "version = '{version}'",
        master_version,
        args.check
    )
    # Pattern: release = 'X.X.X'
    changes_detected |= update_file(
        os.path.join(root_dir, "docs", "source", "conf.py"),
        r"release = '[\d\.]+'",
        "release = '{version}'",
        master_version,
        args.check
    )

    # 3. Update micro_X-A_Technical_Whitepaper.md
    # Pattern: Version: X.X.X (Reflecting...)
    # Note: We only match the version number part to preserve the rest of the line if possible,
    # or we can target the specific known line format.
    changes_detected |= update_file(
        os.path.join(root_dir, "micro_X-A_Technical_Whitepaper.md"),
        r"Version: [\d\.]+ \(Reflecting",
        "Version: {version} (Reflecting",
        master_version,
        args.check
    )

    if args.check:
        if changes_detected:
            print("\n❌ Versions are NOT in sync.")
            sys.exit(1)
        else:
            print("\n✅ All versions are in sync.")
            sys.exit(0)
    else:
        print("\n✨ Version sync complete.")

if __name__ == "__main__":
    main()
