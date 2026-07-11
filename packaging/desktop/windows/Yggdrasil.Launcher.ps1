param(
    [ValidateSet("auto", "en", "zh-CN")]
    [string]$Language = "auto",
    [switch]$Setup
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
    if ($Setup) {
        $RelaunchArguments += "-Setup"
    }
    Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList $RelaunchArguments
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

if ($null -eq ("YggdrasilLauncherNative" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class YggdrasilLauncherNative
{
    [DllImport("user32.dll")]
    public static extern bool ReleaseCapture();

    [DllImport("user32.dll")]
    public static extern IntPtr SendMessage(IntPtr hWnd, int message, IntPtr wParam, IntPtr lParam);
}
"@
}

# The message dictionaries are intentionally local to the Windows surface.
# Add another locale by copying this key set; controls are registered by key.
$Ui = @{
    "en" = @{
        launcher_title = "Project Yggdrasil Launcher"
        setup_title = "Project Yggdrasil Setup"
        setup = "Setup"
        launcher = "Launcher"
        language = "Language"
        english = "EN"
        chinese = "中文"
        system_status = "System Status"
        checking = "Checking local services..."
        ready = "Ready"
        not_running = "Not running"
        maintenance = "Maintenance"
        check_updates = "Check for updates"
        data_safety = "Data Safety"
        local_backup = "Local backup"
        applications = "Applications"
        deep_research = "Deep Research"
        graduate_writing = "Graduate Writing"
        coding_assistant = "Coding Assistant"
        knowledge_base = "Knowledge Base"
        deep_research_copy = "Gather and synthesize complex information across knowledge domains."
        graduate_writing_copy = "Draft, refine, and structure long-form academic and professional work."
        coding_assistant_copy = "Develop, debug, and optimize software projects."
        knowledge_base_copy = "Manage and query saved notes, materials, and insights."
        app_available = "Available"
        launch = "Launch"
        open_window = "Open Window"
        recent_tasks = "Recent Tasks"
        recent_task_hint_one = "Open the workspace to view current tasks and results."
        recent_task_hint_two = "Task state remains available in the browser workbench."
        open_workspace = "Open workspace"
        quick_actions = "Quick Actions"
        create_backup = "Create Backup"
        run_diagnostics = "Run Diagnostics"
        settings = "Settings"
        stop_product = "Stop product"
        status_ready_detail = "Local services are running and the workspace can be opened."
        status_not_running_detail = "Start an application or the local product to prepare this workspace."
        setup_welcome = "Welcome"
        ready_to_begin = "Ready to begin"
        start_setup = "Start setup"
        choose_install_folder = "Install location"
        install_folder_selected = "The installed desktop package is stored here."
        open_install_folder = "Open install folder"
        choose_data_folder = "Data & backups"
        data_folder_copy = "Open local backup and data governance controls."
        open_data_backups = "Open data & backups"
        connect_ai_service = "Connect AI Service"
        connect_ai_copy = "Configure a provider before starting live tasks."
        open_settings = "Open settings"
        available_apps = "Available Applications"
        browse_applications = "Browse applications"
        shortcuts_startup = "Shortcuts & Startup"
        shortcut_copy = "Install the supported desktop and Start Menu shortcuts."
        install_shortcuts = "Install shortcuts"
        setup_complete = "Setup Complete"
        setup_complete_copy = "Open the launcher when you are ready to work."
        open_launcher = "Open Launcher"
        stop_confirm_title = "Stop local product?"
        stop_confirm_copy = "This stops the local services. Your task data and backups remain on this computer."
        tray_running_quietly = "Running quietly"
        tray_open = "Open Project Yggdrasil"
        tray_start = "Start Yggdrasil"
        tray_apps = "Applications"
        tray_maintenance = "Maintenance"
        tray_view_backups = "View Backups"
        tray_restore_backup = "Restore Latest Backup"
        tray_apply_update = "Apply Update"
        tray_rollback = "Restore Previous Version"
        tray_stop = "Stop Yggdrasil"
        tray_exit = "Exit Tray"
        tray_available = "Yggdrasil is available from the tray."
    }
    "zh-CN" = @{
        launcher_title = "世界树启动器"
        setup_title = "世界树安装与准备"
        setup = "准备"
        launcher = "启动器"
        language = "语言"
        english = "EN"
        chinese = "中文"
        system_status = "系统状态"
        checking = "正在检查本地服务..."
        ready = "已就绪"
        not_running = "未启动"
        maintenance = "维护"
        check_updates = "检查更新"
        data_safety = "数据安全"
        local_backup = "本地备份"
        applications = "应用"
        deep_research = "深度研究"
        graduate_writing = "研究写作"
        coding_assistant = "编程助手"
        knowledge_base = "知识库"
        deep_research_copy = "跨资料和知识领域收集、核对并综合复杂信息。"
        graduate_writing_copy = "起草、修订并组织长篇学术与专业内容。"
        coding_assistant_copy = "开发、调试并优化软件项目。"
        knowledge_base_copy = "管理并检索已保存的笔记、材料和洞见。"
        app_available = "可启动"
        launch = "启动"
        open_window = "打开窗口"
        recent_tasks = "最近任务"
        recent_task_hint_one = "在工作台查看当前任务、进度和结果。"
        recent_task_hint_two = "任务状态会保留在浏览器工作台中。"
        open_workspace = "打开工作台"
        quick_actions = "快捷操作"
        create_backup = "创建备份"
        run_diagnostics = "运行诊断"
        settings = "设置"
        stop_product = "停止本地产品"
        status_ready_detail = "本地服务已经就绪，可以打开工作台。"
        status_not_running_detail = "启动任一应用或本地产品以准备工作台。"
        setup_welcome = "欢迎"
        ready_to_begin = "可以开始"
        start_setup = "开始准备"
        choose_install_folder = "安装位置"
        install_folder_selected = "桌面封装安装在此位置。"
        open_install_folder = "打开安装位置"
        choose_data_folder = "数据与备份"
        data_folder_copy = "打开本地备份和数据治理控制项。"
        open_data_backups = "打开数据与备份"
        connect_ai_service = "连接 AI 服务"
        connect_ai_copy = "启动真实任务前，需要先配置模型服务商。"
        open_settings = "打开设置"
        available_apps = "可用应用"
        browse_applications = "浏览应用"
        shortcuts_startup = "快捷方式与启动"
        shortcut_copy = "安装受支持的桌面与开始菜单快捷方式。"
        install_shortcuts = "安装快捷方式"
        setup_complete = "准备完成"
        setup_complete_copy = "准备好工作后，打开启动器即可继续。"
        open_launcher = "打开启动器"
        stop_confirm_title = "停止本地产品？"
        stop_confirm_copy = "这会停止本地服务；任务数据和备份仍会保留在此电脑上。"
        tray_running_quietly = "正在后台运行"
        tray_open = "打开世界树"
        tray_start = "启动世界树"
        tray_apps = "应用"
        tray_maintenance = "维护"
        tray_view_backups = "查看备份"
        tray_restore_backup = "恢复最近备份"
        tray_apply_update = "应用更新"
        tray_rollback = "恢复上一版本"
        tray_stop = "停止世界树"
        tray_exit = "退出托盘"
        tray_available = "世界树已在系统托盘中就绪。"
    }
}

$Colors = @{
    Background = [System.Drawing.Color]::FromArgb(7, 14, 29)
    Surface = [System.Drawing.Color]::FromArgb(12, 19, 34)
    SurfaceLow = [System.Drawing.Color]::FromArgb(20, 27, 43)
    SurfaceContainer = [System.Drawing.Color]::FromArgb(25, 31, 47)
    SurfaceHigh = [System.Drawing.Color]::FromArgb(35, 42, 58)
    SurfaceHighest = [System.Drawing.Color]::FromArgb(46, 53, 69)
    Outline = [System.Drawing.Color]::FromArgb(64, 73, 68)
    Text = [System.Drawing.Color]::FromArgb(220, 226, 247)
    Muted = [System.Drawing.Color]::FromArgb(191, 201, 195)
    Primary = [System.Drawing.Color]::FromArgb(149, 211, 186)
    Secondary = [System.Drawing.Color]::FromArgb(78, 222, 163)
    SecondaryText = [System.Drawing.Color]::FromArgb(0, 56, 36)
    Warning = [System.Drawing.Color]::FromArgb(255, 198, 92)
    Info = [System.Drawing.Color]::FromArgb(116, 183, 255)
    Error = [System.Drawing.Color]::FromArgb(255, 180, 171)
}

$LanguageRegistryPath = "HKCU:\Software\ProjectYggdrasil"
$script:LocalizedControls = [System.Collections.Generic.List[object]]::new()
$script:HealthStatusKey = "checking"
$script:CurrentLanguage = "en"

function Get-SavedLanguage {
    try {
        $Saved = Get-ItemPropertyValue -Path $LanguageRegistryPath -Name "UiLanguage" -ErrorAction Stop
        if ($Ui.ContainsKey([string]$Saved)) {
            return [string]$Saved
        }
    }
    catch {
    }
    return $null
}

function Resolve-UiLanguage {
    if ($Language -ne "auto") {
        return $Language
    }
    $Saved = Get-SavedLanguage
    if ($null -ne $Saved) {
        return $Saved
    }
    if ([System.Globalization.CultureInfo]::CurrentUICulture.Name -like "zh*") {
        return "zh-CN"
    }
    return "en"
}

function Save-UiLanguage {
    try {
        if (-not (Test-Path $LanguageRegistryPath)) {
            New-Item -Path $LanguageRegistryPath -Force | Out-Null
        }
        Set-ItemProperty -Path $LanguageRegistryPath -Name "UiLanguage" -Value $script:CurrentLanguage -Force
    }
    catch {
    }
}

function Get-Text {
    param([string]$Key)
    $Value = $Ui[$script:CurrentLanguage][$Key]
    if ($null -eq $Value) {
        $Value = $Ui["en"][$Key]
    }
    if ($null -eq $Value) {
        return "[$Key]"
    }
    return [string]$Value
}

function Register-LocalizedControl {
    param(
        [System.Windows.Forms.Control]$Control,
        [string]$Key
    )
    $Control.Text = Get-Text $Key
    $script:LocalizedControls.Add([pscustomobject]@{ Control = $Control; Key = $Key }) | Out-Null
}

function New-LocalizedLabel {
    param(
        [string]$Key,
        [System.Drawing.Font]$Font,
        [System.Drawing.Color]$ForeColor,
        [switch]$NoAutoSize
    )
    $Label = New-Object System.Windows.Forms.Label
    $Label.AutoSize = -not $NoAutoSize
    $Label.Font = $Font
    $Label.ForeColor = $ForeColor
    $Label.BackColor = [System.Drawing.Color]::Transparent
    Register-LocalizedControl -Control $Label -Key $Key
    return $Label
}

function New-LocalizedCheckBox {
    param([string]$Key, [bool]$Checked = $true)
    $CheckBox = New-Object System.Windows.Forms.CheckBox
    $CheckBox.AutoSize = $true
    $CheckBox.AutoCheck = $false
    $CheckBox.Checked = $Checked
    $CheckBox.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $CheckBox.FlatAppearance.BorderColor = $Colors.Secondary
    $CheckBox.FlatAppearance.CheckedBackColor = $Colors.Secondary
    $CheckBox.ForeColor = $Colors.Text
    $CheckBox.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
    Register-LocalizedControl -Control $CheckBox -Key $Key
    return $CheckBox
}

function New-SystemIcon {
    param(
        [System.Drawing.Icon]$Icon,
        [int]$Size = 28
    )
    $Picture = New-Object System.Windows.Forms.PictureBox
    $Picture.Size = New-Object System.Drawing.Size($Size, $Size)
    $Picture.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::CenterImage
    $Picture.Image = $Icon.ToBitmap()
    return $Picture
}

function New-Surface {
    param([switch]$Accent)
    $Surface = New-Object System.Windows.Forms.Panel
    $Surface.BackColor = $Colors.SurfaceContainer
    $Surface.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
    if ($Accent) {
        $Surface.BackColor = $Colors.SurfaceHigh
    }
    return $Surface
}

function New-ActionButton {
    param(
        [string]$Key,
        [scriptblock]$Action,
        [switch]$Primary,
        [int]$Height = 34
    )
    $Button = New-Object System.Windows.Forms.Button
    $Button.Height = $Height
    $Button.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $Button.FlatAppearance.BorderSize = 1
    $Button.FlatAppearance.BorderColor = if ($Primary) { $Colors.Secondary } else { $Colors.Outline }
    $Button.FlatAppearance.MouseOverBackColor = if ($Primary) { $Colors.Primary } else { $Colors.SurfaceHighest }
    $Button.BackColor = if ($Primary) { $Colors.Secondary } else { $Colors.SurfaceHigh }
    $Button.ForeColor = if ($Primary) { $Colors.SecondaryText } else { $Colors.Text }
    $Button.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
    $Button.Cursor = [System.Windows.Forms.Cursors]::Hand
    $Button.UseVisualStyleBackColor = $false
    Register-LocalizedControl -Control $Button -Key $Key
    $Button.Add_Click($Action)
    return $Button
}

function Start-YggdrasilAction {
    param(
        [string]$Action,
        [string]$OpenPath = "",
        [switch]$Visible
    )
    $Arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass")
    if (-not $Visible) {
        $Arguments += @("-WindowStyle", "Hidden")
    }
    else {
        $Arguments += "-NoExit"
    }
    $Arguments += @("-File", $DesktopScript, $Action)
    if ($OpenPath.Trim().Length -gt 0) {
        $Arguments += @("-OpenPath", $OpenPath)
    }
    Start-Process -FilePath "powershell.exe" -ArgumentList $Arguments | Out-Null
}

function Start-UpdateCheck {
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-NoExit",
        "-File",
        $UpdateScript,
        "check"
    ) | Out-Null
}

function Show-StopProductConfirmation {
    $Decision = [System.Windows.Forms.MessageBox]::Show(
        (Get-Text "stop_confirm_copy"),
        (Get-Text "stop_confirm_title"),
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Warning
    )
    if ($Decision -eq [System.Windows.Forms.DialogResult]::Yes) {
        Start-YggdrasilAction -Action "stop" -Visible
    }
}

function Update-LanguageButtons {
    if ($null -eq $script:LanguageEnglishButton) {
        return
    }
    $script:LanguageEnglishButton.BackColor = if ($script:CurrentLanguage -eq "en") { $Colors.Secondary } else { $Colors.SurfaceHigh }
    $script:LanguageEnglishButton.ForeColor = if ($script:CurrentLanguage -eq "en") { $Colors.SecondaryText } else { $Colors.Muted }
    $script:LanguageChineseButton.BackColor = if ($script:CurrentLanguage -eq "zh-CN") { $Colors.Secondary } else { $Colors.SurfaceHigh }
    $script:LanguageChineseButton.ForeColor = if ($script:CurrentLanguage -eq "zh-CN") { $Colors.SecondaryText } else { $Colors.Muted }
}

function Update-DynamicText {
    if ($null -ne $script:SystemStatusValue) {
        $script:SystemStatusValue.Text = Get-Text $script:HealthStatusKey
        $script:SystemStatusValue.ForeColor = if ($script:HealthStatusKey -eq "ready") { $Colors.Secondary } else { $Colors.Muted }
    }
    if ($null -ne $script:MaintenanceValue) {
        $script:MaintenanceValue.Text = Get-Text "check_updates"
    }
    if ($null -ne $script:BackupValue) {
        $script:BackupValue.Text = Get-Text "local_backup"
    }
    if ($null -ne $script:HealthDetail) {
        $DetailKey = if ($script:HealthStatusKey -eq "ready") { "status_ready_detail" } else { "status_not_running_detail" }
        $script:HealthDetail.Text = Get-Text $DetailKey
    }
}

function Update-WindowText {
    $InSetup = $null -ne $script:SetupView -and $script:SetupView.Visible
    $TitleKey = if ($InSetup) { "setup_title" } else { "launcher_title" }
    $script:Form.Text = Get-Text $TitleKey
    $script:HeaderTitle.Text = Get-Text $TitleKey
    $script:ModeButton.Text = Get-Text $(if ($InSetup) { "launcher" } else { "setup" })
}

function Update-LocalizedControls {
    foreach ($Entry in $script:LocalizedControls) {
        if ($null -ne $Entry.Control -and -not $Entry.Control.IsDisposed) {
            $Entry.Control.Text = Get-Text $Entry.Key
        }
    }
    Update-DynamicText
    Update-WindowText
    Update-LanguageButtons
}

function Set-UiLanguage {
    param([ValidateSet("en", "zh-CN")][string]$Value)
    $script:CurrentLanguage = $Value
    Save-UiLanguage
    Update-LocalizedControls
}

function Refresh-LauncherHealth {
    $script:HealthStatusKey = "checking"
    Update-DynamicText
    try {
        $Response = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:3000/api/core/health" -TimeoutSec 3
        if ($Response.StatusCode -eq 200) {
            $script:HealthStatusKey = "ready"
        }
        else {
            $script:HealthStatusKey = "not_running"
        }
    }
    catch {
        $script:HealthStatusKey = "not_running"
    }
    Update-DynamicText
}

function New-StatusCard {
    param(
        [string]$TitleKey,
        [System.Drawing.Icon]$Icon,
        [System.Drawing.Color]$ValueColor
    )
    $Card = New-Surface
    $Card.Dock = [System.Windows.Forms.DockStyle]::Fill
    $Card.Margin = New-Object System.Windows.Forms.Padding(0, 0, 12, 0)

    $IconBox = New-SystemIcon -Icon $Icon -Size 32
    $IconBox.Location = New-Object System.Drawing.Point(14, 24)
    $Card.Controls.Add($IconBox)

    $Title = New-LocalizedLabel -Key $TitleKey -Font (New-Object System.Drawing.Font("Segoe UI", 8)) -ForeColor $Colors.Muted
    $Title.Location = New-Object System.Drawing.Point(58, 17)
    $Card.Controls.Add($Title)

    $Value = New-Object System.Windows.Forms.Label
    $Value.AutoSize = $true
    $Value.Location = New-Object System.Drawing.Point(58, 40)
    $Value.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
    $Value.ForeColor = $ValueColor
    $Card.Controls.Add($Value)

    return [pscustomobject]@{
        Card = $Card
        Value = $Value
    }
}

function New-AppCard {
    param(
        [string]$NameKey,
        [string]$DescriptionKey,
        [string]$ActionKey,
        [System.Drawing.Icon]$Icon,
        [scriptblock]$Action,
        [switch]$Primary
    )
    $Card = New-Surface
    $Card.Dock = [System.Windows.Forms.DockStyle]::Fill
    $Card.Margin = New-Object System.Windows.Forms.Padding(0, 0, 12, 12)

    $IconBox = New-SystemIcon -Icon $Icon -Size 36
    $IconBox.Location = New-Object System.Drawing.Point(16, 16)
    $Card.Controls.Add($IconBox)

    $State = New-LocalizedLabel -Key "app_available" -Font (New-Object System.Drawing.Font("Consolas", 7.5)) -ForeColor $Colors.Muted
    $State.BackColor = $Colors.SurfaceHighest
    $State.Padding = New-Object System.Windows.Forms.Padding(6, 3, 6, 3)
    $State.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
    $State.Location = New-Object System.Drawing.Point(310, 18)
    $Card.Controls.Add($State)

    $Name = New-LocalizedLabel -Key $NameKey -Font (New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)) -ForeColor $Colors.Text
    $Name.Location = New-Object System.Drawing.Point(16, 62)
    $Name.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $Name.Size = New-Object System.Drawing.Size(360, 22)
    $Card.Controls.Add($Name)

    $Description = New-LocalizedLabel -Key $DescriptionKey -Font (New-Object System.Drawing.Font("Segoe UI", 8)) -ForeColor $Colors.Muted -NoAutoSize
    $Description.Location = New-Object System.Drawing.Point(16, 88)
    $Description.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $Description.Size = New-Object System.Drawing.Size(360, 36)
    $Card.Controls.Add($Description)

    $Button = New-ActionButton -Key $ActionKey -Action $Action -Primary:$Primary
    $Button.Location = New-Object System.Drawing.Point(16, 138)
    $Button.Width = 132
    $Button.Anchor = [System.Windows.Forms.AnchorStyles]::Bottom -bor [System.Windows.Forms.AnchorStyles]::Left
    $Card.Controls.Add($Button)
    return $Card
}

