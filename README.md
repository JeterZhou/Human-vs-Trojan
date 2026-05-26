# HumanVsTrojan

HumanVsTrojan 是一个基于 Python 的攻防模拟小游戏。项目包含单机/界面版本和局域网联机版本，游戏逻辑主要在 `HVT_final.py` 中，图形界面与联机启动入口在 `HVT_UI.py` 和 `HVT_LAN.py` 中。

## 文件说明

```text
HumanVsTrojan/
├── HVT_final.py                 # 核心游戏逻辑
├── HVT_UI.py                    # 本地 GUI 界面版本
├── HVT_LAN.py                   # 局域网联机 GUI 版本，推荐启动入口
├── HVT统一启动器_windows.bat     # Windows 一键启动脚本
├── HVT统一启动器_mac.command     # macOS 一键启动脚本
├── .gitignore                    # Git 忽略规则
└── README.md                    # 项目说明文件
```

## 运行环境

建议使用 Python 3.10 或以上版本。

项目需要以下 Python 库：

```bash
networkx
matplotlib
```

`tkinter` 通常随 Python 自带，用于显示图形界面。如果程序提示缺少 `tkinter`，请重新安装带 Tk 支持的 Python。

## Windows 运行方法

1. 解压项目压缩包。
2. 进入 `HumanVsTrojan` 文件夹。
3. 双击运行：

```text
HVT统一启动器_windows.bat
```

启动器会自动创建 `.venv` 虚拟环境，并安装所需依赖。

## macOS 运行方法

1. 解压项目压缩包。
2. 进入 `HumanVsTrojan` 文件夹。
3. 如果第一次运行提示没有权限，请在终端中执行：

```bash
chmod +x HVT统一启动器_mac.command
```

4. 双击运行：

```text
HVT统一启动器_mac.command
```

启动器会自动创建 `.venv` 虚拟环境，并安装所需依赖。

## 手动运行方法

也可以不用启动器，手动安装依赖后运行：

```bash
pip install networkx matplotlib
python HVT_LAN.py
```

如果只想打开本地 GUI 版本，可以运行：

```bash
python HVT_UI.py
```

## 局域网联机说明

运行 `HVT_LAN.py` 后，可以在界面中选择 Host 或 Join。

一般流程：

1. 一台电脑选择 Host，作为主机。
2. 另一台电脑选择 Join，输入主机的局域网 IP 地址。
3. 双方选择攻击方或防守方后开始游戏。

两台电脑需要连接在同一个局域网内，例如同一个 Wi-Fi。


## 常见问题

### 1. 双击启动器后窗口闪退怎么办？

可以打开命令行或终端，进入项目文件夹后手动运行启动器，这样可以看到错误信息。

Windows：

```bat
HVT统一启动器_windows.bat
```

macOS：

```bash
./HVT统一启动器_mac.command
```

### 2. 提示找不到 Python 怎么办？

请先安装 Python 3，并确认安装时勾选了“Add Python to PATH”（Windows）。

### 3. 提示缺少 networkx 或 matplotlib 怎么办？

可以手动安装：

```bash
pip install networkx matplotlib
```

