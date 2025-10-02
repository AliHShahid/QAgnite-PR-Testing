from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import JSONField  # type: ignore

class Project(models.Model):
    repo_full_name = models.CharField(max_length=255, unique=True)  # e.g., org/repo
    default_branch = models.CharField(max_length=128, default="main")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.repo_full_name

class PullRequest(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    number = models.IntegerField()
    title = models.CharField(max_length=512)
    head_sha = models.CharField(max_length=64, blank=True, default="")
    head_ref = models.CharField(max_length=255, blank=True, default="")
    author = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=64, default="pending")  # pending/running/success/failure
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("project", "number")

    def __str__(self):
        return f"{self.project.repo_full_name}#{self.number}"

class Job(models.Model):
    pr = models.ForeignKey(PullRequest, on_delete=models.CASCADE, related_name="jobs")
    job_type = models.CharField(max_length=64)  # analysis/generate/execute/triage/patch/report
    status = models.CharField(max_length=32, default="queued")
    payload = models.JSONField(default=dict)
    logs = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

class GeneratedTest(models.Model):
    pr = models.ForeignKey(PullRequest, on_delete=models.CASCADE, related_name="generated_tests")
    path = models.CharField(max_length=512)
    content = models.TextField()
    rationale = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

class TestRun(models.Model):
    pr = models.ForeignKey(PullRequest, on_delete=models.CASCADE, related_name="test_runs")
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    passed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    coverage = models.FloatField(default=0.0)
    junit_xml = models.TextField(blank=True, default="")
    raw_output = models.TextField(blank=True, default="")

class Failure(models.Model):
    test_run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name="failures")
    test_name = models.CharField(max_length=512)
    file = models.CharField(max_length=512, blank=True, default="")
    line = models.IntegerField(default=0)
    message = models.TextField(blank=True, default="")
    stacktrace = models.TextField(blank=True, default="")
    failure_type = models.CharField(max_length=128, blank=True, default="failure")

class FailureCluster(models.Model):
    pr = models.ForeignKey(PullRequest, on_delete=models.CASCADE, related_name="failure_clusters")
    signature = models.CharField(max_length=128)
    summary = models.TextField()
    count = models.IntegerField(default=1)

class PatchSuggestion(models.Model):
    pr = models.ForeignKey(PullRequest, on_delete=models.CASCADE, related_name="patches")
    diff = models.TextField()
    rationale = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    applied = models.BooleanField(default=False)
    pr_url = models.URLField(blank=True, default="")
