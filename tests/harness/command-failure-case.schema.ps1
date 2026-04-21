param()

$ErrorActionPreference = 'Stop'

$HarnessRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$SchemaPath = Join-Path $HarnessRoot 'schemas\command-failure-case.schema.json'

$script:Failures = New-Object System.Collections.Generic.List[string]
$script:PassCount = 0

function Assert-True {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) { throw $Message }
}

function Assert-Equal {
  param([object]$Expected, [object]$Actual, [string]$Message)
  if ($Expected -ne $Actual) {
    throw ("{0} (expected: {1}; actual: {2})" -f $Message, $Expected, $Actual)
  }
}

function Assert-ContainsText {
  param([string]$Text, [string]$Expected, [string]$Message)
  if ([string]::IsNullOrWhiteSpace($Text) -or (-not $Text.Contains($Expected))) {
    throw ("{0} (missing: {1})" -f $Message, $Expected)
  }
}

function Run-TestCase {
  param([string]$Name, [scriptblock]$Body)
  try {
    & $Body
    $script:PassCount += 1
    Write-Host ("PASS {0}" -f $Name)
  } catch {
    $script:Failures.Add(("{0}: {1}" -f $Name, $_.Exception.Message)) | Out-Null
    Write-Host ("FAIL {0}" -f $Name)
    Write-Host ("  {0}" -f $_.Exception.Message)
  }
}

function ConvertTo-NormalizedMap {
  param([object]$InputObject)
  if ($null -eq $InputObject) { return $null }
  if ($InputObject -is [System.Collections.IDictionary]) {
    $map = [ordered]@{}
    foreach ($key in $InputObject.Keys) {
      $map[$key] = ConvertTo-NormalizedMap -InputObject $InputObject[$key]
    }
    return $map
  }
  if (($InputObject -is [System.Collections.IEnumerable]) -and -not ($InputObject -is [string])) {
    $items = @()
    foreach ($item in $InputObject) {
      $items += ,(ConvertTo-NormalizedMap -InputObject $item)
    }
    return $items
  }
  if ($InputObject -is [pscustomobject]) {
    $map = [ordered]@{}
    foreach ($prop in $InputObject.PSObject.Properties) {
      $map[$prop.Name] = ConvertTo-NormalizedMap -InputObject $prop.Value
    }
    return $map
  }
  return $InputObject
}

function Read-JsonMap {
  param([string]$PathValue)
  return (ConvertTo-NormalizedMap -InputObject (Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8 | ConvertFrom-Json))
}

function Add-ValidationError {
  param(
    [System.Collections.Generic.List[string]]$Errors,
    [string]$Path,
    [string]$Message
  )
  $Errors.Add(("{0}: {1}" -f $Path, $Message)) | Out-Null
}

