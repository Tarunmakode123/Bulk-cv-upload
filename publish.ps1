<#
publish.ps1 - helper to create a GitHub repo and push the current project.

Usage:
  1. Open PowerShell in this folder.
  2. Run: `.
un.ps1` to start the app, or use this script to publish:
     - If you have GitHub CLI installed and are logged in (`gh auth login`), this script will use it.
     - Otherwise it will fall back to adding an HTTPS remote and attempting to push (you'll be prompted for credentials).

Note: You must be signed into GitHub via `gh` or have push access to the target repo.
#>

param(
  [string]$RepoName = "Resume_Analyser_Using_Python",
  [string]$Owner = "Tarunmakode123",
  [switch]$Private
)

$root = Get-Location
Write-Host "Publishing project from: $root"

# ensure git repo
if (-not (Test-Path .git)) {
  git init
}

# create .gitignore if missing (safe no-op if it exists)
if (-not (Test-Path .gitignore)) { Write-Host "No .gitignore found. Please create one and run again." }

# remove tracked uploads or compiled files from index (if previously committed)
git rm --cached -r uploads 2>$null | Out-Null
git rm --cached -r __pycache__ 2>$null | Out-Null

git add .
git commit -m "Initial commit: Resume Analyzer" 2>$null

$remoteUrlHttps = "https://github.com/$Owner/$RepoName.git"

if (Get-Command gh -ErrorAction SilentlyContinue) {
  Write-Host "gh CLI found — creating repo via GitHub CLI (you may be prompted to authenticate)."
  $ghArgs = @($Owner + '/' + $RepoName)
  if ($Private) { $ghArgs += '--private' } else { $ghArgs += '--public' }
  $ghArgs += '--source=.'
  $ghArgs += '--remote=origin'
  gh repo create @ghArgs --push
} else {
  Write-Host "gh CLI not found. Creating remote and attempting to push via HTTPS."
  git remote remove origin 2>$null | Out-Null
  git remote add origin $remoteUrlHttps
  git branch -M main
  git push -u origin main
}

Write-Host "Done. If push failed due to authentication, run 'gh auth login' or create a PAT and try again."
