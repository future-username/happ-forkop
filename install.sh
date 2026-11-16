#!/bin/sh
set -eu
umask 077
cd "$(dirname "$0")"
[ "$(id -u)" = 0 ] || { echo 'Запускайте от root.'; exit 1; }
[ -f /etc/openwrt_release ] || { echo 'Запускайте на OpenWrt.'; exit 1; }
[ -f /www/luci-static/resources/view/forkop/main.js ] || { echo 'Сначала установите Forkop с LuCI.'; exit 1; }
[ "$(uci -q get forkop.settings.config_version)" = 2.0.0 ] || { echo 'Нужен Forkop с форматом настроек 2.0.0.'; exit 1; }
for tool in jsonfilter wget sha256sum; do
 command -v "$tool" >/dev/null || { echo "Не установлен $tool"; exit 1; }
done
version=v1.0.3
case "$(uname -m)" in
 aarch64|arm64) asset=linux-arm64; hash=70690e11184ab89ac117d5d1a11b40206c7ce633bff32860c18112f1a1dfcf06 ;;
 x86_64) asset=linux-x86_64; hash=57e448bf9d2a3e6db09378943770f85006b0efb41ef7581e14f17e4eaf331486 ;;
 *) echo 'Установщик поддерживает aarch64 и x86_64. Другим архитектурам нужна проверенная сборка hpwnr.'; exit 1 ;;
esac
tmp=$(mktemp -d /tmp/happ-install.XXXXXX)
trap 'rm -rf "$tmp"' EXIT
trap 'exit 1' HUP INT TERM
wget -O "$tmp/hpwnr" "https://github.com/Omegaplexx/hpwnr/releases/download/$version/hpwnr-$asset"
printf '%s  %s\n' "$hash" "$tmp/hpwnr" | sha256sum -c -
chmod 700 "$tmp/hpwnr"
"$tmp/hpwnr" help > "$tmp/help"
grep -q 'hpwnr v1.0.3' "$tmp/help" && grep -q 'stdout' "$tmp/help" || { echo 'Нужна полная сборка hpwnr v1.0.3 с поддержкой загрузки.'; exit 1; }
mkdir -p /etc/happ-forkop /usr/libexec /usr/share/luci/menu.d /usr/share/rpcd/acl.d
chmod 700 /etc/happ-forkop
cp "$tmp/hpwnr" /usr/bin/hpwnr
cp root/usr/libexec/happ-forkop /usr/libexec/happ-forkop
chmod 700 /usr/bin/hpwnr /usr/libexec/happ-forkop
cp root/www/luci-static/resources/view/happ-forkop.js /www/luci-static/resources/view/
cp root/usr/share/luci/menu.d/luci-app-happ-forkop.json /usr/share/luci/menu.d/
cp root/usr/share/rpcd/acl.d/luci-app-happ-forkop.json /usr/share/rpcd/acl.d/
chmod 644 /www/luci-static/resources/view/happ-forkop.js /usr/share/luci/menu.d/luci-app-happ-forkop.json /usr/share/rpcd/acl.d/luci-app-happ-forkop.json
if [ ! -e /etc/happ-forkop/settings.json ]; then printf '{}\n' > /etc/happ-forkop/settings.json; fi
chmod 600 /etc/happ-forkop/settings.json
touch /etc/sysupgrade.conf
grep -qxF /etc/happ-forkop/ /etc/sysupgrade.conf || printf '\n/etc/happ-forkop/\n' >> /etc/sysupgrade.conf
/etc/init.d/rpcd restart
rm -f /tmp/luci-indexcache
echo 'Установлено. Выйдите из LuCI и войдите снова: Службы → Happ → Forkop.'
