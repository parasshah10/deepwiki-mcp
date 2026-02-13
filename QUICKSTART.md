# DeepWiki MCP Server - Quick Start Guide 🚀

## Installation (5 minutes)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure (Optional)
```bash
cp .env.example .env
# Edit .env if you need custom settings
```

### Step 3: Test the Server
```bash
python deepwiki_mcp.py
```

You should see:
```
======================================================================
DeepWiki MCP Server - Production Grade
======================================================================
API URL: https://api.devin.ai
Max concurrent queries: 5
Poll interval: 2000ms
Log level: INFO
======================================================================
```

## Integration with Claude Desktop

### macOS
Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "deepwiki": {
      "command": "python",
      "args": ["/full/path/to/deepwiki_mcp.py"]
    }
  }
}
```

### Windows
Edit: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "deepwiki": {
      "command": "python",
      "args": ["C:\\full\\path\\to\\deepwiki_mcp.py"]
    }
  }
}
```

### Linux
Edit: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "deepwiki": {
      "command": "python",
      "args": ["/full/path/to/deepwiki_mcp.py"]
    }
  }
}
```

## Example Conversations with Claude

### Example 1: Understanding React Hooks

**You:** "How do React hooks work internally?"

**Claude:** (Uses `deepwiki_query` automatically)
- Calls: `deepwiki_query(question="How do React hooks work internally?", repos=["facebook/react"], mode="deep")`
- Returns: Comprehensive explanation of hooks implementation

### Example 2: Finding Authentication Code

**You:** "Show me where authentication is handled in Next.js"

**Claude:** (Uses `deepwiki_query`)
- Calls: `deepwiki_query(question="Where is authentication handled?", repos=["vercel/next.js"], mode="fast")`
- Returns: Code locations and explanations

### Example 3: Visual Code Flow

**You:** "Create a diagram showing the API request flow in Express.js"

**Claude:** (Uses `deepwiki_query` with codemap)
- Calls: `deepwiki_query(question="API request flow", repos=["expressjs/express"], mode="codemap", include_mermaid=true)`
- Returns: Mermaid flowchart diagram

### Example 4: Comparing Implementations

**You:** "Compare how React and Vue handle state management"

**Claude:** (Makes two queries)
- Query 1: React state management
- Query 2: Vue state management
- Synthesizes comparison

### Example 5: Deep Dive

**You:** "I need a thorough analysis of how error boundaries work in React"

**Claude:** (Uses deep mode)
- Calls: `deepwiki_query(question="How do error boundaries work?", repos=["facebook/react"], mode="deep", context="Focus on error handling lifecycle")`
- Returns: In-depth analysis

## Common Use Cases

### 1. Learning a New Framework
```
You: "I'm learning Next.js. Explain the routing system."
Claude: [Uses deepwiki_query with fast mode]
```

### 2. Debugging
```
You: "Where might I find memory leaks in a React app?"
Claude: [Uses deepwiki_query with deep mode]
```

### 3. Architecture Review
```
You: "Show me the component hierarchy in this admin dashboard repo"
Claude: [Uses codemap mode with diagrams]
```

### 4. Finding Examples
```
You: "Show me examples of custom hooks in the React codebase"
Claude: [Uses fast mode to find patterns]
```

### 5. Migration Planning
```
You: "What would be involved in migrating from React 17 to 18?"
Claude: [Uses deep mode to analyze breaking changes]
```

## Tips for Best Results

### 1. Be Specific
❌ "Tell me about React"
✅ "How does React's virtual DOM diffing algorithm work?"

### 2. Provide Context
✅ "Explain React hooks, focusing on useEffect cleanup"
✅ "Show error handling in Express.js middleware"

### 3. Use the Right Mode
- **Fast mode**: "Where is X defined?"
- **Deep mode**: "Explain the architecture of Y"
- **Codemap mode**: "Show me the flow of Z"

### 4. Iterate
Start with fast mode, then go deeper:
1. Fast: "Where is authentication?"
2. Deep: "Explain this authentication implementation in detail"

### 5. Combine with Other Tools
- Use deepwiki to understand code
- Use Claude's analysis to apply learnings
- Use code generation to implement similar patterns

## Troubleshooting

### Server won't start
```bash
# Check Python version
python --version  # Should be 3.9+

# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### Claude can't see the tools
1. Restart Claude Desktop
2. Check config file location
3. Verify file paths are absolute
4. Check logs: Look for "DeepWiki MCP Server" in Claude's logs

### Queries are slow
- Use `fast` mode instead of `deep`
- Try `deepwiki_warm_repo` first
- Simplify your question
- Check your internet connection

### "Repository not found"
```bash
# Search for available repos first
deepwiki_search_repos(search="react")

# Warm the repo
deepwiki_warm_repo(repo="facebook/react")
```

## Advanced Usage

### Environment Variables
```bash
# Debug mode
export DEEPWIKI_LOG_LEVEL=DEBUG

# Faster polling
export DEEPWIKI_POLL_INTERVAL_MS=1000

# More concurrent queries
export DEEPWIKI_MAX_CONCURRENT_QUERIES=10
```

### Custom Configuration
```python
# In .env file
DEEPWIKI_API_URL=https://your-custom-api.com
DEEPWIKI_API_KEY=your_secret_key
DEEPWIKI_READ_TIMEOUT=300.0  # 5 minutes for very deep analysis
```

## Performance Optimization

### For Frequent Users
1. **Warm commonly used repos:**
   ```
   deepwiki_warm_repo("facebook/react")
   deepwiki_warm_repo("vercel/next.js")
   deepwiki_warm_repo("expressjs/express")
   ```

2. **Start with fast mode:**
   - Get quick results
   - Upgrade to deep only if needed

3. **Cache results:**
   - The server caches internally
   - Reuse query_ids with `deepwiki_get_result`

### For Power Users
```bash
# Increase limits for heavy usage
export DEEPWIKI_MAX_CONCURRENT_QUERIES=10
export DEEPWIKI_POLL_MAX_ATTEMPTS=200
export DEEPWIKI_READ_TIMEOUT=300.0
```

## Next Steps

1. ✅ Install and configure
2. ✅ Test with a simple query
3. ✅ Try different modes
4. ✅ Explore multiple repositories
5. ✅ Build something amazing!

## Resources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Protocol Spec](https://modelcontextprotocol.io)
- [Claude Desktop](https://claude.ai/download)

## Support

- Check logs: Look in Claude Desktop's console
- Debug mode: Set `DEEPWIKI_LOG_LEVEL=DEBUG`
- Test directly: Run `python deepwiki_mcp.py` to see startup logs

---

Happy coding! 🎉
