# Installation & Running Guide 🚀

This guide shows **all the different ways** you can install and run the DeepWiki MCP server.

## Method 1: Direct Run (Quickest) ⚡

**Best for:** Testing, development, quick start

```bash
# Install dependencies
pip install fastmcp httpx pydantic pydantic-settings tenacity

# Run directly
python deepwiki_mcp.py
```

Or if you're using the package structure:
```bash
python -m deepwiki_mcp.server
```

---

## Method 2: Install as Package (Recommended) 📦

**Best for:** Production use, integration with Claude Desktop

### Option A: Install from Local Directory

```bash
# Clone or download the repository
cd deepwiki-mcp

# Install in editable mode (for development)
pip install -e .

# Or install normally
pip install .

# Run the server
deepwiki-mcp
```

### Option B: Install from GitHub

```bash
# Install directly from GitHub
pip install git+https://github.com/yourusername/deepwiki-mcp.git

# Run the server
deepwiki-mcp
```

### Option C: Install with Optional Dependencies

```bash
# Install with development tools
pip install -e ".[dev]"

# Install with performance optimizations
pip install -e ".[performance]"

# Install everything
pip install -e ".[dev,performance]"
```

---

## Method 3: Using uv (Fastest) 🚄

**Best for:** Modern Python workflow, fastest installation

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Run
deepwiki-mcp
```

---

## Method 4: Docker (Most Isolated) 🐳

**Best for:** Deployment, containerized environments

Create a `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY deepwiki_mcp/ deepwiki_mcp/
COPY README.md .

RUN pip install --no-cache-dir .

CMD ["deepwiki-mcp"]
```

Build and run:
```bash
docker build -t deepwiki-mcp .
docker run -it deepwiki-mcp
```

---

## Integration with Claude Desktop

### After Installation

Once installed, add to your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

### Configuration Options

#### Option 1: Using Installed Command
```json
{
  "mcpServers": {
    "deepwiki": {
      "command": "deepwiki-mcp"
    }
  }
}
```

#### Option 2: Using Python Module
```json
{
  "mcpServers": {
    "deepwiki": {
      "command": "python",
      "args": ["-m", "deepwiki_mcp.server"]
    }
  }
}
```

#### Option 3: Using Direct Path
```json
{
  "mcpServers": {
    "deepwiki": {
      "command": "python",
      "args": ["/full/path/to/deepwiki_mcp/server.py"]
    }
  }
}
```

#### With Environment Variables
```json
{
  "mcpServers": {
    "deepwiki": {
      "command": "deepwiki-mcp",
      "env": {
        "DEEPWIKI_LOG_LEVEL": "DEBUG",
        "DEEPWIKI_MAX_CONCURRENT_QUERIES": "10"
      }
    }
  }
}
```

---

## Publishing to GitHub

### Step 1: Initialize Git Repository

```bash
cd deepwiki-mcp
git init
git add .
git commit -m "Initial commit: DeepWiki MCP Server"
```

### Step 2: Create .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo

# Environment
.env
.env.local

# Testing
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db
```

### Step 3: Create GitHub Repository

```bash
# On GitHub, create a new repository named "deepwiki-mcp"

# Link local repo to GitHub
git remote add origin https://github.com/yourusername/deepwiki-mcp.git
git branch -M main
git push -u origin main
```

### Step 4: Add a LICENSE

Create `LICENSE` file (MIT License example):
```
MIT License

Copyright (c) 2026 Your Name

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Publishing to PyPI (Optional)

### Build the Package

```bash
# Install build tools
pip install build twine

# Build distributions
python -m build

# Check the distribution
twine check dist/*
```

### Upload to PyPI

```bash
# Upload to Test PyPI first
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ deepwiki-mcp

# If all good, upload to real PyPI
twine upload dist/*
```

Then users can install with:
```bash
pip install deepwiki-mcp
```

---

## Verification

After installation, verify everything works:

```bash
# Check installation
deepwiki-mcp --help  # Should show help or start server

# Or
python -c "import deepwiki_mcp; print(deepwiki_mcp.__version__)"
```

---

## Development Workflow

### Setup Development Environment

```bash
# Clone the repo
git clone https://github.com/yourusername/deepwiki-mcp.git
cd deepwiki-mcp

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests (when you add them)
pytest

# Format code
black .

# Lint code
ruff check .

# Type check
mypy deepwiki_mcp/
```

### Make Changes and Test

```bash
# Make changes to the code
vim deepwiki_mcp/server.py

# Test locally
deepwiki-mcp

# Run in debug mode
DEEPWIKI_LOG_LEVEL=DEBUG deepwiki-mcp
```

---

## Troubleshooting

### "Command not found: deepwiki-mcp"

**Solution:**
```bash
# Ensure the package is installed
pip install -e .

# Or use the full Python path
python -m deepwiki_mcp.server
```

### Import Errors

**Solution:**
```bash
# Reinstall dependencies
pip install --force-reinstall -e .
```

### Configuration Issues

**Solution:**
```bash
# Check your .env file
cat .env

# Or set environment variables directly
export DEEPWIKI_API_URL=https://api.devin.ai
export DEEPWIKI_LOG_LEVEL=DEBUG
```

---

## Project Structure

```
deepwiki-mcp/
├── deepwiki_mcp/           # Main package
│   ├── __init__.py         # Package initialization
│   ├── server.py           # Main server code
│   └── py.typed            # Type checking marker
├── tests/                  # Tests (optional)
│   └── test_server.py
├── examples/               # Example scripts
│   └── examples.py
├── docs/                   # Documentation
│   ├── README.md
│   ├── QUICKSTART.md
│   └── ARCHITECTURE.md
├── .env.example            # Configuration template
├── .gitignore              # Git ignore rules
├── pyproject.toml          # Project configuration
├── LICENSE                 # License file
└── README.md               # Main documentation
```

---

## Next Steps

1. ✅ Choose your installation method
2. ✅ Install the package
3. ✅ Configure Claude Desktop
4. ✅ Test with a simple query
5. ✅ (Optional) Push to GitHub
6. ✅ (Optional) Publish to PyPI

Happy coding! 🎉
