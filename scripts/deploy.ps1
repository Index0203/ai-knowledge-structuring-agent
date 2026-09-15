# Builds and starts the production stack, then reports where it is reachable.
#
#   pwsh -File scripts/deploy.ps1
#
# The script is idempotent: run it again after pulling changes to rebuild and
# restart. Data lives in named volumes, so nothing is lost between runs.

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "已根据 .env.example 生成 .env（未配置模型密钥时系统运行在降级模式）。" -ForegroundColor Yellow
  Write-Host "如需接入真实模型，请在 .env 中填写 OPENAI_API_KEY / OPENAI_MODEL / OPENAI_BASE_URL。" -ForegroundColor Yellow
}

Write-Host "正在构建并启动生产服务…" -ForegroundColor Cyan
docker compose -f docker-compose.prod.yml up -d --build

Write-Host "等待后端健康检查…" -ForegroundColor Cyan
$healthy = $false
$deadline = (Get-Date).AddMinutes(3)
do {
  Start-Sleep -Seconds 3
  $status = docker compose -f docker-compose.prod.yml ps --format "{{.Service}} {{.Status}}"
  $healthy = [bool]($status | Select-String "backend .*healthy")
} while (-not $healthy -and (Get-Date) -lt $deadline)

docker compose -f docker-compose.prod.yml ps

if ($healthy) {
  Write-Host ""
  Write-Host "部署完成：" -ForegroundColor Green
  Write-Host "  前端      http://localhost:3000"
  Write-Host "  接口文档  http://localhost:8000/docs"
  Write-Host "  查看日志  docker compose -f docker-compose.prod.yml logs -f backend worker"
  Write-Host "  停止服务  docker compose -f docker-compose.prod.yml down"
} else {
  Write-Host "后端在 3 分钟内没有变为健康状态，请查看日志：" -ForegroundColor Red
  Write-Host "  docker compose -f docker-compose.prod.yml logs backend migrate"
  exit 1
}
