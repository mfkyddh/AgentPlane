# Launch Windows Chrome for OpenClaw browser automation and ensure the WSL-visible CDP bridge exists.
# Requires an elevated Windows shell for the portproxy and firewall operations.

$ErrorActionPreference = 'Stop'

$ChromePath = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$ProfileDir = 'C:\Users\Administrator\.codex\openclaw-chrome-profile'
$ChromeDebugPort = 9222
$BridgePort = 9223
$BridgeRuleName = 'OpenClaw Chrome CDP 9223'
$ConnectAddress = '127.0.0.1'

if (-not (Test-Path $ChromePath)) {
  throw "Chrome not found at $ChromePath"
}

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null

$running = Get-CimInstance Win32_Process -Filter "name='chrome.exe'" -ErrorAction SilentlyContinue
if ($running) {
  $running | ForEach-Object {
    try {
      Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
    } catch {
    }
  }
  Start-Sleep -Seconds 2
}

Start-Process -FilePath $ChromePath -ArgumentList "--remote-debugging-port=$ChromeDebugPort","--user-data-dir=$ProfileDir" | Out-Null

$deadline = (Get-Date).AddSeconds(15)
$chromeReady = $false
do {
  Start-Sleep -Milliseconds 750
  try {
    $resp = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$ChromeDebugPort/json/version"
    if ($resp.StatusCode -eq 200) {
      $chromeReady = $true
      break
    }
  } catch {
  }
} while ((Get-Date) -lt $deadline)

if (-not $chromeReady) {
  throw "Chrome CDP did not come up on 127.0.0.1:$ChromeDebugPort"
}

netsh interface portproxy delete v4tov4 listenport=$BridgePort listenaddress=0.0.0.0 | Out-Null
netsh interface portproxy add v4tov4 listenport=$BridgePort listenaddress=0.0.0.0 connectport=$ChromeDebugPort connectaddress=$ConnectAddress | Out-Null

$existingRule = Get-NetFirewallRule -DisplayName $BridgeRuleName -ErrorAction SilentlyContinue
if (-not $existingRule) {
  New-NetFirewallRule -DisplayName $BridgeRuleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $BridgePort | Out-Null
}

$localVersion = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$ChromeDebugPort/json/version" | Select-Object -ExpandProperty Content
$bridgeInfo = netsh interface portproxy show v4tov4

Write-Host "Chrome debug profile: $ProfileDir"
Write-Host "Chrome CDP: 127.0.0.1:$ChromeDebugPort"
Write-Host "Bridge: 0.0.0.0:$BridgePort -> ${ConnectAddress}:$ChromeDebugPort"
Write-Host ""
Write-Host $localVersion
Write-Host ""
Write-Host $bridgeInfo
