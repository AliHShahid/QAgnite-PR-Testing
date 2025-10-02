import os
import json
import datetime
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import PullRequest, Project, Job, GeneratedTest, TestRun, Failure, FailureCluster, PatchSuggestion
from .github import post_pr_comment
from . import sandbox
from . import ai as ai_mod

def log(job: Job, msg: str) -> None:
    job.logs += f"{datetime.datetime.utcnow().isoformat()}Z {msg}\n"
    job.save(update_fields=["logs"])

@shared_task
def orchestrate_pr(pr_id: int) -> None:
    pr = PullRequest.objects.get(id=pr_id)
    pr.status = "running"
    pr.save(update_fields=["status"])

    job = Job.objects.create(pr=pr, job_type="orchestrate", status="running", started_at=timezone.now())
    try:
        workdir = sandbox.new_workspace(settings.WORKSPACE_ROOT)
        log(job, f"workspace: {workdir}")

        # Clone
        repo_full_name = pr.project.repo_full_name
        repo_url = f"https://github.com/{repo_full_name}.git"
        code, out = sandbox.clone_pr(repo_url, pr.number, settings.GITHUB_TOKEN or "", workdir)
        log(job, f"clone code={code}\n{out}")
        if code != 0:
            raise RuntimeError("Clone failed")

        # Static analysis
        analysis_job = Job.objects.create(pr=pr, job_type="analysis", status="running", started_at=timezone.now())
        run_cmd = lambda c: sandbox.run_cmd(c, cwd=workdir)[1]
        bandit = sandbox.run_cmd("bandit -r -q .", cwd=workdir)[1]
        flake = sandbox.run_cmd("flake8 .", cwd=workdir)[1]
        semgrep = sandbox.run_cmd("semgrep scan --quiet --error --config p/ci", cwd=workdir)[1]
        analysis_job.logs = f"Bandit:\n{bandit}\n\nFlake8:\n{flake}\n\nSemgrep:\n{semgrep}\n"
        analysis_job.status = "success"
        analysis_job.finished_at = timezone.now()
        analysis_job.save()

        # AI Test Generation
        gen_job = Job.objects.create(pr=pr, job_type="generate", status="running", started_at=timezone.now())
        py_files = sandbox.list_py_files(workdir)
        def _read(rel: str) -> str:
            try:
                return sandbox.read_file(workdir, rel)
            except Exception:
                return ""
        gens = ai_mod.generate_tests_for_repo(py_files, _read)
        files_to_write = {}
        for rel, content, rationale in gens:
            files_to_write[rel] = content
        sandbox.write_files(workdir, files_to_write)
        for rel, content, rationale in gens:
            GeneratedTest.objects.create(pr=pr, path=rel, content=content, rationale=rationale)
        gen_job.logs = f"Generated {len(gens)} test files"
        gen_job.status = "success"
        gen_job.finished_at = timezone.now()
        gen_job.save()

        # Prepare env & install
        exec_job = Job.objects.create(pr=pr, job_type="execute", status="running", started_at=timezone.now())
        venv = sandbox.prepare_env(workdir)
        if not venv:
            raise RuntimeError("virtualenv failed")
        sandbox.install_requirements(workdir, venv)

        # Execute tests
        code, out = sandbox.run_pytest(workdir, venv)
        test_run = TestRun.objects.create(pr=pr, raw_output=out)
        # Read JUnit if exists
        try:
            report_xml = sandbox.read_file(workdir, "report.xml")
            test_run.junit_xml = report_xml
        except Exception:
            pass

        # naive parsing
        passed = out.count(" PASSED")
        failed = out.count(" FAILED")
        error = out.count(" ERROR")
        test_run.passed = passed
        test_run.failed = failed
        test_run.errors = error
        test_run.finished_at = timezone.now()
        test_run.save()

        exec_job.logs = out
        exec_job.status = "success" if code == 0 else "failure"
        exec_job.finished_at = timezone.now()
        exec_job.save()

        # Failure triage
        triage_job = Job.objects.create(pr=pr, job_type="triage", status="running", started_at=timezone.now())
        failures_list = []
        for line in out.splitlines():
            if "FAILED " in line and "::" in line:
                test_name = line.strip().split()[0]
                failures_list.append({"test_name": test_name, "message": line.strip()})
        clusters = ai_mod.cluster_failures(failures_list)
        for f in failures_list:
            Failure.objects.create(test_run=test_run, test_name=f["test_name"], message=f.get("message", ""))
        for sig, meta in clusters.items():
            FailureCluster.objects.create(pr=pr, signature=sig[:128], summary=meta["summary"], count=meta["count"])
        triage_job.logs = json.dumps(clusters, indent=2)
        triage_job.status = "success"
        triage_job.finished_at = timezone.now()
        triage_job.save()

        # Patch suggestion (placeholder heuristic)
        patch_job = Job.objects.create(pr=pr, job_type="patch", status="running", started_at=timezone.now())
        if failures_list:
            diff = """diff --git a/example.py b/example.py
index 000000..111111 100644
--- a/example.py
+++ b/example.py
@@ -1,4 +1,4 @@
-def add(a,b):return a+b
+def add(a, b):\n    # fix: ensure ints\n    return int(a) + int(b)\n"""
            PatchSuggestion.objects.create(pr=pr, diff=diff, rationale="Auto-fix formatting/types (example)")
            patch_job.logs = "Suggested 1 patch"
        else:
            patch_job.logs = "No failures -> no patch"
        patch_job.status = "success"
        patch_job.finished_at = timezone.now()
        patch_job.save()

        # Report back to GitHub (comment summary)
        summary = f"Static Analysis done. Generated {len(gens)} tests. Test result: {passed} passed, {failed} failed, {error} errors."
        post_pr_comment(repo_full_name, pr.number, summary)

        pr.status = "success" if failed == 0 and error == 0 else "failure"
        pr.save(update_fields=["status"])

    except Exception as e:
        job.logs += f"\nERROR: {e}\n"
        job.status = "failure"
        pr.status = "failure"
        job.finished_at = timezone.now()
        job.save()
        pr.save(update_fields=["status"])
        post_pr_comment(pr.project.repo_full_name, pr.number, f"Pipeline failed: {e}")
        return

    job.status = "success"
    job.finished_at = timezone.now()
    job.save()
