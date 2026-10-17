# MasLCH Repo

MasLCH957 的越狱软件源，主要面向 **Dopamine-roothide / rootless** 的 iOS 设备。

## 源地址

```
https://maslch957.github.io/MasLCH-Repo/
```

签名公钥指纹：`8DF5 053C B022 0986 4265 425E 7CA2 03CF 6711 09F3`

## 添加源

**Sileo**：`源` → `+` → 粘贴上面的地址 → 添加。

**命令行**：

```sh
curl -fsSL https://maslch957.github.io/MasLCH-Repo/key.asc \
  -o /etc/apt/trusted.gpg.d/maslch-repo.asc

echo 'deb [signed-by=/etc/apt/trusted.gpg.d/maslch-repo.asc] https://maslch957.github.io/MasLCH-Repo/ stable main' \
  > /etc/apt/sources.list.d/maslch-repo.list

apt update
```

## 包列表

| 包名 | 版本 | 架构 | 说明 |
|---|---|---|---|
| `com.maslch.nodejs-npm` | 18.20.4-1 | `iphoneos-arm64e` | Node.js 18.20.4 + npm 10.9.2，启动器自适配随机化的 jbroot 路径 |

各项目的详细说明、构建方式与许可信息，见 `projects/<项目名>/`。

## 仓库结构

```
MasLCH-Repo/
├── projects/                各项目的源码（打包脚本、启动器、文档）
│   └── nodejs-npm-roothide/
├── tools/
│   └── build-repo.py        生成索引并签名
└── docs/                    GitHub Pages 根目录 = APT 源本身
    ├── dists/stable/        Release / InRelease / Packages
    ├── pool/main/           .deb 存放位置
    └── key.gpg, key.asc     签名公钥
```

## 维护

新增一个包时，把它的 `.deb` 放进 `dist/`，然后：

```sh
python tools/build-repo.py \
    --debs dist/*.deb \
    --out docs \
    --key /path/to/private-key.asc
```

脚本会重新生成 `Packages`、`Release`，并签名 `InRelease` / `Release.gpg`。它不依赖 `dpkg-scanpackages`，也不需要 `gpg`（签名用纯 Python 的 pgpy 实现），因此在 Windows / macOS / Linux 上都能直接跑。

> `Release` 里的 `Date` 每次构建都会变，所以每次发版都必须重新签名，不能复用旧签名。

## 许可

- 仓库脚本（`tools/`）采用 MIT，见 [`LICENSE`](LICENSE)。
- 各项目内的第三方组件归属见对应项目的 `THIRD-PARTY-NOTICES.md`。
