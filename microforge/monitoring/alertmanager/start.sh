#!/bin/sh
# Lancement d'Alertmanager : notifications Discord seulement si DISCORD_WEBHOOK_URL est fourni.
# Sans webhook, Grafana démarrait en erreur (point de contact vide) : le routage vit désormais ici.
set -eu
if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
  umask 077
  printf '%s' "$DISCORD_WEBHOOK_URL" > /alertmanager/discord_webhook_url
  config=/etc/alertmanager/alertmanager-discord.yml
else
  config=/etc/alertmanager/alertmanager.yml
fi
exec /bin/alertmanager --config.file="$config" --storage.path=/alertmanager
