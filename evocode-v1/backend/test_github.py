import os
import time
import logging
from dotenv import load_dotenv
from utils.github_manager import GitHubManager

# Configure logging for the script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Load environment variables from .env
    load_dotenv()
    
    github_token = os.getenv("GITHUB_TOKEN")
    repo_owner = os.getenv("REPO_OWNER")
    repo_name = os.getenv("REPO_NAME")
    target_file_path = os.getenv("TARGET_FILE_PATH")
    
    if not all([github_token, repo_owner, repo_name, target_file_path]):
        logger.error("Missing required environment variables. Please configure your .env file.")
        return

    # Initialize GitHubManager
    gm = GitHubManager(
        github_token=github_token,
        repo_owner=repo_owner,
        repo_name=repo_name
    )

    # 1. Authenticate
    logger.info("--- Step 1: Authenticate ---")
    auth_resp = gm.authenticate()
    if not auth_resp["success"]:
        logger.error(f"Authentication failed: {auth_resp['error']}")
        return
        
    logger.info(f"Authenticated successfully: {auth_resp['data'].get('repo_full_name')}")

    # Set workflow parameters
    base_branch = "master"
    timestamp = int(time.time())
    new_branch = f"test-fix-{timestamp}"

    # 2. Create new branch
    logger.info(f"--- Step 2: Create new branch ({new_branch}) ---")
    branch_resp = gm.create_branch(base_branch=base_branch, new_branch_name=new_branch)
    if not branch_resp["success"]:
        logger.error(f"Failed to create branch: {branch_resp['error']}")
        # Some repos use 'main' as default. Providing a helpful hint.
        logger.info("Hint: If your default branch is 'main', please update 'base_branch' in this script manually.")
        return
    
    # 3. Read current file content
    logger.info(f"--- Step 3: Read current file content ({target_file_path}) ---")
    read_resp = gm.get_file_content(file_path=target_file_path, branch=base_branch)
    if not read_resp["success"]:
        logger.error(f"Failed to read file '{target_file_path}': {read_resp['error']}")
        return
        
    current_content = read_resp["data"]["content"]
    
    # 4. Update the file
    logger.info("--- Step 4: Update the file ---")
    new_content = "// Test fix applied by EvoCode\n" + current_content
    commit_msg = "test: apply automated EvoCode test fix"
    
    update_resp = gm.update_file(
        branch_name=new_branch,
        file_path=target_file_path,
        new_content=new_content,
        commit_message=commit_msg
    )
    if not update_resp["success"]:
        logger.error(f"Failed to update file: {update_resp['error']}")
        return

    # 5. Create Pull Request
    logger.info("--- Step 5: Create Pull Request ---")
    pr_title = "Test PR from EvoCode"
    pr_body = "This is an automated pull request created by the EvoCode testing script."
    
    pr_resp = gm.create_pull_request(
        head_branch=new_branch,
        base_branch=base_branch,
        title=pr_title,
        body=pr_body
    )
    
    if not pr_resp["success"]:
        logger.error(f"Failed to create PR: {pr_resp['error']}")
        return

    # Success output
    logger.info("--- SUCCESS ---")
    print(f"\nFull workflow completed successfully!")
    print(f"Pull Request URL: {pr_resp['data'].get('pr_url')}")

if __name__ == "__main__":
    main()
