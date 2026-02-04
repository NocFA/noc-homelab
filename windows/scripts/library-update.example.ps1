# Library Update Script
# Called by Zurg on_library_update hook when Real-Debrid content changes
# 1. Runs FileBot to create/update symlinks
# 2. Triggers Emby library scan
# 3. Triggers Jellyfin library scan
# 4. Triggers Plex library scan (if configured)

param(
    [string]$ChangedPath = ""
)

$LogFile = "C:\Users\noc\noc-homelab\windows\logs\library-update.log"
$FileBotExe = "C:\Users\noc\Downloads\apps\FileBot_5.2.0-portable\filebot.exe"  # Adjust to your FileBot location

# === CONFIGURATION ===
# Get your API keys from:
# - Emby: Dashboard > Advanced > API Keys > New API Key
# - Jellyfin: Dashboard > Advanced > API Keys > New API Key
# - Plex: https://www.plex.tv/claim/ (for token)

$EmbyUrl = "http://localhost:8096"
$EmbyApiKey = "YOUR_EMBY_API_KEY_HERE"  # Replace with actual key

$PlexUrl = "http://localhost:32400"
$PlexToken = ""   # Optional - set this if using Plex

$JellyfinUrl = "http://localhost:8097"
$JellyfinApiKey = "YOUR_JELLYFIN_API_KEY_HERE"  # Replace with actual key

# === LOGGING ===
function Log {
    param([string]$Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$Timestamp - $Message" | Out-File -Append -FilePath $LogFile -Encoding utf8
    Write-Host "$Timestamp - $Message"
}

Log "=== Library Update Triggered ==="
if ($ChangedPath) { Log "Changed: $ChangedPath" }

# === CLEANUP STALE SYMLINKS ===
# Remove symlinks whose targets no longer exist (e.g. deleted from RD then re-added)
$MediaRoot = "C:\Users\noc\noc-homelab\windows\media"
$StaleCount = 0
Get-ChildItem -Path $MediaRoot -Recurse -File | Where-Object { $_.LinkType -eq "SymbolicLink" } | ForEach-Object {
    if (-not (Test-Path -LiteralPath $_.Target)) {
        Log "Removing stale symlink: $($_.FullName)"
        Remove-Item $_.FullName -Force
        $StaleCount++
    }
}
# Remove empty folders left behind after stale symlink cleanup
Get-ChildItem -Path $MediaRoot -Recurse -Directory | Sort-Object { $_.FullName.Length } -Descending | ForEach-Object {
    if ((Get-ChildItem $_.FullName -Force | Measure-Object).Count -eq 0) {
        Log "Removing empty folder: $($_.FullName)"
        Remove-Item $_.FullName -Force
    }
}
if ($StaleCount -gt 0) { Log "Cleaned up $StaleCount stale symlink(s)" }

# === FILEBOT SYMLINKS ===
# Wait for Zurg to fully process the new content
Start-Sleep -Seconds 5

Log "Running FileBot for movies..."
& $FileBotExe -rename "Z:\movies" -r --action symlink --db TheMovieDB -non-strict `
    --format "C:/Users/noc/noc-homelab/windows/media/movies/{n} ({y})/{n} ({y})" `
    --log warning 2>&1 | Out-File -Append -FilePath $LogFile -Encoding utf8

Log "Running FileBot for shows..."
& $FileBotExe -rename "Z:\shows" -r --action symlink --db TheTVDB -non-strict `
    --format "C:/Users/noc/noc-homelab/windows/media/shows/{n}/Season {s}/{n} - S{s00}E{e00} - {t}" `
    --log warning 2>&1 | Out-File -Append -FilePath $LogFile -Encoding utf8

# === EMBY SCAN ===
if ($EmbyApiKey -and $EmbyApiKey -ne "YOUR_EMBY_API_KEY_HERE") {
    Log "Triggering Emby library scan..."
    try {
        Invoke-RestMethod -Method Post -Uri "$EmbyUrl/Library/Refresh?api_key=$EmbyApiKey" -ErrorAction Stop
        Log "Emby scan triggered successfully"
    } catch {
        Log "Emby scan failed: $_"
    }
} else {
    Log "Emby API key not configured - skipping"
}

# === PLEX SCAN ===
if ($PlexToken) {
    Log "Triggering Plex library scan..."
    try {
        Invoke-RestMethod -Method Get -Uri "$PlexUrl/library/sections/all/refresh?X-Plex-Token=$PlexToken" -ErrorAction Stop
        Log "Plex scan triggered successfully"
    } catch {
        Log "Plex scan failed: $_"
    }
} else {
    Log "Plex token not configured - skipping"
}

# === JELLYFIN SCAN ===
if ($JellyfinApiKey -and $JellyfinApiKey -ne "YOUR_JELLYFIN_API_KEY_HERE") {
    Log "Triggering Jellyfin library scan..."
    try {
        Invoke-RestMethod -Method Post -Uri "$JellyfinUrl/Library/Refresh?api_key=$JellyfinApiKey" -ErrorAction Stop
        Log "Jellyfin scan triggered successfully"
    } catch {
        Log "Jellyfin scan failed: $_"
    }
} else {
    Log "Jellyfin API key not configured - skipping"
}

Log "=== Library Update Complete ==="
