# nodejs-npm-roothide

在 **Dopamine-roothide**（以及普通 rootless）越狱的 iOS 设备上，一条命令装好 **Node.js 18.20.4 + npm 10.9.2**。

```
com.maslch.nodejs-npm  ·  iphoneos-arm64e  ·  iOS 15+
```

---

## 为什么需要这个包

如果你在 roothide 设备上试过 `apt install nodejs`，大概率会遇到下面三个问题之一。

### 1. 源里根本没有

roothide 的 Procursus 分支是官方 Procursus 的**子集**，实测只有 742 个包：

| 索引 | 包总数 | 编译器 / 运行时 |
|---|---|---|
| `roothide.github.io/procursus`（arm64e） | 742 | 只有 `ld64` |
| `apt.procurs.us`（arm64，rootless） | 1400+ | 有 clang / llvm，但架构不匹配 |

Node.js 和 npm 都不在其中。`apt-cache policy nodejs` 会直接返回 `Candidate: (none)`。

### 2. 上游包的架构是 arm64，不是 arm64e

`io.github.imcynic.nodejs` 的 control 里写的是 `Architecture: iphoneos-arm64`，靠 `com.roothide.patcher` 在安装时改写。这个转换不是 100% 可靠，官方描述里也写着 "not work for all packages"。

本包直接标 `iphoneos-arm64e`，patcher 无需介入。

### 3. 上游的启动器在 roothide 下必然失败

```sh
#!/var/jb/usr/bin/zsh
V8_FLAGS="--no-wasm-code-gc --no-opt --no-sparkplug --single-threaded --liftoff --no-wasm-tier-up"
exec "$NODE_BIN" $V8_FLAGS "$@"
```

两个问题：

- **zsh 不对未加引号的变量做分词**，整串被当成单个参数传给 node，报 `bad option: --no-wasm-code-gc --no-opt …`
- 这组 V8 参数在 node 18 上本来就不成立（`--no-sparkplug`、`--no-wasm-code-gc` 均非合法 CLI 参数）

结果就是：包装上了，`node -v` 永远报错。

---

## 安装

### 通过 APT 源（推荐）

本包发布在 [MasLCH Repo](../../README.md) 里，源地址：

```
https://maslch957.github.io/MasLCH-Repo/
```

**Sileo**：`源` → `+` → 粘贴上面地址 → 添加后搜索 `Node.js + npm (roothide)`。

**命令行**：

```sh
# 1. 导入签名公钥
curl -fsSL https://maslch957.github.io/MasLCH-Repo/key.asc \
  -o /etc/apt/trusted.gpg.d/maslch-repo.asc

# 2. 添加源
echo 'deb [signed-by=/etc/apt/trusted.gpg.d/maslch-repo.asc] https://maslch957.github.io/MasLCH-Repo/ stable main' \
  > /etc/apt/sources.list.d/maslch-repo.list

# 3. 安装
apt update
apt install com.maslch.nodejs-npm
```

签名公钥指纹：`8DF5 053C B022 0986 4265 425E 7CA2 03CF 6711 09F3`

> 若不想导入公钥，也可以把源写成 `deb [trusted=yes] ...`，apt 会跳过签名校验（不推荐）。

### Sileo / Filza（手动装 deb）

下载 Releases 里的 `.deb`，用 Sileo 打开安装即可。

### 命令行（手动装 deb）

```sh
dpkg -i nodejs-npm_18.20.4-1_iphoneos-arm64e.deb
```

安装后 `node`、`npm`、`npx` 立即可用；交互式 SSH 登录时 `PATH` 已自动包含 `/usr/local/bin`。

> 若通过 `ssh host 'cmd'` 这种非交互方式执行，sshd 不会读 `/etc/profile`，需要自己 `export PATH="/usr/local/bin:$PATH"` 或写全路径。

---

## 验证

```sh
node -v                 # v18.20.4
npm  -v                 # 10.9.2
npx  -v                 # 10.9.2

node -p 'process.version + " / " + process.arch'
# v18.20.4 / arm64

mkdir /tmp/t && cd /tmp/t && npm init -y && npm i left-pad
node -e 'console.log(require("left-pad")("7",3,"0"))'
# 007
```

---

## 原理：为什么启动器要这么写

roothide 的核心是把越狱根目录**随机化**，例如 `.jbroot-463D314638170B28`，让 App 检测不到 `/var/jb`。