function New-RecentTasksPanel {
    $Panel = New-Surface
    $Panel.Dock = [System.Windows.Forms.DockStyle]::Fill
    $Panel.Margin = New-Object System.Windows.Forms.Padding(0, 0, 14, 0)

    $Title = New-LocalizedLabel -Key "recent_tasks" -Font (New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)) -ForeColor $Colors.Text
    $Title.Location = New-Object System.Drawing.Point(16, 14)
    $Panel.Controls.Add($Title)

    $LineOne = New-LocalizedLabel -Key "recent_task_hint_one" -Font (New-Object System.Drawing.Font("Segoe UI", 8.5)) -ForeColor $Colors.Muted -NoAutoSize
    $LineOne.Location = New-Object System.Drawing.Point(16, 50)
    $LineOne.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $LineOne.Size = New-Object System.Drawing.Size(590, 28)
    $Panel.Controls.Add($LineOne)

    $LineTwo = New-LocalizedLabel -Key "recent_task_hint_two" -Font (New-Object System.Drawing.Font("Segoe UI", 8.5)) -ForeColor $Colors.Muted -NoAutoSize
    $LineTwo.Location = New-Object System.Drawing.Point(16, 88)
    $LineTwo.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $LineTwo.Size = New-Object System.Drawing.Size(590, 28)
    $Panel.Controls.Add($LineTwo)

    $OpenButton = New-ActionButton -Key "open_workspace" -Action { Start-YggdrasilAction -Action "open" }
    $OpenButton.Location = New-Object System.Drawing.Point(16, 150)
    $OpenButton.Width = 150
    $OpenButton.Anchor = [System.Windows.Forms.AnchorStyles]::Bottom -bor [System.Windows.Forms.AnchorStyles]::Left
    $Panel.Controls.Add($OpenButton)
    return $Panel
}

