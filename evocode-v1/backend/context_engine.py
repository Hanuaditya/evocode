"""
backend/context_engine.py

Tree-Sitter Context Engine & Syntax Guard for EvoCode V2.

Layers:
- Layer 0: Repo Map (walks target repo excluding build/dependency artifacts)
- Layer 1: Next.js Route Mapper (resolves route_path to App/Pages router page, layout, and imports)
- Layer 2: AST Symbol & Import Graph Extractor (extracts exports, React components, Tailwind patterns)
- Layer 3: Post-Edit Syntax Guard (validates TS/TSX/JS/JSX/Python syntax via tree-sitter, returns line/col errors)
"""

import os
import re
import logging
from typing import Optional, Tuple, List, Dict, Any

try:
    import tree_sitter
    from tree_sitter import Language, Parser
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_python

    # Initialize Languages & Parsers
    _JS_LANG = Language(tree_sitter_javascript.language())
    _TS_LANG = Language(tree_sitter_typescript.language_typescript())
    _TSX_LANG = Language(tree_sitter_typescript.language_tsx())
    _PY_LANG = Language(tree_sitter_python.language())

    _JS_PARSER = Parser(_JS_LANG)
    _TS_PARSER = Parser(_TS_LANG)
    _TSX_PARSER = Parser(_TSX_LANG)
    _PY_PARSER = Parser(_PY_LANG)
    TREE_SITTER_AVAILABLE = True
except Exception as e:
    logging.getLogger("context_engine").warning(f"Tree-sitter initialization warning: {e}")
    TREE_SITTER_AVAILABLE = False
    _JS_PARSER = None
    _TS_PARSER = None
    _TSX_PARSER = None
    _PY_PARSER = None

logger = logging.getLogger("context_engine")

_IGNORE_DIRS = {
    "node_modules", ".next", ".git", "dist", "build", "__pycache__",
    ".turbo", ".vercel", "coverage", ".vscode", ".idea"
}


# ---------------------------------------------------------------------------
# Layer 0: Repo Map
# ---------------------------------------------------------------------------

def build_repo_map(repo_path: str, max_depth: int = 4) -> Dict[str, Any]:
    """
    Walks the target repository excluding dependencies and build artifacts,
    returning a structured tree of source files and directories.
    """
    abs_root = os.path.abspath(repo_path)
    if not os.path.exists(abs_root):
        return {"error": f"Path not found: {repo_path}", "files": []}

    repo_files = []
    tree_lines = []

    for root, dirs, files in os.walk(abs_root):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]

        rel_dir = os.path.relpath(root, abs_root)
        depth = 0 if rel_dir == "." else len(rel_dir.split(os.sep))
        if depth > max_depth:
            continue

        indent = "  " * depth
        dir_name = os.path.basename(root) if rel_dir != "." else os.path.basename(abs_root)
        tree_lines.append(f"{indent}📁 {dir_name}/")

        for f in sorted(files):
            if f.startswith(".") or f.endswith(".log"):
                continue
            rel_file = os.path.normpath(os.path.join(rel_dir, f)) if rel_dir != "." else f
            repo_files.append(rel_file.replace("\\", "/"))
            tree_lines.append(f"{indent}  📄 {f}")

    return {
        "repo_root": abs_root,
        "files_count": len(repo_files),
        "files": repo_files,
        "tree_text": "\n".join(tree_lines[:200])  # preview
    }


# ---------------------------------------------------------------------------
# Layer 1: Next.js Route Mapper
# ---------------------------------------------------------------------------

