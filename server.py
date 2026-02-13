#!/usr/bin/env python3
"""
DeepWiki MCP Server - True Async Task-Based Architecture
Query code repositories with background task execution and status tracking.

Inspired by production async patterns - returns task IDs immediately,
executes in background, check status later.
"""

import asyncio
import logging
import os
import json
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Annotated

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

class Settings(BaseSettings):
    """Server configuration with environment variable support."""
    
    deepwiki_api_url: str = Field(
        default="https://api.devin.ai",
        description="Base URL for DeepWiki API"
    )
    deepwiki_api_key: Optional[str] = Field(
        default=None,
        description="API key for DeepWiki (if required)"
    )
    poll_interval_ms: int = Field(
        default=2000,
        description="Polling interval in milliseconds"
    )
    poll_max_attempts: int = Field(
        default=120,
        description="Maximum polling attempts before timeout"
    )
    connect_timeout: float = Field(
        default=10.0,
        description="HTTP connection timeout in seconds"
    )
    read_timeout: float = Field(
        default=180.0,
        description="HTTP read timeout in seconds"
    )
    max_concurrent_queries: int = Field(
        default=5,
        description="Maximum concurrent queries allowed"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DEEPWIKI_"
    )


settings = Settings()

# =============================================================================
# LOGGING SETUP
# =============================================================================

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("deepwiki-mcp")

# =============================================================================
# TASK STORAGE
# =============================================================================

tasks = {}
MAX_TASKS = 100
TASK_EXPIRY_HOURS = 24

def cleanup_old_tasks():
    """Remove tasks older than TASK_EXPIRY_HOURS or exceed MAX_TASKS."""
    current_time = time.time()
    expiry_threshold = current_time - (TASK_EXPIRY_HOURS * 3600)
    
    # Remove expired tasks
    expired = [tid for tid, task in tasks.items() 
               if task["created_at"] < expiry_threshold]
    for tid in expired:
        del tasks[tid]
        logger.debug(f"Removed expired task: {tid}")
    
    # If still too many, remove oldest
    if len(tasks) > MAX_TASKS:
        sorted_tasks = sorted(tasks.items(), key=lambda x: x[1]["created_at"])
        to_remove = len(tasks) - MAX_TASKS
        for tid, _ in sorted_tasks[:to_remove]:
            del tasks[tid]
            logger.debug(f"Removed old task (capacity): {tid}")

# =============================================================================
# ENUMS & TYPES
# =============================================================================

class QueryMode(str, Enum):
    """Query execution modes."""
    FAST = "fast"
    DEEP = "deep"
    CODEMAP = "codemap"
    
    @property
    def engine_id(self) -> str:
        """Map mode to engine ID."""
        mapping = {
            "fast": "multihop_faster",
            "deep": "agent",
            "codemap": "codemap"
        }
        return mapping[self.value]
    
    @property
    def estimated_time(self) -> str:
        """Estimated completion time."""
        times = {
            "fast": "5-15 seconds",
            "deep": "30-90 seconds",
            "codemap": "20-60 seconds"
        }
        return times[self.value]


# =============================================================================
# DATA MODELS
# =============================================================================

class QueryRequest(BaseModel):
    """Request payload for query API."""
    engine_id: str
    user_query: str
    keywords: List[str] = Field(default_factory=list)
    repo_names: List[str]
    additional_context: str = ""
    query_id: str
    use_notes: bool = False
    attached_context: List[Any] = Field(default_factory=list)
    generate_summary: bool = True


class CodemapLocation(BaseModel):
    """A single location in a code trace."""
    id: str
    line_content: str
    path: str
    line_number: int
    title: str
    description: str


class CodemapTrace(BaseModel):
    """A trace of related code locations."""
    id: str
    title: str
    description: str
    locations: List[CodemapLocation]


class Codemap(BaseModel):
    """Complete codemap structure."""
    title: str
    traces: List[CodemapTrace]
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    workspace_info: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# MERMAID DIAGRAM GENERATOR
# =============================================================================

