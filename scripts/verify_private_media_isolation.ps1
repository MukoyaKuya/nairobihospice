param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,
    [Parameter(Mandatory = $true)]
    [string]$KnownPrivatePath
)

$ErrorActionPreference = 'Stop'
$uri = '{0}/{1}' -f $BaseUrl.TrimEnd('/'), $KnownPrivatePath.TrimStart('/')
$response = Invoke-WebRequest -Uri $uri -Method Get -MaximumRedirection 0 -SkipHttpErrorCheck

if ($response.StatusCode -notin @(403, 404)) {
    throw "Private media isolation failed: $uri returned HTTP $($response.StatusCode); expected 403 or 404."
}

Write-Output "Private media isolation passed: $uri returned HTTP $($response.StatusCode)."
