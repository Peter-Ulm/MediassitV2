# MediAssist — one-shot environment setup.
# Run from the repo root:    .\scripts\setup.ps1

$ErrorActionPreference = "Stop"

$repo = Resolve-Path "$PSScriptRoot\.."
Set-Location $repo

Write-Host "==> Python virtual environment" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt

Write-Host ""
Write-Host "==> Frontend dependencies" -ForegroundColor Cyan
Push-Location frontend
npm install
Pop-Location

Write-Host ""
Write-Host "==> .env file" -ForegroundColor Cyan
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Edit it to add your OPENAI_API_KEY if needed."
} else {
    Write-Host ".env already exists — leaving it alone."
}

# Replace the placeholder JWT_SECRET with a real random value. Tokens are signed
# with this; the shipped placeholder must not be used.
$envText = Get-Content ".env" -Raw
if (($envText -match "change-me-to-a-long-random-hex-string") -or ($envText -notmatch "(?m)^\s*JWT_SECRET\s*=\s*\S")) {
    $secret = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))").Trim()
    if ($envText -match "(?m)^\s*JWT_SECRET\s*=.*$") {
        $envText = [regex]::Replace($envText, "(?m)^\s*JWT_SECRET\s*=.*$", "JWT_SECRET=$secret")
    } else {
        $envText = $envText.TrimEnd() + "`r`nJWT_SECRET=$secret`r`n"
    }
    Set-Content ".env" $envText -NoNewline
    Write-Host "Generated a random JWT_SECRET in .env."
} else {
    Write-Host "JWT_SECRET already set — leaving it alone."
}

if (-not (Test-Path ".\frontend\.env.local")) {
    Copy-Item ".\frontend\.env.example" ".\frontend\.env.local"
    Write-Host "Created frontend\.env.local so the UI talks to the live backend."
} else {
    Write-Host "frontend\.env.local already exists — leaving it alone."
}

Write-Host ""
Write-Host "==> Demo login account" -ForegroundColor Cyan
# Seed the demo doctor so the login page's "Continue as Demo Doctor" button
# works immediately. Demo convenience only — see scripts/seed_demo.py.
& .\.venv\Scripts\python.exe -m scripts.seed_demo

Write-Host ""
Write-Host "==> Ollama check" -ForegroundColor Cyan
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($null -eq $ollama) {
    Write-Warning "Ollama is not installed. Install from https://ollama.com if you want offline LLM mode."
} else {
    $configuredModel = "mistral:7b-instruct"
    $modelLine = Get-Content ".env" | Where-Object { $_ -match "^\s*OLLAMA_MODEL\s*=" } | Select-Object -First 1
    if ($modelLine -match "^\s*OLLAMA_MODEL\s*=\s*(.+?)\s*$") {
        $configuredModel = $Matches[1]
    }

    $models = & ollama list 2>$null
    if ($models -notmatch [regex]::Escape($configuredModel)) {
        Write-Host "Pulling configured Ollama model ($configuredModel). This may take a while..."
        & ollama pull $configuredModel
    } else {
        Write-Host "Configured Ollama model already present: $configuredModel"
    }
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Start the app (opens backend + frontend windows):"
Write-Host "       .\scripts\run.ps1"
Write-Host "  2. Open http://localhost:5173 and click 'Continue as Demo Doctor'"
Write-Host "     (or sign in with  dr.demo@mediassist.test  /  DemoPass123)."
Write-Host ""
Write-Host "  To add a real (non-demo) account there is no signup page; use the CLI:"
Write-Host '       .\.venv\Scripts\python.exe -m scripts.create_user --email you@clinic.tz --name "Your Name" --role clinician'
