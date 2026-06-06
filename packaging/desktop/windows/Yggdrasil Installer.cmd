@echo off
if defined YGGDRASIL_REPO_ROOT (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Yggdrasil.Install.ps1" install -RepoRootPath "%YGGDRASIL_REPO_ROOT%" -StartTray
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Yggdrasil.Install.ps1" install -StartTray
)
