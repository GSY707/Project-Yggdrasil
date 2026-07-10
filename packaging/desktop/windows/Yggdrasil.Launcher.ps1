$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopScript = Join-Path $ScriptRoot "Yggdrasil.Desktop.ps1"

if ([System.Threading.Thread]::CurrentThread.ApartmentState -ne "STA") {
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Sta", "-File", $MyInvocation.MyCommand.Path)
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$Colors = @{
    Background = [System.Drawing.Color]::FromArgb(7, 13, 25)
    Panel = [System.Drawing.Color]::FromArgb(17, 26, 42)
    PanelAlt = [System.Drawing.Color]::FromArgb(18, 27, 43)
    Border = [System.Drawing.Color]::FromArgb(39, 52, 74)
    Text = [System.Drawing.Color]::FromArgb(240, 244, 250)
    Muted = [System.Drawing.Color]::FromArgb(137, 148, 166)
    Accent = [System.Drawing.Color]::FromArgb(32, 227, 162)
    AccentText = [System.Drawing.Color]::FromArgb(4, 17, 13)
}

function Start-YggdrasilAction {
    param([string]$Action, [switch]$Visible)
    $Arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass")
    if (-not $Visible) { $Arguments += @("-WindowStyle", "Hidden") }
    $Arguments += @("-File", $DesktopScript, $Action)
    Start-Process powershell.exe -ArgumentList $Arguments | Out-Null
}

function New-LauncherButton {
    param([string]$Text, [int]$X, [int]$Y, [int]$Width, [scriptblock]$Action, [switch]$Primary)
    $Button = New-Object System.Windows.Forms.Button
    $Button.Text = $Text
    $Button.Location = New-Object System.Drawing.Point($X, $Y)
    $Button.Size = New-Object System.Drawing.Size($Width, 38)
    $Button.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $Button.FlatAppearance.BorderSize = 1
    $Button.FlatAppearance.BorderColor = if ($Primary) { $Colors.Accent } else { $Colors.Border }
    $Button.BackColor = if ($Primary) { $Colors.Accent } else { $Colors.PanelAlt }
    $Button.ForeColor = if ($Primary) { $Colors.AccentText } else { $Colors.Text }
    $Button.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
    $Button.Cursor = [System.Windows.Forms.Cursors]::Hand
    $Button.Add_Click($Action)
    return $Button
}

$Form = New-Object System.Windows.Forms.Form
$Form.Text = "Project Yggdrasil Launcher"
$Form.Size = New-Object System.Drawing.Size(820, 540)
$Form.MinimumSize = New-Object System.Drawing.Size(820, 540)
$Form.StartPosition = "CenterScreen"
$Form.BackColor = $Colors.Background
$Form.ForeColor = $Colors.Text
$Form.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$Header = New-Object System.Windows.Forms.Label
$Header.Text = "Project Yggdrasil Launcher"
$Header.Location = New-Object System.Drawing.Point(34, 30)
$Header.AutoSize = $true
$Header.Font = New-Object System.Drawing.Font("Segoe UI", 19, [System.Drawing.FontStyle]::Bold)
$Header.ForeColor = $Colors.Text
$Form.Controls.Add($Header)

$Subhead = New-Object System.Windows.Forms.Label
$Subhead.Text = "LOCAL AGENT SYSTEM  /  CONTROL CENTER"
$Subhead.Location = New-Object System.Drawing.Point(37, 67)
$Subhead.AutoSize = $true
$Subhead.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$Subhead.ForeColor = $Colors.Accent
$Form.Controls.Add($Subhead)

$StatusPanel = New-Object System.Windows.Forms.Panel
$StatusPanel.Location = New-Object System.Drawing.Point(34, 105)
$StatusPanel.Size = New-Object System.Drawing.Size(735, 112)
$StatusPanel.BackColor = $Colors.Panel
$StatusPanel.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$Form.Controls.Add($StatusPanel)

$StatusTitle = New-Object System.Windows.Forms.Label
$StatusTitle.Text = "Local product status"
$StatusTitle.Location = New-Object System.Drawing.Point(20, 17)
$StatusTitle.AutoSize = $true
$StatusTitle.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$StatusPanel.Controls.Add($StatusTitle)

$StatusValue = New-Object System.Windows.Forms.Label
$StatusValue.Text = "Checking local services..."
$StatusValue.Location = New-Object System.Drawing.Point(20, 48)
$StatusValue.Size = New-Object System.Drawing.Size(680, 40)
$StatusValue.ForeColor = $Colors.Muted
$StatusPanel.Controls.Add($StatusValue)

$Form.Controls.Add((New-LauncherButton -Text "Start Yggdrasil" -X 34 -Y 242 -Width 170 -Primary -Action {
    $StatusValue.Text = "Starting local services. This can take a moment..."
    Start-YggdrasilAction "start"
}))
$Form.Controls.Add((New-LauncherButton -Text "Open workspace" -X 216 -Y 242 -Width 170 -Action { Start-YggdrasilAction "open" }))
$Form.Controls.Add((New-LauncherButton -Text "Applications" -X 398 -Y 242 -Width 170 -Action { Start-YggdrasilAction "open-apps" }))
$Form.Controls.Add((New-LauncherButton -Text "Settings" -X 580 -Y 242 -Width 170 -Action { Start-YggdrasilAction "open-settings" }))

$Section = New-Object System.Windows.Forms.Label
$Section.Text = "MAINTENANCE"
$Section.Location = New-Object System.Drawing.Point(37, 313)
$Section.AutoSize = $true
$Section.ForeColor = $Colors.Muted
$Section.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$Form.Controls.Add($Section)

$Form.Controls.Add((New-LauncherButton -Text "Health & diagnostics" -X 34 -Y 342 -Width 170 -Action { Start-YggdrasilAction "status" -Visible }))
$Form.Controls.Add((New-LauncherButton -Text "Back up local data" -X 216 -Y 342 -Width 170 -Action { Start-YggdrasilAction "backup" -Visible }))
$Form.Controls.Add((New-LauncherButton -Text "Check for updates" -X 398 -Y 342 -Width 170 -Action {
    Start-Process powershell.exe -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", (Join-Path $ScriptRoot "Yggdrasil.Update.ps1"), "check") | Out-Null
}))
$Form.Controls.Add((New-LauncherButton -Text "Stop product" -X 580 -Y 342 -Width 170 -Action { Start-YggdrasilAction "stop" -Visible }))

$Privacy = New-Object System.Windows.Forms.Label
$Privacy.Text = "Tasks, materials, results, provider settings and backups remain on this computer by default."
$Privacy.Location = New-Object System.Drawing.Point(37, 420)
$Privacy.Size = New-Object System.Drawing.Size(710, 36)
$Privacy.ForeColor = $Colors.Muted
$Form.Controls.Add($Privacy)

$Form.Add_Shown({
    try {
        $Response = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:3000/api/core/health" -TimeoutSec 3
        if ($Response.StatusCode -eq 200) {
            $StatusValue.Text = "Ready. Local services are running and the workspace can be opened."
            $StatusValue.ForeColor = $Colors.Accent
        }
    }
    catch {
        $StatusValue.Text = "Not running. Start Yggdrasil to prepare the local workspace."
        $StatusValue.ForeColor = $Colors.Muted
    }
})

[void]$Form.ShowDialog()
