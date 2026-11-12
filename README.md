# MX4300 / HomeWRK ImmortalWrt

面向 Linksys MX4300 与 HomeWRK 的固定版本定制固件。默认使用 **NSS 版、Vantage 主题与仪表盘、usteer 漫游协调**，另提供不含 NSS 的 baseline 版。源码、feeds 和主题都固定到提交，当前构建版本为 **r6**，Linux **6.18.60**。

这是 [yahuisme/mx4200-immortalwrt](https://github.com/yahuisme/mx4200-immortalwrt) 的派生项目，保留 ImmortalWrt 应用生态，并整合 NSS 无线支持。标准 MX4300 与 HomeWRK 的分区布局不同，**镜像不可混刷**。外壳型号或卖家描述不能代替设备树和分区核实。

## 下载固件

[下载 r6 预发布版](https://github.com/RC-CHN/mx4200-immortalwrt/releases/tag/mx4300-r6)。提供 NSS / baseline 两套的 HomeWRK / 标准 MX4300 镜像、配套 APK、SHA-256、构建记录和对应源码归档。

默认选择 NSS；按实际板级身份选择 `linksys_homewrk` 或 `linksys_mx4300`。已装兼容系统时使用对应 `sysupgrade.bin`。r6 已完成编译和镜像校验，尚未实机刷入验收，因此标为预发布。完整选择说明见 Release 页面。

## 默认设置

| 项目 | 全新安装 / 恢复出厂的默认值 |
| --- | --- |
| 管理入口 | `http://192.168.1.1`；`root` / `Mx4300CN` |
| Wi-Fi 密码 | `Mx4300CN`，三频 WPA2-PSK，默认开启 |
| 主机名 | `mx4300-<出厂 MAC 后六位>` |
| Wi-Fi 名称 | `MX4300-<后六位>-2G`、`-5G`、`-5G2` |
| 地区、信道与带宽 | CN；2.4G：6 / HE20，5G：36 / HE80，5G2：149 / HE80 |
| 界面 | Vantage v1.0.19 + 中文翻译；自动明暗、网格背景，显示主机名 |
| 时区、WAN | Asia/Shanghai；DHCP 客户端 |
| NSS | NSS 版默认启用；LuCI 中可关闭，重启生效 |
| usteer | 默认启动，在 LAN 上协调 AP；保留上游策略 |
| SMB / NFS 服务 | 已安装，默认不启动，无预设共享目录 |

这些公开密码用于首次连接，配置网络时请改成自己的密码。配置保留升级不重置密码、SSID、主机名或用户的服务开关。r5 升级到 r6 时新主题会被选中；如果原来关闭了 usteer，需在“系统 → 启动项”启用，并检查其配置中的 `enabled` 开关。

主机名首次初始化时从出厂 MAC 生成：HomeWRK 读取 `devinfo/mac_address`，标准 MX4300 读取 `hw_mac_addr`。WebUI 登录页和登录后标题读取当前主机名，手动改名后随之变化。MAC 后六位不是绝对唯一标识；克隆配置到另一节点也会复制主机名，需逐台改名。身份读取失败时无线保持关闭，可经有线管理。

界面型号统一显示 MX4300；HomeWRK 的实际设备树、分区和升级校验身份仍是 `linksys,homewrk`。

## 包含的功能

- 完整 `wpad-openssl`：SAE、802.11s、802.11r 支持；usteer + LuCI，在运行时启用 hostapd 的 k/v 协调能力。
- WireGuard、TUN、全部 15 个已固定源码提供的 `kmod-nft-*`，含 TPROXY、socket、bridge、netdev、queue、compat、xfrm；另有 NFLOG、`ip-full`、支持 nftset 的 `dnsmasq-full`。
- 只预装代理所需内核与网络支持，代理客户端和订阅由用户自行选择。
- USB3、UAS、ext4、exFAT、块设备挂载；SMB 的 CIFS 客户端与 ksmbd 服务端；NFS v3/v4 客户端、v4 服务端及 LuCI 管理。
- iperf3、tcpdump-mini、conntrack，方便测量和排障。

**usteer 不会自动建立无线回程。** 三台无网线节点仍需设置 802.11s 回程、主路由/桥接节点角色、信道和加密。默认 SSID 用于逐台初始化；漫游网络应设置一致的 SSID 与安全配置，再按需要配置 802.11r。当前未验证三节点回程、终端漫游及无线满载。

Vantage 的附加“防火墙概览”页暂不开放：它按 OpenWrt 25.12 的旧语义推断规则，与本构建 fw4 对否定协议（如 `!tcp`）的处理不同。主题、仪表盘和 LuCI 原生防火墙管理不受影响；避免把该附加页的推断当成实际防火墙结论。

## NSS 的开关与边界

默认 NSS 镜像使用支持 Mesh 的 **NSS 固件 11.4**。在 **网络 → NSS 无线加速** 查看保存的设置、实际运行状态与启动保护状态，保存后重启生效。命令行关闭：

```sh
uci set nss-wifi.general.offload='0'
uci commit nss-wifi
reboot
```

改为 `1` 并重启可恢复。不要在线卸载、重载 ath11k 总线驱动。NSS 无线加速与 PPE 有线流卸载分别控制；关闭 NSS 不等于关闭 PPE。也不承诺 NSS 加速 WireGuard 加密或所有透明代理路径。

启动保护会在正常启动约两分钟后清除标记；若异常启动留下标记，下次使用普通无线驱动。页面提供清除旧标记并在下次启动重试的入口。此保护不等于双内核自动回滚。

## 本地构建

使用普通用户在 Linux 上编译。Debian/Ubuntu 所需依赖可按下例安装：

```sh
sudo apt-get update
sudo apt-get install build-essential clang flex bison g++ gawk gcc-multilib \
  gettext git libncurses-dev libssl-dev libelf-dev python3 python3-setuptools \
  rsync swig unzip zlib1g-dev file wget curl cpio patch perl pkgconf \
  time bzip2 xz-utils zstd kmod

git clone https://github.com/RC-CHN/mx4200-immortalwrt.git
cd mx4200-immortalwrt
python3 scripts/build_local.py nss all --work "$HOME/mx4300-build" -j 32
python3 scripts/build_local.py baseline all --work "$HOME/mx4300-build" -j 32
python3 scripts/verify_local.py all --work "$HOME/mx4300-build"
```

ARM64 主机无需 `gcc-multilib`。至少预留 30 GiB；两套完整构建建议预留 80 GiB 以上，实际需求随缓存与归档增长。按 CPU 和内存调整 `-j`；52 核 / 104 线程、64 GiB 主机使用两套各 `-j32`，合计最多 64 个编译任务。可同时运行两条构建命令，下载缓存与构建目录相互独立。

`all` 可替换为 `prepare`、`download`、`toolchain`、`compile` 或 `collect`。默认继承代理环境变量，也可用 `--proxy http://HOST:PORT` 或 `--no-proxy`。大型源码、日志、签名密钥和产物均写入 `--work`，不要提交该目录。

构建入口为 [scripts/build_local.py](scripts/build_local.py)，版本锁为 [local/sources.lock.json](local/sources.lock.json)，通用配置为 [local/mesh.config](local/mesh.config)。本地构建不执行 `user/default/custom.sh`。

- `artifacts/<variant>/bin/targets/qualcommax/ipq807x/`：各机型的临时启动、安装和升级镜像。
- `artifacts/<variant>/bin/packages/`：同次构建的软件包仓库。
- `artifacts/<variant>/build-record/`：源码锁、解析配置、定制文件、模块缓存记录、镜像校验报告和仓库公钥。
- `logs/`：构建日志。旧产物应先归档，选择镜像时以当前 `profiles.json` 为准。

使用同次构建的 kmod 包，不能强装其他 snapshot 的模块。构建脚本先核对实际内核 ABI，再决定是否重编外置模块；仅看版本字符串或 vermagic 不能证明缓存正确。定制覆盖文件也有归属记录，删除旧主题会同步清理，而遇到手动改过的文件会停止，不直接覆盖。

旧滚动构建工作流保留为手动入口，**不生成本 README 的固定 r6 配置，也不再定时运行**；其说明见 [历史上游 README](docs/upstream-README.md)。新的轻量 CI 检查定制构建脚本；完整固件使用上述本地入口。

## 刷机、验证与许可

先阅读 [安装与恢复要点](docs/homewrk-recovery.md) 和 [测试记录](docs/validation.md)。首次写 NAND 前必须核实身份、离线保存完整分区备份、验证恢复入口，并先从内存启动待刷镜像。已经运行兼容 ImmortalWrt 后通常可通过 LAN / LuCI / SSH 升级；TTL 留作启动失败时的恢复手段。

r5 曾在一台 HomeWRK 完成 NAND 安装、保留配置网络升级、NSS 开关/启动保护和有线负载测试。**r6 的主题与 usteer 改动在本地构建和检查，不把 r5 的实机结果当作 r6 已经实机验收。** 原始 NAND、设备密钥、串口记录和真实设备截图不进入公开仓库。

本仓库保留 [GPLv3 许可文本](LICENSE)。包含与引用的各项目按各自许可分发，详见 [第三方来源与修改说明](THIRD_PARTY_NOTICES.md)。NSS 固件为上游提供的二进制固件，使用自身发行许可；整套镜像并非所有组件都采用同一许可。