function New-QuickActionsPanel {
    $Panel = New-Surface
    $Panel.Dock = [System.Windows.Forms.DockStyle]::Fill

    $Title = New-LocalizedLabel -Key "quick_actions" -Font (New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)) -ForeColor $Colors.Text
    $Title.Location = New-Object System.Drawing.Point(16, 14)
    $Panel.Controls.Add($Title)

    $Buttons = @(
        (New-ActionButton -Key "create_backup" -Action { Start-YggdrasilAction -Action "backup" -Visible }),
        (New-ActionButton -Key "run_diagnostics" -Action { Start-YggdrasilAction -Action "status" -Visible }),
        (New-ActionButton -Key "check_updates" -Action { Start-UpdateCheck }),
        (New-ActionButton -Key "settings" -Action { Start-YggdrasilAction -Action "open-settings" }),
        (New-ActionButton -Key "stop_product" -Action { Show-StopProductConfirmation })
    )
    $Top = 48
    foreach ($Button in $Buttons) {
        $Button.Location = New-Object System.Drawing.Point(16, $Top)
        $Button.Width = 212
        $Button.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
        $Panel.Controls.Add($Button)
        $Top += 37
    }
    return $Panel
}

function New-SetupCard {
    param(
        [string]$TitleKey,
        [string]$CopyKey,
        [string]$ActionKey,
        [System.Drawing.Icon]$Icon,
        [scriptblock]$Action,
        [switch]$Primary
    )
    $Card = New-Surface
    $Card.Dock = [System.Windows.Forms.DockStyle]::Fill
    $Card.Margin = New-Object System.Windows.Forms.Padding(0, 0, 12, 12)

    $IconBox = New-SystemIcon -Icon $Icon -Size 22
    $IconBox.Location = New-Object System.Drawing.Point(14, 14)
    $Card.Controls.Add($IconBox)

    $Title = New-LocalizedLabel -Key $TitleKey -Font (New-Object System.Drawing.Font("Consolas", 8, [System.Drawing.FontStyle]::Bold)) -ForeColor $Colors.Text -NoAutoSize
    $Title.Location = New-Object System.Drawing.Point(42, 17)
    $Title.Size = New-Object System.Drawing.Size(175, 20)
    $Title.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $Card.Controls.Add($Title)

    $Copy = New-LocalizedLabel -Key $CopyKey -Font (New-Object System.Drawing.Font("Segoe UI", 8)) -ForeColor $Colors.Muted -NoAutoSize
    $Copy.Location = New-Object System.Drawing.Point(14, 54)
    $Copy.Size = New-Object System.Drawing.Size(200, 40)
    $Copy.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $Card.Controls.Add($Copy)

    $Button = New-ActionButton -Key $ActionKey -Action $Action -Primary:$Primary
    $Button.Location = New-Object System.Drawing.Point(14, 118)
    $Button.Width = 196
    $Button.Anchor = [System.Windows.Forms.AnchorStyles]::Bottom -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $Card.Controls.Add($Button)
    return $Card
}

