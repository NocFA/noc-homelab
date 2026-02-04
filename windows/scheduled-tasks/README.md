# Windows Scheduled Tasks

This directory contains XML exports of Windows Scheduled Tasks used to manage homelab services.

## Why Scheduled Tasks?

**SSH cannot start desktop applications** - When you SSH into Windows and run `Start-Process`, it creates a process in the SSH session, not the logged-in user's desktop session. GUI applications (Emby, Jellyfin, Sunshine, Parsec) exit immediately.

**Solution**: Windows Scheduled Tasks with "Run whether user is logged on or not" and "Run with highest privileges" start processes in the interactive desktop session, even when triggered via SSH.

## Available Tasks

| Task Name | Purpose | Trigger | Program |
|-----------|---------|---------|---------|
| **Homelab-Zurg** | Real-Debrid WebDAV server | At startup | `start-zurg-hidden.vbs` |
| **Homelab-RcloneMount** | Mount Zurg as Z: drive | At startup (after Zurg) | `start-rclone-hidden.vbs` |
| **Homelab-Emby** | Emby media server | At startup | `EmbyServer.exe` |
| **Homelab-Jellyfin** | Jellyfin media server | At startup | `start-jellyfin-hidden.vbs` |
| **Homelab-Sunshine** | Game streaming server | At startup | `sunshine.exe` |
| **Homelab-Parsec** | Remote desktop/gaming | At startup | `parsecd.exe` |
| **Homelab-Glances** | System monitoring | At startup | `glances -w` |
| **Homelab-GatusHealth** | Push health checks to Gatus | Every 1 minute | `healthcheck.ps1` |
| **Homelab-Tray** | System tray control app | At logon | `homelab-tray.pyw` |

## Importing Tasks

### Method 1: Using setup script (Recommended)

```powershell
cd C:\Users\noc\noc-homelab\setup
.\setup-windows.ps1
```

The setup script will:
1. Prompt for required paths (Zurg, FileBot, etc.)
2. Update XML files with correct paths
3. Import all tasks
4. Set credentials
5. Enable tasks

### Method 2: Manual import

```powershell
# Import a single task
Register-ScheduledTask -Xml (Get-Content "Homelab-Zurg.xml" | Out-String) -TaskName "Homelab-Zurg"

# Import all tasks
Get-ChildItem *.xml | ForEach-Object {
    $taskName = $_.BaseName
    Register-ScheduledTask -Xml (Get-Content $_.FullName | Out-String) -TaskName $taskName
}
```

### Method 3: Task Scheduler GUI

1. Open Task Scheduler (`taskschd.msc`)
2. Right-click "Task Scheduler Library"
3. Select "Import Task..."
4. Browse to XML file
5. Adjust user account if needed
6. Enter password for account
7. Click OK

## Task Configuration

### Common Settings

All `Homelab-*` tasks use these settings:

