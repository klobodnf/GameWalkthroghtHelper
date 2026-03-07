param(
  [string]$Provider = "",
  [string]$ApiKey = "",
  [string]$BaseUrl = "",
  [string]$Model = "",
  [string]$Protocol = "",
  [string]$RequestPath = "",
  [string]$ApiKeyEnv = "",
  [switch]$DisableAi
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Set-UserAndProcessEnv {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [string]$Value
  )
  [Environment]::SetEnvironmentVariable($Name, $Value, "User")
  if ($null -eq $Value) {
    Remove-Item -Path "Env:$Name" -ErrorAction SilentlyContinue
  } else {
    Set-Item -Path "Env:$Name" -Value $Value
  }
}

function Normalize-ProviderName {
  param([string]$Raw)
  $value = $Raw
  if ($null -eq $value) {
    $value = ""
  }
  $name = $value.Trim().ToLowerInvariant()
  if (-not $name) { return "" }
  $aliases = @{
    "moonshot" = "kimi"
    "claude" = "anthropic"
    "google" = "gemini"
    "local" = "ollama"
    "openai_compatible" = "openai"
    "custom" = "openai"
  }
  if ($aliases.ContainsKey($name)) {
    return $aliases[$name]
  }
  return $name
}

$providerConfigs = @{
  "openai" = @{
    protocol = "openai_chat"
    base_url = "https://api.openai.com/v1"
    model = "gpt-4o-mini"
    request_path = "/chat/completions"
    api_key_env = "OPENAI_API_KEY"
    requires_key = $true
  }
  "kimi" = @{
    protocol = "openai_chat"
    base_url = "https://api.moonshot.cn/v1"
    model = "moonshot-v1-8k"
    request_path = "/chat/completions"
    api_key_env = "KIMI_API_KEY"
    requires_key = $true
  }
  "deepseek" = @{
    protocol = "openai_chat"
    base_url = "https://api.deepseek.com/v1"
    model = "deepseek-chat"
    request_path = "/chat/completions"
    api_key_env = "DEEPSEEK_API_KEY"
    requires_key = $true
  }
  "qwen" = @{
    protocol = "openai_chat"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = "qwen-plus"
    request_path = "/chat/completions"
    api_key_env = "DASHSCOPE_API_KEY"
    requires_key = $true
  }
  "zhipu" = @{
    protocol = "openai_chat"
    base_url = "https://open.bigmodel.cn/api/paas/v4"
    model = "glm-4-plus"
    request_path = "/chat/completions"
    api_key_env = "ZHIPUAI_API_KEY"
    requires_key = $true
  }
  "anthropic" = @{
    protocol = "anthropic_messages"
    base_url = "https://api.anthropic.com/v1"
    model = "claude-3-5-haiku-latest"
    request_path = "/messages"
    api_key_env = "ANTHROPIC_API_KEY"
    requires_key = $true
  }
  "gemini" = @{
    protocol = "gemini_generate"
    base_url = "https://generativelanguage.googleapis.com/v1beta"
    model = "gemini-1.5-flash"
    request_path = ""
    api_key_env = "GOOGLE_API_KEY"
    requires_key = $true
  }
  "openrouter" = @{
    protocol = "openai_chat"
    base_url = "https://openrouter.ai/api/v1"
    model = "openai/gpt-4o-mini"
    request_path = "/chat/completions"
    api_key_env = "OPENROUTER_API_KEY"
    requires_key = $true
  }
  "xai" = @{
    protocol = "openai_chat"
    base_url = "https://api.x.ai/v1"
    model = "grok-2-latest"
    request_path = "/chat/completions"
    api_key_env = "XAI_API_KEY"
    requires_key = $true
  }
  "ollama" = @{
    protocol = "ollama_chat"
    base_url = "http://127.0.0.1:11434"
    model = "qwen2.5:7b"
    request_path = "/api/chat"
    api_key_env = ""
    requires_key = $false
  }
}

