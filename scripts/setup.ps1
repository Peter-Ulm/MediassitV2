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

if (-not (Test-Path ".\frontend\.env.local")) {
    Copy-Item ".\frontend\.env.example" ".\frontend\.env.local"
    Write-Host "Created frontend\.env.local so the UI talks to the live backend."
} else {
    Write-Host "frontend\.env.local already exists — leaving it alone."
}

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
Write-Host "Setup complete. Start the system with:  .\scripts\run.ps1" -ForegroundColor Green
