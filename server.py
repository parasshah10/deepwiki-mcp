#!/usr/bin/env python3
"""
DeepWiki MCP Server - Production Grade Implementation
A Model Context Protocol server for querying code repositories using DeepWiki AI.

Features:
- Async-first architecture for non-blocking operations
- Intelligent retry logic with exponential backoff
- Streaming progress updates for long-running queries
- Mermaid diagram generation from codemaps
- Comprehensive error handling and logging
- Type-safe with Pydantic validation
- Resource-pooled HTTP client
"""

import asyncio
import logging
import os
import json
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Annotated, Union
from uuid import uuid4

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator
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
        description="HTTP read timeout in seconds (long for deep mode)"
    )
    max_concurrent_queries: int = Field(
        default=5,
        description="Maximum concurrent queries allowed"
    )
    enable_caching: bool = Field(
        default=True,
        description="Enable result caching"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
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


class QueryState(str, Enum):
    """Query execution states."""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


# =============================================================================
# DATA MODELS
# =============================================================================

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


class ProgressUpdate(BaseModel):
    """Progress update for streaming queries."""
    type: str = "progress"
    query_id: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    progress_percent: Optional[int] = None


# =============================================================================
# MERMAID DIAGRAM GENERATOR
# =============================================================================

class MermaidGenerator:
    """Generates Mermaid flowcharts from codemaps."""
    
    TRACE_COLORS = [
        ("#e8f5e9", "#4caf50"),  # green
        ("#e3f2fd", "#2196f3"),  # blue
        ("#fff3e0", "#ff9800"),  # orange
        ("#f3e5f5", "#9c27b0"),  # purple
        ("#fff8e1", "#ffc107"),  # yellow
        ("#fce4ec", "#e91e63"),  # pink
        ("#e0f2f1", "#009688"),  # teal
        ("#fbe9e7", "#ff5722"),  # deep orange
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
        
        # Generate subgraphs for each trace
        for i, trace in enumerate(codemap.traces):
            sg_id = cls.sanitize_id(f"trace_{trace.id}")
            title = cls.escape_label(trace.title)
            
            lines.append("")
            lines.append(f'    subgraph {sg_id}["{trace.id}. {title}"]')
            
            # Add locations
            for loc in trace.locations:
                loc_id = cls.sanitize_id(f"loc_{loc.id}")
                loc_title = cls.escape_label(loc.title)
                filename = cls.short_path(loc.path)
                label = f"{loc_title}\\n{filename}:{loc.line_number}"
                lines.append(f'        {loc_id}["{label}"]')
            
            lines.append("    end")
            
            # Connect locations sequentially within trace
            for j in range(len(trace.locations) - 1):
                a = cls.sanitize_id(f"loc_{trace.locations[j].id}")
                b = cls.sanitize_id(f"loc_{trace.locations[j + 1].id}")
                lines.append(f"    {a} --> {b}")
        
        # Connect traces with dashed lines
        for i in range(len(codemap.traces) - 1):
            curr_locs = codemap.traces[i].locations
            next_locs = codemap.traces[i + 1].locations
            if curr_locs and next_locs:
                a = cls.sanitize_id(f"loc_{curr_locs[-1].id}")
                b = cls.sanitize_id(f"loc_{next_locs[0].id}")
                lines.append(f"    {a} -.-> {b}")
        
        # Add styling
        lines.append("")
        for i, trace in enumerate(codemap.traces):
            sg_id = cls.sanitize_id(f"trace_{trace.id}")
            fill, stroke = cls.TRACE_COLORS[i % len(cls.TRACE_COLORS)]
            lines.append(f"    style {sg_id} fill:{fill},stroke:{stroke},stroke-width:2px")
        
        return '\n'.join(lines)


# =============================================================================
# API CLIENT
# =============================================================================

class DeepWikiClient:
    """Async HTTP client for DeepWiki API with retry logic and connection pooling."""
    
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
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
    
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
                raise ValueError(f"Server error ({e.response.status_code}). The service may be temporarily unavailable.")
            elif e.response.status_code == 404:
                raise ValueError("Resource not found. Check your query ID or repository name.")
            else:
                raise ValueError(f"Request failed: {e.response.text}")
        except httpx.TimeoutException:
            logger.error("Request timeout")
            raise ValueError("Request timed out. Try using 'fast' mode or a simpler query.")
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
    
    async def get_repo_status(self, repo_name: str) -> Dict[str, Any]:
        """Get repository indexing status."""
        logger.debug(f"Checking status for repo {repo_name}")
        result = await self._request(
            "GET",
            f"/ada/public_repo_indexing_status?repo_name={repo_name}"
        )
        return {"repo_name": repo_name, **result}
    
    async def list_repos(self, search_term: str) -> Dict[str, Any]:
        """Search for indexed repositories."""
        logger.debug(f"Searching repos: {search_term}")
        return await self._request(
            "GET",
            f"/ada/list_public_indexes?search_repo={search_term}"
        )
    
    async def warm_repo(self, repo_name: str) -> Dict[str, Any]:
        """Pre-warm repository cache."""
        logger.info(f"Warming repo cache: {repo_name}")
        result = await self._request(
            "POST",
            f"/ada/warm_public_repo?repo_name={repo_name}"
        )
        return {"repo_name": repo_name, **result}
    
    async def poll_until_done(
        self,
        query_id: str,
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Poll query status until completion."""
        logger.info(f"Polling query {query_id}...")
        
        for attempt in range(settings.poll_max_attempts):
            await asyncio.sleep(settings.poll_interval_ms / 1000.0)
            
            result = await self.get_query_status(query_id)
            queries = result.get("queries", [])
            
            if queries:
                last_query = queries[-1]
                state = last_query.get("state")
                
                # Send progress update
                if callback:
                    progress = ProgressUpdate(
                        query_id=query_id,
                        message=f"Query status: {state}",
                        progress_percent=min(95, int((attempt / settings.poll_max_attempts) * 100))
                    )
                    await callback(progress)
                
                if state == "done":
                    logger.info(f"Query {query_id} completed successfully")
                    return result
                elif state == "failed":
                    error_msg = last_query.get("error", "Query failed")
                    logger.error(f"Query {query_id} failed: {error_msg}")
                    raise ValueError(f"Query failed: {error_msg}")
        
        timeout_sec = (settings.poll_interval_ms * settings.poll_max_attempts) / 1000
        logger.error(f"Query {query_id} timed out after {timeout_sec}s")
        raise ValueError(
            f"Query timed out after {timeout_sec}s. "
            "Try using 'fast' mode or breaking down your query into smaller parts."
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

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


def format_query_result(result: Dict[str, Any], include_mermaid: bool = False) -> Dict[str, Any]:
    """Format query result for presentation."""
    formatted = {
        "query_id": result.get("query_id"),
        "status": "completed",
        "queries": result.get("queries", [])
    }
    
    # Extract codemap if requested
    if include_mermaid:
        codemap = extract_codemap(result)
        if codemap:
            formatted["mermaid_diagram"] = MermaidGenerator.generate(codemap)
            formatted["codemap"] = codemap.model_dump()
    
    return formatted


# =============================================================================
# MCP SERVER
# =============================================================================

mcp = FastMCP("deepwiki-mcp")

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
# MCP TOOLS
# =============================================================================

@mcp.tool()
async def deepwiki_query(
    question: Annotated[str, Field(
        description="Natural language question about the codebase. Examples: 'How does authentication work?', 'Where is error handling implemented?', 'Show me the data flow for user registration'",
        min_length=3,
        max_length=2000
    )],
    repos: Annotated[List[str], Field(
        description="List of GitHub repositories in 'owner/repo' format. Example: ['facebook/react', 'vercel/next.js']. Maximum 5 repositories.",
        min_length=1,
        max_length=5
    )],
    mode: Annotated[QueryMode, Field(
        description="Query mode: 'fast' for quick searches (2-5s), 'deep' for thorough analysis (30-60s), 'codemap' for visual flow diagrams (20-40s)"
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
) -> Dict[str, Any]:
    """
    Query code repositories using natural language AI search.
    
    This tool searches and analyzes code across GitHub repositories to answer
    questions about implementation details, architecture, and code patterns.
    
    The tool supports three modes:
    - FAST: Quick searches for finding specific code patterns (recommended for most queries)
    - DEEP: Thorough analysis with detailed explanations (use for complex architectural questions)
    - CODEMAP: Generates visual flow diagrams showing code execution paths
    
    Returns structured results including code locations, explanations, and 
    optionally visual Mermaid diagrams (in codemap mode with include_mermaid=True).
    
    Examples:
    - "How does React handle component updates?"
    - "Where is authentication implemented in Next.js?"
    - "Show me the data flow for API requests"
    """
    try:
        client = await get_client()
        
        # Validate repositories
        for repo in repos:
            if '/' not in repo:
                return {
                    "error": f"Invalid repository format: '{repo}'. Use 'owner/repo' format.",
                    "example": "facebook/react"
                }
        
        # Create query request
        query_id = str(uuid4())
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
        logger.info(f"Waiting for query {query_id} to complete (mode: {mode.value})...")
        result = await client.poll_until_done(query_id)
        
        # Format and return
        return format_query_result(
            result,
            include_mermaid=(include_mermaid and mode == QueryMode.CODEMAP)
        )
        
    except ValueError as e:
        logger.error(f"Query failed: {e}")
        return {
            "error": str(e),
            "suggestion": "Try using 'fast' mode or simplifying your query"
        }
    except Exception as e:
        logger.error(f"Unexpected error in query: {e}", exc_info=True)
        return {
            "error": f"Unexpected error: {str(e)}",
            "type": type(e).__name__
        }


@mcp.tool()
async def deepwiki_get_result(
    query_id: Annotated[str, Field(
        description="Query ID from a previous deepwiki_query call",
        min_length=1
    )],
    include_mermaid: Annotated[bool, Field(
        description="Include Mermaid diagram if available (for codemap queries)"
    )] = False
) -> Dict[str, Any]:
    """
    Retrieve results from a previous query.
    
    Use this to fetch results from a query that was already submitted,
    or to check the status of a long-running query.
    
    Returns the same format as deepwiki_query.
    """
    try:
        client = await get_client()
        result = await client.get_query_status(query_id)
        
        # Check if query is done
        queries = result.get("queries", [])
        if queries:
            state = queries[-1].get("state")
            if state != "done":
                return {
                    "query_id": query_id,
                    "status": state,
                    "message": f"Query is still {state}. Please try again in a few seconds."
                }
        
        return format_query_result(result, include_mermaid=include_mermaid)
        
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error retrieving query: {e}", exc_info=True)
        return {"error": f"Failed to retrieve query: {str(e)}"}


@mcp.tool()
async def deepwiki_repo_status(
    repo: Annotated[str, Field(
        description="Repository name in 'owner/repo' format (e.g., 'facebook/react')",
        min_length=1
    )]
) -> Dict[str, Any]:
    """
    Check if a repository is indexed and ready for querying.
    
    Before querying a repository, you can use this tool to verify it's
    available in the DeepWiki index. If it's not indexed, you may need
    to use deepwiki_warm_repo first.
    
    Returns indexing status and metadata about the repository.
    """
    try:
        if '/' not in repo:
            return {
                "error": f"Invalid repository format: '{repo}'",
                "expected_format": "owner/repo",
                "example": "facebook/react"
            }
        
        client = await get_client()
        return await client.get_repo_status(repo)
        
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error checking repo status: {e}", exc_info=True)
        return {"error": f"Failed to check repository status: {str(e)}"}


@mcp.tool()
async def deepwiki_search_repos(
    search: Annotated[str, Field(
        description="Search term to find repositories. Example: 'react', 'machine learning', 'web framework'",
        min_length=1,
        max_length=100
    )]
) -> Dict[str, Any]:
    """
    Search for indexed repositories available for querying.
    
    Use this to discover which repositories are available in the DeepWiki
    index. Useful for finding repositories related to your topic of interest.
    
    Returns a list of matching repositories with metadata.
    """
    try:
        client = await get_client()
        result = await client.list_repos(search)
        
        # Add helpful metadata
        repos_found = result.get("repositories", [])
        return {
            "search_term": search,
            "count": len(repos_found),
            "repositories": repos_found
        }
        
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error searching repos: {e}", exc_info=True)
        return {"error": f"Failed to search repositories: {str(e)}"}


@mcp.tool()
async def deepwiki_warm_repo(
    repo: Annotated[str, Field(
        description="Repository name in 'owner/repo' format to pre-warm in the cache",
        min_length=1
    )]
) -> Dict[str, Any]:
    """
    Pre-warm a repository's cache for faster queries.
    
    If you're planning to make multiple queries against a repository,
    use this tool first to ensure it's loaded and ready. This can
    significantly improve query response times.
    
    Returns confirmation of cache warming status.
    """
    try:
        if '/' not in repo:
            return {
                "error": f"Invalid repository format: '{repo}'",
                "expected_format": "owner/repo",
                "example": "facebook/react"
            }
        
        client = await get_client()
        result = await client.warm_repo(repo)
        
        return {
            **result,
            "message": f"Repository '{repo}' cache warmed successfully",
            "next_step": "You can now query this repository with deepwiki_query"
        }
        
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error warming repo: {e}", exc_info=True)
        return {"error": f"Failed to warm repository: {str(e)}"}


# =============================================================================
# SERVER LIFECYCLE
# =============================================================================

# Note: FastMCP doesn't have on_shutdown hook
# Cleanup is handled automatically by DeepWikiClient context manager


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the MCP server."""
    logger.info("=" * 70)
    logger.info("DeepWiki MCP Server - Production Grade")
    logger.info("=" * 70)
    logger.info(f"API URL: {settings.deepwiki_api_url}")
    logger.info(f"Max concurrent queries: {settings.max_concurrent_queries}")
    logger.info(f"Poll interval: {settings.poll_interval_ms}ms")
    logger.info(f"Log level: {settings.log_level}")
    logger.info("=" * 70)
    
    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()
