import logging
from typing import Any, Dict, Optional
from github import Github, GithubException, BadCredentialsException

logger = logging.getLogger(__name__)

class GitHubManager:
    """
    A utility class to manage GitHub repository operations such as creating 
    branches, updating files, and opening pull requests.
    """

    def __init__(self, github_token: str, repo_owner: str, repo_name: str) -> None:
        """
        Initialize the GitHubManager with authentication and repository details.

        Args:
            github_token (str): The personal access token for GitHub.
            repo_owner (str): The owner of the repository (user or organization).
            repo_name (str): The name of the repository.
        """
        self.github_token = github_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_client: Optional[Github] = None
        self.repo = None

    def _format_success(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Helper to format a successful response."""
        return {"success": True, "data": data or {}, "error": None}

    def _format_error(self, error_msg: str) -> Dict[str, Any]:
        """Helper to format an error response."""
        return {"success": False, "data": {}, "error": error_msg}

    def authenticate(self) -> Dict[str, Any]:
        """
        Authenticate to GitHub and create a PyGithub instance.
        
        Returns:
            Dict[str, Any]: Structured response with success status.
        """
        try:
            logger.info("Authenticating with GitHub...")
            self.github_client = Github(self.github_token)
            # Fetch the repo to verify credentials
            self.repo = self.github_client.get_repo(f"{self.repo_owner}/{self.repo_name}")
            logger.info(f"Successfully authenticated and accessed repo: {self.repo_owner}/{self.repo_name}")
            return self._format_success({"repo_full_name": self.repo.full_name})
            
        except BadCredentialsException as e:
            msg = f"Bad credentials: {e}"
            logger.error(msg)
            return self._format_error(msg)
        except GithubException as e:
            msg = f"GitHub API error during authentication: {e}"
            logger.error(msg)
            return self._format_error(msg)
        except Exception as e:
            msg = f"Unexpected error during authentication: {e}"
            logger.error(msg)
            return self._format_error(msg)

    def create_branch(self, base_branch: str, new_branch_name: str) -> Dict[str, Any]:
        """
        Create a new branch from a specified base branch.

        Args:
            base_branch (str): The name of the base branch to branch off of.
            new_branch_name (str): The name of the new branch to create.

        Returns:
            Dict[str, Any]: Structured response with success status.
        """
        try:
            logger.info(f"Creating branch '{new_branch_name}' from '{base_branch}'...")
            base_ref = self.repo.get_branch(base_branch)
            self.repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=base_ref.commit.sha)
            
            logger.info(f"Branch '{new_branch_name}' created successfully.")
            return self._format_success({"branch": new_branch_name})
            
        except GithubException as e:
            msg = f"GitHub API error creating branch: {e}"
            logger.error(msg)
            return self._format_error(msg)
        except Exception as e:
            msg = f"Unexpected error creating branch: {e}"
            logger.error(msg)
            return self._format_error(msg)

    def update_file(self, branch_name: str, file_path: str, new_content: str, commit_message: str) -> Dict[str, Any]:
        """
        Update an existing file or create a new one on a specific branch.

        Args:
            branch_name (str): The branch where the file should be updated.
            file_path (str): The path to the file inside the repository.
            new_content (str): The new string content of the file.
            commit_message (str): The commit message for this change.

        Returns:
            Dict[str, Any]: Structured response with success status.
        """
        try:
            logger.info(f"Updating file '{file_path}' on branch '{branch_name}'...")
            try:
                # Need the existing file's SHA to update it
                file_obj = self.repo.get_contents(file_path, ref=branch_name)
                self.repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=new_content,
                    sha=file_obj.sha,
                    branch=branch_name
                )
                logger.info(f"File '{file_path}' updated successfully.")
                return self._format_success({"file_path": file_path, "action": "updated"})
                
            except GithubException as ce:
                # If the file isn't found, create it instead
                if ce.status == 404:
                    logger.info(f"File '{file_path}' not found, creating a new file...")
                    self.repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=new_content,
                        branch=branch_name
                    )
                    logger.info(f"File '{file_path}' created successfully.")
                    return self._format_success({"file_path": file_path, "action": "created"})
                else:
                    raise ce
                    
        except GithubException as e:
            msg = f"GitHub API error updating file: {e}"
            logger.error(msg)
            return self._format_error(msg)
        except Exception as e:
            msg = f"Unexpected error updating file: {e}"
            logger.error(msg)
            return self._format_error(msg)

    def create_pull_request(self, head_branch: str, base_branch: str, title: str, body: str) -> Dict[str, Any]:
        """
        Open a new pull request against a base branch.

        Args:
            head_branch (str): The name of the branch with the changes.
            base_branch (str): The name of the branch to merge the changes into.
            title (str): The title of the pull request.
            body (str): The description/body of the pull request.

        Returns:
            Dict[str, Any]: Structured response containing the PR URL.
        """
        try:
            logger.info(f"Creating pull request from '{head_branch}' to '{base_branch}'...")
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch
            )
            logger.info(f"Pull request created successfully: {pr.html_url}")
            return self._format_success({"pr_url": pr.html_url, "pr_number": pr.number})
            
        except GithubException as e:
            msg = f"GitHub API error creating PR: {e}"
            logger.error(msg)
            return self._format_error(msg)
        except Exception as e:
            msg = f"Unexpected error creating pull request: {e}"
            logger.error(msg)
            return self._format_error(msg)

    def get_file_content(self, file_path: str, branch: str = 'master') -> Dict[str, Any]:
        """
        Read the current string content of a specific file from a given branch.

        Args:
            file_path (str): The path to the file to read.
            branch (str): The branch to read from. Defaults to 'master'.

        Returns:
            Dict[str, Any]: Structured response containing the file content.
        """
        try:
            logger.info(f"Retrieving content for '{file_path}' from branch '{branch}'...")
            file_obj = self.repo.get_contents(file_path, ref=branch)
            
            # get_contents can return a list if file_path is a directory
            if isinstance(file_obj, list):
                msg = f"Path '{file_path}' is a directory, not a file."
                logger.error(msg)
                return self._format_error(msg)
                
            content = file_obj.decoded_content.decode('utf-8')
            logger.info(f"Successfully retrieved content for '{file_path}'.")
            return self._format_success({"content": content})
            
        except GithubException as e:
            msg = f"GitHub API error getting file content: {e}"
            logger.error(msg)
            return self._format_error(msg)
        except Exception as e:
            msg = f"Unexpected error getting file content: {e}"
            logger.error(msg)
            return self._format_error(msg)

    # -----------------------------------------------------------------------
    # V2 Operations: Issue Tracking, Preview Polling & One-Click Merge
    # -----------------------------------------------------------------------

    def create_issue(self, title: str, body: str, labels: Optional[list] = None) -> Dict[str, Any]:
        """Create a GitHub issue for tracking a feature signal."""
        try:
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels or ["evocode", "autonomous-pr"]
            )
            logger.info(f"Created GitHub Issue #{issue.number}: {issue.html_url}")
            return self._format_success({"issue_number": issue.number, "issue_url": issue.html_url})
        except Exception as e:
            logger.error(f"Error creating GitHub issue: {e}")
            return self._format_error(str(e))

    def poll_vercel_preview_url(self, branch_name: str, max_wait_seconds: int = 60, poll_interval: int = 5) -> Optional[str]:
        """
        Polls the GitHub Deployments API for up to max_wait_seconds
        to capture the Vercel Preview URL associated with branch_name.
        """
        import time
        logger.info(f"Polling Vercel Preview URL for branch '{branch_name}' (up to {max_wait_seconds}s)...")
        start_time = time.time()

        while time.time() - start_time < max_wait_seconds:
            try:
                deployments = self.repo.get_deployments(ref=branch_name)
                for dep in deployments:
                    statuses = dep.get_statuses()
                    for status in statuses:
                        if status.environment_url:
                            logger.info(f"Captured Vercel Preview URL: {status.environment_url}")
                            return status.environment_url
            except Exception as e:
                logger.warning(f"Error querying deployments for '{branch_name}': {e}")

            time.sleep(poll_interval)

        logger.info(f"Vercel Preview URL not detected within {max_wait_seconds}s for branch '{branch_name}'")
        return None

    def merge_pull_request(self, pr_number: int, commit_title: Optional[str] = None, merge_method: str = "squash") -> Dict[str, Any]:
        """Squash-merges the given PR."""
        try:
            pr = self.repo.get_pull(pr_number)
            res = pr.merge(
                commit_title=commit_title or f"Squash merge PR #{pr_number} by EvoCode",
                merge_method=merge_method
            )
            logger.info(f"PR #{pr_number} merged successfully (SHA: {res.sha})")
            return self._format_success({"merged": res.merged, "sha": res.sha})
        except Exception as e:
            logger.error(f"Error merging PR #{pr_number}: {e}")
            return self._format_error(str(e))

    def close_pull_request(self, pr_number: int) -> Dict[str, Any]:
        """Closes a PR without merging."""
        try:
            pr = self.repo.get_pull(pr_number)
            pr.edit(state="closed")
            logger.info(f"PR #{pr_number} closed.")
            return self._format_success({"closed": True})
        except Exception as e:
            logger.error(f"Error closing PR #{pr_number}: {e}")
            return self._format_error(str(e))

    def delete_branch(self, branch_name: str) -> Dict[str, Any]:
        """Deletes a remote feature branch."""
        try:
            ref = self.repo.get_git_ref(f"heads/{branch_name}")
            ref.delete()
            logger.info(f"Remote branch '{branch_name}' deleted successfully.")
            return self._format_success({"deleted": True, "branch": branch_name})
        except Exception as e:
            logger.error(f"Error deleting remote branch '{branch_name}': {e}")
            return self._format_error(str(e))

    def close_issue(self, issue_number: int, comment: Optional[str] = None) -> Dict[str, Any]:
        """Closes a GitHub issue with an optional comment (e.g., Closes #X on auto-ship)."""
        try:
            issue = self.repo.get_issue(issue_number)
            if comment:
                issue.create_comment(comment)
            issue.edit(state="closed")
            logger.info(f"GitHub Issue #{issue_number} closed.")
            return self._format_success({"closed": True, "issue_number": issue_number})
        except Exception as e:
            logger.error(f"Error closing GitHub issue #{issue_number}: {e}")
            return self._format_error(str(e))