function New-SetupCatalogCard {
    $Card = New-Surface
    $Card.Dock = [System.Windows.Forms.DockStyle]::Fill
    $Card.Margin = New-Object System.Windows.Forms.Padding(0, 0, 12, 0)

    $Title = New-LocalizedLabel -Key "available_apps" -Font (New-Object System.Drawing.Font("Consolas", 8, [System.Drawing.FontStyle]::Bold)) -ForeColor $Colors.Text
    $Title.Location = New-Object System.Drawing.Point(14, 14)
    $Card.Controls.Add($Title)

    $Names = @("deep_research", "graduate_writing", "coding_assistant", "knowledge_base")
    $Top = 44
    foreach ($Name in $Names) {
        $Item = New-LocalizedCheckBox -Key $Name
        $Item.Location = New-Object System.Drawing.Point(14, $Top)
        $Card.Controls.Add($Item)
        $Top += 26
    }
    $Button = New-ActionButton -Key "browse_applications" -Action { Start-YggdrasilAction -Action "open-apps" }
    $Button.Location = New-Object System.Drawing.Point(14, 155)
    $Button.Width = 220
    $Button.Anchor = [System.Windows.Forms.AnchorStyles]::Bottom -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $Card.Controls.Add($Button)
    return $Card
}

function New-SetupShortcutsCard {
    $Card = New-Surface
    $Card.Dock = [System.Windows.Forms.DockStyle]::Fill
    $Card.Margin = New-Object System.Windows.Forms.Padding(0, 0, 12, 0)

    $Title = New-LocalizedLabel -Key "shortcuts_startup" -Font (New-Object System.Drawing.Font("Consolas", 8, [System.Drawing.FontStyle]::Bold)) -ForeColor $Colors.Text
    $Title.Location = New-Object System.Drawing.Point(14, 14)
    $Card.Controls.Add($Title)

    $Copy = New-LocalizedLabel -Key "shortcut_copy" -Font (New-Object System.Drawing.Font("Segoe UI", 8)) -ForeColor $Colors.Muted -NoAutoSize
    $Copy.Location = New-Object System.Drawing.Point(14, 48)
    $Copy.Size = New-Object System.Drawing.Size(230, 54)
    $Copy.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $Card.Controls.Add($Copy)

    $Button = New-ActionButton -Key "install_shortcuts" -Action { Start-YggdrasilAction -Action "install-shortcuts" -Visible }
    $Button.Location = New-Object System.Drawing.Point(14, 155)
    $Button.Width = 220
    $Button.Anchor = [System.Windows.Forms.AnchorStyles]::Bottom -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $Card.Controls.Add($Button)
    return $Card
}

