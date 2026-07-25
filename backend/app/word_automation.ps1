param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$WdCollapseEnd = 0
$WdContentControlRichText = 0
$WdContentControlText = 1
$DefaultWorkmodeStyle = "gb-t-7714-2015-numeric"

function Write-WorkmodeResult {
    param([hashtable]$Value)
    $Value | ConvertTo-Json -Depth 8 -Compress | Set-Content -LiteralPath $OutputPath -Encoding UTF8
}

function Get-WorkmodeDocumentId {
    param($Document)
    if ([string]$Document.Path) {
        return [string]$Document.FullName
    }
    return "unsaved::$([string]$Document.Name)"
}

function Get-WorkmodeDocumentList {
    param($Word)
    $activeId = $null
    if ($null -ne $Word.ActiveDocument) {
        $activeId = Get-WorkmodeDocumentId $Word.ActiveDocument
    }
    $documents = New-Object System.Collections.Generic.List[object]
    for ($index = 1; $index -le $Word.Documents.Count; $index++) {
        $document = $Word.Documents.Item($index)
        $id = Get-WorkmodeDocumentId $document
        $fullPath = if ([string]$document.Path) { [string]$document.FullName } else { $null }
        $documents.Add([pscustomobject]@{
            id = $id
            name = [string]$document.Name
            full_path = $fullPath
            active = ($id -eq $activeId)
        })
    }
    return [pscustomobject]@{
        Documents = $documents.ToArray()
        ActiveDocumentId = $activeId
    }
}

function Decode-WorkmodePayload {
    param([string]$Encoded)
    $base64 = $Encoded.Replace("-", "+").Replace("_", "/")
    switch ($base64.Length % 4) {
        2 { $base64 += "==" }
        3 { $base64 += "=" }
    }
    $json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($base64))
    return $json | ConvertFrom-Json
}

function Get-WorkmodeStyle {
    param($Document)
    try {
        $style = [string]$Document.Variables.Item("WORKMODE_CITATION_STYLE").Value
        if ($style.Trim()) { return $style }
    } catch {
    }
    return $DefaultWorkmodeStyle
}

function Set-WorkmodeStyle {
    param($Document, [string]$StyleId)
    try {
        $Document.Variables.Item("WORKMODE_CITATION_STYLE").Value = $StyleId
    } catch {
        $Document.Variables.Add("WORKMODE_CITATION_STYLE", $StyleId) | Out-Null
    }
}

function Clean-Doi {
    param($Value)
    $doi = [string]$Value
    $doi = $doi.Trim()
    foreach ($prefix in @("https://doi.org/", "http://doi.org/", "doi:")) {
        if ($doi.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            return $doi.Substring($prefix.Length).Trim()
        }
    }
    return $doi
}

function Format-WorkmodeReference {
    param(
        [int]$Number,
        $Metadata
    )
    $parts = New-Object System.Collections.Generic.List[string]
    $authors = [string]$Metadata.authors
    $title = [string]$Metadata.title
    $journal = [string]$Metadata.journal
    $date = if ($Metadata.publication_date) { [string]$Metadata.publication_date } else { [string]$Metadata.year }
    $doi = Clean-Doi $Metadata.doi

    if ($authors.Trim()) { $parts.Add("$($authors.Trim()).") }
    if ($title.Trim()) { $parts.Add("$($title.Trim()).") }
    if ($journal.Trim() -and $date.Trim()) {
        $parts.Add("$($journal.Trim()), $($date.Trim()).")
    } elseif ($journal.Trim()) {
        $parts.Add("$($journal.Trim()).")
    } elseif ($date.Trim()) {
        $parts.Add("$($date.Trim()).")
    }
    if ($doi) { $parts.Add("DOI: $doi.") }
    if ($parts.Count -eq 0) { $parts.Add("Untitled reference.") }
    return "[$Number] $($parts -join ' ')"
}

function Read-WorkmodeControls {
    param($Document)
    $citations = New-Object System.Collections.Generic.List[object]
    $bibliographies = New-Object System.Collections.Generic.List[object]
    $referencedVariables = @{}
    for ($index = 1; $index -le $Document.ContentControls.Count; $index++) {
        $control = $Document.ContentControls.Item($index)
        $tag = [string]$control.Tag
        if ($tag -match "^workmode-citation:([a-f0-9]{32})$") {
            $variableName = "WORKMODE_CITATION_DATA_$($Matches[1])"
            $referencedVariables[$variableName] = $true
            try {
                $encoded = [string]$Document.Variables.Item($variableName).Value
                $payload = Decode-WorkmodePayload $encoded
                if (
                    ($payload.schema -eq "workmode-citation/v1" -and $payload.paper_id) -or
                    ($payload.schema -eq "workmode-citation/v2" -and $payload.items.Count -gt 0)
                ) {
                    $citations.Add([pscustomobject]@{ Control = $control; Payload = $payload })
                }
            } catch {
                # A damaged control is left untouched so the document remains recoverable.
            }
        } elseif ($tag -match "^workmode-bibliography:([a-f0-9]{32})$") {
            $bibliographies.Add($control)
        }
    }
    return [pscustomobject]@{
        Citations = @($citations | Sort-Object { $_.Control.Range.Start })
        Bibliographies = $bibliographies
        ReferencedVariables = $referencedVariables
    }
}

