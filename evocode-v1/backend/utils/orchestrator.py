import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from models import IssueReport, FixAttempt, PullRequest

logger = logging.getLogger(__name__)

class FixOrchestrator:
    """
    Central orchestrator that coordinates GitHub interactions, LLM code generation,
    sandbox verification, and Database logging to autonomously resolve bugs.
    """
    
    def __init__(self, github_manager, sandbox_runner, code_fix_agent, db_session: Session):
        self.github = github_manager
        self.sandbox = sandbox_runner
        self.agent = code_fix_agent
        self.db = db_session

    def process_issue(self, issue_id: int) -> Dict[str, Any]:
        """
        Executes the autonomous loop for a given issue ID.
        """
        logger.info(f"Starting orchestration pipeline for issue ID {issue_id}")
        
        # 1. Load IssueReport
        issue = self.db.query(IssueReport).filter(IssueReport.id == issue_id).first()
        if not issue:
            msg = f"Issue {issue_id} not found in database."
            logger.error(msg)
            return {"success": False, "error": msg}

        # Update status to processing
        issue.status = "processing"
        self.db.commit()

        # 2. Read current file content from GitHub
        logger.info(f"Fetching current content for {issue.file_path} from GitHub...")
        file_resp = self.github.get_file_content(issue.file_path, branch="master")
        if not file_resp["success"]:
            issue.status = "failed"
            self.db.commit()
            msg = f"Failed to fetch file from GitHub: {file_resp['error']}"
            logger.error(msg)
            return {"success": False, "error": msg}

        current_code = file_resp["data"]["content"]
        
        # 3. Retry loop (max 3 times)
        max_retries = 3
        passed = False
        final_code = ""
        error_history = ""
        
        for attempt in range(1, max_retries + 1):
            logger.info(f"--- Retry Loop Attempt {attempt}/{max_retries} ---")
            
            # Construct description with error history if applicable
            prompt_description = issue.bug_text
            if error_history:
                prompt_description += f"\n\nYOUR PREVIOUS FIX FAILED. THE TEST LOGS RETURNED:\n{error_history}\n\nPlease fix the code according to these errors."
                
            # a. Generate fix using code_fix_agent
            logger.info("Generating code fix...")
            raw_response = self.agent.generate_fix(prompt_description, current_code)
            extracted_code = self.agent.extract_code_from_response(raw_response)
            
            # c. Test the new code using sandbox_runner
            logger.info("Testing generated code in sandbox...")
            test_result = self.sandbox.execute_and_verify(issue.file_path, extracted_code)
            
            # b. Save FixAttempt to database
            fix_attempt = FixAttempt(
                issue_id=issue.id,
                attempt_number=attempt,
                generated_code=extracted_code,
                test_passed=test_result["passed"],
                error_logs=test_result["output"] if not test_result["passed"] else "Success."
            )
            self.db.add(fix_attempt)
            self.db.commit()

            # d. Check loop condition
            if test_result["passed"]:
                logger.info(f"Attempt {attempt} passed the sandbox validation!")
                passed = True
                final_code = extracted_code
                break
            else:
                # e. Fail, append error logs
                logger.warning(f"Attempt {attempt} failed validation. Extracting logs for next retry...")
                error_history = test_result["output"]

        # 4. Result branching
        if passed:
            logger.info("Tests verified successfully. Synchronizing with GitHub...")
            try:
                branch_name = f"fix-issue-{issue_id}"
                
                # a. Create a branch
                b_res = self.github.create_branch(base_branch="master", new_branch_name=branch_name)
                if not b_res["success"]:
                    raise Exception(f"Branch creation failed: {b_res['error']}")
                
                # b. Update the file on GitHub
                commit_msg = f"Automated fix for issue #{issue_id}: {issue.bug_text}"
                u_res = self.github.update_file(
                    branch_name=branch_name,
                    file_path=issue.file_path,
                    new_content=final_code,
                    commit_message=commit_msg
                )
                if not u_res["success"]:
                    raise Exception(f"File update failed: {u_res['error']}")
                
                # c. Create a Pull Request
                pr_title = f"Automated Fix for Issue #{issue_id}"
                pr_body = f"EvoCode automatically resolved this issue.\n\nBug description: {issue.bug_text}"
                pr_res = self.github.create_pull_request(
                    head_branch=branch_name,
                    base_branch="master",
                    title=pr_title,
                    body=pr_body
                )
                if not pr_res["success"]:
                    raise Exception(f"PR creation failed: {pr_res['error']}")
                
                pr_url = pr_res["data"]["pr_url"]
                
                # d. Save PullRequest record
                pr_record = PullRequest(
                    issue_id=issue.id,
                    pr_url=pr_url,
                    branch_name=branch_name,
                    status="completed"
                )
                self.db.add(pr_record)
                
                # e. Update IssueReport status
                issue.status = "completed"
                self.db.commit()
                
                logger.info(f"Issue {issue_id} successfully processed. PR created: {pr_url}")
                return {"success": True, "pr_url": pr_url}
                
            except Exception as e:
                logger.error(f"Post-processing failed after sandbox success: {e}")
                issue.status = "failed"
                self.db.commit()
                return {"success": False, "error": str(e)}
        else:
            # 5. Failed all 3 retries
            logger.error(f"Issue {issue_id} exhausted all {max_retries} retries and failed sandbox validation.")
            issue.status = "failed"
            self.db.commit()
            return {"success": False, "error": "All fix attempts failed sandbox validation."}