function New-SetupCompleteCard {
    $Card = New-Surface -Accent
    $Card.Dock = [System.Windows.Forms.DockStyle]::Fill

    $Title = New-LocalizedLabel -Key "setup_complete" -Font (New-Object System.Drawing.Font("Consolas", 8, [System.Drawing.FontStyle]::Bold)) -ForeColor $Colors.Secondary
    $Title.Location = New-Object System.Drawing.Point(14, 14)
    $Card.Controls.Add($Title)

    $Copy = New-LocalizedLabel -Key "setup_complete_copy" -Font (New-Object System.Drawing.Font("Segoe UI", 8)) -ForeColor $Colors.Text -NoAutoSize
    $Copy.Location = New-Object System.Drawing.Point(14, 48)
    $Copy.Size = New-Object System.Drawing.Size(230, 48)
    $Copy.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $Card.Controls.Add($Copy)

    $Button = New-ActionButton -Key "open_launcher" -Action { Show-DailyView } -Primary
    $Button.Location = New-Object System.Drawing.Point(14, 155)
    $Button.Width = 220
    $Button.Anchor = [System.Windows.Forms.AnchorStyles]::Bottom -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
    $Card.Controls.Add($Button)
    return $Card
}

function New-DailyView {
    $View = New-Object System.Windows.Forms.Panel
    $View.Dock = [System.Windows.Forms.DockStyle]::Fill
    $View.AutoScroll = $true
    $View.BackColor = $Colors.Surface

    $Layout = New-Object System.Windows.Forms.TableLayoutPanel
    $Layout.ColumnCount = 1
    $Layout.RowCount = 4
    $Layout.AutoSize = $false
    $Layout.Dock = [System.Windows.Forms.DockStyle]::Top
    $Layout.Padding = New-Object System.Windows.Forms.Padding(22, 22, 22, 22)
    $Layout.Height = 700
    $Layout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100))) | Out-Null
    $Layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 86))) | Out-Null
    $Layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 38))) | Out-Null
    $Layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 330))) | Out-Null
    $Layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 202))) | Out-Null
    $View.Controls.Add($Layout)

    $StatusGrid = New-Object System.Windows.Forms.TableLayoutPanel
    $StatusGrid.Dock = [System.Windows.Forms.DockStyle]::Fill
    $StatusGrid.ColumnCount = 3
    $StatusGrid.RowCount = 1
    $StatusGrid.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 0)
    foreach ($Index in 1..3) {
        $StatusGrid.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 33.333))) | Out-Null
    }

    $SystemCard = New-StatusCard -TitleKey "system_status" -Icon ([System.Drawing.SystemIcons]::Information) -ValueColor $Colors.Secondary
    $script:SystemStatusValue = $SystemCard.Value
    $StatusGrid.Controls.Add($SystemCard.Card, 0, 0)

    $MaintenanceCard = New-StatusCard -TitleKey "maintenance" -Icon ([System.Drawing.SystemIcons]::Warning) -ValueColor $Colors.Warning
    $script:MaintenanceValue = $MaintenanceCard.Value
    $StatusGrid.Controls.Add($MaintenanceCard.Card, 1, 0)

    $BackupCard = New-StatusCard -TitleKey "data_safety" -Icon ([System.Drawing.SystemIcons]::Shield) -ValueColor $Colors.Info
    $BackupCard.Card.Margin = New-Object System.Windows.Forms.Padding(0)
    $script:BackupValue = $BackupCard.Value
    $StatusGrid.Controls.Add($BackupCard.Card, 2, 0)
    $Layout.Controls.Add($StatusGrid, 0, 0)

    $AppsTitle = New-LocalizedLabel -Key "applications" -Font (New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)) -ForeColor $Colors.Text
    $AppsTitle.Dock = [System.Windows.Forms.DockStyle]::Fill
    $AppsTitle.TextAlign = [System.Drawing.ContentAlignment]::MiddleLeft
    $Layout.Controls.Add($AppsTitle, 0, 1)

    $AppsGrid = New-Object System.Windows.Forms.TableLayoutPanel
    $AppsGrid.Dock = [System.Windows.Forms.DockStyle]::Fill
    $AppsGrid.ColumnCount = 2
    $AppsGrid.RowCount = 2
    $AppsGrid.Margin = New-Object System.Windows.Forms.Padding(0)
    foreach ($Index in 1..2) {
        $AppsGrid.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 50))) | Out-Null
        $AppsGrid.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 50))) | Out-Null
    }
    $AppsGrid.Controls.Add(
        (New-AppCard -NameKey "deep_research" -DescriptionKey "deep_research_copy" -ActionKey "launch" -Icon ([System.Drawing.SystemIcons]::Information) -Primary -Action {
            Start-YggdrasilAction -Action "start-app" -OpenPath "/applications/yggdrasil.app.deep-research"
        }),
        0,
        0
    )
    $AppsGrid.Controls.Add(
        (New-AppCard -NameKey "graduate_writing" -DescriptionKey "graduate_writing_copy" -ActionKey "launch" -Icon ([System.Drawing.SystemIcons]::Question) -Primary -Action {
            Start-YggdrasilAction -Action "start-app" -OpenPath "/applications/yggdrasil.app.graduate-researcher"
        }),
        1,
        0
    )
    $AppsGrid.Controls.Add(
        (New-AppCard -NameKey "coding_assistant" -DescriptionKey "coding_assistant_copy" -ActionKey "open_window" -Icon ([System.Drawing.SystemIcons]::Application) -Action {
            Start-YggdrasilAction -Action "start-app" -OpenPath "/applications/yggdrasil.app.coding-greenfield"
        }),
        0,
        1
    )
    $KnowledgeCard = New-AppCard -NameKey "knowledge_base" -DescriptionKey "knowledge_base_copy" -ActionKey "launch" -Icon ([System.Drawing.SystemIcons]::Asterisk) -Primary -Action {
        Start-YggdrasilAction -Action "start-app" -OpenPath "/applications/yggdrasil.app.knowledge-studio"
    }
    $KnowledgeCard.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 12)
    $AppsGrid.Controls.Add($KnowledgeCard, 1, 1)
    $Layout.Controls.Add($AppsGrid, 0, 2)

    $LowerGrid = New-Object System.Windows.Forms.TableLayoutPanel
    $LowerGrid.Dock = [System.Windows.Forms.DockStyle]::Fill
    $LowerGrid.ColumnCount = 2
    $LowerGrid.RowCount = 1
    $LowerGrid.Margin = New-Object System.Windows.Forms.Padding(0)
    $LowerGrid.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 68))) | Out-Null
    $LowerGrid.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 32))) | Out-Null
    $LowerGrid.Controls.Add((New-RecentTasksPanel), 0, 0)
    $LowerGrid.Controls.Add((New-QuickActionsPanel), 1, 0)
    $Layout.Controls.Add($LowerGrid, 0, 3)

    $ResizeHandler = {
        $Layout.Width = [Math]::Max(860, $View.ClientSize.Width - 18)
    }.GetNewClosure()
    $View.Add_Resize($ResizeHandler)
    return $View
}