class MermaidGenerator:
    """Generates Mermaid flowcharts from codemaps."""
    
    TRACE_COLORS = [
        ("#e8f5e9", "#4caf50"),
        ("#e3f2fd", "#2196f3"),
        ("#fff3e0", "#ff9800"),
        ("#f3e5f5", "#9c27b0"),
        ("#fff8e1", "#ffc107"),
        ("#fce4ec", "#e91e63"),
        ("#e0f2f1", "#009688"),
        ("#fbe9e7", "#ff5722"),
    ]
    
    @staticmethod
    def sanitize_id(s: str) -> str:
        """Sanitize string for use as Mermaid ID."""
        return ''.join(c if c.isalnum() else '_' for c in s)
    
    @staticmethod
    def escape_label(s: str) -> str:
        """Escape string for use in Mermaid labels."""
        return s.replace('"', '#quot;').replace('\n', ' ')
    
    @staticmethod
    def short_path(path: str) -> str:
        """Get filename from path."""
        return path.split('/')[-1] if '/' in path else path
    
    @classmethod
    def generate(cls, codemap: Codemap) -> str:
        """Generate Mermaid diagram from codemap."""
        lines = ["flowchart TB"]
        
        for i, trace in enumerate(codemap.traces):
            sg_id = cls.sanitize_id(f"trace_{trace.id}")
            title = cls.escape_label(trace.title)
            
            lines.append("")
            lines.append(f'    subgraph {sg_id}["{trace.id}. {title}"]')
            
            for loc in trace.locations:
                loc_id = cls.sanitize_id(f"loc_{loc.id}")
                loc_title = cls.escape_label(loc.title)
                filename = cls.short_path(loc.path)
                label = f"{loc_title}\\n{filename}:{loc.line_number}"
                lines.append(f'        {loc_id}["{label}"]')
            
            lines.append("    end")
            
            for j in range(len(trace.locations) - 1):
                a = cls.sanitize_id(f"loc_{trace.locations[j].id}")
                b = cls.sanitize_id(f"loc_{trace.locations[j + 1].id}")
                lines.append(f"    {a} --> {b}")
        
        for i in range(len(codemap.traces) - 1):
            curr_locs = codemap.traces[i].locations
            next_locs = codemap.traces[i + 1].locations
            if curr_locs and next_locs:
                a = cls.sanitize_id(f"loc_{curr_locs[-1].id}")
                b = cls.sanitize_id(f"loc_{next_locs[0].id}")
                lines.append(f"    {a} -.-> {b}")
        
        lines.append("")
        for i, trace in enumerate(codemap.traces):
            sg_id = cls.sanitize_id(f"trace_{trace.id}")
            fill, stroke = cls.TRACE_COLORS[i % len(cls.TRACE_COLORS)]
            lines.append(f"    style {sg_id} fill:{fill},stroke:{stroke},stroke-width:2px")
        
        return '\n'.join(lines)


