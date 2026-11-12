# 第三方来源与本地修改

本仓库由 [yahuisme/mx4200-immortalwrt](https://github.com/yahuisme/mx4200-immortalwrt) 派生，保留原项目历史、许可和构建辅助工具。本地固定构建使用 `scripts/build_local.py` 与 `local/`。完整版本锁见 `local/sources.lock.json`。

| 来源 | 固定版本 | 用途与许可 |
| --- | --- | --- |
| [ImmortalWrt](https://github.com/immortalwrt/immortalwrt) | `4765b657625ec5bbda74b44400465fe043802b30` | 构建根、内核和系统；各包保留自身许可 |
| [openwrt-ppe-nss](https://github.com/JuliusBairaktaris/openwrt-ppe-nss) | `7d65a3ed836a0071e2f19a5944682f457e02efe0`，基点 `606ee33b8a049244759de735a48e98b00ec8ad5c` | `local/patches/nss-wifi.patch`，选取无线 NSS、ath11k、设备树及共享 PPE/EDMA 修改；保留原文件许可 |
| [nss-packages](https://github.com/JuliusBairaktaris/nss-packages) | `1f60d7e9409930bbd298eae1831c5b76d21eb1d2` | NSS 软件包和固件；固件按包内独立许可分发 |
| [Vantage](https://github.com/anothaDev/luci-theme-vantage) | v1.0.19，`ed6be0a7c2fb836164ac0c2be9530ae5e2a21deb` | 主题、仪表盘和中文；GPL-3.0-or-later，版权声明见 `local/VANTAGE-NOTICE` |
| ImmortalWrt LuCI feed | `319f7c96e3530246cf91cfdd9bacb3fa44dc3a4e` | LuCI；本地 `view/status/include/10_system.js` 基于其文件，只改变已知设备的显示型号；Apache-2.0 |
| [usteer](https://git.openwrt.org/project/usteer.git) | `7532e1252fb937fe34b6da05e86fd34babd91ef5`（固定 packages feed 提供） | AP 协调；GPL-2.0-only |

Vantage feed 不直接修改，以下覆盖文件以固定版本源码为基础，随固件透明发布：

- `local/files/usr/share/ucode/luci/template/themes/vantage/sysauth.ut`：登录页标签加入经过 HTML 编码的当前主机名，不把设备 MAC 写死在源码中。
- `local/files/www/luci-static/resources/vantage-theme/host.js`：已知 HomeWRK/MX4300 的显示型号统一为 Linksys MX4300，实际板级身份不变。
- `local/files/usr/share/rpcd/ucode/luci.vantage`：在 MAC 正则校验前拒绝非十六进制或分隔符字符，避免 ucode 的 POSIX 换行边界匹配接受带换行的无效 MAC。未增加 RPC 权限；原上游对应测试用于复核。

- `local/files/usr/share/luci/menu.d/zz-luci-app-vantage.json`：保留仪表盘入口，移除与当前 fw4 否定协议语义不一致的附加防火墙概览入口；LuCI 原生防火墙页面保留。

主题 CSS、图片、字体全部来自本地包资源，没有加入第三方 CDN 或追踪。旧 Argon 覆盖文件已移除。Vantage 保留自己的外观与标志，本项目不冒充其官方发行版。

`LICENSE` 不覆盖所有第三方组件的独立许可。构建下载得到的包内 COPYING/LICENSE/NOTICE 及 package Makefile 的 `PKG_LICENSE` 是相应组件许可依据。发布固件时应同时提供本仓库版本、源码锁、构建配置和可取得的对应源代码；不要只发布不明来源的二进制。
