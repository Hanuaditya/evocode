"""
backend/utils/initialization.py

Pre-flight checks run at FastAPI startup to catch environment issues
before they surface during a demo or production run.
"""
import os
import sys
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def initialize_sandbox_environment() -> Dict[str, Any]:
    """
    Validates that the environment is fully configured.

    Returns a structured report:
    {
        "success": bool,
        "warnings": [list of non-fatal issues],
        "errors":   [list of fatal issues],
        "environment": { system info dict }
    }
    """
    warnings: List[str] = []
    errors: List[str] = []
    env_info: Dict[str, Any] = {}

    # ── 1. Python version ────────────────────────────────────────────────────
    major, minor = sys.version_info[:2]
    env_info["python_version"] = f"{major}.{minor}.{sys.version_info[2]}"
    if (major, minor) < (3, 8):
        errors.append(f"Python >= 3.8 required, found {major}.{minor}")
    else:
        logger.info(f"[Init] Python {env_info['python_version']} OK")

    # ── 2. Node.js + npm ─────────────────────────────────────────────────────
    try:
        from utils.system_checks import (
            check_node_installed,
            check_npm_installed,
            get_system_info,
            validate_project_structure,
        )
        sys_info = get_system_info()
        env_info.update(sys_info)

        if not check_node_installed():
            errors.append("Node.js is not installed or not in PATH")
        else:
            logger.info(f"[Init] Node {sys_info.get('node_version')} OK")

        if not check_npm_installed():
            errors.append("npm is not installed or not in PATH")
        else:
            logger.info(f"[Init] npm {sys_info.get('npm_version')} OK")

    except Exception as e:
        errors.append(f"Could not run system checks: {e}")

    # ── 3. REPO_PATH validation ──────────────────────────────────────────────
    repo_path = os.getenv("REPO_PATH", "")
    env_info["repo_path"] = repo_path

    if not repo_path:
        errors.append("REPO_PATH is not set in .env")
    elif not os.path.exists(repo_path):
        errors.append(f"REPO_PATH does not exist: {repo_path}")
    else:
        logger.info(f"[Init] REPO_PATH exists: {repo_path}")

        # Check writable
        test_file = os.path.join(repo_path, ".evocode_write_test")
        try:
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            logger.info("[Init] REPO_PATH is writable")
        except Exception:
            errors.append(f"REPO_PATH is not writable: {repo_path}")

        # Validate project structure
        try:
            struct = validate_project_structure(repo_path)
            for issue in struct.get("issues", []):
                errors.append(f"Project structure: {issue}")
            for warn in struct.get("warnings", []):
                warnings.append(f"Project structure: {warn}")
        except Exception as e:
            warnings.append(f"Could not validate project structure: {e}")

        # ── 3a. Auto-setup tests if missing ──────────────────────────────────
        try:
            from config import settings
            auto_create = getattr(settings, "SANDBOX_CREATE_MINIMAL_TESTS", True)
        except Exception:
            auto_create = True

        if auto_create:
            try:
                from utils.test_config_helper import create_minimal_test_suite
                from utils.sandbox_runner import SandboxRunner
                runner = SandboxRunner(repo_path)
                cfg = runner.check_test_configuration()
                if not cfg.get("has_tests"):
                    ok = create_minimal_test_suite(repo_path)
                    if ok:
                        logger.info("[Init] Minimal test suite created for project")
                        warnings.append("No tests existed — minimal test-runner.js was auto-created")
                    else:
                        warnings.append("Could not auto-create test suite")
                else:
                    logger.info(f"[Init] Tests already configured: {cfg.get('test_command')}")
            except Exception as e:
                warnings.append(f"Test auto-setup error: {e}")

    # ── 4. GitHub credentials ────────────────────────────────────────────────
    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        errors.append("GITHUB_TOKEN is not set in .env")
    else:
        logger.info("[Init] GITHUB_TOKEN is set")
        # Light validation: try fetching the authenticated user
        try:
            from github import Github
            g = Github(github_token)
            user = g.get_user()
            _ = user.login  # triggers actual API call
            logger.info(f"[Init] GitHub auth OK — logged in as: {user.login}")
            env_info["github_user"] = user.login
        except Exception as e:
            errors.append(f"GitHub token validation failed: {e}")

    # ── 5. AI API keys ───────────────────────────────────────────────────────
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if not gemini_key and not openai_key:
        errors.append("At least one of GEMINI_API_KEY or OPENAI_API_KEY must be set")
    else:
        if gemini_key:
            logger.info("[Init] GEMINI_API_KEY is set")
            env_info["ai_provider"] = "Gemini"
        if openai_key:
            logger.info("[Init] OPENAI_API_KEY is set")
            env_info["ai_provider"] = env_info.get("ai_provider", "") + " OpenAI"

    # ── 6. Build report ──────────────────────────────────────────────────────
    success = len(errors) == 0
    return {
        "success": success,
        "warnings": warnings,
        "errors": errors,
        "environment": env_info,
    }