function Test-ValueAgainstSchema {
  param(
    [object]$Value,
    [object]$Schema,
    [string]$Path = '$'
  )

  $errors = New-Object System.Collections.Generic.List[string]
  if ($null -eq $Schema) {
    return $errors
  }

  $schemaType = if ($Schema.Contains('type')) { [string]$Schema.type } else { '' }
  switch ($schemaType) {
    'object' {
      if (-not ($Value -is [System.Collections.IDictionary])) {
        Add-ValidationError -Errors $errors -Path $Path -Message 'must be object'
        return $errors
      }

      foreach ($requiredKey in @($Schema.required)) {
        if (-not $Value.Contains($requiredKey)) {
          Add-ValidationError -Errors $errors -Path $Path -Message ('missing required property {0}' -f $requiredKey)
        }
      }

      if ($Schema.Contains('properties')) {
        foreach ($propertyName in $Schema.properties.Keys) {
          if ($Value.Contains($propertyName)) {
            $childPath = ('{0}.{1}' -f $Path, $propertyName)
            foreach ($error in (Test-ValueAgainstSchema -Value $Value[$propertyName] -Schema $Schema.properties[$propertyName] -Path $childPath)) {
              $errors.Add($error) | Out-Null
            }
          }
        }
      }
    }
    'array' {
      if (($null -eq $Value) -or ($Value -is [string]) -or (-not ($Value -is [System.Collections.IEnumerable]))) {
        Add-ValidationError -Errors $errors -Path $Path -Message 'must be array'
        return $errors
      }
      $items = @($Value)
      if ($Schema.Contains('minItems') -and ($items.Count -lt [int]$Schema.minItems)) {
        Add-ValidationError -Errors $errors -Path $Path -Message ("must contain at least {0} item(s)" -f [int]$Schema.minItems)
      }
      if ($Schema.Contains('items')) {
        for ($index = 0; $index -lt $items.Count; $index++) {
          $itemPath = ('{0}[{1}]' -f $Path, $index)
          foreach ($error in (Test-ValueAgainstSchema -Value $items[$index] -Schema $Schema.items -Path $itemPath)) {
            $errors.Add($error) | Out-Null
          }
        }
      }
    }
    'string' {
      if ($Value -isnot [string]) {
        Add-ValidationError -Errors $errors -Path $Path -Message 'must be string'
        return $errors
      }
      if ($Schema.Contains('minLength') -and ($Value.Length -lt [int]$Schema.minLength)) {
        Add-ValidationError -Errors $errors -Path $Path -Message ("must have minLength {0}" -f [int]$Schema.minLength)
      }
      if ($Schema.Contains('pattern') -and (-not [regex]::IsMatch($Value, [string]$Schema.pattern))) {
        Add-ValidationError -Errors $errors -Path $Path -Message ("must match pattern {0}" -f [string]$Schema.pattern)
      }
      if ($Schema.Contains('enum') -and (@($Schema.enum) -notcontains $Value)) {
        Add-ValidationError -Errors $errors -Path $Path -Message ("must be one of: {0}" -f (@($Schema.enum) -join ', '))
      }
    }
    'number' {
      $parsed = 0.0
      if (-not [double]::TryParse([string]$Value, [ref]$parsed)) {
        Add-ValidationError -Errors $errors -Path $Path -Message 'must be number'
        return $errors
      }
      if ($Schema.Contains('minimum') -and ($parsed -lt [double]$Schema.minimum)) {
        Add-ValidationError -Errors $errors -Path $Path -Message ('must be >= {0}' -f [double]$Schema.minimum)
      }
      if ($Schema.Contains('maximum') -and ($parsed -gt [double]$Schema.maximum)) {
        Add-ValidationError -Errors $errors -Path $Path -Message ('must be <= {0}' -f [double]$Schema.maximum)
      }
    }
    'integer' {
      $parsed = 0
      if (-not [int]::TryParse([string]$Value, [ref]$parsed)) {
        Add-ValidationError -Errors $errors -Path $Path -Message 'must be integer'
        return $errors
      }
      if ($Schema.Contains('minimum') -and ($parsed -lt [int]$Schema.minimum)) {
        Add-ValidationError -Errors $errors -Path $Path -Message ('must be >= {0}' -f [int]$Schema.minimum)
      }
    }
  }

  return $errors
}

function Assert-SchemaAccepts {
  param(
    [object]$Schema,
    [object]$Value,
    [string]$Message
  )
  $errors = @(Test-ValueAgainstSchema -Value $Value -Schema $Schema)
  if ($errors.Count -gt 0) {
    throw ("{0} (errors: {1})" -f $Message, ($errors -join ' | '))
  }
}

function Assert-SchemaRejects {
  param(
    [object]$Schema,
    [object]$Value,
    [string]$ExpectedFragment,
    [string]$Message
  )
  $errors = @(Test-ValueAgainstSchema -Value $Value -Schema $Schema)
  if ($errors.Count -eq 0) {
    throw ("{0} (schema unexpectedly accepted value)" -f $Message)
  }
  if (-not (($errors -join ' | ').Contains($ExpectedFragment))) {
    throw ("{0} (errors: {1})" -f $Message, ($errors -join ' | '))
  }
}

function New-ValidCase {
  return [ordered]@{
    schema_version = '1.0'
    case_id = 'CASE-0123456789abcdef'
    signature = ('a' * 64)
    command_signature = 'npm test'
    error_signature = 'command not found'
    command_excerpt = 'npm test'
    error_excerpt = 'command not found'
    scope_kind = 'candidate_global'
    scope_confidence = 0.6
    scope_reason = 'environment issue'
    projects_seen = @('proj-a')
    solution = 'install node'
    stats = [ordered]@{
      hit_count = 0
      verify_count = 1
      incident_count = 1
    }
    created_at = '2026-04-20T10:00:00.0000000+08:00'
    updated_at = '2026-04-20T10:00:00.0000000+08:00'
    last_verified_at = ''
    last_hit_at = ''
  }
}

