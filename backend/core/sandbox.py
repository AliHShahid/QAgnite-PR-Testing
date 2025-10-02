import os
import shutil
import subprocess
import tempfile
from typing import Dict, Tuple

def run_cmd(cmd: str, cwd: str | None = None, env: dict | None = None, timeout: int = 600) -> Tuple[int, str]:
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=env)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        return 124, "Command timed out"
    return p.returncode, out.decode("utf-8", errors="ignore")

def new_workspace(root: str) -> str:
    os.makedirs(root, exist_ok=True)
    return tempfile.mkdtemp(prefix="repo_", dir=root)

def prepare_env(workdir: str) -> str:
    venv = os.path.join(workdir, ".venv")
    code, out = run_cmd(f"python -m venv .venv", cwd=workdir, timeout=300)
    if code != 0:
        return ""
    pip = os.path.join(venv, "bin", "pip")
    run_cmd(f"{pip} install -U pip", cwd=workdir, timeout=300)
    return venv

def install_requirements(workdir: str, venv: str) -> None:
    req = os.path.join(workdir, "requirements.txt")
    pip = os.path.join(venv, "bin", "pip")
    if os.path.exists(req):
        run_cmd(f"{pip} install -r requirements.txt", cwd=workdir, timeout=1200)
    # Ensure pytest-related deps exist
    run_cmd(f"{pip} install pytest pytest-cov hypothesis", cwd=workdir, timeout=600)

def clone_pr(repo_https_url: str, pr_number: int, token: str, workdir: str) -> Tuple[int, str]:
    # Use token in URL for private repos
    auth_url = repo_https_url.replace("https://", f"https://{token}@")
    code, out = run_cmd(f"git clone {auth_url} .", cwd=workdir)
    if code != 0:
        return code, out
    # Fetch PR head
    run_cmd(f"git fetch origin pull/{pr_number}/head:pr-{pr_number}", cwd=workdir)
    run_cmd(f"git checkout pr-{pr_number}", cwd=workdir)
    return 0, "cloned"

def write_files(workdir: str, files: Dict[str, str]) -> None:
    for rel, content in files.items():
        path = os.path.join(workdir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

def run_pytest(workdir: str, venv: str) -> Tuple[int, str]:
    pytest_bin = os.path.join(venv, "bin", "pytest")
    code, out = run_cmd(f"{pytest_bin} -q --maxfail=1 --disable-warnings --junitxml=report.xml", cwd=workdir, timeout=1800)
    return code, out

def read_file(workdir: str, rel: str) -> str:
    with open(os.path.join(workdir, rel), "r", encoding="utf-8") as f:
        return f.read()

def list_py_files(workdir: str) -> list[str]:
    files: list[str] = []
    for root, _, fs in os.walk(workdir):
        for name in fs:
            if name.endswith(".py"):
                rel = os.path.relpath(os.path.join(root, name), workdir)
                files.append(rel)
    return files
