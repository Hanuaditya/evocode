import os
import subprocess
import logging
from utils.sandbox_runner import SandboxRunner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

def setup_dummy_repo(project_root: str):
    """Ensure dependencies and minimal Babel config are in place so Jest can parse React."""
    logger.info("Setting up dummy repo test environment (NPM installing, please wait)...")
    
    # 1. Install dependencies required for the dummy React tests to run
    install_cmd = "npm install && npm install --save-dev @babel/preset-env @babel/preset-react jest-environment-jsdom @testing-library/react react react-dom"
    subprocess.run(install_cmd, shell=True, cwd=project_root)
    
    # 2. Write basic babel config
    babelrc_path = os.path.join(project_root, ".babelrc")
    with open(babelrc_path, "w", encoding="utf-8") as f:
         f.write('{"presets": ["@babel/preset-env", ["@babel/preset-react", {"runtime": "automatic"}]]}')
         
    # 3. Write basic jest config
    jest_config_path = os.path.join(project_root, "jest.config.js")
    with open(jest_config_path, "w", encoding="utf-8") as f:
         f.write('module.exports = { testEnvironment: "jsdom" };')

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", "test-target"))
    target_file = "src/checkout.js" # Path adapted for our local evocode dummy structure
    
    logger.info(f"Targeting test sandbox at: {project_root}")
    
    # Pre-flight check
    setup_dummy_repo(project_root)

    sandbox = SandboxRunner(project_root_path=project_root)
    
    logger.info("\n==========================================")
    logger.info("       SCENARIO 1: FAILURE TEST")
    logger.info("==========================================")
    broken_code = """import React from 'react';

// Blatant syntax error
const x = ;

function Checkout({ user }) {
  return <div>Checkout</div>;
}

export default Checkout;
"""
    
    result_fail = sandbox.execute_and_verify(target_file, broken_code)
    logger.info(f"Passed: {result_fail['passed']}")
    if result_fail['error']:
        logger.error(f"Error returned: {result_fail['error']}")
    logger.info(f"Detailed Output:\n{result_fail['output'][:1500]}...\n") 
    
    assert result_fail['passed'] is False, "Failure scenario should NOT have passed!"
    logger.info("✅ FAILING TARGET SUCCESSFULLY REJECTED BY SANDBOX!")
    
    
    logger.info("\n==========================================")
    logger.info("       SCENARIO 2: SUCCESS TEST")
    logger.info("==========================================")
    # Valid component satisfying my exact scaffolded Jest assertions
    fixed_code = """import React from 'react';

function Checkout({ user, order }) {
  return (
    <div className="checkout-container">
      <h2>Checkout Summary</h2>
      <p>Billing Email: {user?.email}</p>
      <p>Order Total: ${order ? order.total : 0}</p>
    </div>
  );
}

export default Checkout;
"""
    
    result_success = sandbox.execute_and_verify(target_file, fixed_code)
    logger.info(f"Passed: {result_success['passed']}")
    if result_success['error']:
        logger.error(f"Error returned: {result_success['error']}")
    logger.info(f"Detailed Output:\n{result_success['output']}")
    
    assert result_success['passed'] is True, "Success scenario INCORRECTLY FAILED! Tests did not pass."
    logger.info("✅ FIXED CODE SUCCESSFULLY VERIFIED BY SANDBOX!")


if __name__ == "__main__":
    main()
