# Baja LÖVE 11.5 portable a tools/love (cliente propio AOF).
$ErrorActionPreference = 'Stop'
$dest = Join-Path $PSScriptRoot 'love'
$zip = Join-Path $env:TEMP 'love-11.5-win64.zip'
$url = 'https://github.com/love2d/love/releases/download/11.5/love-11.5-win64.zip'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
if (-not (Test-Path $zip)) {
  Write-Host "Descargando $url ..."
  Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
}
Expand-Archive -Path $zip -DestinationPath $dest -Force
$lovec = Get-ChildItem $dest -Recurse -Filter 'lovec.exe' | Select-Object -First 1
if (-not $lovec) { throw 'no aparecio lovec.exe' }
Write-Host "Listo:" $lovec.FullName
& $lovec.FullName --version
