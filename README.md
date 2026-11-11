# MX4200 ImmortalWrt

## 本分支：HomeWRK / MX4300 本地 Mesh 实验构建

`feat/homewrk-mesh-nss-local` 在下述上游项目之外提供独立的本地构建入口。
源码和 feeds 固定在 `local/sources.lock.json`，内核为 Linux 6.18.60。
构建生成 HomeWRK 和 MX4300 各自的临时启动、安装及升级镜像，以及同次编译的软件包仓库。
两种分区布局的镜像不可混刷，机身或卖家的型号说明不能代替分区核实。

本地配置包含完整 `wpad-openssl`、usteer / LuCI、WireGuard、USB3 / UAS、
ext4 / exFAT、iperf3 和抓包工具。无线国家、信道、SSID、密钥和节点角色需要按现场设置。
本地构建 r2 增加当前固定源码中的全部 15 个 `kmod-nft-*` 扩展，包含 TPROXY、socket、
bridge、netdev、queue、compat、xfrm 等，另带 NFLOG、完整 `ip` 命令及支持 nftset 的
`dnsmasq-full`。按用户选择，仅准备代理底层，不预装代理客户端或订阅。

r3 修正内核配置变化后的外置模块缓存失效：先生成当前内核配置，ABI 改变或没有可信构建
记录时，清理已选外置内核模块，再完成编译。r2 NSS 镜像在 HomeWRK 的内存启动测试中因
旧 NSS 模块与当前内核的 `net_device` 布局不一致发生崩溃，因此不能将其静态校验通过
视为可刷入结论。实机测试报告与编译校验报告分别记录。

SMB 使用 CIFS 挂载客户端和 ksmbd 的 SMB2/3 服务端；NFS 带 v3/v4 客户端、v4 服务端、
管理工具及 LuCI 页面。ksmbd、NFS、rpcbind 和 WSD 发现服务在首次启动时禁用，没有预设共享目录；
使用时先配置磁盘、用户、允许访问的客户端及导出目录，再启动对应服务。
文件共享消耗的 CPU、内存和带宽取决于实际传输，代理/过滤与 NSS 的组合也需要真机验证。
usteer 预装但默认不启动；它是可选的漫游协调服务，802.11s 回程本身不依赖它。
本地构建不调用上游的 `user/default/custom.sh`，因此沿用 ImmortalWrt 的管理地址、
无线初始状态和主题，不继承下面所述的 US 区域及固定无线密码。

在安装好 OpenWrt 编译依赖的 Linux 主机运行：

```sh
python3 scripts/build_local.py baseline all --work /data/mx4300-op -j 32
python3 scripts/build_local.py nss all --work /data/mx4300-op -j 32
```

可将 `all` 换成 `prepare`、`download`、`toolchain`、`compile` 或 `collect`。
默认继承进程代理；可用 `--no-proxy` 直连，或用 `--proxy http://HOST:PORT` 单独指定。
大型文件写入 `--work`，至少预留 30 GiB，完整两套构建建议预留 80 GiB 以上。
日志位于 `logs/`，成功构建的镜像、配套包与构建记录位于 `artifacts/<variant>/`。
上面的并发数用于本次 52 核、104 线程、64 GiB 内存主机，两套同时执行时合计最多 64 个任务；
其他主机应按可用内存和 CPU 调整 `-j`。`local/sources.lock.json` 中的 `build_revision`
区分本地构建版本，镜像文件名以 `-r3-` 标识包含模块缓存修正的构建。

编译完成后检查实际镜像（主机需有 `modinfo`，Ubuntu 由 `kmod` 包提供）：

```sh
python3 scripts/verify_local.py all --work /data/mx4300-op
```

验证脚本核对镜像校验和、机型和源码版本，并解包 sysupgrade 检查实际安装的软件包、
AArch64 程序和内核模块，以及 NSS 默认配置。报告保存在各自的
`build-record/verification.json`；配套 APK 仓库公钥保存为 `build-record/public-key.pem`。
检查还覆盖全部 nftables 扩展、SMB/NFS 客户端与服务端，以及默认关闭共享的设置。
这些检查不包含真机启动、无线回程或吞吐测试。

