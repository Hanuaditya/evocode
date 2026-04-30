import os
import logging
from dotenv import load_dotenv
from utils.langchain_agent import CodeFixAgent
from utils.sandbox_runner import SandboxRunner

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", "test-target"))
    
    # The target file for our sandboxed practice environment
    # We hardcode it here instead of using ENV to ensure the sandbox test points directly at our broken checkout.js
    target_file = "src/checkout.js"
    abs_target_path = os.path.join(project_root, target_file)
    
    logger.info("Initializing LangChain Agent and SandboxRunner...")
    agent = CodeFixAgent()
    sandbox = SandboxRunner(project_root_path=project_root)
    
    logger.info(f"Reading target buggy file: {abs_target_path}")
    try:
        with open(abs_target_path, "r", encoding="utf-8") as f:
            broken_code = f.read()
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        return
        
    bug_description = "The user object is null causing a crash when trying to access user.email."
    
    logger.info("\n--- Querying LLM to generate fix (Expect 3-5s delay) ---")
    raw_response = agent.generate_fix(bug_description, broken_code)
    
    # Strip away any markdown logic
    extracted_code = agent.extract_code_from_response(raw_response)
    
    logger.info("\n================ GENERATED FIX ================")
    print(extracted_code)
    logger.info("===============================================\n")
    
    logger.info("Passing generated fix directly to SandboxRunner...")
    result = sandbox.execute_and_verify(target_file, extracted_code)
    
    logger.info("\n============== FINAL SANDBOX RESULT ==============")
    logger.info(f"Passed: {result['passed']}")
    if result['error']:
        logger.error(f"Error: {result['error']}")
    
    # Printing tail-end of output for quick validation
    log_snip = result['output'][-1500:] if len(result['output']) > 1500 else result['output']
    logger.info(f"Detailed Output snippet:\n{log_snip}\n")
    logger.info("==================================================")
    
if __name__ == "__main__":
    main()
