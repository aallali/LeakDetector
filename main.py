#!/usr/bin/env python3
"""
Memory Leak Detector - Fast & Minimal with LangChain
Uses LangChain + Deepseek to analyze code for memory issues
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field
import os

def escape_html(text: str) -> str:
    """Escape HTML special chars for safe rendering."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# Define output schema
class MemoryIssue(BaseModel):
    severity: str = Field(description="critical|warning|info")
    title: str = Field(description="Concrete issue name")
    file: str = Field(description="Exact filename")
    lineStart: int = Field(description="Exact line number where problem starts")
    lineEnd: int = Field(description="Exact line number where problem ends")
    description: str = Field(description="WHY this causes memory leak (be specific)")
    code: str = Field(description="EXACT code snippet from file that leaks")
    memoryImpact: str = Field(description="How much memory leaks? (e.g., '500MB per day' or 'unbounded')")
    rootCause: str = Field(description="Root cause mechanism")
    suggestion: str = Field(description="Concrete fix with code example")

class AnalysisResult(BaseModel):
    issues: list[MemoryIssue] = Field(description="List of memory issues found")

def read_codebase(path: str, exclude_dirs: list[str] = None) -> dict[str, str]:
    """Read all code files from path"""
    if exclude_dirs is None:
        exclude_dirs = ["env", "venv", ".venv", "node_modules", ".git", "__pycache__", ".pytest_cache", "dist", "build", ".egg-info"]
    
    files = {}
    path_obj = Path(path)
    
    # Handle single file
    if path_obj.is_file():
        if path_obj.suffix in [".py", ".js", ".ts", ".go"]:
            try:
                with open(path_obj, 'r', encoding='utf-8') as f:
                    files[path_obj.name] = f.read()
            except: pass
        return files
    
    # Handle directory
    if not path_obj.is_dir():
        return files
    
    for pattern in ["*.py", "*.js", "*.ts", "*.go"]:
        for file in path_obj.rglob(pattern):
            # Skip excluded directories
            should_skip = False
            for exclude in exclude_dirs:
                if exclude in file.parts:
                    should_skip = True
                    break
            
            if not should_skip:
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        files[str(file.relative_to(path_obj))] = f.read()
                except: pass
    
    return files

def create_analysis_chain():
    """Create LangChain analysis chain"""
    
    # Initialize Deepseek LLM via OpenAI-compatible endpoint
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        temperature=0,
        max_tokens=2000
    )
    
    # Create prompt template with detailed instructions
    prompt = ChatPromptTemplate.from_template("""Analyze this codebase for ACTUAL MEMORY LEAKS and INEFFICIENCIES.
Be SPECIFIC and CONCRETE. Only report real issues with exact line numbers and code snippets.

Files analyzed:
{file_listing}

LOOK FOR:
1. Unbounded growth: Maps/lists/sets that grow without removal (e.g., cache.set() without delete)
2. Circular references: Object A → B → A preventing garbage collection
3. Event listener leaks: .on() or addEventListener() without .off() or removeEventListener()
4. Resource leaks: File handles, connections, timers not closed (missing close(), cleanup, clearInterval)
5. N+1 patterns: Loops executing queries/API calls instead of batch operations
6. Global data accumulation: Global variables storing data that grows indefinitely

For each issue, return EXACT:
- title: short concrete issue name (5-12 words), never "Unknown Issue"
- severity using this rubric:
    - critical: unbounded growth, resource descriptors not closed, listeners never removed, leaks that can exhaust memory/fds
    - warning: significant memory pressure or delayed collection risk (e.g., circular refs, N+1 with accumulation)
    - info: minor or low-impact inefficiencies
- Line number where problem occurs
- Exact code that causes it
- Why it leaks memory (be specific)
- How much memory could leak (estimate)
- Concrete fix code in a fenced code block using unified diff syntax.
    Use this exact shape:
    ```diff
    --- a/<file>
    +++ b/<file>
    @@
    -old code
    +new code
    ```
    Include at least one removed (-) and one added (+) line.

RETURN ONLY VALID JSON. If no real issues found, return empty issues array.
Do NOT invent issues. Only report code patterns you actually see.
Do NOT suggest general best practices unless they cause actual memory leaks.""")
    
    # Use StrOutputParser to get raw text, then manually extract JSON
    # JsonOutputParser fails when the LLM nests ```diff blocks inside the JSON string values
    parser = StrOutputParser()
    chain = prompt | llm | parser

    return chain, parser