`baseline` 使用 ImmortalWrt 原生无线栈并保留上游项目的 HomeWRK MAC 保护。
`nss` 额外应用 `local/patches/nss-wifi.patch`，来自
[openwrt-ppe-nss](https://github.com/JuliusBairaktaris/openwrt-ppe-nss/tree/7d65a3ed836a0071e2f19a5944682f457e02efe0)
的无线驱动、ath11k、设备树和共享 PPE/EDMA 修改，保持 ImmortalWrt 应用 feeds。
补丁不导入该项目的 GitHub 自动化、通用 CAKE/PPP 调整或默认开启卸载的设置。
原代码和补丁保留原许可；NSS 固件使用其发行包内的独立许可。

NSS 实验版选择支持 Mesh 的 **NSS 固件 11.4**，默认 `offload=0`。
完成普通无线、USB 恢复和完整回程路径测试后，才在测试设备上打开卸载做对照：

```sh
uci set nss-wifi.general.offload='1'
uci commit nss-wifi
reboot
```

改回 `offload='0'` 并重启可关闭卸载。重点实测无线终端经过节点和无线回程的双向流量，
包括两个节点同时传输、漫游和持续负载；编译与镜像校验通过不代表硬件测试通过。
WireGuard 单独测量，不承诺 NSS 加速其加密。内核模块使用本次构建的配套包，不能强装
其他 snapshot 的 kmod。首次刷写前核实设备身份、保存原机分区备份并验证 TTL + USB 启动。

---

基于 [ImmortalWrt 官方最新 snapshot 源码](https://github.com/immortalwrt/immortalwrt/tree/master)，适用于 Linksys MX4200v1 / MX4200v2。

2026.11.05：新增 Linksys MX4300 / HomeWRK 机型固件。

## 固件下载

前往 [Releases](https://github.com/yahuisme/mx4200-immortalwrt/releases)，选择对应发布组：

- **MX4200**：MX4200v1 / MX4200v2。
- **MX4300**：MX4300 / HomeWRK。

请选择对应机型及硬件版本的镜像，不可混刷。

| 镜像 | 用途 |
| --- | --- |
| `factory.bin` | MX4200 / MX4300 从原厂固件刷入 |
| `factory.ubi` | HomeWRK 命令行写入用，本教程无需使用 |
| `sysupgrade.bin` | 系统升级；HomeWRK 从临时系统首次安装 |
| `initramfs-uImage.itb` | HomeWRK 从 USB 启动的临时系统，自带 LuCI |

MX4300 发布组附带 HomeWRK 官方最新稳定版临时镜像，自带 LuCI，管理地址为 `192.168.1.1`。每次构建自动下载并校验大小与 SHA-256，保持官方原版不变。

**首次安装：[Linksys 刷机教程](linksys-first-flash.md)。MX4200 / MX4300 网页刷入，HomeWRK 使用 TTL＋U 盘。**

## 功能与应用

- 中文 LuCI 与 Aurora 主题。
- 设备驱动及基础 USB 支持沿用各机型官方默认。
- 三频 Wi-Fi，默认开启 2.4 GHz 与 5.8 GHz。

| 应用 | 功能 |
| --- | --- |
| [HomeProxy](https://github.com/yahuisme/packages/tree/main/luci-app-homeproxy) | 基于 sing-box 的代理客户端 |
| Aurora 配置 | 主题设置 |
| 高级重启 | MX4200v1/v2、MX4300 双分区重启切换，HomeWRK 不预装 |
| CPU 性能 | 调节 CPU 调频策略 |
| 网络唤醒 | 唤醒局域网设备 |
| 网页终端 | 浏览器终端访问 |

HomeProxy 与 sing-box 使用 [yahuisme/packages](https://github.com/yahuisme/packages) 的最新源码构建。HomeProxy 默认停用，需自行配置节点或订阅后启用。

Aurora 主题及配置插件通过官方签名 APK 软件源预装，可在 **系统 → 软件包** 刷新列表并更新。

## 默认设置

以下设置在首次启动或不保留配置升级时生效。

- 管理地址：`192.168.10.1`
- 管理密码：无
- Wi-Fi 名称：MX4200v1/v2 为 `MX4200`；MX4300 / HomeWRK 为 `MX4300`
- Wi-Fi 密码：`12345678`

| 项目 | 2.4 GHz | 5.2 GHz | 5.8 GHz |
| --- | --- | --- | --- |
| 状态 | 开启 | 关闭 | 开启 |
| 区域 | US | US | US |
| 信道 | 11 | 48 | 149 |
| 加密 | WPA2-PSK | WPA2-PSK | WPA2-PSK |
| 配置功率 | 23 dBm | 25 dBm | 25 dBm |

## 构建与发布

每日自动构建，计划时间为香港时间 12:00；也可手动运行 [Actions](https://github.com/yahuisme/mx4200-immortalwrt/actions/workflows/MX4200.yml)。

每次构建拉取官方 `master` 最新源码，版本显示沿用官方。使用 Ubuntu 24.04 ARM64 与 Debian Docker 环境，一次构建四个机型，按 MX4200、MX4300 两组发布，每组保留最新一版。
