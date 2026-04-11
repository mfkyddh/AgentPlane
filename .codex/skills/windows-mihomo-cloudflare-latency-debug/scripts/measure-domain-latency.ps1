[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Domain,

    [int]$Port = 8443,

    [int]$Samples = 4,

    [string]$OriginIp,

    [string[]]$PublicDnsServers = @('223.5.5.5', '1.1.1.1', '8.8.8.8'),

    [string]$ClashConfigPath = 'C:\Users\Administrator\AppData\Roaming\Clash Nyanpasu\config\clash-config.yaml',

    [string]$ControllerUrl = 'http://127.0.0.1:17650'
)

$ErrorActionPreference = 'Stop'

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "=== $Title ==="
}

function Invoke-CurlTiming {
    param(
        [string[]]$ExtraArgs,
        [string]$Label,
        [int]$Count
    )

    Write-Section $Label
    $url = "https://$Domain`:$Port/"
    1..$Count | ForEach-Object {
        $args = @()
        if ($ExtraArgs) {
            $args += $ExtraArgs
        }
        $args += @(
            '-k', '-o', 'NUL', '-sS',
            '-w', "remote=%{remote_ip} code=%{http_code} dns=%{time_namelookup} tcp=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total}`n",
            $url
        )
        & curl.exe @args
    }
}

function Measure-ResolveDns {
    param(
        [ValidateSet('A', 'AAAA')]
        [string]$Type,
        [string]$Server
    )

    $rows = @()
    foreach ($i in 1..3) {
        if ($Server -eq 'system') {
            Clear-DnsClientCache | Out-Null
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            try {
                $result = Resolve-DnsName $Domain -Type $Type -NoHostsFile -DnsOnly -ErrorAction Stop
                $answer = $result | Where-Object Type -eq $Type | Select-Object -ExpandProperty IPAddress -First 1
            } catch {
                $answer = 'NX/none'
            }
        } else {
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            try {
                $result = Resolve-DnsName $Domain -Type $Type -Server $Server -ErrorAction Stop
                $answer = $result | Where-Object Type -eq $Type | Select-Object -ExpandProperty IPAddress -First 1
            } catch {
                $answer = 'NX/none'
            }
        }
        $sw.Stop()
        $rows += [pscustomobject]@{
            kind   = $Type
            server = $Server
            ms     = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)
            answer = $answer
        }
    }
    return $rows
}

Write-Section 'Context'
[pscustomobject]@{
    timestamp = (Get-Date -Format o)
    domain    = $Domain
    port      = $Port
    samples   = $Samples
    origin_ip = $OriginIp
} | Format-List

if (Test-Path $ClashConfigPath) {
    Write-Section 'Mihomo Runtime'
    try {
        $secretLine = Get-Content $ClashConfigPath | Select-String '^secret:\s*(.+)$' | Select-Object -First 1
        if ($secretLine) {
            $secret = $secretLine.Matches[0].Groups[1].Value.Trim()
            $headers = @{ Authorization = "Bearer $secret" }
            $config = Invoke-RestMethod -Uri "$ControllerUrl/configs" -Headers $headers -Method Get
            [pscustomobject]@{
                mode       = $config.mode
                ipv6       = $config.ipv6
                mixed_port = $config.'mixed-port'
                tun_enable = $config.tun.enable
            } | Format-List
        } else {
            Write-Host 'No controller secret found in Clash config.'
        }
    } catch {
        Write-Host "Unable to read Mihomo runtime: $($_.Exception.Message)"
    }
}

Write-Section 'Hosts Match'
try {
    $hostsMatches = Get-Content 'C:\Windows\System32\drivers\etc\hosts' | Select-String ([regex]::Escape($Domain))
    if ($hostsMatches) {
        $hostsMatches | ForEach-Object { $_.Line }
    } else {
        Write-Host 'No hosts entry.'
    }
} catch {
    Write-Host "Unable to read hosts file: $($_.Exception.Message)"
}

Write-Section 'System Resolution'
try {
    Clear-DnsClientCache | Out-Null
    Resolve-DnsName $Domain -ErrorAction SilentlyContinue | Format-Table -AutoSize
} catch {
    Write-Host "Resolve-DnsName failed: $($_.Exception.Message)"
}

Write-Section 'System Resolution (NoHostsFile + DnsOnly)'
try {
    Resolve-DnsName $Domain -NoHostsFile -DnsOnly -ErrorAction SilentlyContinue | Format-Table -AutoSize
} catch {
    Write-Host "Resolve-DnsName -DnsOnly failed: $($_.Exception.Message)"
}

Write-Section 'DNS Cache'
Get-DnsClientCache |
    Where-Object { $_.Entry -eq $Domain } |
    Select-Object Entry, Type, Data, TimeToLive |
    Format-Table -AutoSize

Write-Section 'DNS Servers'
Get-DnsClientServerAddress -AddressFamily IPv4 |
    Select-Object InterfaceAlias, ServerAddresses |
    Format-Table -AutoSize
Write-Host ""
Get-DnsClientServerAddress -AddressFamily IPv6 |
    Select-Object InterfaceAlias, ServerAddresses |
    Format-Table -AutoSize

Write-Section 'DNS Timing'
$dnsRows = @()
$dnsRows += Measure-ResolveDns -Type A -Server system
$dnsRows += Measure-ResolveDns -Type AAAA -Server system
foreach ($server in $PublicDnsServers) {
    $dnsRows += Measure-ResolveDns -Type A -Server $server
    $dnsRows += Measure-ResolveDns -Type AAAA -Server $server
}
$dnsRows | Sort-Object kind, server, ms | Format-Table -AutoSize

Invoke-CurlTiming -Label 'Curl Default' -Count $Samples
Invoke-CurlTiming -Label 'Curl IPv4' -ExtraArgs @('-4') -Count $Samples
Invoke-CurlTiming -Label 'Curl IPv6' -ExtraArgs @('-6') -Count $Samples

Write-Section 'Curl Verbose'
& curl.exe -vkI "https://$Domain`:$Port/"

if ($OriginIp) {
    Invoke-CurlTiming -Label 'Curl --resolve' -ExtraArgs @('--resolve', "$Domain`:$Port`:$OriginIp") -Count $Samples

    Write-Section 'Curl Direct IP + Host'
    1..$Samples | ForEach-Object {
        & curl.exe -k -H "Host: $Domain`:$Port" -o NUL -sS `
            -w "remote=%{remote_ip} code=%{http_code} dns=%{time_namelookup} tcp=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total}`n" `
            "https://$OriginIp`:$Port/"
    }
}