- **User**: `noc` (or your Windows username)
- **Run with highest privileges**: ✅ Enabled (required for symlinks, network mounts)
- **Run whether user is logged on or not**: ✅ Enabled
- **Hidden**: ✅ Enabled (don't show console windows)
- **Allow task to be run on demand**: ✅ Enabled (for manual start/stop)
- **Stop task if it runs longer than**: ❌ Disabled (services run indefinitely)

### Triggers

**At startup** tasks:
- **Delay**: 10-30 seconds (stagger starts)
- **Repeat**: No (one-time at boot)

**At logon** tasks (Homelab-Tray):
- **Specific user**: noc
- **Delay**: 5 seconds (wait for desktop to load)

**Recurring** tasks (Homelab-GatusHealth):
- **Repeat every**: 1 minute
- **Duration**: Indefinitely
- **Stop if still running**: Yes (prevent overlap)

### Dependencies

Some tasks depend on others:

```
Homelab-Zurg (port 9999)
    ↓
Homelab-RcloneMount (mount Z: from Zurg)
    ↓
Homelab-Emby, Homelab-Jellyfin (scan Z: content)
```

The tasks are configured with delays to ensure proper startup order.

## Customization

### Before Importing

You may need to edit XML files if your setup differs:

#### Update paths in Homelab-Zurg.xml
```xml
<Command>C:\Users\noc\noc-homelab\windows\scripts\start-zurg-hidden.vbs</Command>
```

Change `C:\Users\noc` if homelab is in different location.

#### Update paths in Homelab-Emby.xml
```xml
<Command>C:\Users\noc\Downloads\apps\Emby Server\EmbyServer.exe</Command>
```

Change to your actual Emby installation path.

#### Update username in all tasks
All tasks use `<UserId>NOC-WINLOCAL\noc</UserId>`.

Replace with:
- `YOUR-COMPUTER-NAME\your-username`
- Or just `your-username` for local accounts

Find and replace across all XML files:
```powershell
Get-ChildItem *.xml | ForEach-Object {
    (Get-Content $_) -replace 'NOC-WINLOCAL\\noc', 'YOUR-PC\your-user' | Set-Content $_
}
```

## Managing Tasks

### Start a service
```powershell
# Via scheduled task (recommended)
schtasks /run /tn "Homelab-Zurg"

# Or from dashboard
# http://noc-local:8080
```

### Stop a service
```powershell
# Kill the process
taskkill /IM zurg.exe /F

# For service-backed tasks (Sunshine)
net stop ApolloService
```

### Restart a service
```powershell
# Stop then start
taskkill /IM emby.exe /F
Start-Sleep -Seconds 2
schtasks /run /tn "Homelab-Emby"
```

### Check task status
```powershell
# List all Homelab tasks
Get-ScheduledTask -TaskName "Homelab-*" | Select-Object TaskName,State

# View task details
Get-ScheduledTaskInfo -TaskName "Homelab-Zurg"

# View last run time and result
Get-ScheduledTaskInfo -TaskName "Homelab-Zurg" | Select-Object LastRunTime,LastTaskResult
```

### Enable/Disable tasks
```powershell
# Disable (prevent auto-start)
Disable-ScheduledTask -TaskName "Homelab-Emby"

# Enable
Enable-ScheduledTask -TaskName "Homelab-Emby"
```

### View task logs
```powershell
# Enable task history (if disabled)
wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true

# View in GUI
# Task Scheduler > Homelab-Zurg > History tab

# View via PowerShell
Get-WinEvent -LogName Microsoft-Windows-TaskScheduler/Operational |
    Where-Object { $_.Message -like "*Homelab-Zurg*" } |
    Select-Object TimeCreated,Message -First 10
```

## Troubleshooting

### Task won't start

**Check if enabled**:
```powershell
Get-ScheduledTask -TaskName "Homelab-Zurg" | Select-Object State
```

**Check last run result**:
```powershell
Get-ScheduledTaskInfo -TaskName "Homelab-Zurg" | Select-Object LastTaskResult
```

**Common error codes**:
- `0x0` = Success
- `0x1` = Incorrect function called
- `0x41301` = Task currently running
- `0x41303` = Task has not yet run
- `0x41325` = Task user credentials not valid

**Fix credentials**:
```powershell
# Re-register with correct password
$cred = Get-Credential -UserName "noc" -Message "Enter password"
Set-ScheduledTask -TaskName "Homelab-Zurg" -User $cred.UserName -Password ($cred.GetNetworkCredential().Password)
```

### Task starts but process exits immediately

**Check if program exists**:
```powershell
Test-Path "C:\Users\noc\noc-homelab\windows\scripts\start-zurg-hidden.vbs"
```

**Run command manually**:
```powershell
# Test the command from task XML
& "C:\Users\noc\noc-homelab\windows\scripts\start-zurg-hidden.vbs"
```

**Check permissions**:
- Ensure "Run with highest privileges" is checked
- Ensure user has permissions to program directory
- For symlinks: Must have Administrator or Developer Mode enabled

### Task runs but service doesn't appear

**Check if process is running**:
```powershell
Get-Process zurg -ErrorAction SilentlyContinue
```

**Check task is configured correctly**:
- "Run whether user is logged on or not" ✅
- "Hidden" ✅
- Correct working directory (if applicable)

**View service logs**:
```powershell
Get-Content C:\Users\noc\noc-homelab\windows\logs\zurg.log -Tail 50
```

### Dashboard can't control services

**Check SSH access**:
```powershell
# From macOS
ssh noc@noc-winlocal "schtasks /query /tn Homelab-Zurg"
```

**Check task allows on-demand run**:
```powershell
Get-ScheduledTask -TaskName "Homelab-Zurg" |
    Select-Object -ExpandProperty Settings |
    Select-Object AllowDemandStart
```

Should be `True`. If not:
```powershell
$task = Get-ScheduledTask -TaskName "Homelab-Zurg"
$task.Settings.AllowDemandStart = $true
Set-ScheduledTask -InputObject $task
```

## Exporting Tasks

To update XML files after making changes:

```powershell
# Export single task
Export-ScheduledTask -TaskName "Homelab-Zurg" | Out-File "Homelab-Zurg.xml" -Encoding UTF8

# Export all Homelab tasks
Get-ScheduledTask -TaskName "Homelab-*" | ForEach-Object {
    Export-ScheduledTask -TaskName $_.TaskName | Out-File "$($_.TaskName).xml" -Encoding UTF8
}
```

## Security Notes

- Tasks run as your user account
- XML files do NOT contain passwords (just usernames)
- Password must be entered when importing
- "Run with highest privileges" gives Administrator rights
- Tasks can be triggered by any Administrator user
- Consider using a service account for production deployments

## Alternative: Windows Services (NSSM)

For services that don't need desktop interaction, consider using NSSM (Non-Sucking Service Manager) instead:

```powershell
# Install Gatus as Windows service (example)
nssm install GatusService "C:\Users\noc\homelab\gatus\gatus.exe"
nssm set GatusService AppDirectory "C:\Users\noc\homelab\gatus"
nssm set GatusService AppStdout "C:\Users\noc\noc-homelab\windows\logs\gatus.log"
nssm start GatusService
```

**Advantages**:
- Proper Windows service (services.msc)
- Auto-restart on failure
- Better logging
- No user session required

**Disadvantages**:
- Can't access desktop (no GUI apps)
- More complex setup
- Harder to debug

See `scripts/install-services.ps1` for NSSM setup examples.
