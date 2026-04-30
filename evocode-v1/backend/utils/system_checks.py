import os
import subprocess
import platform
import logging
import json
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

def check_npm_installed() -> bool:
    """
    Check if npm is installed and accessible in the system path.
    """
    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
    try:
        result = subprocess.run([npm_cmd, "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info(f"npm installed. Version: {result.stdout.strip()}")
            return True
        return False
    except Exception as e:
        logger.warning(f"npm check failed: {e}")
        return False

def check_node_installed() -> bool:
    """
    Check if Node.js is installed and accessible in the system path.
    """
    node_cmd = "node.exe" if platform.system() == "Windows" else "node"
    try:
        result = subprocess.run([node_cmd, "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info(f"Node.js installed. Version: {result.stdout.strip()}")
            return True
        return False
    except Exception as e:
        logger.warning(f"Node.js check failed: {e}")
        return False

def validate_project_structure(project_path: str) -> Dict[str, Any]:
    """
    Validate the target project is properly set up.
    
    Checks:
    1. Path exists
    2. package.json exists
    3. node_modules exists (dependencies installed)
    4. Has valid Next.js/React structure
    """
    issues: List[str] = []
    warnings: List[str] = []
    
    # 1. Path exists
    if not os.path.exists(project_path):
        issues.append(f"Project path does not exist: {project_path}")
        return {"valid": False, "issues": issues, "warnings": warnings}
        
    # 2. package.json exists
    pkg_path = os.path.join(project_path, "package.json")
    if not os.path.isfile(pkg_path):
        issues.append("package.json not found in the project root")
    
    # 3. node_modules exists
    if not os.path.isdir(os.path.join(project_path, "node_modules")):
        warnings.append("node_modules directory is missing (dependencies might not be installed)")
        
    # 4. Has valid Next.js/React structure
    has_app = os.path.isdir(os.path.join(project_path, "app"))
    has_pages = os.path.isdir(os.path.join(project_path, "pages"))
    has_src = os.path.isdir(os.path.join(project_path, "src"))
    
    if not (has_app or has_pages or has_src):
        warnings.append("Could not identify typical Next.js/React source directories (app, pages, or src)")
        
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings
    }

def get_system_info(project_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Gather comprehensive system information for debugging and initialization.
    """
    info = {
        "os_type": platform.system(),
        "python_version": platform.python_version(),
        "node_version": None,
        "npm_version": None,
        "project_path": project_path,
        "has_tests_configured": False
    }
    
    # Get node version
    node_cmd = "node.exe" if platform.system() == "Windows" else "node"
    try:
        res = subprocess.run([node_cmd, "--version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            info["node_version"] = res.stdout.strip()
    except Exception:
        pass
        
    # Get npm version
    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
    try:
        res = subprocess.run([npm_cmd, "--version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            info["npm_version"] = res.stdout.strip()
    except Exception:
        pass
        
    # Check test configuration if project path provided
    if project_path and os.path.isfile(os.path.join(project_path, "package.json")):
        try:
            with open(os.path.join(project_path, "package.json"), "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
                scripts = pkg_data.get("scripts", {})
                test_script = scripts.get("test", "")
                if test_script and 'Error: no test specified' not in test_script and 'echo "No tests specified"' not in test_script:
                    info["has_tests_configured"] = True
        except Exception:
            pass
            
    return info
