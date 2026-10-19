"""Install the exact /articles Nginx route after inspecting the active config.

Run with sudo on the Quantelle server. Leaves the existing SPA and API rules intact.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROUTE = """    location = /articles {
        try_files /articles/index.html =404;
    }

    location = /articles/ {
        try_files /articles/index.html =404;
    }

"""
NEEDLE = "    location / {\n        try_files $uri /index.html;"


def patched_config(text):
    if "location = /articles {" in text:
        return text
    if text.count(NEEDLE) != 1 or "server_name quantelle.io www.quantelle.io;" not in text:
        raise RuntimeError("Unexpected Nginx config; inspect it before changing the article route")
    return text.replace(NEEDLE, ROUTE + NEEDLE, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write, test, and reload Nginx")
    args = parser.parse_args()
    matches = [p.resolve() for p in Path("/etc/nginx/sites-enabled").iterdir()
               if p.is_file() and "server_name quantelle.io www.quantelle.io;" in p.read_text()]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Quantelle Nginx config; found {len(matches)}")
    path = matches[0]
    original = path.read_text()
    updated = patched_config(original)
    if updated == original:
        print("The /articles route is already installed")
        return
    if not args.apply:
        print(f"Ready to add exact /articles routes to {path}; rerun with --apply")
        return
    if os.geteuid() != 0:
        raise RuntimeError("Applying the Nginx route requires sudo")
    backup = path.with_suffix(path.suffix + ".quantelle-articles-backup")
    if backup.exists():
        raise RuntimeError(f"Backup already exists: {backup}; inspect it first")
    shutil.copy2(path, backup)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False) as output:
            temporary = Path(output.name)
            output.write(updated)
        shutil.copymode(path, temporary)
        os.replace(temporary, path)
        temporary = None
        subprocess.run(["nginx", "-t"], check=True)
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
    except Exception:
        shutil.copy2(backup, path)
        subprocess.run(["nginx", "-t"], check=True)
        raise
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    print("Installed /articles route; backup:", backup)


if __name__ == "__main__":
    main()
