$ErrorActionPreference = "Stop"

$root = (Resolve-Path "$PSScriptRoot\..\..\").Path
$refs = Join-Path $root "references"

function Ensure-GitRepo {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Url
    )

    if (-not (Test-Path $Path -PathType Container)) {
        Write-Host "Cloning $Name into $Path ..." -ForegroundColor Cyan
        New-Item -ItemType Directory -Force -Path (Split-Path $Path) | Out-Null
        git -C $refs clone $Url (Split-Path $Path -Leaf)
        Write-Host "  $Name cloned." -ForegroundColor Green
    }

    $git = Join-Path $Path ".git"
    if (-not (Test-Path $git -PathType Container)) {
        throw "Reference path is not a git checkout: $Path"
    }

    Write-Host "Updating $Name..." -ForegroundColor Cyan
    git -C $Path fetch --all --prune | Out-Null
    git -C $Path pull --ff-only | Out-Null
    Write-Host "  $Name up to date." -ForegroundColor Green
}

Ensure-GitRepo -Path (Join-Path $refs "codex_workflow") -Name "codex-workflow" -Url "https://github.com/viettran-edgeAI/codex_workflow.git"
Ensure-GitRepo -Path (Join-Path $refs "codex_workflows") -Name "codex-workflows" -Url "https://github.com/viettran-edgeAI/codex_workflows.git"
Ensure-GitRepo -Path (Join-Path $refs "codex-agent-config") -Name "codex-agent-config" -Url "https://github.com/coredo-eu/codex-agent-config.git"

Write-Host "Reference repos refreshed." -ForegroundColor Green
