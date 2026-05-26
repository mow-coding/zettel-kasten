param(
    [Parameter(Mandatory = $true)]
    [string] $Site,

    [Parameter(Mandatory = $true)]
    [string] $AccessTokenEnv,

    [Parameter(Mandatory = $true)]
    [string] $TitlePath,

    [Parameter(Mandatory = $true)]
    [string] $ContentPath,

    [string] $Category = "example_owner",

    [ValidateSet("draft", "publish")]
    [string] $Status = "draft",

    [switch] $Approve
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertTo-FormComponent {
    param([AllowNull()][string] $Value)

    if ($null -eq $Value) {
        return ""
    }

    $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $builder = [Text.StringBuilder]::new()

    foreach ($byte in $bytes) {
        $isAlphaNumeric = (
            ($byte -ge 0x30 -and $byte -le 0x39) -or
            ($byte -ge 0x41 -and $byte -le 0x5A) -or
            ($byte -ge 0x61 -and $byte -le 0x7A)
        )
        $isSafeSymbol = $byte -in @(0x2D, 0x2E, 0x5F, 0x7E)

        if ($isAlphaNumeric -or $isSafeSymbol) {
            [void] $builder.Append([char] $byte)
        }
        elseif ($byte -eq 0x20) {
            [void] $builder.Append("+")
        }
        else {
            [void] $builder.Append("%")
            [void] $builder.Append($byte.ToString("X2"))
        }
    }

    $builder.ToString()
}

function ConvertTo-FormBody {
    param([hashtable] $Values)

    $pairs = foreach ($key in $Values.Keys) {
        "{0}={1}" -f (ConvertTo-FormComponent $key), (ConvertTo-FormComponent ([string] $Values[$key]))
    }

    [Text.Encoding]::ASCII.GetBytes(($pairs -join "&"))
}

if (-not (Test-Path -LiteralPath $TitlePath)) {
    throw "TitlePath not found."
}
if (-not (Test-Path -LiteralPath $ContentPath)) {
    throw "ContentPath not found."
}

$title = (Get-Content -LiteralPath $TitlePath -Raw -Encoding UTF8).Trim()
$content = Get-Content -LiteralPath $ContentPath -Raw -Encoding UTF8

$body = @{
    title = $title
    content = $content
    categories = $Category
    status = $Status
    publicize = "false"
    "discussion[comments_open]" = "false"
    "discussion[pings_open]" = "false"
}

$plan = [pscustomobject]@{
    action = "wordpress_projection_publish"
    site = $Site
    title = $title
    category = $Category
    status = $Status
    content_path = $ContentPath
    would_call_provider = [bool] $Approve
    approval_required = -not [bool] $Approve
}

if (-not $Approve) {
    $plan | ConvertTo-Json -Depth 10
    return
}

$accessToken = [Environment]::GetEnvironmentVariable($AccessTokenEnv)
if ([string]::IsNullOrWhiteSpace($accessToken)) {
    throw "Access token environment variable is not set."
}

$uri = "https://public-api.wordpress.com/rest/v1.1/sites/$Site/posts/new/"
$response = Invoke-RestMethod `
    -Method Post `
    -Uri $uri `
    -Headers @{ Authorization = "Bearer $accessToken"; Accept = "application/json" } `
    -ContentType "application/x-www-form-urlencoded; charset=UTF-8" `
    -Body (ConvertTo-FormBody $body)

$response | Select-Object ID, date, status, URL, title | ConvertTo-Json -Depth 10
