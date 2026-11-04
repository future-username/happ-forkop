#!/bin/sh
set -eu
umask 077
cd "$(dirname "$0")"
[ -f /etc/openwrt_release ] || { echo 'Запускайте на OpenWrt.'; exit 1; }
[ -f /www/luci-static/resources/view/forkop/main.js ] || { echo 'Сначала установите Forkop с LuCI.'; exit 1; }
[ "$(uci -q get forkop.settings.config_version)" = 2.0.0 ] || { echo 'Нужен Forkop с форматом настроек 2.0.0.'; exit 1; }
for tool in jsonfilter wget sha256sum; do
 command -v "$tool" >/dev/null || { echo "Не установлен $tool"; exit 1; }
done
case "$(uname -m)" in
 aarch64) asset=linux-arm64; hash=8fc7465643c79e4ef9c69f3ddd7d43b30356ea05fa319b6d0e5449e186c0351a ;;
 x86_64) asset=linux-x86_64; hash=b63b027dcc6d92b8609203184d9fcde6959685bc2b461808afe108eb29751daa ;;
 *) echo 'Эта сборка установщика поддерживает aarch64 и x86_64. Для другой архитектуры нужна отдельная сборка hpwnr.'; exit 1 ;;
esac
tmp=$(mktemp -d /tmp/happ-install.XXXXXX)
trap 'rm -rf "$tmp"' EXIT
wget -O "$tmp/hpwnr" "https://github.com/Omegaplexx/hpwnr/releases/download/v1.0.2/hpwnr-$asset"
printf '%s  %s\n' "$hash" "$tmp/hpwnr" | sha256sum -c -
chmod 700 "$tmp/hpwnr"
"$tmp/hpwnr" help >/dev/null
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