function Update-WorkmodeDocument {
    param($Document)
    $found = Read-WorkmodeControls $Document
    $numbers = @{}
    $metadataByNumber = @{}
    $nextNumber = 1

    foreach ($citation in $found.Citations) {
        $items = if ($citation.Payload.schema -eq "workmode-citation/v2") {
            @($citation.Payload.items)
        } else {
            @($citation.Payload)
        }
        $citationNumbers = New-Object System.Collections.Generic.List[int]
        foreach ($item in $items) {
            $key = "$($item.project_slug)::$($item.paper_id)"
            if (-not $numbers.ContainsKey($key)) {
                $numbers[$key] = $nextNumber
                $metadataByNumber[$nextNumber] = $item.metadata
                $nextNumber++
            }
            $citationNumbers.Add([int]$numbers[$key])
        }
        $citation.Control.Range.Text = "[$($citationNumbers -join ',')]"
    }

    $references = New-Object System.Collections.Generic.List[string]
    for ($number = 1; $number -lt $nextNumber; $number++) {
        $references.Add((Format-WorkmodeReference $number $metadataByNumber[$number]))
    }
    $bibliographyText = $references -join [char]11
    foreach ($bibliography in $found.Bibliographies) {
        $bibliography.Range.Text = $bibliographyText
    }
    for ($index = $Document.Variables.Count; $index -ge 1; $index--) {
        $variable = $Document.Variables.Item($index)
        $name = [string]$variable.Name
        if (
            $name.StartsWith("WORKMODE_CITATION_DATA_") -and
            -not $found.ReferencedVariables.ContainsKey($name)
        ) {
            $variable.Delete()
        }
    }
    return [pscustomobject]@{
        CitationCount = $found.Citations.Count
        ReferenceCount = $references.Count
        BibliographyCount = $found.Bibliographies.Count
    }
}

function Get-WorkmodeInspection {
    param($Document)
    $found = Read-WorkmodeControls $Document
    $groups = New-Object System.Collections.Generic.List[object]
    foreach ($citation in $found.Citations) {
        $tag = [string]$citation.Control.Tag
        $instanceId = $tag.Substring("workmode-citation:".Length)
        $variableName = "WORKMODE_CITATION_DATA_$instanceId"
        $groups.Add([pscustomobject]@{
            instance_id = $instanceId
            field_payload = [string]$Document.Variables.Item($variableName).Value
            text = [string]$citation.Control.Range.Text
        })
    }
    $endNoteCitationCount = 0
    $endNoteBibliographyCount = 0
    for ($index = 1; $index -le $Document.Fields.Count; $index++) {
        $code = [string]$Document.Fields.Item($index).Code.Text
        if ($code -match "ADDIN\s+EN\.CITE") {
            $endNoteCitationCount++
        } elseif ($code -match "ADDIN\s+EN\.REFLIST") {
            $endNoteBibliographyCount++
        }
    }
    return [pscustomobject]@{
        Groups = $groups.ToArray()
        CitationCount = $found.Citations.Count
        BibliographyCount = $found.Bibliographies.Count
        StyleId = Get-WorkmodeStyle $Document
        EndNoteCitationCount = $endNoteCitationCount
        EndNoteBibliographyCount = $endNoteBibliographyCount
    }
}

