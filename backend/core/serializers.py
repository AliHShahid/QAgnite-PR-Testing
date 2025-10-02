from rest_framework import serializers
from .models import PullRequest, TestRun, Failure

class FailureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Failure
        fields = "__all__"

class TestRunSerializer(serializers.ModelSerializer):
    failures = FailureSerializer(many=True, read_only=True)
    class Meta:
        model = TestRun
        fields = "__all__"

class PullRequestSerializer(serializers.ModelSerializer):
    test_runs = TestRunSerializer(many=True, read_only=True)
    class Meta:
        model = PullRequest
        fields = "__all__"