$schema = Read-JsonMap -PathValue $SchemaPath

Run-TestCase -Name 'Schema contract exposes required command-failure fields' -Body {
  Assert-Equal 'object' ([string]$schema.type) 'schema root must remain object'
  Assert-Equal 'CommandFailureCase' ([string]$schema.title) 'schema title must stay stable'
  Assert-True (@($schema.required) -contains 'schema_version') 'schema must require schema_version'
  Assert-True (@($schema.required) -contains 'scope_kind') 'schema must require scope_kind'
  Assert-True (@($schema.required) -contains 'scope_confidence') 'schema must require scope_confidence'
  Assert-Equal 0 ([int]$schema.properties.scope_confidence.minimum) 'scope_confidence minimum must remain 0'
  Assert-Equal 1 ([int]$schema.properties.scope_confidence.maximum) 'scope_confidence maximum must remain 1'
}

Run-TestCase -Name 'Schema accepts canonical valid case' -Body {
  Assert-SchemaAccepts -Schema $schema -Value (New-ValidCase) -Message 'schema should accept canonical valid case'
}

Run-TestCase -Name 'Schema rejects missing schema_version' -Body {
  $case = New-ValidCase
  $case.Remove('schema_version')
  Assert-SchemaRejects -Schema $schema -Value $case -ExpectedFragment 'schema_version' -Message 'schema should reject missing schema_version'
}

Run-TestCase -Name 'Schema rejects invalid case_id pattern' -Body {
  $case = New-ValidCase
  $case.case_id = 'CASE-invalid'
  Assert-SchemaRejects -Schema $schema -Value $case -ExpectedFragment 'case_id' -Message 'schema should reject invalid case_id'
}

Run-TestCase -Name 'Schema rejects invalid signature pattern' -Body {
  $case = New-ValidCase
  $case.signature = 'xyz'
  Assert-SchemaRejects -Schema $schema -Value $case -ExpectedFragment 'signature' -Message 'schema should reject invalid signature'
}

Run-TestCase -Name 'Schema rejects invalid scope_kind enum' -Body {
  $case = New-ValidCase
  $case.scope_kind = 'workspace'
  Assert-SchemaRejects -Schema $schema -Value $case -ExpectedFragment 'scope_kind' -Message 'schema should reject invalid scope_kind'
}

Run-TestCase -Name 'Schema rejects scope_confidence outside range' -Body {
  $case = New-ValidCase
  $case.scope_confidence = 1.5
  Assert-SchemaRejects -Schema $schema -Value $case -ExpectedFragment 'scope_confidence' -Message 'schema should reject scope_confidence > 1'
}

Run-TestCase -Name 'Schema rejects empty projects_seen' -Body {
  $case = New-ValidCase
  $case.projects_seen = @()
  Assert-SchemaRejects -Schema $schema -Value $case -ExpectedFragment 'projects_seen' -Message 'schema should reject empty projects_seen'
}

Run-TestCase -Name 'Schema rejects negative stats and missing stat fields' -Body {
  $caseWithNegative = New-ValidCase
  $caseWithNegative.stats.hit_count = -1
  Assert-SchemaRejects -Schema $schema -Value $caseWithNegative -ExpectedFragment 'hit_count' -Message 'schema should reject negative hit_count'

  $caseMissingStat = New-ValidCase
  $caseMissingStat.stats.Remove('incident_count')
  Assert-SchemaRejects -Schema $schema -Value $caseMissingStat -ExpectedFragment 'incident_count' -Message 'schema should reject missing incident_count'
}

Write-Host ("TOTAL PASS {0}" -f $script:PassCount)
if ($script:Failures.Count -gt 0) {
  Write-Host ("TOTAL FAIL {0}" -f $script:Failures.Count)
  foreach ($failure in $script:Failures) {
    Write-Host ("  {0}" -f $failure)
  }
  exit 1
}

Write-Host 'ALL TESTS PASSED'
exit 0