def extract_json_from_text(text: str) -> dict:
    """Extract the first valid JSON object from raw LLM output.

    The model often wraps output in ```json ... ``` fences, and may embed
    nested ```diff ... ``` blocks inside string values.  We locate the
    outermost { } pair rather than relying on fence-stripping so that inner
    backtick sequences cannot break parsing.
    """
    # Fast path: the whole string is already valid JSON
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the first '{' and the last '}' in the string
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return {}

    candidate = text[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    return {}


def analyze_memory_issues(files: dict[str, str]) -> list[dict]:
    """Analyze code using LangChain chain"""
    
    print("🔗 Setting up LangChain analysis chain...")
    chain, parser = create_analysis_chain()
    
    # Analyze files individually for better filename fidelity.
    max_file_chars = 4000
    file_items = list(files.items())
    per_file_payloads = []
    for name, content in file_items:
        snippet = content if len(content) <= max_file_chars else content[:max_file_chars] + "\n# ...truncated..."
        per_file_payloads.append((name, snippet))

    try:
        issues = []
        print(f"📡 Sending {len(per_file_payloads)} file analysis request(s) to Deepseek via LangChain...")

        for idx, (file_name, snippet) in enumerate(per_file_payloads, 1):
            file_listing = f"FILE: {file_name}\n```\n{snippet}\n```"

            print(f"   • File {idx}/{len(per_file_payloads)}: {file_name}")
            raw_text = chain.invoke({"file_listing": file_listing})
            result = extract_json_from_text(raw_text) if isinstance(raw_text, str) else raw_text

            if isinstance(result, dict):
                raw_issues = result.get("issues", [])
            elif hasattr(result, 'issues'):
                raw_issues = result.issues
            else:
                raw_issues = []

            for issue in raw_issues:
                if isinstance(issue, dict):
                    normalized = normalize_issue(issue, files=files, file_name_hint=file_name)
                    if normalized:
                        issues.append(normalized)
                elif hasattr(issue, 'dict'):
                    normalized = normalize_issue(issue.dict(), files=files, file_name_hint=file_name)
                    if normalized:
                        issues.append(normalized)

        # De-duplicate overlapping findings from multiple batches.
        deduped = []
        seen = set()
        for issue in issues:
            key = (
                str(issue.get("file", "")).lower(),
                str(issue.get("lineStart", "")).lower(),
                str(issue.get("title", "")).strip().lower()
            )
            if key not in seen:
                seen.add(key)
                deduped.append(issue)
        
        return deduped
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def normalize_issue(issue: dict, files: dict[str, str] | None = None, file_name_hint: str | None = None) -> dict:
    """Convert different issue formats to standard format"""
    
    # Handle different field names
    severity = issue.get("severity") or issue.get("level") or issue.get("type", "info")
    title = issue.get("title") or issue.get("problem") or ""
    suggestion_raw = issue.get("suggestion") or issue.get("fix") or ""
    file = clean_text_value(issue.get("file"), "")
    
    # Handle line number variations
    line_start = None
    line_end = None
    
    if "lineStart" in issue:
        line_start = issue.get("lineStart")
        line_end = issue.get("lineEnd")
    elif "line" in issue:
        line_start = issue.get("line")
        line_end = issue.get("line")
    
    # Handle missing line numbers
    if not line_start or line_start == "None":
        line_start = "?"
    if not line_end or line_end == "None":
        line_end = "?"
    
    description = clean_text_value(
        issue.get("description") or issue.get("problem"),
        "Issue detected but no description was returned."
    )
    code = clean_text_value(issue.get("code") or issue.get("code_snippet"), "")
    root_cause = clean_text_value(issue.get("rootCause") or issue.get("problem"), "")
    if not root_cause:
        root_cause = infer_root_cause(description, code)

    memory_impact = clean_text_value(issue.get("memoryImpact") or issue.get("memory_impact"), "")
    if not memory_impact:
        memory_impact = infer_memory_impact(description, root_cause)

    suggestion = clean_text_value(
        suggestion_raw,
        "Provide a concrete fix as a unified diff using ```diff fenced code blocks."
    )

    file = infer_issue_file(file, suggestion, code, description, files, file_name_hint)

    title = ensure_issue_title(title, description, root_cause, code)
    
    normalized_issue = {
        "severity": severity,
        "title": title,
        "file": file,
        "lineStart": line_start,
        "lineEnd": line_end,
        "description": description,
        "code": code,
        "memoryImpact": memory_impact,
        "rootCause": root_cause,
        "suggestion": suggestion
    }

    normalized_issue["severity"] = infer_severity(normalized_issue)
    return normalized_issue

def infer_issue_file(
    file_value: str,
    suggestion: str,
    code: str,
    description: str,
    files: dict[str, str] | None,
    file_name_hint: str | None
) -> str:
    """Resolve file name reliably when model omits or mislabels it."""
    candidate = clean_text_value(file_value, "")
    if candidate and candidate not in {"unspecified_file", "unresolved_file"}:
        return candidate

    from_diff = extract_file_from_diff(suggestion)
    if from_diff:
        return from_diff

    from_text = extract_file_from_text(description)
    if from_text:
        return from_text

    from_code = match_file_by_code_snippet(code, files)
    if from_code:
        return from_code

    if file_name_hint:
        return file_name_hint

    return "unresolved_file"

def extract_file_from_diff(suggestion: str) -> str:
    """Extract filename from unified diff headers in suggestion text."""
    text = str(suggestion or "")
    if not text:
        return ""

    # Prefer the +++ target path if available.
    match = re.search(r"^\+\+\+\s+[ab]/([^\n\r]+)", text, re.MULTILINE)
    if match:
        return match.group(1).strip()

    match = re.search(r"^---\s+[ab]/([^\n\r]+)", text, re.MULTILINE)
    if match:
        return match.group(1).strip()

    return ""

def extract_file_from_text(text: str) -> str:
    """Extract filename references like test_x.py from plain text."""
    match = re.search(r"([A-Za-z0-9_./-]+\.(py|js|ts|go))", str(text or ""))
    if match:
        return match.group(1)
    return ""

def match_file_by_code_snippet(code: str, files: dict[str, str] | None) -> str:
    """Find the best file match for the code snippet when filename is missing."""
    if not files:
        return ""

    snippet = str(code or "").strip()
    if not snippet:
        return ""

    lines = [line.strip() for line in snippet.splitlines() if line.strip()]
    if not lines:
        return ""

    # Use first non-empty line as anchor for quick matching.
    anchor = lines[0]
    for name, content in files.items():
        if anchor in content:
            return name

    return ""

def ensure_issue_title(title: str, description: str, root_cause: str, code: str) -> str:
    """Guarantee a useful issue title even when the LLM omits it."""
    raw = str(title or "").strip()
    if raw and raw.lower() not in {"unknown issue", "unknown", "n/a", "none"}:
        return raw

    text = " ".join([
        str(description or ""),
        str(root_cause or ""),
        str(code or "")
    ]).lower()

    if "open(" in text and "close" in text:
        return "File Handles Not Closed"
    if "listener" in text and ("never removed" in text or ".on(" in text):
        return "Event Listeners Never Removed"
    if "global" in text and ("accumulate" in text or "indefinitely" in text or "never cleaned" in text):
        return "Global Data Accumulation"
    if "cache" in text and ("unbounded" in text or "never cleared" in text or "grows" in text):
        return "Unbounded Cache Growth"
    if "circular" in text or "cycle" in text:
        return "Circular Reference Retention"
    if "n+1" in text or "query" in text:
        return "N+1 Query Memory Pressure"
    # Fallback: first sentence of description/root cause.
    basis = str(description or root_cause or "Memory Issue Detected").strip().replace("\n", " ")
    first_sentence = basis.split(".")[0].strip()
    if not first_sentence:
        return "Memory Issue Detected"
    return first_sentence[:80]

def clean_text_value(value, fallback: str) -> str:
    """Normalize empty/placeholder values so Unknown-like tokens never leak to outputs."""
    if value is None:
        return fallback

    text = str(value).strip()
    if not text:
        return fallback

    lowered = text.lower()
    placeholders = {
        "unknown",
        "unknown issue",
        "none",
        "null",
        "n/a",
        "na",
        "not provided"
    }
    if lowered in placeholders:
        return fallback

    return text

def infer_root_cause(description: str, code: str) -> str:
    """Derive a concrete root cause when the model omits one."""
    text = f"{description} {code}".lower()
    if "open(" in text and "close" in text:
        return "Resources are opened but not deterministically closed."
    if "listener" in text or ".on(" in text:
        return "Listeners are registered repeatedly without corresponding deregistration."
    if "cache" in text and ("unbounded" in text or "never" in text or "grow" in text):
        return "Cache growth is unbounded due to missing eviction/cleanup."
    if "circular" in text or "cycle" in text:
        return "Mutual references keep objects reachable longer than intended."
    if "n+1" in text or "query" in text:
        return "Repeated per-item queries increase retention of intermediate results."
    if "global" in text and ("accumulate" in text or "indefinitely" in text):
        return "Global mutable state accumulates data without lifecycle limits."
    return "Memory-retaining pattern without cleanup boundaries."

def infer_memory_impact(description: str, root_cause: str) -> str:
    """Provide a non-empty memory impact statement when absent."""
    text = f"{description} {root_cause}".lower()
    if "unbounded" in text or "indefinitely" in text:
        return "Unbounded growth over time; memory usage can continue increasing until failure."
    if "file" in text and "close" in text:
        return "Open handles accumulate and may exhaust OS descriptor limits."
    if "listener" in text:
        return "Callback accumulation increases heap usage and delays garbage collection."
    if "circular" in text:
        return "Objects may remain in memory until cyclic GC runs, causing temporary bloat."
    if "n+1" in text or "query" in text:
        return "Additional query results increase peak memory and processing latency."
    return "Increased memory footprint over runtime due to retained objects."

def infer_severity(issue: dict) -> str:
    """Normalize LLM severity and apply simple fallback heuristics."""
    raw = str(issue.get("severity", "")).strip().lower()
    map_raw = {
        "critical": "critical",
        "high": "critical",
        "warning": "warning",
        "medium": "warning",
        "low": "info",
        "info": "info"
    }
    if raw in map_raw:
        normalized = map_raw[raw]
    else:
        normalized = "info"

    text = " ".join([
        str(issue.get("title", "")),
        str(issue.get("description", "")),
        str(issue.get("memoryImpact", "")),
        str(issue.get("rootCause", ""))
    ]).lower()

    critical_markers = [
        "unbounded",
        "indefinitely",
        "never closed",
        "never removed",
        "too many open files",
        "exhaust",
        "gb",
        "gigabyte"
    ]
    warning_markers = [
        "n+1",
        "memory pressure",
        "temporary memory bloat",
        "circular reference",
        "accumulate"
    ]

    if normalized == "info":
        if any(marker in text for marker in critical_markers):
            return "critical"
        if any(marker in text for marker in warning_markers):
            return "warning"

    return normalized

def save_analysis_json(issues: list[dict], output_file: str) -> None:
    """Save raw analysis results to JSON file"""
    data = {
        "timestamp": datetime.now().isoformat(),
        "total_issues": len(issues),
        "issues": issues
    }
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"💾 Raw analysis saved to: {output_file}")

