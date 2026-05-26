# HumanVsTrojan
HumanVsTrojan is a Python-based offensive and defensive simulation mini-game. The project includes a single-player/UI version and a LAN multiplayer version. The core game logic is in `HVT_final.py`, and the graphical interface and LAN multiplayer launch entrances are in `HVT_UI.py` and `HVT_LAN.py`.

# HumanVsTrojan
HumanVsTrojan 是一个基于 Python 的攻防模拟小游戏。项目包含单机/界面版本和局域网联机版本，游戏逻辑主要在 `HVT_final.py` 中，图形界面与联机启动入口在 `HVT_UI.py` 和 `HVT_LAN.py` 中。

## File Description
```text
HumanVsTrojan/
├── HVT_final.py                 # Core game logic
├── HVT_UI.py                    # Local GUI version
├── HVT_LAN.py                   # LAN multiplayer GUI version (recommended launch entry)
├── HVT统一启动器_windows.bat     # One-click startup script for Windows
├── HVT统一启动器_mac.command     # One-click startup script for macOS
├── .gitignore                   # Git ignore rules
└── README.md                    # Project description file
```

## 文件说明
```text
HumanVsTrojan/
├── HVT_final.py                 # 核心游戏逻辑
├── HVT_UI.py                    # 本地 GUI 界面版本
├── HVT_LAN.py                   # 局域网联机 GUI 版本，推荐启动入口
├── HVT统一启动器_windows.bat     # Windows 一键启动脚本
├── HVT统一启动器_mac.command     # macOS 一键启动脚本
├── .gitignore                   # Git 忽略规则
└── README.md                    # 项目说明文件
```

## Runtime Environment
Python 3.10 or higher is recommended.

The project requires the following Python libraries:
```bash
networkx
matplotlib
```

`tkinter` usually comes with Python by default and is used to display the graphical interface. If the program prompts that `tkinter` is missing, please reinstall Python with Tk support.

## 运行环境
建议使用 Python 3.10 或以上版本。

项目需要以下 Python 库：
```bash
networkx
matplotlib
```

`tkinter` 通常随 Python 自带，用于显示图形界面。如果程序提示缺少 `tkinter`，请重新安装带 Tk 支持的 Python。

## Running Method for Windows
1. Unzip the project compressed package.
2. Enter the `HumanVsTrojan` folder.
3. Double-click to run:
```text
HVT统一启动器_windows.bat
```
The launcher will automatically create a `.venv` virtual environment and install the required dependencies.

## Windows 运行方法
1. 解压项目压缩包。
2. 进入 `HumanVsTrojan` 文件夹。
3. 双击运行：
```text
HVT统一启动器_windows.bat
```
启动器会自动创建 `.venv` 虚拟环境，并安装所需依赖。

## Running Method for macOS
1. Unzip the project compressed package.
2. Enter the `HumanVsTrojan` folder.
3. If you are prompted with no permission when running for the first time, execute the following command in the terminal:
```bash
chmod +x HVT统一启动器_mac.command
```
4. Double-click to run:
```text
HVT统一启动器_mac.command
```
The launcher will automatically create a `.venv` virtual environment and install the required dependencies.

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

## Manual Running Method
You can also run the project without the launcher by manually installing the dependencies first:
```bash
pip install networkx matplotlib
python HVT_LAN.py
```
If you only want to open the local GUI version, run:
```bash
python HVT_UI.py
```

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

## LAN Multiplayer Instructions
After running `HVT_LAN.py`, you can select Host or Join in the interface.

General process:
1. One computer selects Host to act as the server.
2. The other computer selects Join and enters the LAN IP address of the server.
3. Both sides select the attacker or defender role and then start the game.

The two computers need to be connected to the same LAN (e.g., the same Wi-Fi network).

## 局域网联机说明
运行 `HVT_LAN.py` 后，可以在界面中选择 Host 或 Join。

一般流程：
1. 一台电脑选择 Host，作为主机。
2. 另一台电脑选择 Join，输入主机的局域网 IP 地址。
3. 双方选择攻击方或防守方后开始游戏。

两台电脑需要连接在同一个局域网内，例如同一个 Wi-Fi。

## Frequently Asked Questions

### 1. What to do if the window crashes after double-clicking the launcher?
Open the command prompt or terminal, enter the project folder, and run the launcher manually to view the error information.

Windows:
```bat
HVT统一启动器_windows.bat
```
macOS:
```bash
./HVT统一启动器_mac.command
```

### 2. What to do if Python is not found?
First install Python 3, and make sure to check "Add Python to PATH" during installation (Windows).

### 3. What to do if networkx or matplotlib is missing?
You can install them manually:
```bash
pip install networkx matplotlib
```

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


