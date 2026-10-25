"""Load only named secrets from ~/secrets.env; never render Compose config."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from dotenv import dotenv_values
from redact import sanitize

REQUIRED = (
    "REPORTS_DB_PASSWORD", "REPORTS_APP_DB_PASSWORD", "REPORTS_CUBE_DB_PASSWORD", "REPORTS_CUBE_SQL_PASSWORD",
    "REPORTS_SUPERSET_SECRET_KEY", "REPORTS_SUPERSET_CLIENT_SECRET", "REPORTS_KC_ADMIN_PASSWORD",
    "REPORTS_DEMO_ADMIN_PASSWORD", "REPORTS_DEMO_MEMBER_PASSWORD",
)


def main():
    if not shutil.which("docker"):
        print("Docker is not installed; run contract checks with ci/check.sh instead.")
        return 2
    path = Path.home() / "secrets.env"
    values = dotenv_values(path) if path.is_file() else {}
    missing = [key for key in REQUIRED if not values.get(key)]
    if missing:
        print("Missing keys in ~/secrets.env: " + ", ".join(missing))
        return 2
    if len(values["REPORTS_SUPERSET_SECRET_KEY"]) < 32:
        print("REPORTS_SUPERSET_SECRET_KEY must contain at least 32 characters")
        return 2
    env = os.environ.copy()
    env.update({key: values[key] for key in REQUIRED})
    env["REPORTS_DATABASE_URL"] = "postgresql://reports_owner:" + quote(values["REPORTS_DB_PASSWORD"], safe="") + "@postgres:5432/reports"
    env["REPORTS_APP_DATABASE_URL"] = "postgresql://reports_app:" + quote(values["REPORTS_APP_DB_PASSWORD"], safe="") + "@postgres:5432/reports"
    env["REPORTS_BI_METADATA_URL"] = "postgresql+psycopg2://reports_owner:" + quote(values["REPORTS_DB_PASSWORD"], safe="") + "@postgres:5432/superset"
    # No .env, generated secret manifest or credentials in argv.
    args = sys.argv[1:] or ["up", "--build", "-d"]
    project = 'reports-pilot'
    if len(args) >= 2 and args[0] == '--project':
        project, args = args[1], args[2:]
        if not re.fullmatch(r'reports-(?:pilot|check-[a-f0-9]{12})', project) or not args:
            print('Only reports-pilot or an isolated reports-check-<12 hex> project is allowed')
            return 2
    if args[0] not in {"up", "down", "ps", "logs", "run", "exec", "build"}:
        print("Supported commands: up/down/ps/logs/run/exec/build")
        return 2
    process = subprocess.Popen(["docker", "compose", "-p", project, "-f", str(Path(__file__).with_name("compose.yaml")), *args],
                               env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(sanitize(line.rstrip('\n'), [values[key] for key in REQUIRED]), flush=True)
    return process.wait()


if __name__ == "__main__":
    sys.exit(main())
