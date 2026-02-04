# Setup Auto-Login for noc user (no password)
# Run this script as Administrator

$regPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"

Set-ItemProperty -Path $regPath -Name "AutoAdminLogon" -Value "1" -Type String
Set-ItemProperty -Path $regPath -Name "DefaultUserName" -Value "noc" -Type String
Set-ItemProperty -Path $regPath -Name "DefaultPassword" -Value "" -Type String

Write-Host "Auto-login configured for user 'noc'" -ForegroundColor Green
Write-Host ""
Write-Host "Verifying settings:"
Get-ItemProperty -Path $regPath | Select-Object AutoAdminLogon, DefaultUserName | Format-List
