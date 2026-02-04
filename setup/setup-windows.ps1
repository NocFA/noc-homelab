# Windows Homelab Setup Script
# One-command deployment for noc-winlocal Real-Debrid automation
#
# Usage: .\setup-windows.ps1
#
# This script will:
# 1. Prompt for required API keys (Real-Debrid, Emby, Jellyfin)
# 2. Generate configs from .example templates
# 3. Create necessary directories
# 4. Import scheduled tasks
# 5. Start services

param(
    [switch]$SkipTaskImport,  # Skip importing scheduled tasks
    [switch]$SkipServiceStart  # Skip starting services after setup
)

$ErrorActionPreference = "Stop"

# Colors
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Error { Write-Host $args -ForegroundColor Red }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }

Write-Host ""
Write-Host "================================================" -ForegroundColor Magenta
Write-Host "  Windows Homelab Setup - Real-Debrid Pipeline  " -ForegroundColor Magenta
Write-Host "================================================" -ForegroundColor Magenta
Write-Host ""

# Detect repo root
$RepoRoot = Split-Path -Parent $PSScriptRoot
Write-Info "Repo root: $RepoRoot"

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Not running as Administrator. Some features (symlinks, scheduled tasks) may fail."
    Write-Warning "Recommended: Right-click PowerShell -> Run as Administrator"
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne 'y') { exit 1 }
}

# === STEP 1: Prompt for API Keys ===
Write-Host ""
Write-Host "[1/7] Collecting API Keys" -ForegroundColor Yellow
Write-Host "--------------------------------------"

Write-Info "You'll need:"
Write-Info "  - Real-Debrid API token (https://real-debrid.com/apitoken)"
Write-Info "  - Emby API key (Dashboard > Advanced > API Keys)"
Write-Info "  - Jellyfin API key (Dashboard > Advanced > API Keys)"
Write-Info "  - Plex token (optional, https://www.plex.tv/claim/)"
Write-Host ""

# Real-Debrid Token
$RD_TOKEN = Read-Host "Enter Real-Debrid API token (required)"
if (-not $RD_TOKEN) {
    Write-Error "Real-Debrid token is required for Zurg to work"
    exit 1
}

# Emby API Key
$EMBY_KEY = Read-Host "Enter Emby API key (or press Enter to skip)"

# Jellyfin API Key
$JELLYFIN_KEY = Read-Host "Enter Jellyfin API key (or press Enter to skip)"

# Plex Token (optional)
$PLEX_TOKEN = Read-Host "Enter Plex token (or press Enter to skip)"

Write-Success "✓ API keys collected"

# === STEP 2: Create Directory Structure ===
Write-Host ""
Write-Host "[2/7] Creating Directory Structure" -ForegroundColor Yellow
Write-Host "--------------------------------------"

$DirsToCreate = @(
    "$RepoRoot\windows\media\movies",
    "$RepoRoot\windows\media\shows",
    "$RepoRoot\windows\logs",
    "$RepoRoot\windows\cache",
    "$RepoRoot\windows\services\zurg\data"
)

foreach ($dir in $DirsToCreate) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Info "  Created: $dir"
    } else {
        Write-Info "  Exists: $dir"
    }
}

Write-Success "✓ Directory structure created"

# === STEP 3: Generate Zurg Config ===
Write-Host ""
Write-Host "[3/7] Generating Zurg Configuration" -ForegroundColor Yellow
Write-Host "--------------------------------------"

$ZurgExamplePath = "$RepoRoot\windows\services\zurg\config.example.yml"
$ZurgConfigPath = "$RepoRoot\windows\services\zurg\config.yml"

if (Test-Path $ZurgExamplePath) {
    $zurgContent = Get-Content $ZurgExamplePath -Raw
    $zurgContent = $zurgContent -replace 'YOUR_REAL_DEBRID_API_TOKEN_HERE', $RD_TOKEN
    # Update paths to use noc-homelab instead of homelab-win
    $zurgContent = $zurgContent -replace 'homelab-win', 'noc-homelab\windows'
    Set-Content -Path $ZurgConfigPath -Value $zurgContent -Encoding UTF8
    Write-Success "✓ Generated: $ZurgConfigPath"
} else {
    Write-Error "✗ config.example.yml not found at $ZurgExamplePath"
    exit 1
}

# === STEP 4: Generate Library Update Script ===
Write-Host ""
Write-Host "[4/7] Generating Library Update Script" -ForegroundColor Yellow
Write-Host "--------------------------------------"

