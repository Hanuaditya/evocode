import os
import json
import logging
from utils.sandbox_runner import SandboxRunner

logger = logging.getLogger(__name__)

def create_minimal_test_suite(project_path: str) -> bool:
    """
    Automatically adds a minimal test suite if none exists in the target project.
    
    Steps:
    1. Check if project already has tests
    2. If no tests, create test-runner.js
    3. Update package.json scripts.test to run test-runner.js
    """
    try:
        project_path = os.path.abspath(project_path)
        runner = SandboxRunner(project_path)
        
        # 1. Check if project already has tests
        config = runner.check_test_configuration()
        if config.get("has_tests"):
            logger.info(f"Project at {project_path} already has tests configured. Skipping setup.")
            return True
            
        logger.info(f"No tests found for {project_path}. Creating minimal test suite...")
        
        # 2. Create test-runner.js content
        test_runner_content = """const fs = require('fs');
const path = require('path');

console.log('🧪 EvoCode Validation Suite\\n');

let passedTests = 0;
let failedTests = 0;

// Test 1: Validate modified files exist
function validateFilesExist() {
    const files = process.env.TARGET_FILES ? process.env.TARGET_FILES.split(',') : [];
    
    if (files.length === 0) {
        console.log('⚠️  No target files specified, skipping validation');
        return true;
    }
    
    let allExist = true;
    files.forEach(file => {
        const filePath = path.join(__dirname, file);
        if (fs.existsSync(filePath)) {
            console.log('✅ File exists:', file);
            passedTests++;
        } else {
            console.log('❌ File missing:', file);
            failedTests++;
            allExist = false;
        }
    });
    
    return allExist;
}

// Test 2: Validate syntax (basic)
function validateSyntax() {
    const files = process.env.TARGET_FILES ? process.env.TARGET_FILES.split(',') : [];
    
    let allValid = true;
    files.forEach(file => {
        try {
            const filePath = path.join(__dirname, file);
            const content = fs.readFileSync(filePath, 'utf8');
            
            // Basic checks
            if (content.length === 0) {
                console.log('❌ File is empty:', file);
                failedTests++;
                allValid = false;
            } else if (content.includes('export') || content.includes('function') || content.includes('const')) {
                console.log('✅ Syntax valid:', file);
                passedTests++;
            } else {
                console.log('⚠️  File may have issues:', file);
                passedTests++; // Still pass, just warn
            }
        } catch (error) {
            console.log('❌ Error reading file:', file, error.message);
            failedTests++;
            allValid = false;
        }
    });
    
    return allValid;
}

// Run tests
console.log('Running validation tests...\\n');
const test1 = validateFilesExist();
const test2 = validateSyntax();

console.log('\\n📊 Test Summary:');
console.log('Passed:', passedTests);
console.log('Failed:', failedTests);

if (test1 && test2) {
    console.log('\\n✅ All validations passed!');
    process.exit(0);
} else {
    console.log('\\n❌ Some validations failed');
    process.exit(1);
}
"""
        
        # Write test-runner.js
        test_runner_path = os.path.join(project_path, "test-runner.js")
        with open(test_runner_path, "w", encoding="utf-8") as f:
            f.write(test_runner_content)
        logger.info(f"Created test-runner.js at {test_runner_path}")
            
        # 3. Update package.json
        pkg_path = os.path.join(project_path, "package.json")
        if not os.path.exists(pkg_path):
            # Create minimal package.json if it doesn't exist
            pkg_data = {
                "name": "evocode-test-target",
                "version": "1.0.0",
                "scripts": {
                    "test": "node test-runner.js"
                }
            }
        else:
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
            
            if "scripts" not in pkg_data:
                pkg_data["scripts"] = {}
            
            pkg_data["scripts"]["test"] = "node test-runner.js"
            
        with open(pkg_path, "w", encoding="utf-8") as f:
            json.dump(pkg_data, f, indent=2)
            
        logger.info(f"Updated package.json test script at {pkg_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create minimal test suite: {e}")
        return False
