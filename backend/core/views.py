import json
import hmac
from typing import Any, Dict
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpRequest, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from .github import verify_signature
from .models import Project, PullRequest, TestRun
from .tasks import orchestrate_pr

# # 🔹 New Splash View
# def splash(request: HttpRequest):
#     return render(request, "splash.html")

def splash(request):
    return render(request, "splash.html")

@csrf_exempt
def gh_webhook(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")
    payload = request.body
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(payload, sig):
        return HttpResponseBadRequest("bad signature")
    event = request.headers.get("X-GitHub-Event", "")
    data = json.loads(payload.decode("utf-8"))
    if event in ("pull_request",):
        action = data.get("action")
        if action in ("opened", "synchronize", "ready_for_review", "reopened"):
            repo_full = data["repository"]["full_name"]
            pr_num = data["number"]
            title = data["pull_request"]["title"]
            head_sha = data["pull_request"]["head"]["sha"]
            head_ref = data["pull_request"]["head"]["ref"]
            project, _ = Project.objects.get_or_create(
                repo_full_name=repo_full, defaults={"default_branch": data["repository"]["default_branch"]}
            )
            pr, _ = PullRequest.objects.get_or_create(
                project=project, number=pr_num,
                defaults={"title": title, "head_sha": head_sha, "head_ref": head_ref, "status": "pending"}
            )
            pr.title = title
            pr.head_sha = head_sha
            pr.head_ref = head_ref
            pr.status = "pending"
            pr.save()
            orchestrate_pr.delay(pr.id)
    return JsonResponse({"ok": True})

def dashboard(request: HttpRequest):
    prs = PullRequest.objects.select_related("project").order_by("-updated_at")[:50]
    return render(request, "dashboard.html", {"prs": prs})

# def pr_detail(request: HttpRequest, project: str, number: int):
#     project_obj = Project.objects.get(repo_full_name=project)
#     pr = get_object_or_404(PullRequest, project=project_obj, number=number)
#     runs = pr.test_runs.order_by("-started_at")
#     return render(request, "pr_detail.html", {"pr": pr, "runs": runs})

def pr_detail(request: HttpRequest, user: str, project: str, number: int):
    repo_full_name = f"{user}/{project}"   # "AliHShahid/PeerStudy"
    project_obj = Project.objects.get(repo_full_name=repo_full_name)
    pr = get_object_or_404(PullRequest, project=project_obj, number=number)
    runs = pr.test_runs.order_by("-started_at")
    return render(request, "pr_detail.html", {"pr": pr, "runs": runs})