def extract_codemap(query_response: Dict[str, Any]) -> Optional[Codemap]:
    """Extract codemap from query response."""
    try:
        queries = query_response.get("queries", [])
        if not queries:
            return None
        
        response_data = queries[-1].get("response", [])
        if not response_data:
            return None
        
        for chunk in response_data:
            if chunk.get("type") == "chunk" and chunk.get("data"):
                data = chunk["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                if data.get("traces"):
                    return Codemap(**data)
        
        return None
    except Exception as e:
        logger.warning(f"Failed to extract codemap: {e}")
        return None


def _extract_answer_from_response(result: Dict[str, Any]) -> str:
    """
    Extract clean answer text from the verbose API response.
    
    The API returns data in multiple formats:
    - "chunk" entries contain the main detailed answer
    - "summary_chunk" entries build up a condensed summary
    - "file_contents" and "reference" entries are metadata we don't need
    
    This function extracts the detailed answer, not just the summary.
    """
    queries = result.get("queries", [])
    if not queries:
        return "No response data available."
    
    response_data = queries[-1].get("response", [])
    if not response_data:
        return "No response data available."
    
    # Collect meaningful text chunks (the detailed answer)
    answer_chunks = []
    
    for item in response_data:
        item_type = item.get("type")
        data = item.get("data")
        
        # Main answer chunks - these contain the detailed response
        if item_type == "chunk" and isinstance(data, str):
            # Skip progress indicators (lines starting with >)
            # Skip AI thinking aloud ("I'll help you...", "Let me search...")
            trimmed = data.strip()
            if trimmed and not trimmed.startswith(">"):
                # Skip the "I'll help" preambles but keep the actual content
                if not any(trimmed.startswith(prefix) for prefix in [
                    "I'll help", 
                    "Let me search",
                    "I'll search",
                    "> Searching"
                ]):
                    answer_chunks.append(data)
    
    if answer_chunks:
        # Join all chunks and clean up excessive newlines
        full_answer = "".join(answer_chunks)
        # Normalize multiple newlines to at most 2
        import re
        full_answer = re.sub(r'\n{3,}', '\n\n', full_answer)
        return full_answer.strip()
    else:
        return "Response received but no readable text found."


# =============================================================================
# API CLIENT
# =============================================================================

class DeepWikiClient:
    """Async HTTP client for DeepWiki API."""
    
    def __init__(self):
        """Initialize the HTTP client."""
        self.base_url = settings.deepwiki_api_url
        self.timeout = httpx.Timeout(
            connect=settings.connect_timeout,
            read=settings.read_timeout,
            write=10.0,
            pool=5.0
        )
        self.limits = httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10
        )
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_queries)
    
    async def start(self):
        """Start the HTTP client."""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if settings.deepwiki_api_key:
                headers["Authorization"] = f"Bearer {settings.deepwiki_api_key}"
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=self.limits,
                headers=headers,
                follow_redirects=True
            )
            logger.info("DeepWiki API client started")
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("DeepWiki API client closed")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        if not self._client:
            await self.start()
        
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP {e.response.status_code}: {e.response.text}")
            if e.response.status_code == 429:
                raise ValueError("Rate limit exceeded. Please try again later.")
            elif e.response.status_code >= 500:
                raise ValueError(f"Server error ({e.response.status_code}). Service may be unavailable.")
            elif e.response.status_code == 404:
                raise ValueError("Resource not found. Check query ID or repository name.")
            else:
                raise ValueError(f"Request failed: {e.response.text}")
        except httpx.TimeoutException:
            logger.error("Request timeout")
            raise ValueError("Request timed out. Try 'fast' mode or simpler query.")
        except httpx.NetworkError as e:
            logger.error(f"Network error: {e}")
            raise ValueError(f"Network error: {str(e)}")
    
    async def submit_query(self, request: QueryRequest) -> None:
        """Submit a new query."""
        async with self._semaphore:
            logger.info(f"Submitting query {request.query_id}: {request.user_query[:50]}...")
            await self._request(
                "POST",
                "/ada/query",
                json=request.model_dump()
            )
            logger.info(f"Query {request.query_id} submitted successfully")
    
    async def get_query_status(self, query_id: str) -> Dict[str, Any]:
        """Get query status and results."""
        logger.debug(f"Checking status for query {query_id}")
        return await self._request("GET", f"/ada/query/{query_id}")
    
    async def poll_until_done(self, query_id: str) -> Dict[str, Any]:
        """Poll query status until completion."""
        logger.info(f"Polling query {query_id}...")
        
        for attempt in range(settings.poll_max_attempts):
            await asyncio.sleep(settings.poll_interval_ms / 1000.0)
            
            result = await self.get_query_status(query_id)
            queries = result.get("queries", [])
            
            if queries:
                last_query = queries[-1]
                state = last_query.get("state")
                
                if state == "done":
                    logger.info(f"Query {query_id} completed successfully")
                    return result
                elif state == "failed":
                    error_msg = last_query.get("error", "Query failed")
                    logger.error(f"Query {query_id} failed: {error_msg}")
                    raise ValueError(f"Query failed: {error_msg}")
        
        timeout_sec = (settings.poll_interval_ms * settings.poll_max_attempts) / 1000
        logger.error(f"Query {query_id} timed out after {timeout_sec}s")
        raise ValueError(f"Query timed out after {timeout_sec}s. Try 'fast' mode.")


