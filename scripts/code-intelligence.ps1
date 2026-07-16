[CmdletBinding()]
param(
    [ValidateSet(
        "status",
        "codegraph-init",
        "codegraph-sync",
        "codegraph-status",
        "codegraph-query",
        "understand-prepare"
    )]
    [string]$Action = "status",

    [string]$Query,

    [ValidateRange(1, 100)]
    [int]$Limit = 10
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$UnderstandRoot = Join-Path $ProjectRoot ".understand-anything"

function Resolve-CommandPath {
    param([Parameter(Mandatory)][string]$Name)

    $candidates = if ($IsWindows -or $env:OS -eq "Windows_NT") {
        @("$Name.cmd", $Name)
    } else {
        @($Name)
    }

    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            return $command.Source
        }
    }

    throw "Required command '$Name' was not found on PATH."
}

function Initialize-UnderstandAnything {
    New-Item -ItemType Directory -Force -Path $UnderstandRoot | Out-Null

    $ignorePath = Join-Path $UnderstandRoot ".understandignore"
    $ignoreContent = @"
# Local and generated content excluded from architecture analysis.
.codegraph/
.understand-anything/
.gca/
.venv/
.idea/
.mypy_cache/
.pytest_cache/
.ruff_cache/
__pycache__/
build/
dist/
htmlcov/
*.egg-info/
*.pyc
*.pyo
*.sqlite
*.db
*.log
uv.lock
"@
    [System.IO.File]::WriteAllText($ignorePath, $ignoreContent, [System.Text.UTF8Encoding]::new($false))

    $configPath = Join-Path $UnderstandRoot "config.json"
    $config = [ordered]@{
        autoUpdate = $false
        outputLanguage = "zh-CN"
    } | ConvertTo-Json
    [System.IO.File]::WriteAllText($configPath, "$config`n", [System.Text.UTF8Encoding]::new($false))

    Write-Host "Prepared Understand-Anything configuration at $UnderstandRoot"
    Write-Host "Run /understand . --language zh-CN --no-auto-update in Codex to build the graph."
}

function Show-Status {
    $codeGraphPath = Get-Command codegraph.cmd, codegraph -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $codeGraphPath) {
        Write-Host "CodeGraph: not installed"
    } else {
        Write-Host "CodeGraph: $($codeGraphPath.Source)"
        & $codeGraphPath.Source status $ProjectRoot
    }

    $graphPath = Join-Path $UnderstandRoot "knowledge-graph.json"
    if (Test-Path $graphPath) {
        $graph = Get-Content -Raw -Encoding UTF8 $graphPath | ConvertFrom-Json
        Write-Host "Understand-Anything: graph ready ($($graph.nodes.Count) nodes, $($graph.edges.Count) edges)"
    } elseif (Test-Path (Join-Path $UnderstandRoot "config.json")) {
        Write-Host "Understand-Anything: configured; graph not generated"
    } else {
        Write-Host "Understand-Anything: not prepared"
    }
}

switch ($Action) {
    "status" {
        Show-Status
    }
    "codegraph-init" {
        $codegraph = Resolve-CommandPath "codegraph"
        & $codegraph init $ProjectRoot
    }
    "codegraph-sync" {
        $codegraph = Resolve-CommandPath "codegraph"
        & $codegraph sync $ProjectRoot
    }
    "codegraph-status" {
        $codegraph = Resolve-CommandPath "codegraph"
        & $codegraph status $ProjectRoot
    }
    "codegraph-query" {
        if ([string]::IsNullOrWhiteSpace($Query)) {
            throw "-Query is required for the codegraph-query action."
        }
        $codegraph = Resolve-CommandPath "codegraph"
        & $codegraph query $Query --path $ProjectRoot --limit $Limit
    }
    "understand-prepare" {
        Initialize-UnderstandAnything
    }
}
