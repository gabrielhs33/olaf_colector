#!/bin/bash

echo "=== [1/3] Instalando dependências ==="
sudo apt-get update -qq
sudo apt-get install -y chromium-browser chromium-chromedriver curl 2>/dev/null || \
sudo apt-get install -y chromium chromium-driver curl

pip install --break-system-packages selenium yt-dlp 2>/dev/null || \
pip install --user selenium yt-dlp

echo "=== [2/3] Instalando Deno ==="
curl -fsSL https://deno.land/install.sh | sh
grep -q 'DENO_INSTALL' ~/.bashrc || echo '
export DENO_INSTALL="$HOME/.deno"
export PATH="$DENO_INSTALL/bin:$PATH"' >> ~/.bashrc
export PATH="$HOME/.deno/bin:$PATH"

echo "=== [3/3] Criando perfil Chrome ==="
mkdir -p /tmp/chrome_persona

echo ""
echo "✅ Pronto"
echo "   source ~/.bashrc"
echo "   python3 olaf_colector.py"
