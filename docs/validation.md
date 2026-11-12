# 构建与验证记录

记录日期：2026-11-12。r6 的固定配置见 `local/sources.lock.json`；完整镜像元数据与解包校验结果见 [r6-artifacts.json](r6-artifacts.json)。这里明确区分静态/本地检查与真实设备测试。

## r6：Vantage + usteer

NSS 与 baseline 均成功编译，各生成 HomeWRK、MX4300 两种布局，每种三个镜像，共 12 个镜像。实际解包四个 sysupgrade，确认：

- Linux 6.18.60，内核包 ABI `6.18.60~6cb93a1075ad7565cb686dc30128496a-r1`，外置模块缓存记录匹配；AArch64 程序及关键 `.ko` 已核对。
- Vantage 主题、仪表盘、两份中文翻译存在，现代 CSS 与固定上游文件完全一致，没有被旧压缩器破坏；Argon 包与定制模板已移除。
- 默认配置包含 usteer 启用、LAN 协调及保留配置升级保护；SMB/NFS 不自动开启；WireGuard、TUN、USB3、15 个 nft 扩展及共享客户端/服务端齐全。
- NSS 版具有 NSS 驱动及 11.4 固件，默认 `offload=1`；baseline 不含该无线 NSS 驱动。
- 所有定制文件的内容、执行权限、设备支持列表、镜像长度与 SHA-256 均通过检查。
- Vantage 附加防火墙概览入口未暴露；仪表盘与 LuCI 原生防火墙管理保留。

本机产物的 sysupgrade 大小与 SHA-256：

| 版本 | 设备布局 | 字节数 | 大小 | SHA-256 |
| --- | --- | ---: | ---: | --- |
| nss | `linksys_homewrk` | 22,057,231 | 21.04 MiB | `61c16baffabe97c2ecca3e57398b4bf8ceeb114ba7445858d89ea983cf4a09b3` |
| nss | `linksys_mx4300` | 22,067,469 | 21.05 MiB | `3f0f99b57c9287d7c5a371b0a5bc2f68487a584ceec51a37c664dc2ec14a00c5` |
| baseline | `linksys_homewrk` | 21,330,191 | 20.34 MiB | `9d8a73bf95938f159c42bfb60c80f334b37eedcd08c89d8e6714e45989c27624` |
| baseline | `linksys_mx4300` | 21,340,429 | 20.35 MiB | `ac83873f1a77bb4955354de4be8047f6cee62c99cc1bf5d59bf3236de2d7475d` |

这些哈希标识本机这一轮构建。不同签名密钥、宿主工具或构建环境可能影响输出，不承诺在任意机器逐字节复现。源码和包版本固定，可重新构建相同功能配置。二进制、配套 APK、公开构建记录和对应源码归档已提供为 [r6 预发布版](https://github.com/RC-CHN/mx4200-immortalwrt/releases/tag/mx4300-r6)，尚未经过 r6 实机验收。Release 的 `SHA256SUMS` 覆盖全部附件。

### 检查命令

```sh
python3 -m unittest tests.test_local_overlay tests.test_homewrk_dts \
  tests.test_kernel_module_cache tests.test_build_schedule \
  tests.test_official_migration tests.test_shared_profile
python3 scripts/verify_local.py all --work "$HOME/mx4300-build"
python3 scripts/check_vantage.py --work "$HOME/mx4300-build"
```

最后一项需 Node.js、GNU gettext、Perl，读取已经编译的 NSS 镜像与固定 feed，不接触路由器。其模板测试引擎不能直接读取 ucode 字节码，因此从同次固定 LuCI feed 提供对应的模板源码。
仓库的设备树测试还需 `device-tree-compiler`（含 `dtc`、`fdtget`、`fdtput`）；包含旧工作流测试时需 Python 的 PyYAML。

- 本次相关仓库测试：23 项，22 通过、1 项上游条件跳过。
- Vantage 测试：470 通过、4 条件跳过；另外明确排除 1 项旧 fw4 否定协议语义测试，其对应附加页面已从固件菜单移除。没有修改实际防火墙去迎合旧测试。
- 登录/模板安全检查：10 通过，保留 2 项上游 LuCI 核心的 TODO（匿名 404 的页面树数据及脚本 JSON 转义）。本地标题测试确认主机名在标题与标题栏各出现一次，并保留原有恶意输入和权限检查。
- ACL 检查 20 通过，DOM 检查零违规，主题树地址扫描零发现，翻译模板与目录一致。
- 上游 MAC 校验测试在原始 v1.0.19 + 当前 ucode 下出现换行边界差异；本地覆盖文件拒绝非法字符后，对应完整 RPC 测试通过。

也运行过继承仓库的 350 项旧测试：本次调整后，剩余 7 项旧缓存/HomeProxy 测试问题在未修改的 r5 提交 `55f9002` 上逐项复现（缓存祖先路径/键、损坏压缩流用例和旧 `FORBIDDEN_PACKAGES` 导入）。它们属于旧滚动构建路径，不被固定版本本地构建入口调用。没有把全仓库旧测试描述为全部通过；新的 CI 运行定制构建的回归检查。

r6 未刷入测试设备 NAND，也未以 r6 做无线/有线负载测试。没有完整的 Vantage 回放录制，因此本次没有把测试替身当作真实路由器的 UI 验收或截图。

## r5 及此前的 HomeWRK 实机结果

一台已核实为 `linksys,homewrk` 的设备，2 GiB RAM、1 GiB NAND。下列数字来自此前真实测试，只作为同一内核/NSS 基础的历史证据，不能替代 r6 验收。

| 检查 | 结果与范围 |
| --- | --- |
| r4 内存启动有线端点吞吐 | 单向约 941 Mbps；同时双向合计约 935 Mbps；端点测试不等于 NAT 或无线 NSS 测试 |
| 隔离 VLAN NAT 测试 | 双方向分别约 931 Mbps，0 TCP 重传，conntrack 确认 `[HW_OFFLOAD]`；这是有线 PPE 证据 |
| WireGuard 加密流量 | 分别约 543 / 584 Mbps；发送方向存在重传，不宣称 NSS 加速加密 |
| r5 NAND 最终负载 | 30 秒、4 流同时双向约 926 Mbps；CPU 约 74%，没有发现内核崩溃 |
| NSS 开/关/保护 | 实际重启测试开、关以及模拟遗留保护标记；NSS 启动时 core 状态为 1、固件 11.4，正常启动清除标记 |
| 三频与 Mesh 接口 | 三个 AP 启动；k/v/r 配置和 SAE 802.11s 接口可建立，但没有第二节点流量 |
| USB | 已识别 USB3 5000 Mbps；曾实际从救援 U 盘启动 |
| 网络升级 | r4 → r5 经 LAN/SSH 保留配置，密码、网络、服务状态和自定义主机名探针保留；没有用 TTL 执行升级命令 |
| NAND 校验 | kernel/root 与镜像哈希一致，其余 23 个 MTD 分区的 ECC 数据与原始备份一致 |
| r5 界面 | Argon 时期的桌面/手机、自动明暗、登录、NSS 与网络页面检查通过；不作为 Vantage 截图证据 |

尚未验证三节点无线回程、移动终端漫游、真实 PPPoE 线路、无线饱和吞吐和长期稳定性。原始设备日志、NAND 备份、密码文件和真实网络截图只在本地保存。
