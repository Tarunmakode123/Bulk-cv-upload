# How to publish this project to GitHub

Recommended: use the `publish.ps1` helper included in this folder.

1) Using the helper (PowerShell)

  Open PowerShell in the project folder and run:

  ```powershell
  # optional: login with gh first
  gh auth login

  # run the publish script (defaults to Tarunmakode123/Resume_Analyser_Using_Python)
  .\publish.ps1 -Owner Tarunmakode123 -RepoName Resume_Analyser_Using_Python
  ```

2) Manual steps (if you prefer web + git)

- Create a new repo on https://github.com (name it `Resume_Analyser_Using_Python`).
- From your project folder run:

  ```powershell
  git init
  git add .
  git commit -m "Initial commit"
  git remote add origin https://github.com/Tarunmakode123/Resume_Analyser_Using_Python.git
  git branch -M main
  git push -u origin main
  ```

Notes:
- Make sure `.gitignore` contains `.venv`, `uploads/`, `.env`, and other local files. This repo already includes a `.gitignore`.
- If you use HTTPS and are prompted for credentials, provide your GitHub username and a Personal Access Token (PAT) as the password. Or use `gh auth login` to avoid PAT prompts.

If you want, I can prepare and stage the commit for you (I cannot push from here). Tell me to create or modify the commit message you prefer and I'll update the working tree files accordingly.