def load_html_template() -> str:
    """Load HTML template from file"""
    template_path = Path(__file__).parent / "report_template.html"
    try:
        with open(template_path, 'r') as f:
            return f.read()
    except:
        # Fallback if template not found
        return ""

def generate_issue_html(issue: dict) -> str:
    """Generate HTML for a single issue with proper code highlighting"""
    
    severity = issue.get("severity", "info")
    title = issue.get("title", "Memory Issue Detected")
    file = issue.get("file", "unspecified_file")
    lineStart = issue.get("lineStart", "?")
    lineEnd = issue.get("lineEnd", "?")
    description = issue.get("description", "No description")
    code = issue.get("code", "")
    memoryImpact = issue.get("memoryImpact", "Increased memory footprint over runtime due to retained objects.")
    rootCause = issue.get("rootCause", "Memory-retaining pattern without cleanup boundaries.")
    suggestion = issue.get("suggestion", "Provide a concrete fix as a unified diff using ```diff fenced code blocks.")
    
    # Safe string conversion for None values
    title = clean_text_value(title, "Memory Issue Detected")
    description = clean_text_value(description, "Issue detected but no description was returned.")
    code = clean_text_value(code, "")
    memoryImpact = clean_text_value(memoryImpact, "Increased memory footprint over runtime due to retained objects.")
    rootCause = clean_text_value(rootCause, "Memory-retaining pattern without cleanup boundaries.")
    suggestion = clean_text_value(suggestion, "Provide a concrete fix as a unified diff using ```diff fenced code blocks.")
    
    # Format code block - detect language from context
    code_html = ""
    if code:
        code_escaped = escape_html(code)
        code_html = f'<div class="code-snippet"><code class="language-python">{code_escaped}</code></div>'
    else:
        code_html = '<div class="code-snippet"><code>&lt;no code provided&gt;</code></div>'
    
    # Format suggestion as proper code block with syntax highlighting
    suggestion_html = ""
    if suggestion:
        # Check if suggestion contains code blocks (look for triple backticks)
        if "```" in suggestion:
            # Extract and format code blocks
            parts = suggestion.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 0:
                    # Text part
                    if part.strip():
                        suggestion_html += f'<p>{escape_html(part.strip())}</p>'
                else:
                    # Code part
                    code_lines = part.strip().split('\n')
                    language = "python"
                    # First line may be a language hint: diff/python/js/javascript/ts/go
                    if code_lines:
                        first = code_lines[0].strip().lower()
                        if first in ['diff', 'python', 'js', 'javascript', 'ts', 'go']:
                            language = first
                            code_lines = code_lines[1:]
                    code_content = '\n'.join(code_lines)
                    code_escaped = escape_html(code_content)
                    suggestion_html += f'<pre><code class="language-{language}">{code_escaped}</code></pre>'
        else:
            # No code fences: preserve line breaks for readability
            suggestion_html = f'<pre><code class="language-diff">{escape_html(suggestion)}</code></pre>'
    
    return f"""        <div class="issue {severity}" data-severity="{severity}">
            <div class="issue-header">
                <div class="issue-title">{title}</div>
                <div class="severity-badge {severity}">{severity}</div>
            </div>
            
            <div class="issue-location">
                {file}:{lineStart}-{lineEnd}
            </div>
            
            <div class="issue-description">
                {description}
            </div>
            
            {code_html}
            
            <div class="issue-details">
                <div class="detail">
                    <div class="detail-label">Memory Impact</div>
                    <div>{memoryImpact}</div>
                </div>
                <div class="detail">
                    <div class="detail-label">Root Cause</div>
                    <div>{rootCause}</div>
                </div>
            </div>
            
            <div class="fix-section">
                <div class="fix-title">Fix</div>
                {suggestion_html}
            </div>
        </div>
"""

