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

function Write-WorkmodeResult {
    param([hashtable]$Value)
    $Value | ConvertTo-Json -Depth 8 -Compress | Set-Content -LiteralPath $OutputPath -Encoding UTF8
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
                if ($payload.schema -eq "workmode-citation/v1" -and $payload.paper_id) {
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
        $key = "$($citation.Payload.project_slug)::$($citation.Payload.paper_id)"
        if (-not $numbers.ContainsKey($key)) {
            $numbers[$key] = $nextNumber
            $metadataByNumber[$nextNumber] = $citation.Payload.metadata
            $nextNumber++
        }
        $citation.Control.Range.Text = "[$($numbers[$key])]"
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

try {
    $request = Get-Content -LiteralPath $InputPath -Raw -Encoding UTF8 | ConvertFrom-Json
    try {
        $word = [Runtime.InteropServices.Marshal]::GetActiveObject("Word.Application")
    } catch {
        throw "WORD_NOT_RUNNING"
    }
    if ($null -eq $word.ActiveDocument) {
        throw "WORD_NO_DOCUMENT"
    }
    $document = $word.ActiveDocument

    if ($request.action -eq "insert_citation") {
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

    $updated = Update-WorkmodeDocument $document
    $document.Saved = $false
    Write-WorkmodeResult @{
        ok = $true
        citation_count = $updated.CitationCount
        reference_count = $updated.ReferenceCount
        bibliography_count = $updated.BibliographyCount
    }
} catch {
    Write-WorkmodeResult @{ ok = $false; error = $_.Exception.Message }
    exit 1
}