$LibUpdateExamplePath = "$RepoRoot\windows\scripts\library-update.example.ps1"
$LibUpdatePath = "$RepoRoot\windows\scripts\library-update.ps1"

if (Test-Path $LibUpdateExamplePath) {
    $libContent = Get-Content $LibUpdateExamplePath -Raw
    $libContent = $libContent -replace 'YOUR_EMBY_API_KEY_HERE', $EMBY_KEY
    $libContent = $libContent -replace 'YOUR_JELLYFIN_API_KEY_HERE', $JELLYFIN_KEY
    if ($PLEX_TOKEN) {
        $libContent = $libContent -replace '\$PlexToken = ""', "`$PlexToken = `"$PLEX_TOKEN`""
    }
    Set-Content -Path $LibUpdatePath -Value $libContent -Encoding UTF8
    Write-Success "✓ Generated: $LibUpdatePath"
} else {
    Write-Error "✗ library-update.example.ps1 not found"
    exit 1
}

# === STEP 5: Check Prerequisites ===
Write-Host ""
Write-Host "[5/7] Checking Prerequisites" -ForegroundColor Yellow
Write-Host "--------------------------------------"

# Check WebDAV client
$webdav = Get-WindowsOptionalFeature -Online -FeatureName WebDAV-Redirector -ErrorAction SilentlyContinue
if ($webdav -and $webdav.State -eq "Enabled") {
    Write-Success "✓ WebDAV client is enabled"
} else {
    Write-Warning "⚠ WebDAV client is not enabled"
    Write-Info "  Attempting to enable..."
    try {
        Enable-WindowsOptionalFeature -Online -FeatureName WebDAV-Redirector -NoRestart
        Write-Success "✓ WebDAV client enabled (restart may be required)"
    } catch {
        Write-Error "✗ Failed to enable WebDAV client: $_"
        Write-Info "  Enable manually: Control Panel > Programs > Turn Windows features on or off > WebDAV Redirector"
    }
}

# Check Zurg binary
$ZurgBinary = "$RepoRoot\windows\services\zurg\zurg.exe"
if (Test-Path $ZurgBinary) {
    Write-Success "✓ Zurg binary found"
} else {
    Write-Warning "⚠ Zurg binary not found at $ZurgBinary"
    Write-Info "  Download from: https://github.com/debridmediamanager/zurg-testing/releases"
    Write-Info "  Place at: $ZurgBinary"
}

# Check FileBot
$FileBotPath = "C:\Users\$env:USERNAME\Downloads\apps\FileBot_5.2.0-portable\filebot.exe"
if (Test-Path $FileBotPath) {
    Write-Success "✓ FileBot found at $FileBotPath"
} else {
    Write-Warning "⚠ FileBot not found at $FileBotPath"
    Write-Info "  Download from: https://www.filebot.net/"
    Write-Info "  Or update path in $LibUpdatePath"
}

# === STEP 6: Import Scheduled Tasks ===
if (-not $SkipTaskImport) {
    Write-Host ""
    Write-Host "[6/7] Importing Scheduled Tasks" -ForegroundColor Yellow
    Write-Host "--------------------------------------"

    $TasksDir = "$RepoRoot\windows\scheduled-tasks"
    $TaskXmls = Get-ChildItem "$TasksDir\Homelab-*.xml" -ErrorAction SilentlyContinue

    if ($TaskXmls.Count -eq 0) {
        Write-Warning "⚠ No task XMLs found in $TasksDir"
    } else {
        # Update XML files with correct paths before importing
        $CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $ComputerName = $env:COMPUTERNAME

        foreach ($xml in $TaskXmls) {
            Write-Info "  Processing: $($xml.Name)"

            # Read XML content
            $xmlContent = Get-Content $xml.FullName -Raw

            # Replace paths and usernames
            $xmlContent = $xmlContent -replace 'C:\\Users\\noc\\homelab-win', $RepoRoot.Replace('\', '\\') + '\\windows'
            $xmlContent = $xmlContent -replace 'NOC-WINLOCAL\\noc', "$ComputerName\\$env:USERNAME"

            # Save to temp file
            $tempXml = "$env:TEMP\$($xml.Name)"
            Set-Content -Path $tempXml -Value $xmlContent -Encoding UTF8

            # Import task
            $taskName = $xml.BaseName
            try {
                Register-ScheduledTask -Xml (Get-Content $tempXml | Out-String) -TaskName $taskName -Force | Out-Null
                Write-Success "  ✓ Imported: $taskName"
            } catch {
                Write-Warning "  ⚠ Failed to import $taskName : $_"
            }

            Remove-Item $tempXml -Force
        }

        Write-Success "✓ Scheduled tasks imported"
        Write-Info "  Note: You may need to re-enter password for tasks"
        Write-Info "  Right-click task in Task Scheduler > Properties > General > Change User/Password"
    }
} else {
    Write-Warning "Skipping scheduled task import (--SkipTaskImport flag)"
}

# === STEP 7: Start Services ===
if (-not $SkipServiceStart) {
    Write-Host ""
    Write-Host "[7/7] Starting Services" -ForegroundColor Yellow
    Write-Host "--------------------------------------"

    # Start Zurg
    if (Test-Path $ZurgBinary) {
        Write-Info "  Starting Zurg..."
        try {
            Start-ScheduledTask -TaskName "Homelab-Zurg" -ErrorAction Stop
            Start-Sleep -Seconds 3
            $zurgProc = Get-Process zurg -ErrorAction SilentlyContinue
            if ($zurgProc) {
                Write-Success "  ✓ Zurg started (PID: $($zurgProc.Id))"
            } else {
                Write-Warning "  ⚠ Zurg task triggered but process not found"
            }
        } catch {
            Write-Warning "  ⚠ Failed to start Zurg: $_"
            Write-Info "    Try manually: schtasks /run /tn `"Homelab-Zurg`""
        }
    } else {
        Write-Warning "  ⚠ Skipping Zurg start (binary not found)"
    }

    # Mount Rclone
    Write-Info "  Mounting Rclone (Z: drive)..."
    try {
        Start-ScheduledTask -TaskName "Homelab-RcloneMount" -ErrorAction Stop
        Start-Sleep -Seconds 3
        $drive = Get-PSDrive Z -ErrorAction SilentlyContinue
        if ($drive) {
            Write-Success "  ✓ Z: drive mounted"
        } else {
            Write-Warning "  ⚠ RcloneMount task triggered but Z: not found"
        }
    } catch {
        Write-Warning "  ⚠ Failed to mount rclone: $_"
        Write-Info "    Try manually: schtasks /run /tn `"Homelab-RcloneMount`""
    }

    Write-Success "✓ Services started"
} else {
    Write-Warning "Skipping service start (--SkipServiceStart flag)"
}

# === SUMMARY ===
Write-Host ""
Write-Host "================================================" -ForegroundColor Magenta
Write-Host "  Setup Complete!" -ForegroundColor Magenta
Write-Host "================================================" -ForegroundColor Magenta
Write-Host ""

Write-Success "Configuration files generated:"
Write-Info "  - $ZurgConfigPath"
Write-Info "  - $LibUpdatePath"
Write-Host ""

Write-Success "Next steps:"
Write-Info "  1. Add a test torrent to Real-Debrid"
Write-Info "     https://real-debrid.com/torrents"
Write-Host ""
Write-Info "  2. Check if Z: drive shows content (wait 10-60 seconds)"
Write-Info "     dir Z:\movies"
Write-Info "     dir Z:\shows"
Write-Host ""
Write-Info "  3. Test FileBot organization"
Write-Info "     .\windows\scripts\library-update.ps1"
Write-Host ""
Write-Info "  4. Configure Emby/Jellyfin libraries"
Write-Info "     Point libraries to: $RepoRoot\windows\media\movies"
Write-Info "                         $RepoRoot\windows\media\shows"
Write-Host ""
Write-Info "  5. Monitor logs"
Write-Info "     Get-Content $RepoRoot\windows\logs\library-update.log -Tail 50 -Wait"
Write-Host ""

Write-Success "Useful commands:"
Write-Info "  Start Zurg:    schtasks /run /tn `"Homelab-Zurg`""
Write-Info "  Stop Zurg:     taskkill /IM zurg.exe /F"
Write-Info "  Mount Z:       schtasks /run /tn `"Homelab-RcloneMount`""
Write-Info "  Unmount Z:     net use Z: /delete"
Write-Info "  Check status:  Get-Process zurg,rclone -ErrorAction SilentlyContinue"
Write-Host ""

Write-Success "Documentation:"
Write-Info "  - Windows README:  $RepoRoot\windows\README.md"
Write-Info "  - Zurg README:     $RepoRoot\windows\services\zurg\README.md"
Write-Info "  - Scripts README:  $RepoRoot\windows\scripts\README.md"
Write-Host ""

Write-Host "Enjoy your automated media pipeline! 🎬" -ForegroundColor Cyan
Write-Host ""
