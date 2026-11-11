#!/bin/sh
case "$1" in
list) echo '{"status":{},"retry":{}}';;
call)
	if [ "$2" = retry ]; then
		# Only acknowledge a previous failed boot while the ordinary driver runs.
		[ -e /tmp/mx4300-nss-guarded ] &&
		[ "$(cat /sys/module/ath11k/parameters/nss_offload 2>/dev/null)" != Y ] || exit 1
		rm -f /etc/nss-wifi.pending
		sync
		echo '{"ok":true}'
		exit 0
	fi
	[ "$2" = status ] || exit 1
	. /usr/share/libubox/jshn.sh
	json_init
	json_add_boolean configured "$([ "$(uci -q get nss-wifi.general.offload)" = 1 ] && echo 1 || echo 0)"
	json_add_boolean boot_requested "$([ "$(cat /tmp/mx4300-nss-boot-requested 2>/dev/null)" = 1 ] && echo 1 || echo 0)"
	json_add_boolean guarded "$([ -e /tmp/mx4300-nss-guarded ] && echo 1 || echo 0)"
	json_add_boolean pending "$([ -e /etc/nss-wifi.pending ] && echo 1 || echo 0)"
	ath="$(cat /sys/module/ath11k/parameters/nss_offload 2>/dev/null)"
	boot="$(cat /sys/kernel/debug/39000000.nss/boot 2>/dev/null)"
	json_add_boolean running "$([ "$ath" = Y ] && [ "$boot" = 1 ] && echo 1 || echo 0)"
	json_add_string firmware "$(cat /sys/module/nss_wifi_drv/parameters/firmware 2>/dev/null)"
	json_add_boolean software_flow "$([ "$(uci -q get firewall.@defaults[0].flow_offloading)" = 1 ] && echo 1 || echo 0)"
	json_add_boolean hardware_flow "$([ "$(uci -q get firewall.@defaults[0].flow_offloading_hw)" = 1 ] && echo 1 || echo 0)"
	json_dump
	;;
*) exit 1;;
esac
