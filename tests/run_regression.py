"""Run independent non-GUI tests in fresh processes."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
TESTS=("test_bridge_mock.py", "test_phase_v5_contract.py", "test_qt_save_reorder_contract.py", "test_reference_autoscroll.py", "test_qt_shutdown_overlay.py", "test_legacy_sync_retired.py")
if __name__ == "__main__":
    failed=[]
    for name in TESTS:
        print("RUN:",name,flush=True)
        if subprocess.run([sys.executable,str(ROOT/"tests"/name)],cwd=ROOT).returncode:
            failed.append(name)
    print("FAIL:",failed) if failed else print("PASS: all non-GUI regression scripts")
    print("NOT RUN: Blender integration_smoke.py; pending legacy retirement contracts")
    raise SystemExit(bool(failed))
