"""
backend/test_complete_flow.py

Run this script from the backend/ directory to verify the entire
sandbox execution pipeline works before a demo:

    cd evocode-v1/backend
    python test_complete_flow.py
"""
import os
import sys
import io

# Ensure UTF-8 output on Windows terminals that default to cp1252
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


from dotenv import load_dotenv
load_dotenv()

from utils.sandbox_runner import SandboxRunner
from utils.test_config_helper import create_minimal_test_suite
from utils.system_checks import get_system_info, check_npm_installed, check_node_installed, validate_project_structure


def test_complete_flow():
    """
    Test the complete sandbox execution flow
    """
    print("🧪 Testing EvoCode Complete Flow\n")
    
    # ── Step 1: System checks ────────────────────────────────────────────────
    print("1️⃣  Checking system requirements...")
    system_info = get_system_info()
    print(f"   OS:   {system_info.get('os_type')}")
    print(f"   Node: {system_info.get('node_version', '❌ Not found')}")
    print(f"   npm:  {system_info.get('npm_version',  '❌ Not found')}")

    if not check_node_installed():
        print("   ❌ Node.js is not installed — cannot proceed.")
        return False
    if not check_npm_installed():
        print("   ❌ npm is not installed — cannot proceed.")
        return False
    print("   ✅ Node + npm OK")

    # ── Step 2: Project setup ────────────────────────────────────────────────
    print("\n2️⃣  Validating project setup...")
    project_path = os.getenv("REPO_PATH", "../evocode-test-target")
    print(f"   Project path: {project_path}")

    if not os.path.exists(project_path):
        print("   ❌ Project path does not exist!")
        return False
    print("   ✅ Project path exists")

    struct = validate_project_structure(project_path)
    if struct["issues"]:
        for issue in struct["issues"]:
            print(f"   ❌ {issue}")
        return False
    for warning in struct.get("warnings", []):
        print(f"   ⚠️  {warning}")
    print("   ✅ Project structure valid")

    # ── Step 3: Test configuration ───────────────────────────────────────────
    print("\n3️⃣  Checking test configuration...")
    created = create_minimal_test_suite(project_path)
    if created:
        print("   ✅ Test suite configured")
    else:
        print("   ⚠️  Could not auto-configure test suite (will still try to run)")

    # ── Step 4: Create sandbox runner ────────────────────────────────────────
    print("\n4️⃣  Creating sandbox runner...")
    try:
        sandbox = SandboxRunner(project_root_path=project_path)
        print("   ✅ Sandbox runner created")
    except Exception as e:
        print(f"   ❌ Failed to create sandbox: {e}")
        return False

    # ── Step 5: Test file writing ────────────────────────────────────────────
    print("\n5️⃣  Testing file write...")
    test_code = """export default function TestComponent() {
    return <div>Test</div>;
}
"""
    result = sandbox.write_code_to_file("test-file.jsx", test_code)
    if result["success"]:
        print(f"   ✅ File written: {result['bytes_written']} bytes")
    else:
        print(f"   ❌ Write failed: {result['error']}")
        return False

    # ── Step 6: Test execution ───────────────────────────────────────────────
    print("\n6️⃣  Testing test execution...")
    test_result = sandbox.run_tests()

    if test_result.get("skipped"):
        print(f"   ⚠️  Tests skipped: {test_result['output']}")
    elif test_result["passed"]:
        count = test_result.get("test_count")
        suffix = f" ({count} tests)" if count else ""
        print(f"   ✅ Tests passed{suffix}")
    else:
        print(f"   ❌ Tests failed")
        print(f"   Error: {test_result.get('error', 'Unknown')}")
        if test_result.get("output"):
            print("\n   --- Test Output ---")
            for line in test_result["output"].splitlines()[:20]:
                print(f"   {line}")

    # ── Step 7: Cleanup ──────────────────────────────────────────────────────
    print("\n7️⃣  Cleaning up...")
    test_file = os.path.join(project_path, "test-file.jsx")
    if os.path.exists(test_file):
        os.remove(test_file)
        print("   ✅ Test file removed")
    else:
        print("   ℹ️  No test file to clean up")

    print("\n✅ Complete flow test finished!")
    return True


if __name__ == "__main__":
    success = test_complete_flow()
    sys.exit(0 if success else 1)
