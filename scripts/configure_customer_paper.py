"""Provision admin paper defaults without displaying or replacing credentials."""
import base64
import os
from pathlib import Path
import secrets
import tempfile


def provision(path):
    path = Path(path)
    original = path.stat()
    lines = path.read_text().splitlines()
    values = {}
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip().strip("\"'")
    defaults = {
        "CUSTOMER_PAPER_CREDENTIAL_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "CUSTOMER_PAPER_CONNECT_ENABLED": "true",
        "CUSTOMER_PAPER_EXECUTION_ENABLED": "true",
        "CUSTOMER_PAPER_CUSTOMERS_ENABLED": "false",
    }
    if "CUSTOMER_PAPER_CREDENTIAL_KEY" in values:
        try:
            if len(base64.urlsafe_b64decode(values["CUSTOMER_PAPER_CREDENTIAL_KEY"])) != 32:
                raise ValueError
        except (ValueError, TypeError):
            raise SystemExit("Existing customer credential key is invalid; nothing changed.")
    for name, value in defaults.items():
        if name not in values:
            lines.append(f"{name}={value}")
    fd, temporary = tempfile.mkstemp(prefix=".customer-paper-env-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            os.fchmod(output.fileno(), 0o600)
            current = os.fstat(output.fileno())
            if (current.st_uid, current.st_gid) != (original.st_uid, original.st_gid):
                os.fchown(output.fileno(), original.st_uid, original.st_gid)
            output.write("\n".join(lines) + "\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("Customer paper defaults provisioned; existing settings and credentials preserved.")


if __name__ == "__main__":
    provision(".env.docker")
