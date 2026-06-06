param(
    [switch]$StartProduct
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
        $MyInvocation.MyCommand.Path
    )
    if ($StartProduct) {
        $RelaunchArguments += "-StartProduct"
    }
    Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList $RelaunchArguments
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

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

if (-not (Test-Path $DesktopScript)) {
    throw "Missing desktop controller: $DesktopScript"
}

$NotifyIcon = New-Object System.Windows.Forms.NotifyIcon
$NotifyIcon.Text = "Project Yggdrasil"
$NotifyIcon.Icon = [System.Drawing.SystemIcons]::Application
$NotifyIcon.Visible = $true

$Menu = New-Object System.Windows.Forms.ContextMenuStrip
[void](New-TrayItem -Menu $Menu -Text "Start and Open" -Action { Start-DesktopAction -Action "start" })
[void](New-TrayItem -Menu $Menu -Text "Open Web" -Action { Start-DesktopAction -Action "open" })
[void](New-TrayItem -Menu $Menu -Text "Status" -Action { Start-DesktopAction -Action "status" -Visible })
[void](New-TrayItem -Menu $Menu -Text "Logs" -Action { Start-DesktopAction -Action "logs" -Visible })
[void]$Menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
[void](New-TrayItem -Menu $Menu -Text "Backup" -Action { Start-DesktopAction -Action "backup" -Visible })
[void](New-TrayItem -Menu $Menu -Text "Snapshots" -Action { Start-DesktopAction -Action "snapshots" -Visible })
[void](New-TrayItem -Menu $Menu -Text "Restore Latest" -Action { Start-DesktopAction -Action "restore" -Visible })
[void]$Menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
[void](New-TrayItem -Menu $Menu -Text "Check Updates" -Action { Start-UpdateAction -Action "check" -Visible })
[void](New-TrayItem -Menu $Menu -Text "Apply Update" -Action { Start-UpdateAction -Action "apply" -Visible })
[void](New-TrayItem -Menu $Menu -Text "Rollback" -Action { Start-DesktopAction -Action "rollback" -Visible })
[void]$Menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
[void](New-TrayItem -Menu $Menu -Text "Stop Product" -Action { Start-DesktopAction -Action "stop" -Visible })
[void](New-TrayItem -Menu $Menu -Text "Exit Tray" -Action {
    $NotifyIcon.Visible = $false
    [System.Windows.Forms.Application]::Exit()
})

$NotifyIcon.ContextMenuStrip = $Menu
$NotifyIcon.Add_DoubleClick({ Start-DesktopAction -Action "open" })
$NotifyIcon.ShowBalloonTip(3000, "Project Yggdrasil", "Tray controller is running.", [System.Windows.Forms.ToolTipIcon]::Info)

if ($StartProduct) {
    Start-DesktopAction -Action "start"
}

[System.Windows.Forms.Application]::Run()
