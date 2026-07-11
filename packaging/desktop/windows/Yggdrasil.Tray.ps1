param(
    [switch]$StartProduct,
    [ValidateSet("auto", "en", "zh-CN")]
    [string]$Language = "auto"
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopScript = Join-Path $ScriptRoot "Yggdrasil.Desktop.ps1"
$UpdateScript = Join-Path $ScriptRoot "Yggdrasil.Update.ps1"

if ([System.Threading.Thread]::CurrentThread.ApartmentState -ne "STA") {
    $RelaunchArguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Sta",
        "-File",
        $MyInvocation.MyCommand.Path,
        "-Language",
        $Language
    )
    if ($StartProduct) {
        $RelaunchArguments += "-StartProduct"
    }
    Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList $RelaunchArguments
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$Ui = @{
    en = @{
        start = "Start Yggdrasil"; open = "Open Start"; apps = "Open Apps"; settings = "Open Settings"; health = "Health and Diagnostics"; logs = "Diagnostic Logs";
        backup = "Back Up Local Data"; snapshots = "View Backups"; restore = "Restore Latest Backup"; updates = "Check for Updates"; apply = "Apply Update";
        rollback = "Restore Previous Version"; stop = "Stop Yggdrasil"; exit = "Exit Tray"; language = "Language"; english = "English"; chinese = "中文";
        tray_title = "Project Yggdrasil"; tray_hint = "Yggdrasil is available from the tray."
    }
    "zh-CN" = @{
        start = "启动世界树"; open = "打开开始页"; apps = "打开应用"; settings = "打开设置"; health = "健康与诊断"; logs = "诊断日志";
        backup = "备份本地数据"; snapshots = "查看备份"; restore = "恢复最近备份"; updates = "检查更新"; apply = "应用更新";
        rollback = "恢复上一版本"; stop = "停止世界树"; exit = "退出托盘"; language = "语言"; english = "English"; chinese = "中文";
        tray_title = "世界树"; tray_hint = "世界树已在系统托盘中就绪。"
    }
}
$LanguageRegistryPath = "HKCU:\Software\ProjectYggdrasil"
function Resolve-TrayLanguage {
    if ($Language -ne "auto") { return $Language }
    try {
        $Saved = Get-ItemPropertyValue -Path $LanguageRegistryPath -Name "UiLanguage" -ErrorAction Stop
        if ($Ui.ContainsKey([string]$Saved)) { return [string]$Saved }
    } catch { }
    if ([System.Globalization.CultureInfo]::CurrentUICulture.Name -like "zh*") {
        return "zh-CN"
    }
    return "en"
}
function Save-TrayLanguage {
    param([ValidateSet("en", "zh-CN")][string]$Value)
    try {
        if (-not (Test-Path $LanguageRegistryPath)) {
            New-Item -Path $LanguageRegistryPath -Force | Out-Null
        }
        Set-ItemProperty -Path $LanguageRegistryPath -Name "UiLanguage" -Value $Value -Force
    }
    catch {
        # Language selection remains usable for this tray session even when the registry is unavailable.
    }
}
function Get-TrayText { param([string]$Key); return $Ui[$script:CurrentLanguage][$Key] }
function Start-TrayLanguage {
    param([ValidateSet("en", "zh-CN")][string]$Value)
    Save-TrayLanguage -Value $Value
    $Args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Sta", "-File", $MyInvocation.MyCommand.Path, "-Language", $Value)
    if ($StartProduct) { $Args += "-StartProduct" }
    Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList $Args | Out-Null
    [System.Windows.Forms.Application]::Exit()
}

function Start-DesktopAction {
    param(
        [string]$Action,
        [switch]$Visible
    )
    $Arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass")
    if (-not $Visible) {
        $Arguments += "-WindowStyle"
        $Arguments += "Hidden"
    }
    else {
        $Arguments += "-NoExit"
    }
    $Arguments += "-File"
    $Arguments += $DesktopScript
    $Arguments += $Action
    Start-Process -FilePath "powershell.exe" -ArgumentList $Arguments | Out-Null
}

function Start-UpdateAction {
    param(
        [string]$Action,
        [switch]$Visible
    )
    $Arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass")
    if (-not $Visible) {
        $Arguments += "-WindowStyle"
        $Arguments += "Hidden"
    }
    else {
        $Arguments += "-NoExit"
    }
    $Arguments += "-File"
    $Arguments += $UpdateScript
    $Arguments += $Action
    Start-Process -FilePath "powershell.exe" -ArgumentList $Arguments | Out-Null
}

function New-TrayItem {
    param(
        [System.Windows.Forms.ContextMenuStrip]$Menu,
        [string]$Text,
        [scriptblock]$Action
    )
    $Item = New-Object System.Windows.Forms.ToolStripMenuItem
    $Item.Text = $Text
    $Item.Add_Click($Action)
    [void]$Menu.Items.Add($Item)
    return $Item
}

function New-StandaloneTrayItem {
    param(
        [string]$Text,
        [scriptblock]$Action
    )
    $Item = New-Object System.Windows.Forms.ToolStripMenuItem
    $Item.Text = $Text
    $Item.Add_Click($Action)
    return $Item
}

if (-not (Test-Path $DesktopScript)) {
    throw "Missing desktop controller: $DesktopScript"
}

$NotifyIcon = New-Object System.Windows.Forms.NotifyIcon
$script:CurrentLanguage = Resolve-TrayLanguage
$NotifyIcon.Text = Get-TrayText "tray_title"
$NotifyIcon.Icon = [System.Drawing.SystemIcons]::Application
$NotifyIcon.Visible = $true

$Menu = New-Object System.Windows.Forms.ContextMenuStrip
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "start") -Action { Start-DesktopAction -Action "start" })
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "open") -Action { Start-DesktopAction -Action "open" })
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "apps") -Action { Start-DesktopAction -Action "open-apps" })
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "settings") -Action { Start-DesktopAction -Action "open-settings" })
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "health") -Action { Start-DesktopAction -Action "status" -Visible })
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "logs") -Action { Start-DesktopAction -Action "logs" -Visible })
[void]$Menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "backup") -Action { Start-DesktopAction -Action "backup" -Visible })
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "snapshots") -Action { Start-DesktopAction -Action "snapshots" -Visible })
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "restore") -Action { Start-DesktopAction -Action "restore" -Visible })
[void]$Menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "updates") -Action { Start-UpdateAction -Action "check" -Visible })
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "apply") -Action { Start-UpdateAction -Action "apply" -Visible })
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "rollback") -Action { Start-DesktopAction -Action "rollback" -Visible })
[void]$Menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "stop") -Action { Start-DesktopAction -Action "stop" -Visible })
[void](New-TrayItem -Menu $Menu -Text (Get-TrayText "exit") -Action {
    $NotifyIcon.Visible = $false
    [System.Windows.Forms.Application]::Exit()
})

$LanguageMenu = New-Object System.Windows.Forms.ToolStripMenuItem
$LanguageMenu.Text = Get-TrayText "language"
[void]$LanguageMenu.DropDownItems.Add((New-StandaloneTrayItem -Text (Get-TrayText "english") -Action { Start-TrayLanguage "en" }))
[void]$LanguageMenu.DropDownItems.Add((New-StandaloneTrayItem -Text (Get-TrayText "chinese") -Action { Start-TrayLanguage "zh-CN" }))
[void]$Menu.Items.Add($LanguageMenu)

$NotifyIcon.ContextMenuStrip = $Menu
$NotifyIcon.Add_DoubleClick({ Start-DesktopAction -Action "open" })
$NotifyIcon.ShowBalloonTip(3000, (Get-TrayText "tray_title"), (Get-TrayText "tray_hint"), [System.Windows.Forms.ToolTipIcon]::Info)

if ($StartProduct) {
    Start-DesktopAction -Action "start"
}

[System.Windows.Forms.Application]::Run()
