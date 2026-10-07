$ErrorActionPreference = "Stop"

function Write-Result {
    param([hashtable]$Value)
    [pscustomobject]$Value | ConvertTo-Json -Compress
}

function Get-AutomationStateHash {
    param([object[]]$Windows)
    $builder = New-Object System.Text.StringBuilder
    $sha = $null
    try {
        $count = 0
        foreach ($window in $Windows) {
            $elements = $window.FindAll(
                [System.Windows.Automation.TreeScope]::Descendants,
                [System.Windows.Automation.Condition]::TrueCondition
            )
            foreach ($element in $elements) {
                if ($count -ge 600) { break }
                try {
                    [void]$builder.Append($element.Current.ControlType.ProgrammaticName)
                    [void]$builder.Append('|')
                    [void]$builder.Append(([string]$element.Current.AutomationId).Substring(0, [Math]::Min(160, ([string]$element.Current.AutomationId).Length)))
                    [void]$builder.Append('|')
                    [void]$builder.Append(([string]$element.Current.Name).Substring(0, [Math]::Min(160, ([string]$element.Current.Name).Length)))
                    [void]$builder.Append('|')
                    [void]$builder.Append($element.Current.IsEnabled)
                    [void]$builder.Append('|')
                    [void]$builder.Append($element.Current.IsOffscreen)
                    [void]$builder.AppendLine()
                    $count += 1
                }
                catch {
                    continue
                }
            }
            if ($count -ge 600) { break }
        }
        $sha = [System.Security.Cryptography.SHA256]::Create()
        return [Convert]::ToHexString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($builder.ToString())))
    }
    catch {
        return $null
    }
    finally {
        if ($null -ne $sha) { $sha.Dispose() }
    }
}