def resolve_nextjs_route(route_path: str, repo_path: str) -> Dict[str, Any]:
    """
    Given a URL pathname (e.g. '/pricing', '/about', '/'), resolves:
      - The primary page file (app/pricing/page.tsx or pages/pricing.tsx)
      - The parent layout files
      - Direct imported components referenced in that page
    """
    abs_root = os.path.abspath(repo_path)
    clean_route = route_path.strip()
    if clean_route.startswith("/"):
        clean_route = clean_route[1:]
    if clean_route.endswith("/"):
        clean_route = clean_route[:-1]

    # Candidate page directories
    extensions = [".tsx", ".jsx", ".js", ".ts"]
    app_dirs = ["app", "src/app"]
    pages_dirs = ["pages", "src/pages"]

    page_file: Optional[str] = None
    layout_files: List[str] = []
    imported_components: List[str] = []

    # 1. Search Next.js App Router (app/**/page.tsx)
    for base in app_dirs:
        candidate_dir = os.path.join(abs_root, base, clean_route) if clean_route else os.path.join(abs_root, base)
        if os.path.isdir(candidate_dir):
            for ext in extensions:
                p = os.path.join(candidate_dir, f"page{ext}")
                if os.path.isfile(p):
                    page_file = os.path.relpath(p, abs_root).replace("\\", "/")
                    break
        if page_file:
            # Check layouts from route dir up to base app dir
            curr = candidate_dir
            app_root = os.path.join(abs_root, base)
            while curr.startswith(app_root):
                for ext in extensions:
                    lay = os.path.join(curr, f"layout{ext}")
                    if os.path.isfile(lay):
                        rel_lay = os.path.relpath(lay, abs_root).replace("\\", "/")
                        if rel_lay not in layout_files:
                            layout_files.append(rel_lay)
                if curr == app_root:
                    break
                curr = os.path.dirname(curr)
            break

    # 2. Search Next.js Pages Router (pages/pricing.tsx) if not found in App Router
    if not page_file:
        for base in pages_dirs:
            target_name = "index" if not clean_route else clean_route
            for ext in extensions:
                p = os.path.join(abs_root, base, f"{target_name}{ext}")
                if os.path.isfile(p):
                    page_file = os.path.relpath(p, abs_root).replace("\\", "/")
                    break
            if page_file:
                break

    # 3. Fallback: search common components matching route name (e.g. About.jsx for /about)
    if not page_file:
        route_slug = clean_route.split("/")[-1] if clean_route else "index"
        for root, dirs, files in os.walk(abs_root):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for f in files:
                name, ext = os.path.splitext(f)
                if ext in extensions and name.lower() == route_slug.lower():
                    page_file = os.path.relpath(os.path.join(root, f), abs_root).replace("\\", "/")
                    break
            if page_file:
                break

    # 4. Resolve imported components from the page file
    if page_file:
        full_page = os.path.join(abs_root, page_file)
        try:
            with open(full_page, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            # Regex for import statements: import Foo from './components/Foo'
            import_matches = re.findall(r'from\s+[\'"]([^\'"]+)[\'"]', content)
            page_dir = os.path.dirname(full_page)
            for imp in import_matches:
                if imp.startswith("."):
                    # Relative import
                    base_imp = os.path.normpath(os.path.join(page_dir, imp))
                    for ext in extensions + ["/index.tsx", "/index.jsx", "/index.js"]:
                        candidate = base_imp + ext if not ext.startswith("/") else base_imp + ext
                        if os.path.isfile(candidate):
                            rel_comp = os.path.relpath(candidate, abs_root).replace("\\", "/")
                            if rel_comp not in imported_components:
                                imported_components.append(rel_comp)
                                break
        except Exception as e:
            logger.warning(f"[context_engine] Error reading imports from {page_file}: {e}")

    primary_file = page_file or (imported_components[0] if imported_components else None)
    return {
        "route_path": route_path,
        "page_file": page_file,
        "primary_file": primary_file,
        "layout_files": layout_files,
        "imported_components": imported_components,
    }


# ---------------------------------------------------------------------------
# Layer 2: AST Symbol & Import Graph Extractor
# ---------------------------------------------------------------------------

def extract_ast_symbols(file_path: str, code: str) -> Dict[str, Any]:
    """
    Extracts exports, component names, imports, and Tailwind classes
    using tree-sitter or regex fallback.
    """
    ext = os.path.splitext(file_path)[1].lower()
    parser = _get_parser_for_ext(ext)

    components: List[str] = []
    exports: List[str] = []
    imports: List[str] = []
    tailwind_classes: List[str] = []

    # Regex extraction (works across all languages)
    # React component: function PascalCase or const PascalCase =
    comp_matches = re.findall(r'(?:function|class|const|let)\s+([A-Z][a-zA-Z0-9_]*)', code)
    components = list(dict.fromkeys(comp_matches))

    # Exports
    export_matches = re.findall(r'export\s+(?:default\s+)?(?:function|class|const|let)?\s*([a-zA-Z0-9_]+)?', code)
    exports = [e for e in export_matches if e]

    # Imports
    import_matches = re.findall(r'import\s+(?:.*?)\s+from\s+[\'"]([^\'"]+)[\'"]', code)
    imports = list(dict.fromkeys(import_matches))

    # Tailwind classes in className="..."
    class_matches = re.findall(r'className\s*=\s*[\'"`]([^\'"`]+)[\'"`]', code)
    for c in class_matches:
        tailwind_classes.extend(c.split())
    tailwind_classes = list(dict.fromkeys(tailwind_classes))[:40]

    return {
        "file_path": file_path,
        "components": components,
        "exports": exports,
        "imports": imports,
        "sample_tailwind_classes": tailwind_classes,
        "loc": len(code.splitlines()),
    }


# ---------------------------------------------------------------------------
# Layer 3: Post-Edit Syntax Guard (Tree-Sitter AST Validation)
# ---------------------------------------------------------------------------

def _get_parser_for_ext(ext: str) -> Optional[Any]:
    if not TREE_SITTER_AVAILABLE:
        return None
    if ext == ".tsx":
        return _TSX_PARSER
    elif ext == ".ts":
        return _TS_PARSER
    elif ext in (".jsx", ".js", ".mjs", ".cjs"):
        return _JS_PARSER
    elif ext == ".py":
        return _PY_PARSER
    return _TSX_PARSER  # default to TSX for modern web code


def _find_first_error_node(node: Any) -> Optional[Any]:
    """Recursively finds the first node with type ERROR or is_missing."""
    if node.type == "ERROR" or getattr(node, "is_missing", False):
        return node
    for child in node.children:
        res = _find_first_error_node(child)
        if res:
            return res
    return None


def validate_syntax(file_path: str, code: str) -> Tuple[bool, Optional[str]]:
    """
    Parses `code` using tree-sitter.
    If tree.root_node.has_error is True, locates the line and column of the error
    and returns (False, error_message).
    If valid or parser unavailable, returns (True, None).
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".js", ".jsx", ".ts", ".tsx", ".py"):
        # For non-code files (md, json, css), skip AST tree-sitter
        return True, None

    parser = _get_parser_for_ext(ext)
    if not parser:
        return True, None

    try:
        source_bytes = code.encode("utf-8")
        tree = parser.parse(source_bytes)

        if not tree.root_node.has_error:
            return True, None

        # Locate the exact error position
        err_node = _find_first_error_node(tree.root_node)
        if err_node:
            row, col = err_node.start_point
            line_no = row + 1
            col_no = col + 1
            # Extract surrounding line text for context
            lines = code.splitlines()
            line_snippet = lines[row].strip() if row < len(lines) else ""
            err_msg = (
                f"AST Syntax error in '{file_path}' at line {line_no}, col {col_no}: "
                f"unexpected token near '{line_snippet}'"
            )
        else:
            err_msg = f"AST Syntax error in '{file_path}': malformed syntax or unclosed tag/bracket"

        logger.warning(f"[context_engine] Syntax check failed: {err_msg}")
        return False, err_msg

    except Exception as e:
        logger.error(f"[context_engine] Error during tree-sitter syntax validation: {e}")
        return True, None  # Don't block on internal parser exceptions
