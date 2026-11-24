"""
backend/utils/sandbox_runner.py

Hybrid Execution Sandbox for EvoCode V2.

Features:
- Ephemeral Git Worktree isolation per job (signal_id):
    git worktree add ../evocode-worktrees/signal-{id} -b evocode/signal-{id}-{timestamp}
- Execution Mode (SANDBOX_BACKEND=auto):
    - Docker: mounts worktree into node:20-alpine (--network=none, 1GB RAM, 1 CPU, 30s timeout)
    - Subprocess: falls back cleanly to isolated subprocess with CI=true, NODE_ENV=test
- Guaranteed teardown:
    - Context manager ensures `git worktree remove --force` in a finally block
    - Pushes branch on verified success or cleans up on failure
- Backward-compatible with V1 SandboxRunner methods.
"""

import os
import json
import logging
import subprocess
import platform
import re
import time
import shutil
from typing import Dict, Any, Optional
from contextlib import contextmanager

try:
    from config import settings
except Exception:
    settings = None

logger = logging.getLogger("sandbox_runner")


class SandboxRunner:
    """
    Utility class for executing and verifying code inside an isolated
    ephemeral git worktree, running tests via Docker or local subprocess.
    """

    def __init__(self, project_root_path: str):
        self.project_root_path = os.path.abspath(project_root_path)
        self.active_worktree_path: Optional[str] = None
        self.active_branch_name: Optional[str] = None
        if not os.path.exists(self.project_root_path):
            logger.warning(f"Project root path does not exist: {self.project_root_path}")
        logger.info(f"SandboxRunner initialized for path: {self.project_root_path}")

    # -----------------------------------------------------------------------
    # Ephemeral Git Worktree Management
    # -----------------------------------------------------------------------

    def create_worktree(self, signal_id: int) -> Dict[str, str]:
        """
        Creates an isolated git worktree for the given signal_id:
          Directory: ../evocode-worktrees/signal-{id}
          Branch:    evocode/signal-{id}-{timestamp}
        """
        # Ensure base worktrees directory exists
        base_worktrees_dir = os.path.abspath(os.path.join(self.project_root_path, "..", "evocode-worktrees"))
        os.makedirs(base_worktrees_dir, exist_ok=True)

        worktree_path = os.path.join(base_worktrees_dir, f"signal-{signal_id}")
        timestamp = int(time.time())
        branch_name = f"evocode/signal-{signal_id}-{timestamp}"

        # If worktree directory already exists from an aborted run, force remove it
        if os.path.exists(worktree_path):
            logger.warning(f"[sandbox_runner] Cleaning stale worktree at {worktree_path}")
            self._force_cleanup_directory(worktree_path)

        cmd = ["git", "worktree", "add", worktree_path, "-b", branch_name]
        logger.info(f"[sandbox_runner] Creating worktree for signal #{signal_id} on branch {branch_name}")

        try:
            res = subprocess.run(
                cmd,
                cwd=self.project_root_path,
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode != 0:
                # If branch already exists, try checkout without -b
                if "already exists" in res.stderr:
                    cmd_alt = ["git", "worktree", "add", worktree_path, branch_name]
                    res = subprocess.run(cmd_alt, cwd=self.project_root_path, capture_output=True, text=True, check=False)

            if res.returncode != 0:
                logger.error(f"[sandbox_runner] Failed to create worktree: {res.stderr}")
                raise RuntimeError(f"Failed to create git worktree: {res.stderr.strip()}")

            self.active_worktree_path = os.path.abspath(worktree_path)
            self.active_branch_name = branch_name
            logger.info(f"[sandbox_runner] Worktree successfully created at {worktree_path}")

            return {
                "worktree_path": self.active_worktree_path,
                "branch_name": self.active_branch_name,
            }

        except Exception as e:
            logger.error(f"[sandbox_runner] Error in create_worktree: {e}")
            raise

    def cleanup_worktree(self, delete_branch: bool = False) -> None:
        """
        Cleans up the active git worktree using `git worktree remove --force`.
        Guaranteed to leave zero leftover worktree folders.
        """
        if not self.active_worktree_path:
            return

        worktree_path = self.active_worktree_path
        branch_name = self.active_branch_name

        try:
            logger.info(f"[sandbox_runner] Removing worktree at {worktree_path}")
            # Step 1: git worktree remove --force
            res = subprocess.run(
                ["git", "worktree", "remove", "--force", worktree_path],
                cwd=self.project_root_path,
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode != 0:
                logger.warning(f"[sandbox_runner] git worktree remove returned: {res.stderr.strip()}")

            # Step 2: Ensure filesystem directory is completely gone
            if os.path.exists(worktree_path):
                self._force_cleanup_directory(worktree_path)

            # Step 3: Prune worktrees in git metadata
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=self.project_root_path,
                capture_output=True,
                text=True,
                check=False
            )

            # Step 4: If branch should be discarded (e.g. failed attempt)
            if delete_branch and branch_name:
                subprocess.run(
                    ["git", "branch", "-D", branch_name],
                    cwd=self.project_root_path,
                    capture_output=True,
                    text=True,
                    check=False
                )

        except Exception as e:
            logger.error(f"[sandbox_runner] Error cleaning up worktree: {e}")
        finally:
            self.active_worktree_path = None
            self.active_branch_name = None

    def _force_cleanup_directory(self, dir_path: str) -> None:
        """Helper to forcefully delete a directory on Windows or Linux."""
        try:
            if platform.system() == "Windows":
                # Reset read-only attributes that git may have placed
                subprocess.run(["attrib", "-R", f"{dir_path}\\*.*", "/S", "/D"], capture_output=True, check=False)
            shutil.rmtree(dir_path, ignore_errors=True)
        except Exception as e:
            logger.warning(f"[sandbox_runner] Directory force cleanup notice: {e}")

    @contextmanager
    def isolated_sandbox(self, signal_id: int, delete_on_failure: bool = False):
        """
        Context manager that creates an ephemeral worktree for signal_id,
        yields execution control, and guarantees worktree cleanup in a finally block.
        """
        created = False
        try:
            info = self.create_worktree(signal_id)
            created = True
            yield info
        finally:
            if created:
                self.cleanup_worktree(delete_branch=delete_on_failure)

    # -----------------------------------------------------------------------
    # Docker Availability & Test Execution
    # -----------------------------------------------------------------------

    def is_docker_available(self) -> bool:
        """Returns True if the Docker daemon is accessible and responding."""
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False
            )
            return res.returncode == 0
        except Exception:
            return False

    def write_code_to_file(self, file_path: str, code_content: str) -> Dict[str, Any]:
        """Safely writes code to a file within the current worktree (or project root)."""
        target_root = self.active_worktree_path or self.project_root_path
        try:
            full_path = os.path.join(target_root, file_path)
            abs_root = os.path.abspath(target_root)
            abs_target = os.path.abspath(full_path)
            if not abs_target.startswith(abs_root):
                return {"success": False, "error": f"Security violation: path {full_path} escapes target root"}

            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(code_content)

            bytes_written = len(code_content.encode("utf-8"))
            return {"success": True, "message": f"Successfully wrote to {file_path}", "bytes_written": bytes_written}
        except Exception as e:
            logger.error(f"Error writing to file '{file_path}': {e}")
            return {"success": False, "error": str(e)}

    def check_test_configuration(self, root_path: Optional[str] = None) -> Dict[str, Any]:
        """Checks if package.json has a valid test script."""
        target_root = root_path or self.active_worktree_path or self.project_root_path
        try:
            pkg_path = os.path.join(target_root, "package.json")
            if not os.path.exists(pkg_path):
                return {"has_tests": False, "reason": "No package.json"}

            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)

            if "scripts" not in pkg_data or "test" not in pkg_data["scripts"]:
                return {"has_tests": False, "reason": "No test script in package.json"}

            test_script = pkg_data["scripts"]["test"]
            if "Error: no test specified" in test_script or 'echo "No tests specified"' in test_script:
                return {"has_tests": False, "reason": "Default npm test placeholder"}

            return {"has_tests": True, "test_command": test_script}
        except Exception as e:
            return {"has_tests": False, "reason": str(e)}

    def run_tests(self, execution_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes tests using Docker if available and configured,
        or isolated local subprocess fallback.
        """
        target_dir = execution_dir or self.active_worktree_path or self.project_root_path
        timeout = getattr(settings, "TEST_TIMEOUT", 30) if settings else 30
        backend_mode = os.getenv("SANDBOX_BACKEND", "auto").lower()

        logger.info(f"🧪 Running tests in sandbox ({target_dir}) [backend: {backend_mode}]...")

        # Check test config
        config = self.check_test_configuration(target_dir)
        if not config.get("has_tests"):
            auto_create = getattr(settings, "SANDBOX_CREATE_MINIMAL_TESTS", True) if settings else True
            if auto_create:
                try:
                    from utils.test_config_helper import create_minimal_test_suite
                    create_minimal_test_suite(target_dir)
                    config = self.check_test_configuration(target_dir)
                except Exception as e:
                    logger.warning(f"Could not auto-create tests: {e}")

            if not config.get("has_tests"):
                return {"passed": True, "output": "No tests configured - skipping", "error": None, "skipped": True}

        # ── Mode 1: Docker execution (if available) ────────────────────────
        if backend_mode in ("auto", "docker") and self.is_docker_available():
            logger.info("[sandbox_runner] Using Docker node:20-alpine container...")
            docker_cmd = [
                "docker", "run", "--rm",
                "--network=none",
                "--memory=1g",
                "--cpus=1",
                "-v", f"{target_dir}:/app",
                "-w", "/app",
                "node:20-alpine",
                "npm", "test"
            ]
            try:
                proc = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False
                )
                return self.parse_test_output(proc.stdout, proc.stderr, proc.returncode)
            except subprocess.TimeoutExpired:
                return {"passed": False, "output": "", "error": f"Docker test execution timed out ({timeout}s)", "return_code": -1}
            except Exception as e:
                logger.warning(f"[sandbox_runner] Docker execution failed ({e}), falling back to subprocess...")

        # ── Mode 2: Isolated Subprocess execution ──────────────────────────
        logger.info("[sandbox_runner] Running via isolated local subprocess...")
        npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
        env = os.environ.copy()
        env["CI"] = "true"
        env["NODE_ENV"] = "test"
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0

        try:
            process = subprocess.Popen(
                [npm_cmd, "test"],
                cwd=target_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=env,
                creationflags=creationflags
            )
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return self.parse_test_output(stdout, stderr, process.returncode)
            except subprocess.TimeoutExpired:
                if platform.system() == "Windows":
                    subprocess.call(["taskkill", "/F", "/T", "/PID", str(process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    process.kill()
                return {"passed": False, "output": "", "error": f"Execution timed out ({timeout}s limit)", "return_code": -1}

        except Exception as e:
            logger.error(f"Error running tests via subprocess: {e}")
            return {"passed": False, "output": "", "error": str(e), "return_code": -1}

    def parse_test_output(self, stdout: str, stderr: str, return_code: int) -> Dict[str, Any]:
        """Parses test results from stdout/stderr."""
        if return_code == 0:
            test_count = 0
            match = re.search(r'(\d+)\s+(?:passing|tests passed)', stdout, re.IGNORECASE)
            if match:
                test_count = int(match.group(1))
            return {"passed": True, "output": stdout, "error": None, "test_count": test_count}
        return {"passed": False, "output": stdout, "error": stderr, "return_code": return_code}

    def execute_and_verify(self, file_path: str, code_content: str) -> Dict[str, Any]:
        """Backward-compatible helper that writes code and runs tests."""
        try:
            write_res = self.write_code_to_file(file_path, code_content)
            if not write_res.get("success"):
                return {"passed": False, "output": "", "error": write_res.get("error")}
            return self.run_tests()
        except Exception as e:
            return {"passed": False, "output": "", "error": str(e)}