try {
    $request = Get-Content -LiteralPath $InputPath -Raw -Encoding UTF8 | ConvertFrom-Json
    try {
        $word = [Runtime.InteropServices.Marshal]::GetActiveObject("Word.Application")
    } catch {
        if ($request.action -eq "list_documents") {
            Write-WorkmodeResult @{
                ok = $true
                documents = @()
                active_document_id = $null
            }
            exit 0
        }
        throw "WORD_NOT_RUNNING"
    }

    if ($request.action -eq "list_documents") {
        $listed = Get-WorkmodeDocumentList $word
        Write-WorkmodeResult @{
            ok = $true
            documents = $listed.Documents
            active_document_id = $listed.ActiveDocumentId
        }
        exit 0
    }

    $document = $null
    if ($request.document_id) {
        $targetId = [string]$request.document_id
        for ($index = 1; $index -le $word.Documents.Count; $index++) {
            $candidate = $word.Documents.Item($index)
            if ((Get-WorkmodeDocumentId $candidate) -eq $targetId) {
                $document = $candidate
                break
            }
        }
        if ($null -eq $document) {
            throw "WORD_DOCUMENT_NOT_FOUND"
        }
        $document.Activate()
    } else {
        $document = $word.ActiveDocument
        if ($null -eq $document) {
            throw "WORD_NO_DOCUMENT"
        }
    }

    if ($request.action -eq "inspect_document") {
        $inspection = Get-WorkmodeInspection $document
        Write-WorkmodeResult @{
            ok = $true
            document_id = Get-WorkmodeDocumentId $document
            document_name = [string]$document.Name
            style_id = $inspection.StyleId
            citation_count = $inspection.CitationCount
            bibliography_count = $inspection.BibliographyCount
            citation_groups = $inspection.Groups
            endnote_citation_count = $inspection.EndNoteCitationCount
            endnote_bibliography_count = $inspection.EndNoteBibliographyCount
        }
        exit 0
    } elseif ($request.action -eq "apply_formatting") {
        $found = Read-WorkmodeControls $document
        foreach ($citation in $found.Citations) {
            $tag = [string]$citation.Control.Tag
            $instanceId = $tag.Substring("workmode-citation:".Length)
            $property = $request.citation_texts.PSObject.Properties[$instanceId]
            if ($null -ne $property) {
                $citation.Control.Range.Text = [string]$property.Value
            }
        }
        $bibliographyEntries = @($request.bibliography_entries)
        if ($bibliographyEntries.Count -eq 0) {
            for ($index = $found.Bibliographies.Count - 1; $index -ge 0; $index--) {
                $found.Bibliographies[$index].Delete($true)
            }
        } else {
            $bibliographyText = $bibliographyEntries -join [char]11
            foreach ($bibliography in $found.Bibliographies) {
                $bibliography.Range.Text = $bibliographyText
            }
        }
        Set-WorkmodeStyle $document ([string]$request.style_id)
    } elseif ($request.action -eq "update_citation") {
        if (-not $request.instance_id -or -not $request.field_payload) {
            throw "WORD_MISSING_CITATION"
        }
        $variableName = "WORKMODE_CITATION_DATA_$([string]$request.instance_id)"
        try {
            $document.Variables.Item($variableName).Value = [string]$request.field_payload
        } catch {
            throw "WORD_CITATION_NOT_FOUND"
        }
    } elseif ($request.action -eq "remove_citation") {
        if (-not $request.instance_id) {
            throw "WORD_CITATION_NOT_FOUND"
        }
        $targetTag = "workmode-citation:$([string]$request.instance_id)"
        $removed = $false
        for ($index = $document.ContentControls.Count; $index -ge 1; $index--) {
            $control = $document.ContentControls.Item($index)
            if ([string]$control.Tag -eq $targetTag) {
                $control.Delete($true)
                $removed = $true
                break
            }
        }
        if (-not $removed) {
            throw "WORD_CITATION_NOT_FOUND"
        }
        try {
            $document.Variables.Item("WORKMODE_CITATION_DATA_$([string]$request.instance_id)").Delete()
        } catch {
        }
    } elseif ($request.action -eq "insert_citation") {
        if (-not $request.field_payload) {
            throw "WORD_MISSING_CITATION"
        }
        $instanceId = [Guid]::NewGuid().ToString("N")
        $document.Variables.Add(
            "WORKMODE_CITATION_DATA_$instanceId",
            [string]$request.field_payload
        ) | Out-Null
        $range = $word.Selection.Range
        $range.Collapse($WdCollapseEnd)
        $control = $document.ContentControls.Add($WdContentControlText, $range)
        $control.Tag = "workmode-citation:$instanceId"
        $control.Title = "Workmode citation"
        $control.Range.Text = "[?]"
        $afterStart = $control.Range.End + 1
        $afterRange = $document.Range($afterStart, $afterStart)
        $afterRange.InsertAfter(" ")
        $word.Selection.SetRange($afterStart + 1, $afterStart + 1)
    } elseif ($request.action -eq "insert_bibliography") {
        $existing = Read-WorkmodeControls $document
        if ($existing.Citations.Count -eq 0) {
            throw "WORD_NO_CITATIONS"
        }
        if ($existing.Bibliographies.Count -eq 0) {
            $instanceId = [Guid]::NewGuid().ToString("N")
            $range = $word.Selection.Range
            $range.Collapse($WdCollapseEnd)
            $control = $document.ContentControls.Add($WdContentControlRichText, $range)
            $control.Tag = "workmode-bibliography:$instanceId"
            $control.Title = "Workmode bibliography"
            $control.Range.Text = "Updating bibliography..."
        }
    } else {
        throw "WORD_UNSUPPORTED_ACTION"
    }

    $updated = if ($request.action -eq "apply_formatting") {
        $found = Read-WorkmodeControls $document
        [pscustomobject]@{
            CitationCount = $found.Citations.Count
            ReferenceCount = $bibliographyEntries.Count
            BibliographyCount = $found.Bibliographies.Count
        }
    } else {
        Update-WorkmodeDocument $document
    }
    $document.Saved = $false
    Write-WorkmodeResult @{
        ok = $true
        citation_count = $updated.CitationCount
        reference_count = $updated.ReferenceCount
        bibliography_count = $updated.BibliographyCount
        document_id = Get-WorkmodeDocumentId $document
        document_name = [string]$document.Name
    }
} catch {
    Write-WorkmodeResult @{ ok = $false; error = $_.Exception.Message }
    exit 1
}