try {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw) -or $raw.Length -gt 4096) {
        throw "The UI Automation request is empty or too large."
    }
    $payload = $raw | ConvertFrom-Json
    $expected = @("application_name", "control_name", "process_names")
    $actual = @($payload.PSObject.Properties.Name | Sort-Object)
    if (@(Compare-Object ($expected | Sort-Object) $actual).Count -ne 0) {
        throw "The UI Automation request schema is invalid."
    }
    $applicationName = [string]$payload.application_name
    $controlName = [string]$payload.control_name
    $processNames = @($payload.process_names)
    if ($applicationName.Length -lt 1 -or $applicationName.Length -gt 120 -or
        $controlName.Length -lt 1 -or $controlName.Length -gt 120 -or
        $processNames.Count -lt 1 -or $processNames.Count -gt 8) {
        throw "The UI Automation request values are outside bounded limits."
    }
    $blockedProcesses = @("cmd.exe", "credentialui.exe", "lsass.exe", "powershell.exe", "pwsh.exe", "regedit.exe", "securityhealthsystray.exe", "taskmgr.exe", "windowsterminal.exe")
    $validatedProcessNames = @()
    foreach ($name in $processNames) {
        $text = ([string]$name).ToLowerInvariant()
        if ($text -notmatch '^[A-Za-z0-9._-]{1,80}$' -or $blockedProcesses -contains $text) {
            throw "A process identity is invalid or protected."
        }
        $validatedProcessNames += $text
    }

    $processIds = @()
    foreach ($name in $validatedProcessNames) {
        $baseName = [IO.Path]::GetFileNameWithoutExtension($name)
        $processIds += @(Get-Process -Name $baseName -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    }
    $processIds = @($processIds | Sort-Object -Unique)
    if ($processIds.Count -eq 0) {
        throw "$applicationName is not running."
    }

    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $topLevel = $root.FindAll(
        [System.Windows.Automation.TreeScope]::Children,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    $windows = @($topLevel | Where-Object { $processIds -contains $_.Current.ProcessId })
    if ($windows.Count -eq 0) {
        throw "No visible $applicationName window is available."
    }
    $matches = @()
    $nameCondition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::NameProperty,
        $controlName,
        [System.Windows.Automation.PropertyConditionFlags]::IgnoreCase
    )
    foreach ($window in $windows) {
        $found = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $nameCondition)
        foreach ($control in $found) {
            $typeName = $control.Current.ControlType.ProgrammaticName
            if ($typeName -in @("ControlType.Button", "ControlType.CheckBox", "ControlType.Hyperlink", "ControlType.MenuItem", "ControlType.RadioButton", "ControlType.TabItem") -and
                $control.Current.IsEnabled -and -not $control.Current.IsOffscreen -and -not $control.Current.IsPassword) {
                $matches += [pscustomobject]@{ Window = $window; Control = $control; Type = $typeName }
            }
        }
    }
    if ($matches.Count -ne 1) {
        throw "The exact enabled control is unavailable or ambiguous."
    }

    $selected = $matches[0]
    $target = $selected.Control
    $window = $selected.Window
    $windowTitleBefore = $window.Current.Name
    $windowCountBefore = $windows.Count
    $automationHashBefore = Get-AutomationStateHash -Windows $windows
    $pattern = $null
    $patternName = $null
    $stateBefore = $null
    $stateAfter = $null
    if ($target.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern, [ref]$pattern)) {
        $patternName = "TogglePattern"
        $stateBefore = $pattern.Current.ToggleState.ToString()
        $pattern.Toggle()
    }
    elseif ($target.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern)) {
        $patternName = "SelectionItemPattern"
        $stateBefore = $pattern.Current.IsSelected.ToString()
        $pattern.Select()
    }
    elseif ($target.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern, [ref]$pattern)) {
        $patternName = "ExpandCollapsePattern"
        $stateBefore = $pattern.Current.ExpandCollapseState.ToString()
        if ($stateBefore -eq "Collapsed" -or $stateBefore -eq "PartiallyExpanded") {
            $pattern.Expand()
        }
        else {
            $pattern.Collapse()
        }
    }
    elseif ($target.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
        $patternName = "InvokePattern"
        $pattern.Invoke()
    }
    else {
        throw "The exact control does not expose an approved invocation pattern."
    }

    Start-Sleep -Milliseconds 650
    if ($patternName -eq "TogglePattern") {
        try { $stateAfter = $pattern.Current.ToggleState.ToString() } catch { $stateAfter = "unavailable" }
    }
    elseif ($patternName -eq "SelectionItemPattern") {
        try { $stateAfter = $pattern.Current.IsSelected.ToString() } catch { $stateAfter = "unavailable" }
    }
    elseif ($patternName -eq "ExpandCollapsePattern") {
        try { $stateAfter = $pattern.Current.ExpandCollapseState.ToString() } catch { $stateAfter = "unavailable" }
    }
    $afterTopLevel = $root.FindAll(
        [System.Windows.Automation.TreeScope]::Children,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    $windowsAfter = @($afterTopLevel | Where-Object { $processIds -contains $_.Current.ProcessId })
    $automationHashAfter = Get-AutomationStateHash -Windows $windowsAfter
    $windowTitleAfter = if ($windowsAfter.Count -gt 0) { $windowsAfter[0].Current.Name } else { "closed" }
    $stateChanged = $null -ne $stateBefore -and $stateBefore -ne $stateAfter
    $treeChanged = $null -ne $automationHashBefore -and $null -ne $automationHashAfter -and $automationHashBefore -ne $automationHashAfter
    $windowChanged = $windowsAfter.Count -ne $windowCountBefore -or $windowTitleBefore -ne $windowTitleAfter
    $observed = $stateChanged -or $treeChanged -or $windowChanged
    $observation = if ($stateChanged) {
        "automation_state_changed"
    }
    elseif ($windowChanged) {
        "application_window_changed"
    }
    elseif ($treeChanged) {
        "automation_tree_changed"
    }
    elseif ($null -eq $automationHashBefore -or $null -eq $automationHashAfter) {
        "automation_probe_unavailable"
    }
    else {
        "no_post_action_change"
    }
    Write-Result @{
        ok = $observed
        invoked = $true
        observed = $observed
        application = $applicationName
        control_type = $selected.Type.Replace("ControlType.", "")
        automation_pattern = $patternName
        observation = $observation
        memory_only_automation_observation = $true
        error = if ($observed) { $null } else { "Windows accepted the invocation but no post-action UI change was observed." }
    }
}
catch {
    Write-Result @{
        ok = $false
        invoked = $false
        observed = $false
        error = $_.Exception.Message
        memory_only_automation_observation = $false
    }
    exit 1
}
