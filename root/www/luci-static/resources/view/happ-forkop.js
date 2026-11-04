'use strict';
'require view';
'require fs';
'require uci';
'require ui';

return view.extend({
 load: function() {
  return Promise.all([uci.load('forkop'), fs.read('/etc/happ-forkop/settings.json').catch(function() { return '{}'; })]);
 },
 render: function(data) {
  var saved; try { saved = JSON.parse(data[1]); } catch (_) { saved = {}; }
  var link = E('textarea', { 'class': 'cbi-input-textarea', 'rows': 4, 'placeholder': 'happ://crypt5/…' });
  link.value = saved.link || '';
  var section = E('select', { 'class': 'cbi-input-select' });
  uci.sections('forkop', 'section', function(s) {
   if (s.action === 'connection') section.appendChild(E('option', { 'value': s['.name'] }, [s.name || s['.name']]));
  });
  if (saved.section) section.value = saved.section;
  var interval = E('select', { 'class': 'cbi-input-select' }, ['30m', '1h', '6h', '12h', '1d'].map(function(v) { return E('option', { 'value': v }, [v]); }));
  interval.value = saved.interval || '1h';
  var hwid = E('input', { 'class': 'cbi-input-text', 'type': 'text', 'placeholder': 'Необязательно' });
  hwid.value = saved.hwid || '';
  var status = E('p', { 'role': 'status' });
  function row(title, input) { return E('div', { 'class': 'cbi-value' }, [E('label', { 'class': 'cbi-value-title' }, [title]), E('div', { 'class': 'cbi-value-field' }, [input])]); }
  var button = E('button', { 'class': 'btn cbi-button cbi-button-apply', 'click': ui.createHandlerFn(this, async function() {
   if (!/^happ:\/\/crypt\w*\/.+/.test(link.value.trim())) { status.textContent = 'Вставьте зашифрованную ссылку Happ.'; return; }
   if (!section.value) { status.textContent = 'Сначала создайте в Forkop секцию с действием «Подключение» и примените настройки.'; return; }
   button.disabled = true;
   try {
    await fs.write('/etc/happ-forkop/settings.json', JSON.stringify({ link: link.value.trim(), section: section.value, interval: interval.value, hwid: hwid.value.trim() }));
    var result = await fs.exec('/usr/libexec/happ-forkop', []);
    status.textContent = (result.stdout || 'Импорт не выполнен.') + (result.code ? ' Код: ' + result.code : '');
   } catch (e) { status.textContent = 'Ошибка импорта: ' + e.message; }
   finally { button.disabled = false; }
  }) }, ['Добавить в Forkop']);
  return E('div', {}, [E('h2', {}, ['Happ → Forkop']), E('p', {}, ['Вставьте ссылку один раз. Подписку будет обновлять Forkop. Повторный импорт заменяет только подписку, созданную этим дополнением.']), row('Ссылка Happ', link), row('Секция Forkop', section), row('Интервал обновления', interval), row('X-HWID', hwid), E('p', {}, ['Если провайдер требует привязку устройства, укажите разрешённый для подписки HWID.']), button, status]);
 },
 handleSaveApply: null,
 handleSave: null,
 handleReset: null
});
