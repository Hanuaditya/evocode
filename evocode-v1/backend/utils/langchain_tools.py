"""
backend/utils/langchain_tools.py

Centralized LangChain @tool definitions available to the CodeAgentWithTools.

Tools:
  - read_file       : Read any file inside the repo safely
  - write_file      : Overwrite a file inside the repo (with path traversal guard)
  - list_directory  : List entries inside a repo directory
  - search_codebase : Search for a string pattern across the repo

All tools enforce a REPO_PATH boundary so the agent cannot escape the repository.

CRITICAL: Explicit args_schema (Pydantic) is required for Gemini to avoid
          MALFORMED_FUNCTION_CALL errors during tool-use agentic loops.
"""

import os
import re
import fnmatch
import logging
from typing import Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_repo_path() -> str:
    """Return the absolute, normalised repo root from the environment."""
    repo_path = os.getenv("REPO_PATH", ".")
    return os.path.abspath(repo_path)


def _safe_resolve(filepath: str) -> tuple[str, str | None]:
    """
    Resolve *filepath* relative to REPO_PATH and verify it stays inside.

    Returns:
        (full_path, None)        on success
        ("",       error_msg)    when the path escapes the repo boundary
    """
    repo_root = _get_repo_path()
    full_path = os.path.abspath(os.path.join(repo_root, filepath))

    if not full_path.startswith(repo_root + os.sep) and full_path != repo_root:
        error = (
            f"❌ Security error: '{filepath}' resolves outside the repository root "
            f"('{repo_root}'). Operation blocked."
        )
        logger.warning(f"[langchain_tools] Path traversal attempt blocked: {filepath!r}")
        return "", error

    return full_path, None


# ---------------------------------------------------------------------------
# Pydantic schemas — Gemini requires explicit args_schema to generate valid
# tool-call JSON. Without these, Gemini emits MALFORMED_FUNCTION_CALL.
# ---------------------------------------------------------------------------

class ReadFileInput(BaseModel):
    """Input schema for reading a file."""
    filepath: str = Field(
        description=(
            "Relative path from the repository root to the file you want to read. "
            "Example: 'app/components/About.jsx'. "
            "Must NOT start with '/' or contain '..' path traversal."
        )
    )


class WriteFileInput(BaseModel):
    """Input schema for writing / overwriting a file."""
    filepath: str = Field(
        description=(
            "Relative path from the repository root to the file you want to write. "
            "Example: 'app/components/About.jsx'. "
            "Must NOT start with '/' or contain '..' path traversal."
        )
    )
    content: str = Field(
        description=(
            "Complete, valid file content to write. "
            "MUST include the entire file — never a partial snippet. "
            "Preserve original indentation and line endings."
        )
    )


class ListDirectoryInput(BaseModel):
    """Input schema for listing directory contents."""
    dirpath: str = Field(
        default=".",
        description=(
            "Relative path to the directory inside the repository. "
            "Use '.' to list the repository root."
        )
    )


class ReplaceInFileInput(BaseModel):
    """Input schema for surgically replacing text in a file."""
    file_path: str = Field(
        description="Relative path from the repository root to the file you want to edit."
    )
    exact_old_text: str = Field(
        description="The original text to be replaced. Must match the file content."
    )
    new_text: str = Field(
        description="The new text to insert in its place."
    )


class SearchCodebaseInput(BaseModel):
    """Input schema for searching the codebase for a text pattern."""
    query: str = Field(
        description="The text string or keyword to search for across files."
    )
    file_pattern: Optional[str] = Field(
        default="*",
        description=(
            "Glob pattern to restrict which files are searched. "
            "Examples: '*.jsx', '*.py', '*.ts'. Defaults to all files ('*')."
        )
    )


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

@tool(args_schema=ReadFileInput)
def read_file(filepath: str) -> str:
    """
    Read the full text content of a file inside the repository.

    Always call this tool BEFORE writing to any file so you have the current
    state of the code and can avoid overwriting unrelated logic.
    """
    try:
        full_path, err = _safe_resolve(filepath)
        if err:
            return err

        if not os.path.isfile(full_path):
            return f"❌ File not found: '{filepath}' (resolved to '{full_path}')"

        with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()

        logger.info(f"[read_file] Read {len(content):,} chars from {filepath!r}")
        return content

    except Exception as exc:
        error_msg = f"❌ Error reading '{filepath}': {exc}"
        logger.error(f"[langchain_tools] {error_msg}")
        return error_msg


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------