# Global client instance
_client: Optional[DeepWikiClient] = None


async def get_client() -> DeepWikiClient:
    """Get or create the global API client."""
    global _client
    if _client is None:
        _client = DeepWikiClient()
        await _client.start()
    return _client


# =============================================================================
# BACKGROUND TASK EXECUTION
# =============================================================================

async def execute_query_background(
    task_id: str,
    question: str,
    repos: List[str],
    mode: QueryMode,
    context: Optional[str],
    generate_summary: bool,
    include_mermaid: bool
):
    """Execute query in background and update task status."""
    try:
        tasks[task_id]["status"] = "running"
        logger.info(f"Task {task_id} started (mode: {mode.value})")
        
        client = await get_client()
        
        # Create query request
        query_id = str(uuid.uuid4())
        request = QueryRequest(
            engine_id=mode.engine_id,
            user_query=question,
            repo_names=repos,
            additional_context=context or "",
            query_id=query_id,
            generate_summary=generate_summary
        )
        
        # Submit query
        await client.submit_query(request)
        
        # Poll for results
        result = await client.poll_until_done(query_id)
        
        # Format results
        formatted = {
            "query_id": query_id,
            "status": "completed",
            "question": question,
            "repos": repos,
            "mode": mode.value,
            "queries": result.get("queries", [])
        }
        
        # Add Mermaid diagram if requested
        if include_mermaid and mode == QueryMode.CODEMAP:
            codemap = extract_codemap(result)
            if codemap:
                formatted["mermaid_diagram"] = MermaidGenerator.generate(codemap)
                formatted["codemap"] = codemap.model_dump()
        
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["result"] = formatted
        tasks[task_id]["completed_at"] = time.time()
        
        elapsed = int(time.time() - tasks[task_id]["created_at"])
        logger.info(f"Task {task_id} completed in {elapsed}s")
        
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        tasks[task_id]["completed_at"] = time.time()
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)


# =============================================================================
# MCP SERVER
# =============================================================================

mcp = FastMCP("deepwiki-mcp")


# =============================================================================
# MCP TOOLS
# =============================================================================

