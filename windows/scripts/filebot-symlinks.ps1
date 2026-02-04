# FileBot Symlink Creator for Zurg/Real-Debrid
# Creates renamed symlinks from Z:\movies and Z:\shows to media\ folder
# Run as Administrator OR enable Developer Mode for symlink support

$FileBotExe = "C:\Users\noc\Downloads\apps\FileBot_5.2.0-portable\filebot.exe"
$SourceMovies = "Z:\movies"
$SourceShows = "Z:\shows"
$DestMovies = "C:/Users/noc/homelab-win/media/movies"
$DestShows = "C:/Users/noc/homelab-win/media/shows"

# Check if Z: drive is mounted
if (-not (Test-Path "Z:\")) {
    Write-Error "Z: drive not mounted. Start Zurg and Rclone first."
    exit 1
}

Write-Host "=== FileBot Symlink Creator ===" -ForegroundColor Cyan
Write-Host ""

# Process Movies
Write-Host "Processing Movies..." -ForegroundColor Yellow
& $FileBotExe -rename $SourceMovies `
    --action symlink `
    --db TheMovieDB `
    -non-strict `
    --format "$DestMovies/{n} ({y})/{n} ({y})" `
    --log info

Write-Host ""

# Process TV Shows
Write-Host "Processing TV Shows..." -ForegroundColor Yellow
& $FileBotExe -rename $SourceShows `
    --action symlink `
    --db TheTVDB `
    -non-strict `
    --format "$DestShows/{n}/Season {s}/{n} - S{s00}E{e00} - {t}" `
    --log info

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Symlinks created in: C:\Users\noc\homelab-win\media\"
Write-Host "Point Emby/Plex libraries at media\movies and media\shows"