def generate_html_report(issues: list[dict], codebase_path: str) -> str:
    """Generate HTML report from issues using template"""
    
    # Map unknown severities to standard ones
    severity_map = {
        "critical": "critical",
        "high": "critical",
        "warning": "warning",
        "medium": "warning",
        "low": "info",
        "info": "info"
    }
    
    counts = {"critical": 0, "warning": 0, "info": 0}
    
    # Normalize issues
    normalized_issues = []
    for issue in issues:
        if isinstance(issue, dict):
            sev = issue.get("severity", "info").lower()
            normalized_sev = severity_map.get(sev, "info")
            issue["severity"] = normalized_sev
            normalized_issues.append(issue)
        else:
            sev = getattr(issue, "severity", "info").lower()
            normalized_sev = severity_map.get(sev, "info")
            issue.severity = normalized_sev
            normalized_issues.append(issue)
        
        counts[normalized_sev] += 1
    
    issues = normalized_issues
    
    # Generate issue HTML
    issues_html = "\n".join([generate_issue_html(issue) for issue in issues])
    
    # Load template
    template = load_html_template()
    
    if not template:
        print("⚠️  Warning: Could not load HTML template, generating inline HTML")
        # Fallback to simple HTML if template not found
        return generate_simple_html(issues, counts)
    
    # Escape literal braces in CSS/JS while keeping our known placeholders.
    # This prevents str.format from interpreting style/script blocks as fields.
    safe_template = template.replace("{", "{{").replace("}", "}}")
    for key in ["timestamp", "critical_count", "warning_count", "info_count", "issues_html"]:
        safe_template = safe_template.replace(f"{{{{{key}}}}}", f"{{{key}}}")

    # Fill template with data
    html = safe_template.format(
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M UTC'),
        critical_count=counts['critical'],
        warning_count=counts['warning'],
        info_count=counts['info'],
        issues_html=issues_html
    )
    
    return html

