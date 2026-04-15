# jtok installer — downloads and configures jtok for Claude Code
# Usage: irm https://raw.githubusercontent.com/siddharthkochar/jtok/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$REPO = "https://raw.githubusercontent.com/siddharthkochar/jtok/main"
$INSTALL_DIR = Join-Path $HOME ".claude\jtok"

Write-Host "Installing jtok..."

# Check Python
try {
    $null = & python --version 2>&1
} catch {
    Write-Host "Error: Python is required. Install it from https://python.org" -ForegroundColor Red
    exit 1
}

# Create install directory
New-Item -ItemType Directory -Path "$INSTALL_DIR\hooks" -Force | Out-Null

# Download files
Write-Host "  Downloading jtok.py..."
Invoke-WebRequest -Uri "$REPO/jtok.py" -OutFile "$INSTALL_DIR\jtok.py" -UseBasicParsing

Write-Host "  Downloading hooks..."
Invoke-WebRequest -Uri "$REPO/hooks/jtok-read.ps1" -OutFile "$INSTALL_DIR\hooks\jtok-read.ps1" -UseBasicParsing
Invoke-WebRequest -Uri "$REPO/hooks/jtok-mcp.ps1" -OutFile "$INSTALL_DIR\hooks\jtok-mcp.ps1" -UseBasicParsing

# Run install
Write-Host "  Configuring Claude Code hooks..."
& python "$INSTALL_DIR\jtok.py" install

Write-Host ""
Write-Host "Done! jtok is now active in Claude Code."
Write-Host "Run 'python $INSTALL_DIR\jtok.py status' to verify."
