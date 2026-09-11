"""在隔离副本中运行离线回归，避免读取生产账号或误跑真实出图脚本。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
NEW_MODULES = [
    "test.test_image_model_routing",
    "test.test_production_image_recovery",
    "test.test_gpt_image_25",
    "test.test_image_25_protocols",
]
BASELINE_MODULES = [
    "test.test_account_export",
    "test.test_account_image_capabilities",
    "test.test_chat_completion_cache",
    "test.test_config",
    "test.test_image_base_url_api",
    "test.test_image_storage_service",
    "test.test_image_task_service",
    "test.test_image_tasks_api",
    "test.test_image_tokens",
    "test.test_init_proxy_config",
    "test.test_multi_image_results",
    "test.test_proxy_runtime_api",
    "test.test_proxy_runtime_config",
    "test.test_proxy_service",
    "test.test_register_proxy_runtime",
    "test.test_v1_images_edits_api",
    "test.test_v1_images_edits_json",
    "test.test_v1_models.ModelListTests.test_list_models_only_returns_image_models_backed_by_account_types",
    "test.test_v1_models.ModelListTests.test_list_models_does_not_return_codex_models_for_web_plus_accounts",
]

WORKER = r'''
import json, os, sys, unittest, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["CHATGPT2API_AUTH_KEY"] = "chatgpt2api"
os.environ["STORAGE_BACKEND"] = "json"
import requests
import curl_cffi.requests

def deny_network(*args, **kwargs):
    raise RuntimeError("offline test: outbound network is disabled")

requests.sessions.Session.request = deny_network
curl_cffi.requests.Session.request = deny_network
urllib.request.urlopen = deny_network

def audit(event, args):
    if event == "socket.connect":
        address = args[1]
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            deny_network()

sys.addaudithook(audit)
suite = unittest.defaultTestLoader.loadTestsFromName(sys.argv[1])
result = unittest.TextTestRunner(verbosity=1).run(suite)
print("OFFLINE_RESULT=" + json.dumps({
    "tests": result.testsRun, "failures": len(result.failures),
    "errors": len(result.errors), "skipped": len(result.skipped),
}))
sys.exit(0 if result.wasSuccessful() else 1)
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-only", action="store_true", help="只运行本次新增回归")
    parser.add_argument("modules", nargs="*", help="可选：指定离线 unittest 模块或方法")
    args = parser.parse_args()
    targets = args.modules or (NEW_MODULES if args.new_only else [*BASELINE_MODULES, *NEW_MODULES])
    total = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    failed = False
    with tempfile.TemporaryDirectory(prefix="ch2a-offline-", ignore_cleanup_errors=True) as tmp:
        snapshot = Path(tmp).resolve()
        if snapshot.parent != Path(tempfile.gettempdir()).resolve():
            raise RuntimeError("测试临时目录不在预期位置")
        for folder in ("api", "services", "utils", "test", "scripts"):
            shutil.copytree(
                ROOT / folder, snapshot / folder,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", ".venv"),
            )
        shutil.copy2(ROOT / "VERSION", snapshot / "VERSION")
        # 不复制原 config.json、.env 或 data，注册/备份均保持关闭。
        (snapshot / "config.json").write_text(
            json.dumps({"auth-key": "chatgpt2api", "log_levels": [], "auto_remove_invalid_accounts": True}),
            encoding="utf-8",
        )
        worker = snapshot / "_offline_worker.py"
        worker.write_text(WORKER, encoding="utf-8")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        env.pop("PYTHONPATH", None)
        for target in targets:
            try:
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", "-B", str(worker), target],
                    cwd=snapshot, env=env, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=120,
                )
            except subprocess.TimeoutExpired:
                failed = True
                total["errors"] += 1
                print(f"TIMEOUT {target}", flush=True)
                continue
            markers = [line for line in result.stdout.splitlines() if line.startswith("OFFLINE_RESULT=")]
            counts = json.loads(markers[-1].split("=", 1)[1]) if markers else {"errors": 1}
            for key in total:
                total[key] += counts.get(key, 0)
            failed = failed or result.returncode != 0
            print(f"{'PASS' if result.returncode == 0 else 'FAIL'} {target}: {json.dumps(counts)}", flush=True)
            if result.returncode != 0:
                print(result.stderr, flush=True)
        print("TOTAL " + json.dumps(total), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
