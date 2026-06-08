$ErrorActionPreference = "Stop"
$ServiceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python (Join-Path $ServiceDir "video_notes_service.py")
