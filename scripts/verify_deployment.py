"""Production & Deployment Verification Script for DSE Market Signal App.

Validates that:
1. Dockerfile, docker-compose.yml, and systemd service files exist and are valid.
2. Configuration files exist and are valid JSON.
3. Database schema and tables are initialized.
4. All 5 configured symbols exist with historical records.
5. FastAPI app and health endpoint can be imported and initialized.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def verify_deployment() -> bool:
    print("=" * 60)
    print(" DSE MARKET SIGNAL - DEPLOYMENT READINESS VERIFICATION")
    print("=" * 60)

    checks = []

    # 1. Deployment configuration files
    dockerfile = ROOT / "Dockerfile"
    docker_compose = ROOT / "docker-compose.yml"
    service_file = ROOT / "dse-market-signal.service"
    ci_file = ROOT / ".github" / "workflows" / "ci.yml"

    has_docker = dockerfile.exists() and "uvicorn" in dockerfile.read_text(encoding="utf-8")
    has_compose = docker_compose.exists() and "dse-market-signal" in docker_compose.read_text(encoding="utf-8")
    has_service = service_file.exists() and "ExecStart" in service_file.read_text(encoding="utf-8")
    has_ci = ci_file.exists() and "pytest" in ci_file.read_text(encoding="utf-8")

    checks.append(("Dockerfile valid & configured", has_docker))
    checks.append(("docker-compose.yml present & configured", has_compose))
    checks.append(("Systemd service unit file present", has_service))
    checks.append(("GitHub Actions CI/CD workflow configured", has_ci))

    # 2. Settings JSON
    settings_file = ROOT / "config" / "settings.json"
    has_settings = False
    symbols = []
    if settings_file.exists():
        try:
            cfg = json.loads(settings_file.read_text(encoding="utf-8"))
            symbols = cfg.get("market", {}).get("symbols", [])
            has_settings = len(symbols) == 5
        except Exception:
            pass
    checks.append(("Settings JSON configured (5 symbols)", has_settings))

    # 3. Database records for configured symbols
    from backend.db import connect
    try:
        with connect() as con:
            counts = dict(con.execute("SELECT symbol, count(*) FROM prices GROUP BY symbol").fetchall())
        all_symbols_present = all(s in counts and counts[s] > 0 for s in symbols)
        checks.append((f"Historical records populated for {symbols}: {counts}", all_symbols_present))
    except Exception as exc:
        checks.append((f"Database connection & records ({exc})", False))

    # 4. FastAPI & Health check
    try:
        from backend.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        res = client.get("/health")
        health_ok = res.status_code == 200 and res.json().get("status") == "ok"
        checks.append(("FastAPI application & /health endpoint operational", health_ok))
    except Exception as exc:
        checks.append((f"FastAPI initialization ({exc})", False))

    # Summary
    print("\nCheck Results:")
    all_passed = True
    for name, passed in checks:
        mark = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{mark}] {name}")

    print("-" * 60)
    if all_passed:
        print("RESULT: ALL DEPLOYMENT & PRODUCTION CHECKS PASSED.")
    else:
        print("RESULT: ONE OR MORE CHECKS FAILED.")
    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    success = verify_deployment()
    sys.exit(0 if success else 1)
