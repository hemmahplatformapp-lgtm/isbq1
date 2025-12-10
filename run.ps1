# run.ps1 - Create venv, install deps, and run the Flask-SocketIO app
$ErrorActionPreference = 'Stop'

# Ensure script runs from repository root
Set-Location -Path $PSScriptRoot

# 1) Create virtual environment if missing
if (-Not (Test-Path "$PSScriptRoot\.venv")) {
    Write-Host "Creating virtual environment .venv..."
    python -m venv "$PSScriptRoot\.venv"
}

# 2) Activate the venv
Write-Host "Activating virtual environment..."
. "$PSScriptRoot\.venv\Scripts\Activate.ps1"

# 3) Upgrade pip and install requirements
Write-Host "Upgrading pip and installing backend requirements..."
python -m pip install --upgrade pip
# Install core packages first (quicker and helps satisfy runtime imports)
$core = @('Flask','Flask-SQLAlchemy','Flask-SocketIO','python-dotenv','eventlet')
Write-Host "Installing core packages: $($core -join ', ')"
pip install --no-cache-dir $core

# Then try to install the full requirements file with retries and larger timeout
if (Test-Path "$PSScriptRoot\backend\requirements.txt") {
    $attempt = 0
    $maxAttempts = 3
    $success = $false
    while (-not $success -and $attempt -lt $maxAttempts) {
        try {
            $attempt++
            Write-Host "Installing full requirements (attempt $attempt of $maxAttempts)..."
            pip install --no-cache-dir --default-timeout=100 -r "$PSScriptRoot\backend\requirements.txt"
            $success = $true
        } catch {
            Write-Warning "requirements install attempt $attempt failed: $($_.Exception.Message)"
            if ($attempt -lt $maxAttempts) { Start-Sleep -Seconds (5 * $attempt) }
        }
    }
    if (-not $success) {
        Write-Warning "Failed to install all requirements after $maxAttempts attempts. Continuing with core packages installed."
    }
} else {
    Write-Warning "backend\requirements.txt not found. Please ensure requirements file exists."
}

# 4) Check for data file
if (-Not (Test-Path "$PSScriptRoot\pilgrims_data.csv")) {
    Write-Warning "pilgrims_data.csv not found in project root. Some features may fail."
}

# 5) Run the application
Write-Host "Starting the Flask-SocketIO server (backend/app.py)..."
python "$PSScriptRoot\backend\app.py"
