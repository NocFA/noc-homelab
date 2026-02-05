# Gatus External Endpoint Health Check
# Checks Parsec and Rclone processes and pushes status to local Gatus API.
# Run as a scheduled task (e.g., every 30s via Homelab-GatusHealth).

$GatusUrl = "http://localhost:3001/api/v1/endpoints"
$ParsecToken = "CHANGE_ME_PARSEC_TOKEN"
$RcloneToken = "CHANGE_ME_RCLONE_TOKEN"

# --- Parsec ---
$parsecKey = "services_parsec"
$parsecRunning = $null -ne (Get-Process -Name "parsecd" -ErrorAction SilentlyContinue)
$parsecSuccess = if ($parsecRunning) { "true" } else { "false" }
try {
    Invoke-RestMethod -Uri "$GatusUrl/$parsecKey/external?success=$parsecSuccess" `
        -Method POST `
        -Headers @{ Authorization = "Bearer $ParsecToken" } `
        -ErrorAction Stop
} catch {
    Write-Warning "Failed to push Parsec status: $_"
}

# --- Rclone Mount ---
$rcloneKey = "services_rclone-mount"
$rcloneRunning = $null -ne (Get-Process -Name "rclone" -ErrorAction SilentlyContinue)
$rcloneSuccess = if ($rcloneRunning) { "true" } else { "false" }
try {
    Invoke-RestMethod -Uri "$GatusUrl/$rcloneKey/external?success=$rcloneSuccess" `
        -Method POST `
        -Headers @{ Authorization = "Bearer $RcloneToken" } `
        -ErrorAction Stop
} catch {
    Write-Warning "Failed to push Rclone Mount status: $_"
}