@tool(args_schema=WriteFileInput)
def write_file(filepath: str, content: str) -> str:
    """
    Overwrite a file in the repository with new code.

    Use this tool ONLY after you have:
      1. Read the current file with read_file.
      2. Generated the COMPLETE updated file content.
      3. Verified the code is syntactically correct.

    Do NOT write partial files — always provide the full file content.
    """
    try:
        # Security: block path traversal outside the repo
        full_path, err = _safe_resolve(filepath)
        if err:
            return err

        # Create parent directories if they don't exist yet
        parent_dir = os.path.dirname(full_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Write the file
        with open(full_path, "w", encoding="utf-8") as fh:
            fh.write(content)

        byte_count = len(content.encode("utf-8"))
        logger.info(
            f"[write_file] ✅ Modified {filepath!r} — "
            f"{len(content):,} chars / {byte_count:,} bytes"
        )
        return (
            f"✅ Successfully wrote {len(content):,} chars "
            f"({byte_count:,} bytes) to '{filepath}'"
        )

    except Exception as exc:
        error_msg = f"❌ Error writing '{filepath}': {exc}"
        logger.error(f"[langchain_tools] {error_msg}")
        return error_msg


# ---------------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------------

@tool(args_schema=ListDirectoryInput)
def list_directory(dirpath: str = ".") -> str:
    """
    List the files and subdirectories inside a repository directory.

    Use this tool when you need to discover what files exist before deciding
    which ones to read or modify.
    """
    try:
        full_path, err = _safe_resolve(dirpath)
        if err:
            return err

        if not os.path.isdir(full_path):
            return f"❌ Directory not found: '{dirpath}' (resolved to '{full_path}')"

        entries = sorted(os.listdir(full_path))
        logger.info(
            f"[list_directory] {len(entries)} entries in {dirpath!r}"
        )
        return "\n".join(entries) if entries else "(empty directory)"

    except Exception as exc:
        error_msg = f"❌ Error listing '{dirpath}': {exc}"
        logger.error(f"[langchain_tools] {error_msg}")
        return error_msg


def _clean_llm_markdown(text: str) -> str:
    """Strips accidental markdown code-fence wrappers that the LLM may emit."""
    text = re.sub(r'^```[a-zA-Z]*\n', '', text)
    text = re.sub(r'\n```$', '', text)
    return text.strip()


@tool(args_schema=ReplaceInFileInput)
def replace_in_file(file_path: str, exact_old_text: str, new_text: str) -> str:
    """
    Surgical edit tool: replaces exact_old_text with new_text in the target file.
    PREFER this over write_file — only the changed lines are touched.
    """
    try:
        full_path, err = _safe_resolve(file_path)
        if err:
            return err

        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Strip any accidental markdown fences the LLM may have wrapped around the text
        cleaned_old = _clean_llm_markdown(exact_old_text)
        cleaned_new = _clean_llm_markdown(new_text)

        # ── Attempt 1: exact string match ────────────────────────────────
        if cleaned_old in content:
            new_content = content.replace(cleaned_old, cleaned_new, 1)

        else:
            # ── Attempt 2: flexible-whitespace regex fallback ─────────────
            escaped = re.escape(cleaned_old)
            flexible = re.sub(r'\\\s+', r'\\s+', escaped)
            match = re.search(flexible, content)
            if not match:
                return (
                    f"❌ Could not find the target text in {file_path}.\n"
                    f"Ensure the exact_old_text matches the file precisely "
                    f"(including indentation). Try reading the file first."
                )
            new_content = content[:match.start()] + cleaned_new + content[match.end():]

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        logger.info(f"[replace_in_file] Surgical edit applied to {file_path!r}")
        return f"✅ Successfully replaced text in {file_path}"

    except Exception as e:
        error_msg = f"❌ Error modifying file: {str(e)}"
        logger.error(f"[langchain_tools] {error_msg}")
        return error_msg


# ---------------------------------------------------------------------------
# search_codebase
# ---------------------------------------------------------------------------

@tool(args_schema=SearchCodebaseInput)
def search_codebase(query: str, file_pattern: str = "*") -> str:
    """
    Search for a text string across all files in the repository.

    Use this when you need to find where a function, variable, or string
    is defined or used before making targeted edits.
    """
    try:
        repo_root = _get_repo_path()
        matches = []

        for root, dirs, files in os.walk(repo_root):
            # Skip hidden and dependency directories
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".next", "dist", "build")
            ]
            for filename in files:
                if not fnmatch.fnmatch(filename, file_pattern):
                    continue
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, repo_root)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                        for line_no, line in enumerate(fh, 1):
                            if query in line:
                                matches.append(f"{rel_path}:{line_no}: {line.rstrip()}")
                except Exception:
                    continue

        if not matches:
            return f"No matches found for '{query}' (pattern: {file_pattern})"

        logger.info(f"[search_codebase] {len(matches)} match(es) for {query!r}")
        # Cap output to avoid flooding context window
        result_lines = matches[:50]
        suffix = f"\n... ({len(matches) - 50} more results truncated)" if len(matches) > 50 else ""
        return "\n".join(result_lines) + suffix

    except Exception as exc:
        error_msg = f"❌ Error searching codebase: {exc}"
        logger.error(f"[langchain_tools] {error_msg}")
        return error_msg


# ---------------------------------------------------------------------------
# Exported tool bundle
# ---------------------------------------------------------------------------

# Import this list directly into CodeAgentWithTools:
#   from utils.langchain_tools import ALL_TOOLS
ALL_TOOLS = [read_file, list_directory, search_codebase, replace_in_file]