function New-SetupView {
    $View = New-Object System.Windows.Forms.Panel
    $View.Dock = [System.Windows.Forms.DockStyle]::Fill
    $View.AutoScroll = $true
    $View.BackColor = $Colors.Background

    $Layout = New-Object System.Windows.Forms.TableLayoutPanel
    $Layout.ColumnCount = 1
    $Layout.RowCount = 2
    $Layout.AutoSize = $false
    $Layout.Dock = [System.Windows.Forms.DockStyle]::Top
    $Layout.Padding = New-Object System.Windows.Forms.Padding(22, 28, 22, 22)
    $Layout.Height = 428
    $Layout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100))) | Out-Null
    $Layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 164))) | Out-Null
    $Layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 210))) | Out-Null
    $View.Controls.Add($Layout)

    $TopGrid = New-Object System.Windows.Forms.TableLayoutPanel
    $TopGrid.Dock = [System.Windows.Forms.DockStyle]::Fill
    $TopGrid.ColumnCount = 4
    $TopGrid.RowCount = 1
    foreach ($Index in 1..4) {
        $TopGrid.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 25))) | Out-Null
    }
    $TopGrid.Controls.Add(
        (New-SetupCard -TitleKey "setup_welcome" -CopyKey "ready_to_begin" -ActionKey "start_setup" -Icon ([System.Drawing.SystemIcons]::Information) -Primary -Action {
            Start-YggdrasilAction -Action "start"
            Refresh-LauncherHealth
        }),
        0,
        0
    )
    $TopGrid.Controls.Add(
        (New-SetupCard -TitleKey "choose_install_folder" -CopyKey "install_folder_selected" -ActionKey "open_install_folder" -Icon ([System.Drawing.SystemIcons]::Application) -Action {
            Start-Process -FilePath "explorer.exe" -ArgumentList @($ScriptRoot) | Out-Null
        }),
        1,
        0
    )
    $TopGrid.Controls.Add(
        (New-SetupCard -TitleKey "choose_data_folder" -CopyKey "data_folder_copy" -ActionKey "open_data_backups" -Icon ([System.Drawing.SystemIcons]::Shield) -Action {
            Start-YggdrasilAction -Action "start-app" -OpenPath "/data-governance"
        }),
        2,
        0
    )
    $DataCard = New-SetupCard -TitleKey "connect_ai_service" -CopyKey "connect_ai_copy" -ActionKey "open_settings" -Icon ([System.Drawing.SystemIcons]::Question) -Action {
        Start-YggdrasilAction -Action "open-settings"
    }
    $DataCard.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 12)
    $TopGrid.Controls.Add($DataCard, 3, 0)
    $Layout.Controls.Add($TopGrid, 0, 0)

    $BottomGrid = New-Object System.Windows.Forms.TableLayoutPanel
    $BottomGrid.Dock = [System.Windows.Forms.DockStyle]::Fill
    $BottomGrid.ColumnCount = 3
    $BottomGrid.RowCount = 1
    foreach ($Index in 1..3) {
        $BottomGrid.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 33.333))) | Out-Null
    }
    $BottomGrid.Controls.Add((New-SetupCatalogCard), 0, 0)
    $BottomGrid.Controls.Add((New-SetupShortcutsCard), 1, 0)
    $BottomGrid.Controls.Add((New-SetupCompleteCard), 2, 0)
    $Layout.Controls.Add($BottomGrid, 0, 1)

    $ResizeHandler = {
        $Layout.Width = [Math]::Max(900, $View.ClientSize.Width - 18)
    }.GetNewClosure()
    $View.Add_Resize($ResizeHandler)
    return $View
}

