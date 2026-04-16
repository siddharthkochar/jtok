# jtok installer — downloads and configures jtok for Claude Code
# Usage: irm https://raw.githubusercontent.com/siddharthkochar/jtok/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$REPO = "https://raw.githubusercontent.com/siddharthkochar/jtok/main"
$INSTALL_DIR = Join-Path $HOME ".claude\jtok"
$BIN_DIR = Join-Path $HOME ".local\bin"

Write-Host "Installing jtok..."

# Check Python
try {
    $null = & python --version 2>&1
} catch {
    Write-Host "Error: Python is required. Install it from https://python.org" -ForegroundColor Red
    exit 1
}

# Create directories
New-Item -ItemType Directory -Path "$INSTALL_DIR\hooks" -Force | Out-Null
New-Item -ItemType Directory -Path $BIN_DIR -Force | Out-Null

# Download files
Write-Host "  Downloading jtok.py..."
Invoke-WebRequest -Uri "$REPO/jtok.py" -OutFile "$INSTALL_DIR\jtok.py" -UseBasicParsing

Write-Host "  Downloading hooks..."
Invoke-WebRequest -Uri "$REPO/hooks/jtok-read.sh" -OutFile "$INSTALL_DIR\hooks\jtok-read.sh" -UseBasicParsing
Invoke-WebRequest -Uri "$REPO/hooks/jtok-mcp.sh" -OutFile "$INSTALL_DIR\hooks\jtok-mcp.sh" -UseBasicParsing

# Create 'jtok' command on PATH
Write-Host "  Creating 'jtok' shim..."
@"
@echo off
python "$INSTALL_DIR\jtok.py" %*
"@ | Out-File -FilePath "$BIN_DIR\jtok.bat" -Encoding ASCII

# Configure Claude Code hooks
Write-Host "  Configuring Claude Code hooks..."
& python "$INSTALL_DIR\jtok.py" install

Write-Host ""
Write-Host "Done! jtok is now active in Claude Code."

$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -like "*$BIN_DIR*") {
    Write-Host "Run 'jtok status' to verify."
} else {
    Write-Host "Add $BIN_DIR to your PATH, then run 'jtok status' to verify."
}
