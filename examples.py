#!/usr/bin/env python3
"""
Example usage and testing script for DeepWiki MCP Server.
This demonstrates how to use the MCP tools programmatically.
"""

import asyncio
import json
from deepwiki_mcp import (
    DeepWikiClient,
    QueryRequest,
    QueryMode,
    MermaidGenerator,
    extract_codemap,
)


async def example_basic_query():
    """Example: Basic fast query."""
    print("\n" + "=" * 70)
    print("Example 1: Basic Fast Query")
    print("=" * 70)
    
    async with DeepWikiClient() as client:
        # Create query
        request = QueryRequest(
            engine_id=QueryMode.FAST.engine_id,
            user_query="How does authentication work?",
            repo_names=["facebook/react"],
            query_id=str(uuid4()),
            generate_summary=True
        )
        
        # Submit and wait
        await client.submit_query(request)
        result = await client.poll_until_done(request.query_id)
        
        print(f"\nQuery ID: {request.query_id}")
        print(f"Status: {result.get('queries', [{}])[-1].get('state', 'unknown')}")
        print("\nFirst 500 chars of result:")
        print(json.dumps(result, indent=2)[:500])


async def example_deep_analysis():
    """Example: Deep mode for thorough analysis."""
    print("\n" + "=" * 70)
    print("Example 2: Deep Mode Analysis")
    print("=" * 70)
    
    async with DeepWikiClient() as client:
        request = QueryRequest(
            engine_id=QueryMode.DEEP.engine_id,
            user_query="Explain the component lifecycle and state management",
            repo_names=["facebook/react"],
            additional_context="Focus on hooks and functional components",
            query_id=str(uuid4()),
            generate_summary=True
        )
        
        await client.submit_query(request)
        print(f"\nQuery submitted: {request.query_id}")
        print("Waiting for deep analysis (this may take 30-60 seconds)...")
        
        result = await client.poll_until_done(request.query_id)
        print(f"Analysis complete!")
        print(f"Result size: {len(json.dumps(result))} bytes")


async def example_codemap_with_diagram():
    """Example: Generate visual codemap diagram."""
    print("\n" + "=" * 70)
    print("Example 3: Codemap with Mermaid Diagram")
    print("=" * 70)
    
    async with DeepWikiClient() as client:
        request = QueryRequest(
            engine_id=QueryMode.CODEMAP.engine_id,
            user_query="Show the authentication flow",
            repo_names=["facebook/react"],
            query_id=str(uuid4()),
            generate_summary=False
        )
        
        await client.submit_query(request)
        result = await client.poll_until_done(request.query_id)
        
        # Extract and generate diagram
        codemap = extract_codemap(result)
        if codemap:
            diagram = MermaidGenerator.generate(codemap)
            print("\nMermaid Diagram Generated!")
            print("-" * 70)
            print(diagram)
            print("-" * 70)
            
            # Save to file
            with open("/tmp/codemap.mmd", "w") as f:
                f.write(diagram)
            print("\nDiagram saved to: /tmp/codemap.mmd")
        else:
            print("\nNo codemap found in result")


async def example_multi_repo_comparison():
    """Example: Query multiple repositories."""
    print("\n" + "=" * 70)
    print("Example 4: Multi-Repository Comparison")
    print("=" * 70)
    
    async with DeepWikiClient() as client:
        request = QueryRequest(
            engine_id=QueryMode.FAST.engine_id,
            user_query="How is routing implemented?",
            repo_names=["facebook/react", "vercel/next.js"],
            query_id=str(uuid4()),
            generate_summary=True
        )
        
        await client.submit_query(request)
        print(f"\nComparing routing implementations across 2 repos...")
        result = await client.poll_until_done(request.query_id)
        print(f"Comparison complete!")


async def example_repo_management():
    """Example: Check status and warm repos."""
    print("\n" + "=" * 70)
    print("Example 5: Repository Management")
    print("=" * 70)
    
    async with DeepWikiClient() as client:
        # Check status
        print("\nChecking React repository status...")
        status = await client.get_repo_status("facebook/react")
        print(f"Status: {json.dumps(status, indent=2)}")
        
        # Search for repos
        print("\nSearching for 'machine learning' repositories...")
        repos = await client.list_repos("machine learning")
        print(f"Found {len(repos.get('repositories', []))} repositories")
        
        # Warm a repo
        print("\nWarming Express.js repository...")
        warm_result = await client.warm_repo("expressjs/express")
        print(f"Warm result: {json.dumps(warm_result, indent=2)}")


async def example_error_handling():
    """Example: Handling errors gracefully."""
    print("\n" + "=" * 70)
    print("Example 6: Error Handling")
    print("=" * 70)
    
    async with DeepWikiClient() as client:
        # Invalid repo format
        print("\n1. Testing invalid repo format...")
        try:
            await client.get_repo_status("invalid-repo-format")
        except ValueError as e:
            print(f"Caught expected error: {e}")
        
        # Non-existent query ID
        print("\n2. Testing non-existent query...")
        try:
            await client.get_query_status("non-existent-query-id")
        except ValueError as e:
            print(f"Caught expected error: {e}")


async def example_concurrent_queries():
    """Example: Running multiple queries concurrently."""
    print("\n" + "=" * 70)
    print("Example 7: Concurrent Queries")
    print("=" * 70)
    
    async with DeepWikiClient() as client:
        # Create multiple queries
        queries = [
            QueryRequest(
                engine_id=QueryMode.FAST.engine_id,
                user_query="How does authentication work?",
                repo_names=["facebook/react"],
                query_id=str(uuid4()),
                generate_summary=True
            ),
            QueryRequest(
                engine_id=QueryMode.FAST.engine_id,
                user_query="How is routing implemented?",
                repo_names=["vercel/next.js"],
                query_id=str(uuid4()),
                generate_summary=True
            ),
            QueryRequest(
                engine_id=QueryMode.FAST.engine_id,
                user_query="Show middleware implementation",
                repo_names=["expressjs/express"],
                query_id=str(uuid4()),
                generate_summary=True
            ),
        ]
        
        # Submit all queries
        print(f"\nSubmitting {len(queries)} queries concurrently...")
        await asyncio.gather(*[
            client.submit_query(q) for q in queries
        ])
        
        # Wait for all results
        print("Waiting for all queries to complete...")
        results = await asyncio.gather(*[
            client.poll_until_done(q.query_id) for q in queries
        ])
        
        print(f"\nAll {len(results)} queries completed!")
        for i, result in enumerate(results):
            state = result.get('queries', [{}])[-1].get('state', 'unknown')
            print(f"  Query {i+1}: {state}")


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("DeepWiki MCP Server - Example Usage")
    print("=" * 70)
    print("\nThis script demonstrates various usage patterns.")
    print("Note: Some examples may take time due to API processing.")
    
    examples = [
        ("Basic Query", example_basic_query),
        ("Deep Analysis", example_deep_analysis),
        ("Codemap Diagram", example_codemap_with_diagram),
        ("Multi-Repo Comparison", example_multi_repo_comparison),
        ("Repo Management", example_repo_management),
        ("Error Handling", example_error_handling),
        ("Concurrent Queries", example_concurrent_queries),
    ]
    
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    
    print("\nRunning all examples (this will take several minutes)...\n")
    
    for name, example_func in examples:
        try:
            await example_func()
        except Exception as e:
            print(f"\nExample '{name}' failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Examples Complete!")
    print("=" * 70)


if __name__ == "__main__":
    # Need to import uuid
    from uuid import uuid4
    
    # Run examples
    asyncio.run(main())
