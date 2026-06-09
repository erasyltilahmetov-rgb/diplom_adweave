
# AdWeave Watchdog
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$CLOUDFLARED = "$env:USERPROFILE\Downloads\cloudflared-windows-amd64.exe"
$LOG = "$env:USERPROFILE\adweave.log"
$TG_TOKEN = "8250873717:AAEnClwyEbtgJi4U4BRSzDfxcGAtYwuCCiQ"
$TG_CHAT = "-4804805555"

function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line
    Add-Content $LOG $line
}

function TG($msg) {
    try {
        $uri = "https://api.telegram.org/bot${TG_TOKEN}/sendMessage"
        Invoke-RestMethod -Uri $uri -Method Post -Body @{
            chat_id = $TG_CHAT
            text = $msg
        } | Out-Null
    } catch { Log "TG error: $_" }
}

function Get-WSL-IP {
    return (wsl -d Ubuntu -- hostname -I).Trim().Split(" ")[0]
}

function Is-Django-Up {
    $r = wsl -d Ubuntu -- bash -c "pgrep -f 'manage.py' | wc -l"
    return ([int]$r.Trim()) -gt 0
}

function Start-Django {
    Log "Starting Django..."
    Start-Process -WindowStyle Minimized "wsl.exe" -ArgumentList "-d Ubuntu -- bash ~/start_django.sh"
    Start-Sleep 5
}

function Start-Tunnel($ip) {
    Log "Starting tunnel for $ip:8000..."
    # Убиваем старые процессы cloudflared чтобы освободить лог-файлы
    Get-Process -Name "cloudflared*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 1
    $err = "$env:TEMP\cf_err.log"
    "" | Set-Content $err
    $proc = Start-Process -PassThru -WindowStyle Minimized $CLOUDFLARED `
        -ArgumentList "tunnel --url http://${ip}:8000" `
        -RedirectStandardOutput "$env:TEMP\cf_out.log" `
        -RedirectStandardError $err

    $url = ""
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep 2
        $content = (Get-Content $err -ErrorAction SilentlyContinue) + (Get-Content "$env:TEMP\cf_out.log" -ErrorAction SilentlyContinue) | Out-String
        if ($content -match "([\w-]+\.trycloudflare\.com)") {
            $url = $Matches[1]
            break
        }
    }

    if ($url) {
        $full = "https://$url"
        Log "Tunnel URL: $full"
        Update-Env $full
        TG "AdWeave is UP! $full"
        try { [System.Windows.Forms.Clipboard]::SetText($full) } catch {}
    } else {
        Log "Tunnel started but URL not found"
        TG "AdWeave tunnel started but URL not found"
    }
    return $proc
}

function Update-Env($full) {
    $envFile = Join-Path $PSScriptRoot ".env"
    if (-not (Test-Path $envFile)) { Log "Env file not found: $envFile"; return }

    $lines = Get-Content $envFile -Encoding UTF8
    $updated = $lines | ForEach-Object {
        if ($_ -match "^THREADS_REDIRECT_URI=") {
            "THREADS_REDIRECT_URI=${full}/threads/oauth/callback/"
        } elseif ($_ -match "^TUNNEL_URL=") {
            "TUNNEL_URL=${full}/"
        } elseif ($_ -match "^DJANGO_CSRF_TRUSTED_ORIGINS=") {
            "DJANGO_CSRF_TRUSTED_ORIGINS=${full}/"
        } elseif ($_ -match "^DJANGO_ALLOWED_HOSTS=") {
            # Берём домен без https://
            $domain = $full -replace "^https://", ""
            "DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,${domain}"
        } else {
            $_
        }
    }
    # UTF-8 без BOM (PowerShell 5.1 добавляет BOM при -Encoding UTF8, что ломает python-dotenv)
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllLines($envFile, $updated, $utf8NoBom)
    Log ".env обновлён: REDIRECT_URI и TUNNEL_URL -> $full"

    # Перезапускаем Django чтобы подхватил новый .env
    wsl -d Ubuntu -- bash -c "pkill -f 'manage.py' 2>/dev/null; true"
    Start-Sleep 2
    Start-Django
}

Add-Type -AssemblyName System.Windows.Forms
Log "=== Watchdog starting ==="
TG "AdWeave watchdog started. Getting URL..."

$ip = Get-WSL-IP
Log "WSL IP: $ip"

if (-not (Is-Django-Up)) { Start-Django }
$tunnel = Start-Tunnel $ip

while ($true) {
    Start-Sleep 30

    if (-not (Is-Django-Up)) {
        Log "Django down! Restarting..."
        TG "AdWeave: Django crashed, restarting..."
        Start-Django
    }

    if ($tunnel.HasExited) {
        Log "Tunnel down! Restarting..."
        TG "AdWeave: Tunnel crashed, restarting..."
        $ip = Get-WSL-IP
        $tunnel = Start-Tunnel $ip
    }
}
