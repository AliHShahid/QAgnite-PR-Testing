import os
import re
import ast
import json
import textwrap
from typing import List, Tuple, Dict, Any, Optional
import requests

HF_API_URL = os.getenv("HF_INFERENCE_API_URL")
HF_API_KEY = os.getenv("HF_API_KEY")

PROMPT_TEMPLATE = """You are an expert test generator. Given Python source code, write focused pytest tests.
Aim for:
- deterministic unit tests
- property-based tests using hypothesis for pure functions
- edge cases and error handling

Return only test file content without explanations.
Source:
{code}
"""

def call_hf(prompt: str) -> Optional[str]:
    if not HF_API_URL or not HF_API_KEY:
        return None
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    resp = requests.post(HF_API_URL, headers=headers, json={"inputs": prompt}, timeout=120)
    if resp.status_code == 200:
        try:
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0].get("generated_text", "")
            if isinstance(data, dict) and "generated_text" in data:
                return data["generated_text"]
            # Some endpoints return raw text
            return resp.text
        except Exception:
            return resp.text
    return None

def heuristic_generate_tests(py_file_path: str, code: str) -> str:
    try:
        tree = ast.parse(code)
    except Exception:
        tree = None
    tests = ["import pytest", "from hypothesis import given, strategies as st"]
    module_name = os.path.basename(py_file_path).replace(".py", "")
    tests.append(f"import {module_name} as module")
    if tree:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                fname = node.name
                tests.append("")
                tests.append(f"def test_{fname}_basic():")
                tests.append(f"    # basic smoke test for {fname}")
                call_args = " "
                # naive arg defaults
                params = []
                for arg in node.args.args:
                    if arg.arg == "self":
                        continue
                    params.append("0")
                call_args = ", ".join(params)
                tests.append(f"    try:")
                tests.append(f"        _ = module.{fname}({call_args})")
                tests.append(f"    except Exception as e:")
                tests.append(f"        pytest.fail(f'unexpected error: { '{'}e{'}' }')")

                # property-based sketch for single-arg numeric
                if len(params) == 1:
                    tests.append("")
                    tests.append(f"@given(st.integers())")
                    tests.append(f"def test_{fname}_property(x):")
                    tests.append(f"    # property: function should not crash for any integer")
                    tests.append(f"    module.{fname}(x)")
    return "\n".join(tests)

def generate_tests_for_repo(files: List[str], read_file) -> List[Tuple[str, str, str]]:
    outputs: List[Tuple[str, str, str]] = []
    for f in files:
        if not f.endswith(".py"):
            continue
        if os.path.basename(f).startswith("test_"):
            continue
        code = read_file(f)
        prompt = PROMPT_TEMPLATE.format(code=code[:8000])
        llm = call_hf(prompt)
        if llm and "def test" in llm:
            content = llm
            rationale = "Generated via HF model"
        else:
            content = heuristic_generate_tests(f, code)
            rationale = "Heuristic AST-based generator"
        test_rel_path = f"tests/generated/test_{os.path.basename(f)}"
        outputs.append((test_rel_path, content, rationale))
    return outputs

def cluster_failures(failures: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    clusters: Dict[str, Dict[str, Any]] = {}
    for f in failures:
        key = f.get("message", "")[:120] + f.get("test_name", "")[:60]
        if key not in clusters:
            clusters[key] = {"summary": f.get("message", "")[:280], "count": 0, "items": []}
        clusters[key]["count"] += 1
        clusters[key]["items"].append(f)
    return clusters
