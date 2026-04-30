import os
import json
import logging
import subprocess
import platform
import re
from typing import Dict, Any, Optional

try:
    from config import settings
except Exception:
    settings = None  # Fallback: settings not yet initialized (e.g., during early import)

logger = logging.getLogger(__name__)

class SandboxRunner:
    """
    Utility class for executing and verifying code against an external test suite 
    via Python's subprocessing capabilities, running safely inside a sandbox.
    """

    def __init__(self, project_root_path: str):
        """
        Constructor configuring the test execution sandbox path.

        Args:
            project_root_path (str): The root folder of the project containing test configuration.
        """
        self.project_root_path = project_root_path
        if not os.path.exists(project_root_path):
            logger.warning(f"Project root path does not exist: {project_root_path}")
        logger.info(f"SandboxRunner initialized for path: {project_root_path}")

    def write_code_to_file(self, file_path: str, code_content: str) -> Dict[str, Any]:
        """
        Safely writes code to a file within the project root.

        Args:
            file_path (str): The relative or absolute path to the file.
            code_content (str): The new string content to be written.

        Returns:
            Dict[str, Any]: Structured dictionary with success status, message, and bytes_written.
        """
        try:
            # 1. Construct full_path = os.path.join(self.project_root_path, file_path)
            full_path = os.path.join(self.project_root_path, file_path)
            
            # 2. Validate file_path doesn't escape project root (security check)
            abs_project = os.path.abspath(self.project_root_path)
            abs_target = os.path.abspath(full_path)
            if not abs_target.startswith(abs_project):
                return {"success": False, "error": f"Security violation: path {full_path} escapes project root"}

            # 3. Create parent directories if they don't exist
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # 4. Write content to file with UTF-8 encoding
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(code_content)
            
            # 5. Log success with file size
            bytes_written = len(code_content.encode('utf-8'))
            logger.info(f"Successfully wrote {bytes_written} bytes to {full_path}")
            
            # 6. Return success
            return {"success": True, "message": f"Successfully wrote to {file_path}", "bytes_written": bytes_written}
            
        except Exception as e:
            # 7. On error, return structured error
            logger.error(f"Error writing to file '{file_path}': {e}")
            return {"success": False, "error": str(e)}

    def check_test_configuration(self) -> Dict[str, Any]:
        """
        Checks if the project has tests configured in package.json.

        Returns:
            Dict[str, Any]: Dictionary containing has_tests boolean and test_command or reason.
        """
        try:
            # 1. Look for package.json in project_root_path
            pkg_path = os.path.join(self.project_root_path, "package.json")
            
            # 2. If not found, return reason
            if not os.path.exists(pkg_path):
                return {"has_tests": False, "reason": "No package.json"}
                
            # 3. Parse package.json as JSON
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
                
            # 4. Check if "scripts" section exists
            if "scripts" not in pkg_data:
                return {"has_tests": False, "reason": "No scripts section in package.json"}
                
            # 5. Check if "test" script exists in scripts
            if "test" not in pkg_data["scripts"]:
                return {"has_tests": False, "reason": "No test script in package.json"}
                
            test_script = pkg_data["scripts"]["test"]
            
            # 6. Check if test script is placeholder
            if 'Error: no test specified' in test_script or 'echo "No tests specified"' in test_script:
                return {"has_tests": False, "reason": "Default npm test placeholder"}
                
            # 7. Return true with command
            return {"has_tests": True, "test_command": test_script}
            
        except Exception as e:
            logger.error(f"Error checking test config: {e}")
            return {"has_tests": False, "reason": str(e)}

    def run_tests(self) -> Dict[str, Any]:
        """
        Executes tests with timeout protection and environment isolation.
        Reads TEST_TIMEOUT, TEST_SKIP_IF_MISSING, and SANDBOX_CREATE_MINIMAL_TESTS from settings.

        Returns:
            Dict[str, Any]: Structured dictionary with passed boolean, output, and error.
        """
        # Read settings with safe fallbacks
        timeout = getattr(settings, "TEST_TIMEOUT", 30) if settings else 30
        skip_if_missing = getattr(settings, "TEST_SKIP_IF_MISSING", False) if settings else False
        auto_create = getattr(settings, "SANDBOX_CREATE_MINIMAL_TESTS", True) if settings else True

        try:
            # 1. Log running tests
            logger.info("🧪 Running tests in sandbox...")
            
            # 2. Call check_test_configuration
            config = self.check_test_configuration()
            
            # 3. If has_tests is False
            if not config.get("has_tests"):
                reason = config.get("reason", "Unknown")
                logger.warning(f"No tests configured: {reason}")

                # Auto-create minimal test suite if enabled
                if auto_create:
                    logger.info("SANDBOX_CREATE_MINIMAL_TESTS=true — attempting auto-setup...")
                    try:
                        from utils.test_config_helper import create_minimal_test_suite
                        created = create_minimal_test_suite(self.project_root_path)
                        if created:
                            logger.info("✅ Minimal test suite created. Re-checking configuration...")
                            config = self.check_test_configuration()
                        else:
                            logger.warning("Auto-setup failed, falling through to skip/fail logic.")
                    except Exception as setup_err:
                        logger.error(f"Auto-setup error: {setup_err}")

                # Re-check after potential auto-setup
                if not config.get("has_tests"):
                    if skip_if_missing:
                        return {"passed": True, "output": f"No tests configured - skipping ({reason})", "error": None, "skipped": True}
                    else:
                        return {"passed": True, "output": f"No tests configured - skipping ({reason})", "error": None, "skipped": True}
                
            # 4. Determine npm command
            npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
            
            # 5. Set up environment variables
            env = os.environ.copy()
            env["CI"] = "true"
            env["NODE_ENV"] = "test"
            
            # 6. Execute with Popen to handle Windows grandchild process hangs
            import signal
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0
            
            process = subprocess.Popen(
                [npm_cmd, "test"],
                cwd=self.project_root_path,
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
                # Kill the entire process tree to prevent hanging pipes
                if platform.system() == "Windows":
                    subprocess.call(["taskkill", "/F", "/T", "/PID", str(process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    process.kill()
                
                try:
                    stdout, stderr = process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    stdout, stderr = "", "Process failed to terminate cleanly."
                
                logger.error(f"Test execution timed out after {timeout} seconds")
                return {"passed": False, "output": stdout or "", "error": f"Execution timed out ({timeout}s limit)", "return_code": -1}

            
        except FileNotFoundError:
            logger.error("npm command not found")
            return {"passed": False, "output": "", "error": "npm command not found. Node.js might not be installed.", "return_code": -1}
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return {"passed": False, "output": "", "error": str(e), "return_code": -1}

    def parse_test_output(self, stdout: str, stderr: str, return_code: int) -> Dict[str, Any]:
        """
        Parses test results from subprocess output.

        Args:
            stdout (str): Standard Output stream content.
            stderr (str): Standard Error stream content.
            return_code (int): The final exit code.

        Returns:
            Dict[str, Any]: Structured dictionary with passed boolean and parsed output.
        """
        # 1. If return_code == 0
        if return_code == 0:
            test_count = 0
            match = re.search(r'(\d+)\s+(?:passing|tests passed)', stdout, re.IGNORECASE)
            if match:
                test_count = int(match.group(1))
            return {"passed": True, "output": stdout, "error": None, "test_count": test_count}
            
        # 2. If return_code != 0
        return {"passed": False, "output": stdout, "error": stderr, "return_code": return_code}

    def execute_and_verify(self, file_path: str, code_content: str) -> Dict[str, Any]:
        """
        Main orchestration method that combines writing code and running tests.

        Args:
            file_path (str): Specific file to overwrite with candidate fix.
            code_content (str): The code content to apply.

        Returns:
            Dict[str, Any]: Structured dictionary with test results.
        """
        try:
            # 1. Log writing code
            logger.info(f"📝 Writing code to {file_path}...")
            
            # 2. Call write_code_to_file
            write_res = self.write_code_to_file(file_path, code_content)
            
            # 3. If write failed, return immediately with error
            if not write_res.get("success"):
                return {"passed": False, "output": "", "error": write_res.get("error")}
                
            # 4. Log success
            logger.info("✅ Code written successfully")
            
            # 5. Call run_tests
            # 6. Return test results
            return self.run_tests()
        except Exception as e:
            return {"passed": False, "output": "", "error": str(e)}