function Show-DailyView {
    $script:SetupView.Visible = $false
    $script:DailyView.Visible = $true
    $script:DailyView.BringToFront()
    Update-WindowText
}

function Show-SetupView {
    $script:DailyView.Visible = $false
    $script:SetupView.Visible = $true
    $script:SetupView.BringToFront()
    Update-WindowText
}

$script:CurrentLanguage = Resolve-UiLanguage

if (-not (Test-Path $DesktopScript)) {
    throw "Missing desktop controller: $DesktopScript"
}

$script:Form = New-Object System.Windows.Forms.Form
$script:Form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$script:Form.ClientSize = New-Object System.Drawing.Size(1080, 760)
$script:Form.MinimumSize = New-Object System.Drawing.Size(980, 680)
$script:Form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$script:Form.BackColor = $Colors.Background
$script:Form.Padding = New-Object System.Windows.Forms.Padding(18)
$script:Form.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$MainWindow = New-Object System.Windows.Forms.Panel
$MainWindow.Dock = [System.Windows.Forms.DockStyle]::Fill
$MainWindow.BackColor = $Colors.Surface
$MainWindow.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$script:Form.Controls.Add($MainWindow)

$Header = New-Object System.Windows.Forms.Panel
$Header.Dock = [System.Windows.Forms.DockStyle]::Top
$Header.Height = 54
$Header.BackColor = $Colors.SurfaceLow
$MainWindow.Controls.Add($Header)

$ContentHost = New-Object System.Windows.Forms.Panel
$ContentHost.Dock = [System.Windows.Forms.DockStyle]::Fill
$ContentHost.BackColor = $Colors.Surface
$MainWindow.Controls.Add($ContentHost)

$BrandIcon = New-SystemIcon -Icon ([System.Drawing.SystemIcons]::Shield) -Size 24
$BrandIcon.Location = New-Object System.Drawing.Point(18, 15)
$Header.Controls.Add($BrandIcon)

