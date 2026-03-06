param(
  [string]$GameId = "MyGame",
  [string]$Config = "config/default.yaml"
)

gwh init-db --config $Config
gwh run-loop --config $Config --game-id $GameId

