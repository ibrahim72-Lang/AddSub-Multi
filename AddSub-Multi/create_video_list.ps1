Param(
    [Parameter(Mandatory=$true)]
    [string]$InputList,

    [Parameter(Mandatory=$true)]
    [string]$OutputList
)

$videoExts = '.mp4', '.mkv', '.avi'
$videoList = @()

if (Test-Path -LiteralPath $InputList) {
    Get-Content -LiteralPath $InputList | ForEach-Object {
            $path = $_.Trim()
            $path = $path.Trim('"')
            if (-not $path) { continue }
        if (Test-Path -LiteralPath $path -PathType Container) {
            foreach ($ext in $videoExts) {
                $videoList += Get-ChildItem -LiteralPath $path -Recurse -Filter "*$ext" -File -ErrorAction SilentlyContinue
            }
        } elseif (Test-Path -LiteralPath $path -PathType Leaf) {
            $item = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
            if ($item -and $videoExts -contains $item.Extension.ToLowerInvariant()) {
                $videoList += $item
            }
        }
    }
}

$sortedList = $videoList | Sort-Object DirectoryName, CreationTimeUtc -Unique | ForEach-Object { $_.FullName }
if ($null -eq $sortedList) {
    $sortedList = @()
}
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($OutputList, $sortedList, $utf8NoBom)
