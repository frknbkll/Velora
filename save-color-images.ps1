Add-Type -AssemblyName System.Drawing
$workspace = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$entries = Get-Content -LiteralPath (Join-Path $workspace 'generated-color-files.json') -Raw | ConvertFrom-Json
$jpegCodec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object MimeType -eq 'image/jpeg'
$parameters = [System.Drawing.Imaging.EncoderParameters]::new(1)
$parameters.Param[0] = [System.Drawing.Imaging.EncoderParameter]::new([System.Drawing.Imaging.Encoder]::Quality, [long]90)
foreach ($entry in $entries) {
    $destination = Join-Path $workspace $entry.destination
    if (Test-Path -LiteralPath $destination) { continue }
    $original = [System.Drawing.Image]::FromFile($entry.source)
    try {
        $width = 768
        $height = [int][Math]::Round($original.Height * $width / $original.Width)
        $bitmap = [System.Drawing.Bitmap]::new($width, $height)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.DrawImage($original, 0, 0, $width, $height)
            $bitmap.Save($destination, $jpegCodec, $parameters)
        } finally { $graphics.Dispose(); $bitmap.Dispose() }
    } finally { $original.Dispose() }
}
$parameters.Dispose()
Write-Output ('Saved {0} optimized color photos' -f $entries.Count)