def generate_simple_html(issues: list[dict], counts: dict) -> str:
    """Fallback simple HTML generation if template not found"""
    issues_html = "\n".join([generate_issue_html(issue) for issue in issues])
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Memory Analysis Report</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-light.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
</head>
<body>
    {issues_html}
    <script>document.querySelectorAll('pre code').forEach(hljs.highlightElement);</script>
</body>
</html>"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python memory_analyzer.py <code_path> [output.html] [--exclude folder1,folder2]")
        sys.exit(1)
    
    code_path = sys.argv[1]
    output_file = "memory_report.html"
    exclude_dirs = None
    
    # Parse arguments
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg.startswith("--exclude"):
            exclude_dirs = sys.argv[i+1].split(",") if i+1 < len(sys.argv) else []
            break
        elif not arg.startswith("--"):
            output_file = arg
    
    # Add a timestamp suffix to generated report filenames.
    # Example: memory_report_20260409_101530.html
    timestamp_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(output_file)
    output_file = str(output_path.with_name(f"{output_path.stem}_{timestamp_suffix}{output_path.suffix or '.html'}"))

    print(f"📂 Reading codebase from: {code_path}")
    files = read_codebase(code_path, exclude_dirs)
    
    if not files:
        print("❌ No code files found")
        sys.exit(1)
    
    print(f"✅ Found {len(files)} files")
    print("🔍 Analyzing for memory issues with LangChain...")
    
    issues = analyze_memory_issues(files)
    
    print(f"📊 Found {len(issues)} issues")
    
    # Save raw JSON response for analysis
    json_file = output_file.replace(".html", "_analysis.json")
    save_analysis_json(issues, json_file)
    
    print("📄 Generating HTML report...")
    
    html = generate_html_report(issues, code_path)
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"✅ Report saved to: {output_file}")

if __name__ == "__main__":
    main()