$script:HeaderTitle = New-Object System.Windows.Forms.Label
$script:HeaderTitle.AutoSize = $true
$script:HeaderTitle.Location = New-Object System.Drawing.Point(50, 17)
$script:HeaderTitle.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$script:HeaderTitle.ForeColor = $Colors.Primary
$Header.Controls.Add($script:HeaderTitle)

$script:ModeButton = New-ActionButton -Key "setup" -Action {
    if ($script:SetupView.Visible) {
        Show-DailyView
    }
    else {
        Show-SetupView
    }
}
$script:ModeButton.Size = New-Object System.Drawing.Size(72, 28)
$script:ModeButton.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
$Header.Controls.Add($script:ModeButton)

$script:LanguageEnglishButton = New-Object System.Windows.Forms.Button
$script:LanguageEnglishButton.Text = "EN"
$script:LanguageEnglishButton.Size = New-Object System.Drawing.Size(38, 28)
$script:LanguageEnglishButton.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$script:LanguageEnglishButton.FlatAppearance.BorderColor = $Colors.Outline
$script:LanguageEnglishButton.Font = New-Object System.Drawing.Font("Segoe UI", 8, [System.Drawing.FontStyle]::Bold)
$script:LanguageEnglishButton.Cursor = [System.Windows.Forms.Cursors]::Hand
$script:LanguageEnglishButton.UseVisualStyleBackColor = $false
$script:LanguageEnglishButton.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
$script:LanguageEnglishButton.Add_Click({ Set-UiLanguage -Value "en" })
$Header.Controls.Add($script:LanguageEnglishButton)

$script:LanguageChineseButton = New-Object System.Windows.Forms.Button
$script:LanguageChineseButton.Text = "中文"
$script:LanguageChineseButton.Size = New-Object System.Drawing.Size(48, 28)
$script:LanguageChineseButton.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$script:LanguageChineseButton.FlatAppearance.BorderColor = $Colors.Outline
$script:LanguageChineseButton.Font = New-Object System.Drawing.Font("Segoe UI", 8, [System.Drawing.FontStyle]::Bold)
$script:LanguageChineseButton.Cursor = [System.Windows.Forms.Cursors]::Hand
$script:LanguageChineseButton.UseVisualStyleBackColor = $false
$script:LanguageChineseButton.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
$script:LanguageChineseButton.Add_Click({ Set-UiLanguage -Value "zh-CN" })
$Header.Controls.Add($script:LanguageChineseButton)

$MinimizeButton = New-Object System.Windows.Forms.Button
$MinimizeButton.Text = "–"
$MinimizeButton.Size = New-Object System.Drawing.Size(30, 28)
$MinimizeButton.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$MinimizeButton.FlatAppearance.BorderSize = 0
$MinimizeButton.BackColor = $Colors.SurfaceLow
$MinimizeButton.ForeColor = $Colors.Muted
$MinimizeButton.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$MinimizeButton.Cursor = [System.Windows.Forms.Cursors]::Hand
$MinimizeButton.UseVisualStyleBackColor = $false
$MinimizeButton.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
$MinimizeButton.Add_Click({ $script:Form.WindowState = [System.Windows.Forms.FormWindowState]::Minimized })
$Header.Controls.Add($MinimizeButton)

$CloseButton = New-Object System.Windows.Forms.Button
$CloseButton.Text = "×"
$CloseButton.Size = New-Object System.Drawing.Size(30, 28)
$CloseButton.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$CloseButton.FlatAppearance.BorderSize = 0
$CloseButton.FlatAppearance.MouseOverBackColor = $Colors.Error
$CloseButton.BackColor = $Colors.SurfaceLow
$CloseButton.ForeColor = $Colors.Muted
$CloseButton.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$CloseButton.Cursor = [System.Windows.Forms.Cursors]::Hand
$CloseButton.UseVisualStyleBackColor = $false
$CloseButton.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
$CloseButton.Add_Click({ $script:Form.Close() })
$Header.Controls.Add($CloseButton)

$Header.Add_Resize({
    $CloseButton.Location = New-Object System.Drawing.Point($Header.ClientSize.Width - 40, 13)
    $MinimizeButton.Location = New-Object System.Drawing.Point($Header.ClientSize.Width - 72, 13)
    $script:LanguageChineseButton.Location = New-Object System.Drawing.Point($Header.ClientSize.Width - 130, 13)
    $script:LanguageEnglishButton.Location = New-Object System.Drawing.Point($Header.ClientSize.Width - 172, 13)
    $script:ModeButton.Location = New-Object System.Drawing.Point($Header.ClientSize.Width - 252, 13)
})

$Header.Add_MouseDown({
    param($Sender, $EventArgs)
    if ($EventArgs.Button -eq [System.Windows.Forms.MouseButtons]::Left) {
        [YggdrasilLauncherNative]::ReleaseCapture() | Out-Null
        [YggdrasilLauncherNative]::SendMessage($script:Form.Handle, 0xA1, [IntPtr]2, [IntPtr]::Zero) | Out-Null
    }
})

$ViewHost = New-Object System.Windows.Forms.Panel
$ViewHost.Dock = [System.Windows.Forms.DockStyle]::Fill
$ContentHost.Controls.Add($ViewHost)

$script:DailyView = New-DailyView
$script:SetupView = New-SetupView
$ViewHost.Controls.Add($script:DailyView)
$ViewHost.Controls.Add($script:SetupView)

$script:HealthDetail = $null
if ($Setup) {
    Show-SetupView
}
else {
    Show-DailyView
}
Update-LocalizedControls

$HealthTimer = New-Object System.Windows.Forms.Timer
$HealthTimer.Interval = 30000
$HealthTimer.Add_Tick({ Refresh-LauncherHealth })
$script:Form.Add_Shown({
    Refresh-LauncherHealth
    $HealthTimer.Start()
})
$script:Form.Add_FormClosed({ $HealthTimer.Stop() })

[void]$script:Form.ShowDialog()
