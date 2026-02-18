#!/usr/bin/env bash
# Rebuild and redeploy cinny web (cinny.nocfa.net)
set -e

CINNY_DIR="/home/noc/dev/cinny"
WEBROOT="/srv/cinny"

echo "Pulling latest element-call branch..."
cd "$CINNY_DIR"
git pull

echo "Installing deps..."
npm ci --silent

echo "Building..."
npm run build

echo "Deploying to $WEBROOT..."
sudo rsync -a --delete dist/ "$WEBROOT/"
sudo chown -R www-data:www-data "$WEBROOT"

echo "Done. cinny.nocfa.net updated."
