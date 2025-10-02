from django.contrib import admin
from .models import Project, PullRequest, Job, GeneratedTest, TestRun, Failure, FailureCluster, PatchSuggestion

admin.site.register(Project)
admin.site.register(PullRequest)
admin.site.register(Job)
admin.site.register(GeneratedTest)
admin.site.register(TestRun)
admin.site.register(Failure)
admin.site.register(FailureCluster)
admin.site.register(PatchSuggestion)