if ($DisableAi) {
  Set-UserAndProcessEnv -Name "GWH_AI_ADVISOR_ENABLED" -Value "false"
  Write-Host "[OK] AI advisor disabled."
  exit 0
}

$resolvedProvider = Normalize-ProviderName -Raw $Provider
if (-not $resolvedProvider) {
  $supported = $providerConfigs.Keys | Sort-Object
  Write-Host "Supported providers:"
  for ($i = 0; $i -lt $supported.Count; $i++) {
    Write-Host ("  {0}. {1}" -f ($i + 1), $supported[$i])
  }
  $selection = (Read-Host "Choose provider by number or name").Trim()
  if ($selection -match "^\d+$") {
    $index = [int]$selection - 1
    if ($index -ge 0 -and $index -lt $supported.Count) {
      $resolvedProvider = $supported[$index]
    }
  } else {
    $resolvedProvider = Normalize-ProviderName -Raw $selection
  }
}

if (-not $providerConfigs.ContainsKey($resolvedProvider)) {
  throw "Unsupported provider '$resolvedProvider'."
}

$cfg = $providerConfigs[$resolvedProvider].Clone()
if ($BaseUrl) { $cfg["base_url"] = $BaseUrl.Trim() }
if ($Model) { $cfg["model"] = $Model.Trim() }
if ($Protocol) { $cfg["protocol"] = $Protocol.Trim().ToLowerInvariant() }
if ($RequestPath) { $cfg["request_path"] = $RequestPath.Trim() }
if ($ApiKeyEnv) { $cfg["api_key_env"] = $ApiKeyEnv.Trim() }

if ([bool]$cfg["requires_key"] -and -not $ApiKey) {
  $secure = Read-Host "Enter API key for $resolvedProvider" -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

if ([bool]$cfg["requires_key"] -and -not $ApiKey) {
  throw "Provider '$resolvedProvider' requires API key."
}

Set-UserAndProcessEnv -Name "GWH_AI_ADVISOR_ENABLED" -Value "true"
Set-UserAndProcessEnv -Name "GWH_AI_ADVISOR_PROVIDER" -Value $resolvedProvider
Set-UserAndProcessEnv -Name "GWH_AI_ADVISOR_PROTOCOL" -Value ([string]$cfg["protocol"])
Set-UserAndProcessEnv -Name "GWH_AI_ADVISOR_BASE_URL" -Value ([string]$cfg["base_url"])
Set-UserAndProcessEnv -Name "GWH_AI_ADVISOR_MODEL" -Value ([string]$cfg["model"])
Set-UserAndProcessEnv -Name "GWH_AI_ADVISOR_REQUEST_PATH" -Value ([string]$cfg["request_path"])
Set-UserAndProcessEnv -Name "GWH_AI_ADVISOR_API_KEY_ENV" -Value ([string]$cfg["api_key_env"])

$apiKeyEnvName = ([string]$cfg["api_key_env"]).Trim()
if ($apiKeyEnvName -and $ApiKey) {
  Set-UserAndProcessEnv -Name $apiKeyEnvName -Value $ApiKey
}

Write-Host "[OK] AI provider configured."
Write-Host ("    provider    : {0}" -f $resolvedProvider)
Write-Host ("    protocol    : {0}" -f $cfg["protocol"])
Write-Host ("    base_url    : {0}" -f $cfg["base_url"])
Write-Host ("    model       : {0}" -f $cfg["model"])
if ($apiKeyEnvName) {
  $item = Get-Item -Path "Env:$apiKeyEnvName" -ErrorAction SilentlyContinue
  $keyLen = 0
  if ($null -ne $item -and $null -ne $item.Value) {
    $keyLen = ([string]$item.Value).Length
  }
  Write-Host ("    key env     : {0} (len={1})" -f $apiKeyEnvName, $keyLen)
} else {
  Write-Host "    key env     : (not required)"
}
Write-Host "Open a new terminal to ensure all tools read updated user-level env vars."