@mcp.tool()
async def deepwiki_query(
    question: Annotated[str, Field(
        description="Natural language question about the codebase. Examples: 'How does authentication work?', 'Show me the data flow for user registration'",
        min_length=3,
        max_length=2000
    )],
    repos: Annotated[List[str], Field(
        description="List of GitHub repositories in 'owner/repo' format. Example: ['facebook/react', 'vercel/next.js']. Maximum 5 repositories.",
        min_length=1,
        max_length=5
    )],
    mode: Annotated[QueryMode, Field(
        description="Query mode: 'fast' (5-15s) for quick searches, 'deep' (30-90s) for thorough analysis, 'codemap' (20-60s) for visual flow diagrams"
    )] = QueryMode.FAST,
    context: Annotated[Optional[str], Field(
        description="Additional context to guide the search. Example: 'Focus on React hooks', 'Look at recent changes'"
    )] = None,
    generate_summary: Annotated[bool, Field(
        description="Whether to generate a summary of findings"
    )] = True,
    include_mermaid: Annotated[bool, Field(
        description="Include Mermaid diagram in response (only works with 'codemap' mode)"
    )] = False
) -> str:
    """
    Query code repositories using natural language AI search.
    
    This tool searches and analyzes code across GitHub repositories. It returns
    a TASK ID immediately and executes the query in the background.
    
    ASYNC EXECUTION:
    - Query is submitted and runs in background
    - Returns task_id immediately (no waiting)
    - Use deepwiki_check_task(task_id) to retrieve results
    
    MODES:
    - FAST (5-15s): Quick searches for specific code patterns
    - DEEP (30-90s): Thorough analysis with detailed explanations  
    - CODEMAP (20-60s): Visual flow diagrams showing code execution
    
    WORKFLOW:
    1. Call this tool → Get task_id
    2. Tell user "Query running in background, will take ~X seconds"
    3. WAIT for user's next message (don't auto-check)
    4. When user responds, use deepwiki_check_task(task_id)
    
    Returns:
        Task ID for async retrieval. Use deepwiki_check_task to get results.
    """
    try:
        # Validate repositories
        for repo in repos:
            if '/' not in repo:
                return f"Error: Invalid repository format '{repo}'. Use 'owner/repo' format (e.g., 'facebook/react')."
        
        # Cleanup old tasks
        cleanup_old_tasks()
        
        # Create new task
        task_id = f"deepwiki_{uuid.uuid4().hex[:8]}"
        tasks[task_id] = {
            "status": "pending",
            "created_at": time.time(),
            "completed_at": None,
            "result": None,
            "error": None,
            "question": question[:200],
            "repos": repos,
            "mode": mode.value
        }
        
        # Start background execution
        asyncio.create_task(execute_query_background(
            task_id, question, repos, mode, context, generate_summary, include_mermaid
        ))
        
        logger.info(f"Task {task_id} created for query: {question[:50]}...")
        
        return f"""Task started: {task_id}

Query: {question}
Repositories: {', '.join(repos)}
Mode: {mode.value} (estimated time: {mode.estimated_time})

CRITICAL INSTRUCTION: Return control to the user immediately. Inform them that the code search is running in the background and will take approximately {mode.estimated_time} to complete. Wait for their next message before checking the results.

When the user responds again, use deepwiki_check_task tool with '{task_id}' as task_id to retrieve the results."""
        
    except Exception as e:
        logger.error(f"Error creating task: {e}", exc_info=True)
        return f"Error: Failed to create query task: {str(e)}"