问题在于，**路径虚拟化不是全局的**：

- `sh`、`ls`、`dpkg`、`curl` 这些被 patch 过的进程，看到的 `/usr` 是 jbroot 里的那一份
- 而 **node 二进制看到的是真实文件系统**，在它眼里 `/usr/local` 和 `/var/jb` 都不存在

所以任何传给 node 的路径都必须是真实绝对路径。但 jbroot 的目录名带随机后缀，写死会在重装越狱后失效。

启动器的做法是让 node 自己回答：

```sh
cd /
ROOT=$(node -e 'process.stdout.write(process.cwd())')   # 得到 jbroot 真实路径
exec "$ROOT/.jbroot/usr/local/lib/nodejs/node" "$@"
```

这样随机后缀变了也能自动适配，不需要改任何脚本。

npm 的启动器在此基础上多做了三件事：把 `npm_config_prefix`、`npm_config_cache`、`HOME` 都指向真实路径——因为 npm 跑在 node 里，它解析这些路径时同样走真实文件系统。

---

## 从源码构建

本仓库只包含**打包脚本**，不包含 74 MB 的 node 二进制。构建需要在已部署好 node + npm 的设备上进行：

```sh
# 把整个 MasLCH-Repo 拷到设备
scp -r MasLCH-Repo root@<device-ip>:/var/mobile/

# 在设备上执行
ssh root@<device-ip>
cd /var/mobile/MasLCH-Repo/projects/nodejs-npm-roothide
VERSION=18.20.4-1 sh build.sh
```

产物：`/var/mobile/nodejs-npm_18.20.4-1_iphoneos-arm64e.deb`

`dpkg-deb` 自带 zlib/lzma 支持，**不需要**设备上有 `gzip` 或 `xz` 二进制。

`--root-owner-group` 参数不能省，否则从 `/usr/local` 复制来的文件会带着 `501/mobile` 属主进包。

---

## 发布

本包是 [MasLCH Repo](../../README.md) 里的一个项目。源由仓库根目录的 `tools/build-repo.py` 统一生成，结构与发布流程见仓库首页。

发布新版本时，在仓库根目录执行：

```sh
python tools/build-repo.py \
    --debs dist/nodejs-npm_<version>_iphoneos-arm64e.deb \
    --out docs \
    --key /path/to/private-key.asc
```

> **签名私钥不在仓库内。** 它是 `8DF5053CB02209864265425E7CA203CF671109F3` 对应的私钥，请自行离线备份。丢失后旧客户端会因公钥变更而报错，需要重新导入 `key.asc`。

---

## 已知限制

| 限制 | 说明 |
|---|---|
| 不包含 iOS SDK | 能跑 JS，但不能 `node-gyp` 编译原生模块 |
| 依赖真实路径解析 | 启动器每次多两次 node 启动，单次约 +100 ms |
| 与上游包冲突 | `Conflicts` + `Replaces: io.github.imcynic.nodejs`，安装时会替换掉上游包 |

---

## 卸载

```sh
dpkg -r com.maslch.nodejs-npm     # 保留配置
dpkg -P com.maslch.nodejs-npm     # 连 postrm 一起清理
```

---

## 致谢与许可

- **Node.js 的 iOS arm64 构建来自 [imcynic](https://github.com/imcynic/nodejs-ios)**，本仓库只做重新打包，未从源码编译。
- Node.js 采用 MIT 许可，npm 采用 Artistic License 2.0，完整文本见 [`licenses/`](licenses/)。
- 本仓库的打包脚本与启动器采用 MIT 许可，见 [`LICENSE`](LICENSE)。
- 详细归属说明见 [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)。

---

## English

Repackages Node.js 18.20.4 + npm 10.9.2 for **Dopamine-roothide** on iOS 15+.

The stock upstream package ships an `iphoneos-arm64` build whose launcher relies
on zsh word-splitting that never worked, and roothide's own Procursus subset has
no node/npm at all. This package targets `iphoneos-arm64e` natively and replaces
the launcher with one that resolves the randomized `jbroot` path at runtime, so
it survives re-jailbreaking.

Node.js binary by [imcynic](https://github.com/imcynic/nodejs-ios) (MIT);
npm by npm, Inc. (Artistic-2.0). Packaging scripts MIT.
