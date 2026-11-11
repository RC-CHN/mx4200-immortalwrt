'use strict';
'require view';
'require form';
'require rpc';
'require poll';
'require uci';
'require ui';

var callStatus = rpc.declare({ object: 'mx4300.nss', method: 'status', expect: {} });
var callRetry = rpc.declare({ object: 'mx4300.nss', method: 'retry', expect: {} });

return view.extend({
	load: function() { return Promise.all([uci.load('nss-wifi'), callStatus()]); },
	render: function(data) {
		var status = E('div', { 'class': 'cbi-section', 'aria-live': 'polite' });
		function update(s) {
			var message = s.guarded ? (s.pending ? '上次启动未完成保护检查，本次使用普通无线驱动。请检查系统日志。' : '保护标记已清除，重启后会按保存的设置重新启动。') :
				(s.configured !== s.boot_requested ? '设置已保存，重启后生效。' :
				(s.running ? (s.pending ? 'NSS 已启动，正在完成启动保护检查（约 2 分钟）。' : 'NSS 已运行，启动保护检查已完成。') :
				(s.boot_requested ? '已请求启用，但 NSS 尚未运行。请检查系统日志。' : '当前使用普通无线驱动。')));
			status.replaceChildren(E('h3', {}, '运行状态'), E('p', {}, message),
				E('p', {}, '当前 NSS：' + (s.running ? '已运行' : '未运行') + ' · 保存的设置：' + (s.configured ? '开启' : '关闭')),
				E('p', {}, 'NSS 固件：' + (s.firmware || '未加载') + ' · 有线 PPE 硬件流卸载设置：' + (s.hardware_flow && s.software_flow ? '开启' : '关闭')),
				E('p', { 'class': 'description' }, 'PPE 与 NSS 分别控制；关闭 NSS 不会关闭有线硬件流卸载。实际流量是否加速还取决于协议和连接条件。'),
				E('a', { 'class': 'cbi-button cbi-button-action', 'href': L.url('admin/system/reboot') }, '前往重启'));
			if (s.guarded && s.pending && !s.running)
				status.appendChild(E('button', { 'class': 'cbi-button', 'click': ui.createHandlerFn(this, function() {
					return callRetry().then(callStatus).then(update);
				}) }, '清除启动保护标记（下次重启重试）'));
		}
		update(data[1]);
		poll.add(function() { return callStatus().then(update); }, 5);
		var m = new form.Map('nss-wifi', 'NSS 无线加速',
			'用于支持的无线数据路径。保存并应用后需要重启路由器；重启会暂时中断有线和无线连接。');
		var s = m.section(form.NamedSection, 'general', 'general');
		var o = s.option(form.Flag, 'offload', '启用 NSS');
		o.rmempty = false;
		o.default = '1';
		o.description = '遇到无线兼容性或稳定性问题时，可关闭此项并重启。';
		return m.render().then(function(formNode) { return E('div', {}, [status, formNode]); });
	}
});