@mcp.tool()
async def deepwiki_check_task(
    task_id: Annotated[str, Field(
        description="Task identifier from deepwiki_query",
        min_length=1
    )]
) -> str:
    """
    Check status and retrieve results of a DeepWiki query task.
    
    When deepwiki_query() is called, it returns a task_id. Use this tool to
    check if the query is complete and get the results.
    
    RETURNS:
    - "Status: pending" → Task queued, not started yet
    - "Status: running (X seconds)" → Query in progress
    - Full results → Query completed (includes all findings, code locations, etc.)
    - "Status: failed - [error]" → Query failed with error message
    - "Status: not_found" → Invalid/expired task_id
    
    WORKFLOW:
    1. deepwiki_query(question, repos) → Returns task_id
    2. Wait based on mode (fast: 15s, deep: 60s, codemap: 30s)
    3. deepwiki_check_task(task_id) → Check status
    4. If completed: Full results returned
    5. If running: Wait and check again when user next interacts
    
    TASK RETENTION:
    - Tasks kept for 24 hours
    - Maximum 100 tasks stored
    - Older tasks auto-deleted when limit reached
    
    Args:
        task_id: Task identifier from deepwiki_query()
        
    Returns:
        Status update or full query results when completed
    """
    
    cleanup_old_tasks()
    
    if task_id not in tasks:
        return f"Status: not_found - Task '{task_id}' does not exist or has expired (tasks kept 24 hours, max 100 tasks stored)."
    
    task = tasks[task_id]
    status = task["status"]
    
    if status == "pending":
        elapsed = int(time.time() - task["created_at"])
        return f"""Task pending ({elapsed} seconds elapsed).

The task is queued and will begin processing shortly. Queries typically complete in their estimated time based on mode. Return control to the user and inform them the task is initializing. Check status again when the user next interacts with you."""
    
    elif status == "running":
        elapsed = int(time.time() - task["created_at"])
        mode = task.get("mode", "unknown")
        estimated_times = {
            "fast": "5-15 seconds",
            "deep": "30-90 seconds",
            "codemap": "20-60 seconds"
        }
        estimated = estimated_times.get(mode, "30-60 seconds")
        
        return f"""Task still running ({elapsed} seconds elapsed).

Mode: {mode} (estimated time: {estimated})
Question: {task['question']}
Repositories: {', '.join(task['repos'])}

The query is actively searching and analyzing code. Return control to the user and inform them the task is still in progress. Check status again when the user next interacts with you."""
    
    elif status == "completed":
        result = task["result"]
        
        # Extract the clean answer from the verbose API response
        answer_text = _extract_answer_from_response(result)
        
        # Format the response nicely
        response = f"""✅ Query Completed Successfully

**Question:** {result['question']}
**Repositories:** {', '.join(result['repos'])}
**Mode:** {result['mode']}

---

**Answer:**

{answer_text}
"""
        
        return response
    
    elif status == "failed":
        elapsed = int(time.time() - task["created_at"])
        return f"""Status: failed ({elapsed} seconds elapsed)

Error: {task['error']}

The query encountered an error. This might be due to:
- Repository not indexed
- Network issues
- Invalid query parameters
- API timeout

Try:
- Using 'fast' mode instead of 'deep'
- Simplifying your question
- Checking if the repository exists and is public
- Trying again in a moment"""
    
    else:
        return f"Status: unknown - Unexpected task state: {status}"


@mcp.tool()
async def deepwiki_search_repos(
    search: Annotated[str, Field(
        description="Search term to find repositories. Example: 'react', 'machine learning', 'web framework'",
        min_length=1,
        max_length=100
    )]
) -> str:
    """
    Search for indexed repositories available for querying.
    
    Use this to discover which repositories are available in the DeepWiki
    index before querying them. Helps prevent errors from querying
    non-indexed repositories.
    
    Args:
        search: Search term for repositories
        
    Returns:
        List of matching repositories with metadata
    """
    try:
        client = await get_client()
        
        result = await client._request(
            "GET",
            f"/ada/list_public_indexes?search_repo={search}"
        )
        
        repos_found = result.get("repositories", [])
        
        if not repos_found:
            return f"""No repositories found matching '{search}'.

Try:
- Broader search terms (e.g., 'react' instead of 'react-dom')
- Popular repository names
- Framework or library names"""
        
        response = f"""Found {len(repos_found)} repositories matching '{search}':

"""
        for repo in repos_found[:10]:  # Limit to first 10
            name = repo.get("name", "unknown")
            description = repo.get("description", "No description")
            response += f"- **{name}**: {description}\n"
        
        if len(repos_found) > 10:
            response += f"\n... and {len(repos_found) - 10} more repositories."
        
        return response
        
    except Exception as e:
        logger.error(f"Error searching repos: {e}", exc_info=True)
        return f"Error: Failed to search repositories: {str(e)}"


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the MCP server."""
    logger.info("=" * 70)
    logger.info("DeepWiki MCP Server - Async Task-Based Architecture")
    logger.info("=" * 70)
    logger.info(f"API URL: {settings.deepwiki_api_url}")
    logger.info(f"Max concurrent queries: {settings.max_concurrent_queries}")
    logger.info(f"Poll interval: {settings.poll_interval_ms}ms")
    logger.info(f"Log level: {settings.log_level}")
    logger.info(f"Task retention: {TASK_EXPIRY_HOURS}h, max {MAX_TASKS} tasks")
    logger.info("=" * 70)
    
    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()
