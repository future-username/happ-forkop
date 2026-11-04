#!/bin/sh
# Download and install Happ -> Forkop on OpenWrt.
set -eu
umask 077
[ "$(id -u)" = 0 ] || { echo 'Запускайте от root.'; exit 1; }
[ -f /etc/openwrt_release ] || { echo 'Запускайте на OpenWrt.'; exit 1; }
[ -f /www/luci-static/resources/view/forkop/main.js ] || { echo 'Сначала установите Forkop с LuCI.'; exit 1; }
for tool in wget tar; do
 command -v "$tool" >/dev/null || { echo "Не установлен $tool"; exit 1; }
done
tmp=$(mktemp -d /tmp/happ-download.XXXXXX)
trap 'rm -rf "$tmp"' EXIT
trap 'exit 1' HUP INT TERM
echo 'Скачивание Happ → Forkop...'
wget -O "$tmp/package.tar.gz" 'https://codeload.github.com/future-username/happ-forkop/tar.gz/refs/heads/main'
tar -xzf "$tmp/package.tar.gz" -C "$tmp"
[ -f "$tmp/happ-forkop-main/install.sh" ] || { echo 'В архиве нет установщика.'; exit 1; }
sh "$tmp/happ-forkop-main/install.sh"
