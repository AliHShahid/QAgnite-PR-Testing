import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional
from github import Github

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")

def verify_signature(payload: bytes, signature_header: str) -> bool:
    if not WEBHOOK_SECRET:
        return True
    signature = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={signature}", signature_header or "")

def get_client() -> Optional[Github]:
    if not GITHUB_TOKEN:
        return None
    return Github(GITHUB_TOKEN)

def post_pr_comment(repo_full_name: str, pr_number: int, body: str) -> None:
    client = get_client()
    if not client:
        return
    repo = client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(body)

def create_check_run(repo_full_name: str, head_sha: str, name: str, summary: str, conclusion: Optional[str] = None) -> None:
    # Simplified: use PR comment for visibility
    if conclusion:
        summary = f"[{name}] {conclusion.upper()}\n\n{summary}"
    # Without GitHub App auth, we fallback to comment on PR list (requires PR number). Caller can post separately.
    # No-op for now or handled by post_pr_comment.
    return
