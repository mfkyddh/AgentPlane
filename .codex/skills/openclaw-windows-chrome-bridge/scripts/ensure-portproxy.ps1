# Recreate the Windows-side bridge that exposes Chrome CDP to WSL.
# Requires an elevated Windows shell for netsh/firewall changes.

$ListenPort = 9223
$ConnectPort = 9222
$ConnectAddress = '127.0.0.1'
$RuleName = 'OpenClaw Chrome CDP 9223'

netsh interface portproxy delete v4tov4 listenport=$ListenPort listenaddress=0.0.0.0 | Out-Null
netsh interface portproxy add v4tov4 listenport=$ListenPort listenaddress=0.0.0.0 connectport=$ConnectPort connectaddress=$ConnectAddress

$existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if (-not $existing) {
  New-NetFirewallRule -DisplayName $RuleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $ListenPort | Out-Null
}

Write-Host "Bridge ready: 0.0.0.0:$ListenPort -> $ConnectAddress:$ConnectPort"
