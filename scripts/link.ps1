# Prints the links for this project: one for this machine, one to share with
# people on the same network, plus a quick health check of the running stack.
#
#   powershell -ExecutionPolicy Bypass -File scripts\link.ps1

$ErrorActionPreference = "Stop"

$frontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "3000" }
$backendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }

function Test-Port([string]$targetHost, [int]$port) {
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect($targetHost, $port, $null, $null)
    if (-not $async.AsyncWaitHandle.WaitOne(800)) { return $false }
    $client.EndConnect($async)
    return $true
  } catch {
    return $false
  } finally {
    $client.Close()
  }
}

$address = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object {
    $_.IPAddress -notlike "127.*" -and
    $_.IPAddress -notlike "169.254.*" -and
    $_.InterfaceAlias -notmatch "Bluetooth|蓝牙|vEthernet|Loopback|SSTAP"
  } |
  Sort-Object @{ Expression = { if ($_.InterfaceAlias -match "WLAN|Wi-Fi|无线|Ethernet|以太网") { 0 } else { 1 } } } |
  Select-Object -First 1

$frontUp = Test-Port "127.0.0.1" ([int]$frontendPort)
$backUp = Test-Port "127.0.0.1" ([int]$backendPort)

Write-Host ""
Write-Host "自己访问：       http://localhost:$frontendPort"
if ($address) {
  Write-Host "分享给同一 WiFi： http://$($address.IPAddress):$frontendPort" -ForegroundColor Green
} else {
  Write-Host "没有检测到局域网地址，请先连接 WiFi 或有线网络" -ForegroundColor Yellow
}
Write-Host ""
if ($frontUp -and $backUp) {
  Write-Host "服务状态：前端与后端都在监听，可以直接把上面那条链接发出去。" -ForegroundColor Green
} else {
  $frontState = if ($frontUp) { "前端正常" } else { "前端未启动" }
  $backState = if ($backUp) { "后端正常" } else { "后端未启动" }
  Write-Host "服务状态：$frontState，$backState" -ForegroundColor Yellow
  Write-Host "先启动服务：.\scripts\deploy.cmd（或 docker compose up -d）"
}
Write-Host ""
Write-Host "提示：自己用 localhost 那条，换网络也不会变；分享链接里的 IP 会随网络变化，重新运行本脚本即可。"
