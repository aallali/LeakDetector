# LeakDetector

**AI-powered memory leak analysis tool** that identifies resource violations in Python code using LangChain + Deepseek.

## Overview

LeakDetector demonstrates enterprise-grade AI agent integration:
- **LangChain orchestration** for robust LLM interactions with proper fallback parsing
- **Deepseek API** for cost-effective, specialized code analysis
- **Structured output handling** with nested code block parsing

The tool scans codebases and detects 6 categories of memory leaks:
- Unbounded cache/collection growth
- Unclosed resources (files, connections, sockets)
- Event listener accumulation
- Circular reference retention
- N+1 query patterns with memory pressure
- Global data accumulation

## Usage

```bash
python3 main.py <code_directory>
```

Generates an interactive HTML report with:
- ✅ Exact line numbers and code snippets
- 🎯 Memory impact estimates
- 🔧 Unified diff fixes ready to apply

## Example Output

**Dashboard View** — Severity breakdown and filtering:
![Dashboard](/.github/Screenshot%20from%202026-02-09%2019-50-56.png)

**Critical Issues** — Resource leaks requiring immediate attention:
![Resource Leak](/.github/Screenshot%20from%202026-02-09%2019-51-11.png)

**Root Cause Analysis** — Detailed memory impact and concrete fixes:
![Memory Issue](/.github/Screenshot%20from%202026-02-09%2019-51-25.png)

**Warning Level** — Deferred collection risks and inefficiencies:
![N+1 Pattern](/.github/Screenshot%20from%202026-02-09%2019-51-36.png)

## Tech Stack

- **LangChain**: Chat prompts, LLM chains, output parsing
- **Deepseek Chat**: Specialized code analysis model via OpenAI API
- **Pydantic**: Structured schema definition and validation
- **Python 3.12+**: Async support, modern type hints
 
## Key Implementation Details

### Robust JSON Parsing
Handles edge case where LLM output embeds `\`\`\`diff` blocks inside JSON string values (would break standard fence-stripping). Solution: locate outermost `{}` pair instead.

### File-by-File Analysis
Processes each file individually for better filename fidelity and to stay within token limits.

### Deduplication
Filters overlapping findings across multiple analysis passes.

### Smart Fallbacks
Normalizes inconsistent LLM outputs — infers root causes, memory impact, and severity when missing.

## Setup

```bash
pip install -r requirements.txt
export DEEPSEEK_API_KEY="your_api_key"
```
