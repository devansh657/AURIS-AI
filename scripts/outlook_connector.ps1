$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$outlook = $null
$namespace = $null
$folder = $null
$items = $null
$restricted = $null
$mail = $null

try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) {
        throw "A connector request is required."
    }
    $request = $raw | ConvertFrom-Json
    $mode = [string]$request.mode
    if ($mode -notin @("search_mail", "calendar", "search_contacts", "draft", "send")) {
        throw "Unsupported Outlook connector operation."
    }

    $lastConnectionError = $null
    for ($attempt = 0; $attempt -lt 4 -and $null -eq $outlook; $attempt++) {
        try {
            $outlook = [Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application")
        } catch {
            try {
                $outlook = New-Object -ComObject Outlook.Application
            } catch {
                $lastConnectionError = $_.Exception
                if ($attempt -lt 3) { Start-Sleep -Seconds 2 }
            }
        }
    }
    if ($null -eq $outlook) {
        throw $lastConnectionError
    }
    $namespace = $outlook.GetNamespace("MAPI")
    if ($null -eq $namespace -or $namespace.Stores.Count -lt 1) {
        throw "No authorised classic Outlook mailbox profile is configured."
    }

    if ($mode -eq "search_mail") {
        $query = ([string]$request.query).Trim()
        if ($query.Length -lt 2 -or $query.Length -gt 200) {
            throw "The email search query must contain 2 to 200 characters."
        }
        $limit = [Math]::Max(1, [Math]::Min(20, [int]$request.limit))
        $folder = $namespace.GetDefaultFolder(6)
        $items = $folder.Items
        $items.Sort("[ReceivedTime]", $true)
        $maximum = [Math]::Min(500, $items.Count)
        $matches = [System.Collections.Generic.List[object]]::new()
        for ($index = 1; $index -le $maximum -and $matches.Count -lt $limit; $index++) {
            $item = $items.Item($index)
            try {
                $subject = [string]$item.Subject
                $sender = [string]$item.SenderName
                $senderAddress = [string]$item.SenderEmailAddress
                $body = [string]$item.Body
                $searchable = "$subject`n$sender`n$senderAddress`n$body"
                if ($searchable.IndexOf($query, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
                    continue
                }
                $preview = (($body -replace "\s+", " ").Trim())
                if ($preview.Length -gt 240) {
                    $preview = $preview.Substring(0, 240)
                }
                $matches.Add([pscustomobject]@{
                    subject = $subject
                    sender = $sender
                    sender_address = $senderAddress
                    received_at = ([datetime]$item.ReceivedTime).ToUniversalTime().ToString("o")
                    unread = [bool]$item.UnRead
                    preview = $preview
                })
            } finally {
                if ($null -ne $item) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($item) }
            }
        }
        @{
            ok = $true
            operation = $mode
            scanned = $maximum
            items = @($matches)
        } | ConvertTo-Json -Depth 6 -Compress
    } elseif ($mode -eq "calendar") {
        $days = [Math]::Max(1, [Math]::Min(31, [int]$request.days))
        $limit = [Math]::Max(1, [Math]::Min(50, [int]$request.limit))
        $start = [datetime]::Now
        $finish = $start.AddDays($days)
        $folder = $namespace.GetDefaultFolder(9)
        $items = $folder.Items
        $items.Sort("[Start]")
        $items.IncludeRecurrences = $true
        $filter = "[Start] >= '$($start.ToString("g"))' AND [Start] <= '$($finish.ToString("g"))'"
        $restricted = $items.Restrict($filter)
        $events = [System.Collections.Generic.List[object]]::new()
        $skipped = 0
        $maximum = [Math]::Min($limit, $restricted.Count)
        for ($index = 1; $index -le $maximum; $index++) {
            $item = $restricted.Item($index)
            try {
                if ($null -eq $item) {
                    $skipped++
                    continue
                }
                $eventStart = $item.Start
                $eventEnd = $item.End
                if ($null -eq $eventStart -or $null -eq $eventEnd) {
                    $skipped++
                    continue
                }
                $events.Add([pscustomobject]@{
                    subject = [string]$item.Subject
                    start_at = ([datetime]$eventStart).ToUniversalTime().ToString("o")
                    end_at = ([datetime]$eventEnd).ToUniversalTime().ToString("o")
                    location = [string]$item.Location
                    organizer = [string]$item.Organizer
                    all_day = [bool]$item.AllDayEvent
                    busy_status = [int]$item.BusyStatus
                })
            } catch {
                $skipped++
                continue
            } finally {
                if ($null -ne $item) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($item) }
            }
        }
        @{
            ok = $true
            operation = $mode
            range_start = $start.ToUniversalTime().ToString("o")
            range_end = $finish.ToUniversalTime().ToString("o")
            items = @($events)
            skipped = $skipped
        } | ConvertTo-Json -Depth 6 -Compress
    } elseif ($mode -eq "search_contacts") {
        $query = ([string]$request.query).Trim()
        if ($query.Length -lt 2 -or $query.Length -gt 200) {
            throw "The contact search query must contain 2 to 200 characters."
        }
        $limit = [Math]::Max(1, [Math]::Min(20, [int]$request.limit))
        $folder = $namespace.GetDefaultFolder(10)
        $items = $folder.Items
        $maximum = [Math]::Min(1000, $items.Count)
        $matches = [System.Collections.Generic.List[object]]::new()
        for ($index = 1; $index -le $maximum -and $matches.Count -lt $limit; $index++) {
            $item = $items.Item($index)
            try {
                if ($null -eq $item -or [string]$item.MessageClass -ne "IPM.Contact") {
                    continue
                }
                $name = ([string]$item.FullName).Trim()
                $company = ([string]$item.CompanyName).Trim()
                $email = ([string]$item.Email1Address).Trim()
                $businessPhone = ([string]$item.BusinessTelephoneNumber).Trim()
                $mobilePhone = ([string]$item.MobileTelephoneNumber).Trim()
                $searchable = "$name`n$company`n$email"
                if ($searchable.IndexOf($query, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
                    continue
                }
                $matches.Add([pscustomobject]@{
                    name = $name.Substring(0, [Math]::Min(200, $name.Length))
                    company = $company.Substring(0, [Math]::Min(200, $company.Length))
                    email = $email.Substring(0, [Math]::Min(320, $email.Length))
                    business_phone = $businessPhone.Substring(0, [Math]::Min(80, $businessPhone.Length))
                    mobile_phone = $mobilePhone.Substring(0, [Math]::Min(80, $mobilePhone.Length))
                })
            } catch {
                continue
            } finally {
                if ($null -ne $item) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($item) }
            }
        }
        @{
            ok = $true
            operation = $mode
            scanned = $maximum
            items = @($matches)
        } | ConvertTo-Json -Depth 6 -Compress
    } else {
        $recipient = ([string]$request.recipient).Trim()
        $subject = ([string]$request.subject).Trim()
        $body = [string]$request.body
        if ($recipient -notmatch '^[^\s@]+@[^\s@]+\.[^\s@]+$') {
            throw "An explicit valid recipient email address is required."
        }
        if ($subject.Length -lt 1 -or $subject.Length -gt 200) {
            throw "The email subject must contain 1 to 200 characters."
        }
        if ($body.Length -lt 1 -or $body.Length -gt 5000) {
            throw "The email body must contain 1 to 5000 characters."
        }
        $mail = $outlook.CreateItem(0)
        $mail.To = $recipient
        $mail.Subject = $subject
        $mail.Body = $body
        if ($mode -eq "draft") {
            $mail.Save()
            @{
                ok = $true
                operation = $mode
                recipient = $recipient
                subject = $subject
                entry_id = [string]$mail.EntryID
                sent = $false
            } | ConvertTo-Json -Depth 4 -Compress
        } else {
            $mail.Send()
            @{
                ok = $true
                operation = $mode
                recipient = $recipient
                subject = $subject
                accepted_by_outlook = $true
                sent = $true
            } | ConvertTo-Json -Depth 4 -Compress
        }
    }
} catch {
    @{ ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
    exit 1
} finally {
    foreach ($comObject in @($mail, $restricted, $items, $folder, $namespace, $outlook)) {
        if ($null -ne $comObject -and [Runtime.InteropServices.Marshal]::IsComObject($comObject)) {
            try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($comObject) } catch {}
        }
    }
}
