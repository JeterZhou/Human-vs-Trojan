# HumanVsTrojan

HumanVsTrojan is a Python and NetworkX based offensive and defensive simulation mini-game on graphs. The game abstracts computers, servers, or network assets as nodes in an undirected graph, and abstracts communication relationships as edges. The Trojan/Virus side tries to spread, hide, activate infected nodes, and launch attacks. The Human/Defender side tries to reinforce, scan, clean, recover, and counter the attacker's C2 server.

The project includes a local GUI version and a LAN multiplayer version. The core game logic is mainly implemented in `HVT_final.py`, while the graphical interface and launch entrances are mainly provided by `HVT_UI.py` and `HVT_LAN.py`.

> Note: This README is organized according to the game rule document and focuses on gameplay, rules, and running instructions. If there are minor differences between this README and the actual code/UI parameters, please follow the current code and UI implementation.

---

## Project Structure

```text
HumanVsTrojan/
├── HVT_final.py                 # Core game logic
├── HVT_UI.py                    # Local GUI version
├── HVT_LAN.py                   # LAN multiplayer GUI version; recommended launch entry
├── HVT统一启动器_windows.bat     # One-click launcher for Windows
├── HVT统一启动器_mac.command     # One-click launcher for macOS
├── .gitignore                   # Git ignore rules
└── README.md                    # Project description file
```

## Runtime Environment

Python 3.10 or higher is recommended.

Main dependencies:

```bash
networkx
matplotlib
```

`tkinter` is usually included with Python and is used for the graphical interface. If the program reports that `tkinter` is missing, please reinstall Python with Tk support.

## Quick Start

### Windows

1. Unzip the project package.
2. Enter the `HumanVsTrojan` folder.
3. Double-click:

```text
HVT统一启动器_windows.bat
```

The launcher will automatically create a `.venv` virtual environment and install the required dependencies.

### macOS

1. Unzip the project package.
2. Enter the `HumanVsTrojan` folder.
3. If permission is denied during the first launch, run the following command in Terminal:

```bash
chmod +x HVT统一启动器_mac.command
```

4. Double-click:

```text
HVT统一启动器_mac.command
```

The launcher will automatically create a `.venv` virtual environment and install the required dependencies.

### Manual Run

You can also run the project manually without using the launcher:

```bash
pip install networkx matplotlib
python HVT_LAN.py
```

To run only the local GUI version:

```bash
python HVT_UI.py
```

## LAN Multiplayer Instructions

After running `HVT_LAN.py`, choose **Host** or **Join** in the interface.

General process:

1. One computer chooses **Host** and acts as the server.
2. The other computer chooses **Join** and enters the LAN IP address of the host.
3. Both players choose their roles: Attacker or Defender.
4. After both sides are ready, the game starts.

Both computers must be connected to the same LAN, such as the same Wi-Fi network.

## Game Background

The game world can be understood as a three-layer model:

- **Map Layer**: An undirected graph. Nodes represent network assets, and edges represent connections. The map layer itself does not actively perform actions.
- **Virus Layer / Attacker**: The attacker owns a C2 server that does not exist as a normal node on the graph. The C2 server gives commands to infected nodes. The virus only has local visibility around its controlled nodes.
- **Defense Layer / Defender**: The defender can use global topology and node value information, but does not know the exact virus locations unless they are discovered through scans, honeypots, or traffic analysis.

The defender aims to protect the map and stop the virus from spreading, stealing data, damaging nodes, or launching large-scale attacks. The attacker aims to use local propagation and C2 commands to reach infection, damage, or data theft objectives under limited resources.

## Core Concepts

### Node States

Nodes in the game may have the following states:

| State | Meaning |
| --- | --- |
| Neutral Node | Not controlled by either side. |
| Defender Node | Controlled by the Human/Defender side. It can be reinforced, scanned, shut down, or recovered. |
| Dormant Infected Node | Infected by the virus but not actively exposed. It can still be used as a stepping stone or wait for C2 commands. |
| Active Infected Node | Activated by C2. It can attack, steal data, destroy, ransom, or participate in zombie-swarm attacks. |
| Disabled Node | Destroyed and unavailable. It belongs to neither side until recovered by the defender. |
| Reinforced Node | Strengthened by the defender. Virus infection success is reduced or requires extra effort. |
| Honeypot Node | Disguised as a high-value target. If the virus tries to steal from or ransom it, the virus location is exposed. |

### Graph and Node Value

Maps are generated or managed with NetworkX. Node importance can be estimated using the following metrics:

- **Degree / Hubs**: Nodes connected to many other nodes. They are usually important expansion or defense targets.
- **Betweenness / Bridges**: Nodes that connect different regions. Even if their degree is not high, they may control critical paths.
- **Closeness Centrality**: Nodes with shorter average distances to other nodes are often useful as spreading or defense centers.
- **Eigenvector Centrality**: Nodes connected to other important nodes are also important. Isolated nodes can affect centrality calculations.

These metrics can guide both human tactical decisions and AI heuristic strategies.

## Turn Flow

A recommended turn resolution order is:

1. **Budget/Energy Recovery**: Both sides gain base budget or energy. Controlled nodes may provide extra income.
2. **Defender Preventive Actions**: The defender may reinforce nodes, deploy honeypots, shut down key nodes, and so on.
3. **Attacker Propagation and C2 Commands**: The virus attempts neighbor propagation, remote scan infection, or sends commands to dormant/active infected nodes.
4. **Scan and Clean**: The defender scans suspicious nodes and cleans detected infections.
5. **Attack and Response**: Active infected nodes may attack, steal, destroy, ransom, or launch zombie-swarm attacks. The defender may perform traffic cleaning, restore disabled nodes, or counter C2.
6. **Conflict Resolution**: Resolve cases where both sides choose the same node in the same turn.
7. **Victory Check**: Check whether either side has reached its victory conditions. If not, continue to the next turn.

## Attacker Rules: Trojan / Virus

### Basic Attributes

The attacker has the following resources and constraints:

- **C2 Server**: A special entity outside the graph. It can issue commands such as activation, scanning, attack, stealing, destruction, ransom, and special attacks.
- **Energy `E`**: Similar to a budget. Propagation, scanning, attacks, and special moves consume energy.
- **Local Vision Radius `r`**: The virus can only observe nodes and states within radius `r` around its controlled nodes.
- **Communication Delay**: C2-to-node commands can have a 1-turn delay. A command issued this turn takes effect next turn.
- **Action Limits**: Propagation attempts per turn are limited by `Pmax`, and C2 commands per turn are limited by `Mcmd`.

### Propagation Methods

#### 1. Neighbor Propagation / Local Propagation

The virus attempts to spread from an infected node `u` to an adjacent node `v`. Propagation depends on a simulated user action, such as clicking a malicious link or opening an infected attachment.

Example default rules:

- Infection success rate for an unreinforced node is about `60%`.
- Each propagation attempt costs `cprop` energy. A suggested value is `1`.
- A newly infected node enters the **dormant** state by default and does not immediately perform malicious actions.

#### 2. Remote Scan / Non-neighbor Propagation

The virus can select an infected node as a scanning source and attempt to infect nodes within scanning radius `s`.

Example default rules:

- Scanning radius: `s = 2`.
- Success rate is inversely related to graph distance `d`; for example, `success = beta / d`.
- Longer distance costs more energy; for example, `cscan * d`.

### Dormancy, Activation, and Normal Attack

- **Dormant State**: Newly infected nodes stay dormant. They do not actively expose themselves, but they can receive C2 commands and act as propagation stepping stones.
- **Activation**: C2 can activate dormant nodes and turn them into active infected nodes.
- **Sleep**: Active infected nodes can return to the dormant state to reduce detection risk.
- **Normal Attack**: Active nodes can attack adjacent nodes. A sample success rate is `30%`. If the target is reinforced, the success rate is halved. If the target already has a dormant infection, the attacker may receive an additional success bonus.

### Zombie Swarm / Concentrated Attack

When the number of virus-controlled nodes reaches a threshold, such as `theta_zombie = 20%` of all nodes, the attacker can launch a zombie-swarm attack.

Example rules:

- The attack can be used at most `Zmax` times per game.
- The target can be any node and does not have to be adjacent.
- All active infected nodes, or all virus nodes depending on the chosen rule, join the attack.
- Attack strength can be calculated as `number of participating nodes * unit attack power`.
- If the attack strength exceeds the target defense strength, the target may be captured, disabled, or converted from defender control to virus control.
- The move consumes a large amount of energy, and participating nodes enter a 1-turn cooldown.

### Non-propagation Malicious Actions

Active infected nodes can perform the following actions. Each active node can perform at most one action per turn.

| Action | Description |
| --- | --- |
| Data Theft | Steals a percentage of the remaining data value of a node. The virus wins if cumulative stolen value reaches a threshold. |
| Node Destruction | Turns a node into the disabled state and weakens defender infrastructure. |
| Ransom | Forces the defender to choose between paying resources or restoring from backup. |

## Defender Rules: Human / Defender

### Information Advantage and Limitations

The defender knows the full graph topology and node values, making centrality-based strategies useful. However, the defender does not know the exact virus positions by default and must discover them through scanning, honeypots, or traffic analysis.

### Preventive Actions

Preventive actions are resolved before the attacker's main actions.

| Action | Effect |
| --- | --- |
| Reinforce Node | Increases node defense strength. Virus propagation may require extra turns or have about 30% lower success rate. |
| Deploy Honeypot | Disguises a node as a high-value target. If the virus tries to steal from or ransom it, the virus is exposed. |
| Shut Down Node | Temporarily sacrifices node availability to prevent the node from being further used by the attacker. |

### Scan and Clean

| Action | Effect |
| --- | --- |
| Scan | Selects nodes to inspect. It reveals dormant infections but does not directly remove them. |
| Targeted Clean | Removes virus from a detected node and restores it to defender control. |
| Recapture Node | Attempts to regain control of a virus-controlled node. The rule can define success rate and cost. |
| Counter C2 | After locating the C2 server, the defender can silence it for several turns. |

### Responsive Actions

Responsive actions are usually performed after virus attacks.

| Action | Effect |
| --- | --- |
| Restore Disabled Node | Spends resources to recover a destroyed node as neutral or defender-controlled. |
| Refuse Ransom + Backup Recovery | Refuses to pay ransom and restores the node from backup. The node is unavailable during recovery. |
| Traffic Cleaning | Counters zombie-swarm or DDoS attacks by reducing attack success rate or protecting the target. |
| Traceback Counterattack | After successfully locating C2, the defender may launch a high-cost counterattack to destroy it. |

### Defender Budget Reference

Example costs from the rule design:

| Action | Example Cost |
| --- | ---: |
| Reinforce one node | 1 |
| Shut down one node | 2 |
| Targeted clean | 3 |
| Counter C2 | 5 |
| Global scan | 1, covering about 10% of nodes |

Both sides may recover a base budget each turn, such as `+2`. Successfully defended nodes and virus-controlled nodes may also provide extra budget to their corresponding side. Once a node is recaptured, the related extra income disappears.

## C2 Silence Rule

When the C2 server is countered by the defender and enters a silent state, all actions requiring C2 commands are disabled, except neighbor propagation.

Disabled actions include:

- Remote scanning
- Activation or sleep
- Normal attack commands
- Data theft, destruction, and ransom
- Zombie swarm or precision strike

This makes C2 a key weakness for the attacker and an important strategic target for the defender.

## Conflict Resolution Rules

Recommended same-turn conflict rules:

1. **Prevention First**: Defender preventive actions, such as reinforcement, shutdown, and honeypots, are resolved first and affect the attacker's success rate in the same turn.
2. **Successful Attack Beats Clean**: If the virus successfully captures a node in the same turn that the defender tries to clean it, the clean action fails, the node belongs to the attacker, and both sides still pay their costs.
3. **Scan Is Not Clean**: Scanning only reveals virus positions and does not directly change node ownership.
4. **Disabled Nodes Must Be Recovered First**: Disabled nodes cannot be used as normal nodes until recovered.
5. **Insufficient Resources Cause Failure**: If a side does not have enough budget or energy, the action is not executed.

## Victory Conditions

The game can support one or multiple victory conditions.

### Attacker Victory

- Virus-controlled nodes reach a threshold, such as at least `1/3` of all nodes.
- Disabled nodes reach a threshold, causing large-scale infrastructure failure.
- Cumulative stolen data reaches a percentage of total data value, such as `30%`.
- A special attack objective is completed on key nodes.

### Defender Victory

- The virus fails to reach any victory condition within `T` turns.
- All virus nodes are cleaned and C2 is destroyed or silenced for a long period.
- The virus has insufficient energy and cannot act for several consecutive turns.
- The defender wins by cost advantage, forcing the virus to exceed a total-cost threshold.

## Strategy Suggestions

### Defender

- Prioritize Hubs and Bridges to prevent fast cross-region virus expansion.
- Deploy honeypots on high-value nodes or suspected attack paths.
- Focus scanning resources around infected neighborhoods or critical paths.
- Locate C2 as early as possible. Once C2 is silenced, the virus loses many advanced actions.
- On 2D grid-like maps or maps with clear local connections, manual defense and key-node blocking are often more valuable.

### Attacker

- Infect high-centrality nodes first to improve future spreading efficiency.
- Stay dormant on bridge nodes and activate them at the right time.
- Avoid exposing too many active nodes too early to reduce the risk of mass cleaning.
- On random graphs or maps with more long-range connections, AI-prioritized scanning and propagation may be more effective.
- Once the zombie-swarm threshold is reached, concentrate attacks on high-value or high-defense-cost targets.

## Experiments and Paper Extension Ideas

The project can support the following research or course-paper tasks:

1. **Basic Model**: Define neutral, defender-controlled, and attacker-controlled nodes in an undirected graph space `V`; design turn flow, conflict resolution, and victory conditions.
2. **Multi-map Simulation**: Run experiments on at least four graph structures, such as 2D grids, random graphs, small-world graphs, scale-free graphs, or 3D random graphs.
3. **Strategy Combination Comparison**: Design at least three pairs of “human strategy + AI strategy” and compare win rates on different maps.
4. **Parameter Sensitivity Analysis**: Study how `kA/kB`, vision radius `r`, propagation capacity `k`, and related parameters affect win rates, and find the threshold where the virus win rate exceeds 50%.
5. **Budget Allocation Experiment**: Compare the best budget split among human manual occupation, AI vision upgrade `r`, and AI propagation upgrade `k`.
6. **Reinforcement Learning Replacement**: Replace heuristic strategy pairs with RL, encode limited vision as a fixed-size input vector, and encode the human player's latest manual action as a tactical signal toward a specific area.

## Useful Strategy and Algorithm Keywords

- Network Centrality Measures
- Firefighter Problem on Graphs
- Information Diffusion in Social Networks
- Game Theory on Graphs
- Heuristic Algorithms for Network Protection
- Monte Carlo Simulation on Graphs
- Reinforcement Learning on Graphs

## Frequently Asked Questions

### 1. What should I do if the window closes immediately after double-clicking the launcher?

Open Command Prompt or Terminal, enter the project folder, and run the launcher manually to view error messages.

Windows:

```bat
HVT统一启动器_windows.bat
```

macOS:

```bash
./HVT统一启动器_mac.command
```

### 2. What should I do if Python is not found?

Install Python 3 first, and make sure to check **Add Python to PATH** during installation on Windows.

### 3. What should I do if `networkx` or `matplotlib` is missing?

Install them manually:

```bash
pip install networkx matplotlib
```

### 4. What should I do if two computers cannot connect in LAN mode?

Please check:

- Whether both computers are on the same LAN or Wi-Fi network.
- Whether the Join side entered the correct LAN IP address of the Host side.
- Whether the system firewall blocked Python or the LAN port.
- Whether the Host side started first and is waiting for connection.

## Development Notes

- Map generation and centrality calculations are recommended to be implemented with `networkx`.
- Win-rate experiments should use Monte Carlo simulation by running many randomized games and averaging the results.
- UI node colors should clearly distinguish neutral, defender-controlled, dormant infected, active infected, disabled, and reinforced nodes.
- When adding new strategies, it is recommended to keep the interface as “strategy function receives the currently visible state and returns an action list,” so heuristic strategies can be replaced by reinforcement-learning strategies more easily.

---

# HumanVsTrojan 中文版

HumanVsTrojan 是一个基于 Python 与 NetworkX 的图论攻防模拟小游戏。游戏把电脑、服务器或网络资产抽象成无向图中的节点，把通信关系抽象成边。Trojan/病毒阵营通过传播、潜伏、激活感染节点和发动攻击来扩张影响力；Human/防守方阵营通过加固、扫描、清除、恢复和反制 C2 来阻止病毒达成目标。

项目包含本地 GUI 版本和局域网联机版本。核心游戏逻辑主要在 `HVT_final.py` 中，图形界面和启动入口主要由 `HVT_UI.py` 与 `HVT_LAN.py` 提供。

> 说明：本 README 根据游戏规则文档整理，重点介绍玩法、规则与运行方式。若 README 与实际代码或 UI 参数存在细节差异，请以当前代码和 UI 实现为准。

---

## 项目结构

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

## 运行环境

建议使用 Python 3.10 或以上版本。

项目主要依赖：

```bash
networkx
matplotlib
```

`tkinter` 通常随 Python 自带，用于显示图形界面。如果程序提示缺少 `tkinter`，请重新安装带 Tk 支持的 Python。

## 快速开始

### Windows

1. 解压项目压缩包。
2. 进入 `HumanVsTrojan` 文件夹。
3. 双击运行：

```text
HVT统一启动器_windows.bat
```

启动器会自动创建 `.venv` 虚拟环境，并安装所需依赖。

### macOS

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

### 手动运行

不使用启动器时，可以手动安装依赖并运行：

```bash
pip install networkx matplotlib
python HVT_LAN.py
```

如果只想打开本地 GUI 版本，可以运行：

```bash
python HVT_UI.py
```

## 局域网联机说明

运行 `HVT_LAN.py` 后，可以在界面中选择 **Host** 或 **Join**。

一般流程：

1. 一台电脑选择 **Host**，作为主机。
2. 另一台电脑选择 **Join**，输入主机的局域网 IP 地址。
3. 双方选择攻击方或防守方角色。
4. 双方准备完成后开始游戏。

两台电脑需要连接在同一个局域网内，例如同一个 Wi-Fi。

## 游戏背景

游戏世界可以理解为三层模型：

- **地图层**：由无向图组成，节点代表网络资产，边代表连接关系。地图层本身不会主动行动。
- **病毒层 / 进攻方**：进攻方拥有一个不作为普通节点存在于图上的 C2 服务器，用来向已感染节点下达指令。病毒只能看到自己控制节点附近的局部信息。
- **防守层 / 防守方**：防守方可以利用全图拓扑和节点价值信息，但默认不知道病毒的准确位置，除非通过扫描、蜜罐或流量分析发现。

防守方的目标是保护地图，阻止病毒扩张、窃取、破坏或发动大规模攻击；进攻方的目标是在有限资源下利用局部传播和 C2 指令，尽快达成感染、破坏或窃取目标。

## 核心概念

### 节点状态

游戏中的节点可能处于以下状态：

| 状态 | 含义 |
| --- | --- |
| 中立节点 | 尚未被任何一方控制。 |
| 防守方节点 | 由 Human/防守方控制，可被加固、扫描、关闭或恢复。 |
| 潜伏感染节点 | 已被病毒感染，但暂时不主动暴露，可继续作为跳板传播或等待 C2 指令。 |
| 活跃感染节点 | 已被 C2 激活，可以执行攻击、窃取、破坏、勒索或参与僵尸军团。 |
| 废置节点 | 被破坏后不可用，不属于任何一方；防守方可消耗资源恢复。 |
| 加固节点 | 防守方预防性强化过的节点，病毒传播成功率降低或需要更多回合。 |
| 蜜罐节点 | 被防守方伪装成高价值目标，病毒尝试窃取或勒索时会暴露位置。 |

### 图与节点价值

地图使用 NetworkX 生成或管理。节点重要性可以参考以下指标：

- **Degree / Hubs**：连接很多节点的高出度或高度节点，适合优先争夺。
- **Betweenness / Bridges**：连接不同区域的桥梁节点，即使连接数不多，也可能控制关键通路。
- **Closeness Centrality**：节点到其他节点的平均距离越短，越适合作为传播或防守中心。
- **Eigenvector Centrality**：连接到重要节点的节点也更重要。是否存在孤立点会影响中心性计算。

这些指标既可用于人类玩家的战术选择，也可用于 AI 的启发式策略。

## 每回合流程

推荐的回合结算顺序如下：

1. **预算/能量恢复**：双方获得基础预算或能量；已控制节点可提供额外收益。
2. **防守方预防行动**：防守方可提前加固节点、部署蜜罐、关闭关键节点等。
3. **进攻方传播与 C2 指令**：病毒尝试邻居传播、远程扫描感染，或向潜伏/活跃节点下达指令。
4. **扫描与清除**：防守方可扫描可疑节点，发现潜伏病毒后进行清除。
5. **攻击与响应**：活跃病毒可攻击、窃取、破坏或发动僵尸军团；防守方可进行流量清洗、恢复废置节点或反制 C2。
6. **冲突结算**：处理双方同回合选择同一节点时的归属、消耗和状态变化。
7. **胜负判定**：检查病毒或防守方是否达成胜利条件；若没有，则进入下一回合。

## 进攻方规则：Trojan / Virus

### 基础属性

进攻方拥有以下核心资源和约束：

- **C2 服务器**：不在图上的特殊实体，用于下达激活、扫描、攻击、窃取、破坏、勒索等指令。
- **能量 `E`**：类似预算，传播、扫描、攻击和大招都会消耗能量。
- **局部视野半径 `r`**：病毒只能观察已占领节点附近半径 `r` 内的节点及状态。
- **通信延迟**：C2 与病毒节点之间的指令可设置为 1 回合延迟，即本回合下达、下回合生效。
- **行动次数限制**：每回合传播尝试数量不超过 `Pmax`，C2 指令数量不超过 `Mcmd`。

### 传播方式

#### 1. 邻居传播 / 局部传播

病毒从已感染节点 `u` 向相邻节点 `v` 尝试传播。传播需要依赖“用户动作”，例如点击恶意链接或打开带毒附件。

默认规则示例：

- 未加固节点的感染成功率约为 `60%`。
- 每次传播消耗 `cprop` 能量，规则文档中建议值为 `1`。
- 新感染节点默认进入**潜伏态**，不会立即执行恶意行为。

#### 2. 远程扫描 / 非邻居传播

病毒可以指定一个已感染节点作为扫描源，对距离不超过扫描半径 `s` 的节点发起远程感染。

默认规则示例：

- 扫描半径 `s = 2`。
- 成功率与图距离 `d` 成反比，例如 `success = beta / d`。
- 距离越远，能量消耗越高，例如 `cscan * d`。

### 潜伏、激活与普通攻击

- **潜伏态**：刚感染的节点默认潜伏，不主动暴露；可以接收 C2 指令，也可以作为传播跳板。
- **激活**：C2 可以将潜伏节点激活为活跃节点。
- **休眠**：活跃节点也可以重新转为潜伏态，以降低被发现的风险。
- **普通攻击**：活跃节点可攻击相邻节点。默认成功率可设为 `30%`；若目标已加固，成功率减半；若目标已有潜伏体，可获得额外成功率加成。

### 僵尸军团 / 集中攻击

当病毒占领节点数达到全图节点数的一定比例，例如 `theta_zombie = 20%` 时，可以发动“僵尸军团”。

规则示例：

- 每局最多发动 `Zmax` 次。
- 可选择任意目标节点，不一定相邻。
- 所有活跃节点或所有病毒节点共同参与攻击，具体取决于所选规则。
- 攻击强度可按 `参与节点数 * 单位攻击力` 计算。
- 若攻击强度超过目标防御强度，目标节点可能被占领、废置，或从防守方转为病毒控制。
- 发动后消耗大量能量，参与节点进入 1 回合冷却。

### 非传播性恶意行为

活跃感染节点可以执行以下行为，每回合每个节点最多执行一种：

| 行为 | 说明 |
| --- | --- |
| 窃取数据 | 按比例窃取节点剩余数据价值，累计窃取量达到阈值时病毒获胜。 |
| 破坏节点 | 将节点变为废置状态，削弱防守方基础设施。 |
| 勒索 | 迫使防守方在支付资源和备份恢复之间做选择。 |

## 防守方规则：Human / Defender

### 信息优势与限制

防守方知道全图拓扑结构和节点价值，适合使用中心性指标制定防守策略。但防守方默认不知道病毒的准确位置，必须通过扫描、蜜罐或流量分析发现潜伏节点或 C2 线索。

### 预防性行动

预防性行动在进攻方主要行动前结算：

| 行动 | 作用 |
| --- | --- |
| 加固节点 | 增加节点防御强度，使病毒传播需要更多回合或成功率降低约 30%。 |
| 部署蜜罐 | 将节点伪装成高价值目标，病毒尝试窃取或勒索时暴露位置。 |
| 关闭节点 | 临时牺牲节点可用性，阻止其被继续利用。 |

### 扫描与清除

| 行动 | 作用 |
| --- | --- |
| 扫描 | 选择若干节点检测，揭示是否存在潜伏病毒，但不直接清除。 |
| 定点清除 | 对已发现病毒的节点投入资源，清除后节点恢复为防守方控制。 |
| 夺回节点 | 对已经被病毒占领的节点尝试重新控制，可设置成功率和资源成本。 |
| 反制 C2 | 定位 C2 后发动封杀，使 C2 在接下来若干回合无法下达指令。 |

### 响应性行动

响应性行动通常在病毒攻击后执行：

| 行动 | 作用 |
| --- | --- |
| 恢复废置节点 | 消耗资源将被破坏的节点恢复为中立或防守方控制。 |
| 拒绝勒索 + 备份恢复 | 拒绝支付勒索并从备份恢复，恢复期间节点不可用。 |
| 流量清洗 | 对抗僵尸军团或 DDoS 攻击，降低攻击成功率或保护目标节点。 |
| 溯源反击 | 成功定位 C2 后可发动高成本反击，直接摧毁 C2。 |

### 防守方预算参考

规则设计中的预算示例：

| 行动 | 成本示例 |
| --- | ---: |
| 加固一个节点 | 1 |
| 关闭一个节点 | 2 |
| 定点清除 | 3 |
| 反制 C2 | 5 |
| 全局扫描 | 1，覆盖约 10% 节点 |

双方每回合都可以获得基础预算恢复，例如 `+2`。成功防守的节点和已被病毒攻占的节点，也可以分别为双方提供额外预算；节点被夺回后，对应的额外收益消失。

## C2 静默规则

当 C2 被防守方反制并进入静默状态时，除邻居传播外，所有需要 C2 下达指令的行为都无法执行。

被禁用的行为包括：

- 远程扫描
- 激活或休眠
- 普通攻击指令
- 窃取、破坏、勒索
- 僵尸军团或精准打击

这使得 C2 成为进攻方的关键弱点，也是防守方的重要战略目标。

## 冲突结算规则

推荐使用以下规则处理同回合冲突：

1. **预防优先**：防守方的加固、关闭、蜜罐等预防行动先结算，会影响当回合病毒传播或攻击成功率。
2. **成功攻击优先于清除**：如果病毒在同一回合成功攻占某节点，而防守方也选择清除该节点，则清除失败，该节点归进攻方，双方资源消耗均保留。
3. **扫描不等于清除**：扫描只揭示病毒位置，不直接改变节点归属。
4. **废置节点需先恢复**：废置节点不能直接作为正常节点使用，防守方需要先消耗资源恢复。
5. **资源不足则行动失败**：如果某方预算或能量不足，对应行动不执行。

## 胜负条件

游戏可支持多种胜负条件，实际使用时可以选择其中一种或组合使用。

### 进攻方胜利

- 病毒占领节点数达到阈值，例如占领全图 `1/3` 或更多节点。
- 废置节点数达到阈值，防守方基础设施被大面积破坏。
- 累计窃取数据达到总数据价值的一定比例，例如 `30%`。
- 在关键节点上完成特定攻击目标。

### 防守方胜利

- 在 `T` 回合内阻止病毒达成任一胜利条件。
- 清除所有病毒节点并摧毁或长期静默 C2。
- 让病毒连续若干回合能量不足、无法行动。
- 通过成本优势使病毒总消耗超过设定阈值。

## 策略建议

### 防守方

- 优先保护 Hubs 和 Bridges，避免病毒快速跨区扩张。
- 在高价值节点或疑似攻击路径上部署蜜罐。
- 将扫描资源集中在病毒已占领节点的邻域或关键路径附近。
- 尽早尝试定位 C2；一旦 C2 静默，病毒的高级行动会受到明显限制。
- 在 2D 网格或局部连接明显的地图中，人类手动防守和关键点封锁通常更有价值。

### 进攻方

- 优先感染高中心性的节点，提高后续传播效率。
- 在关键桥梁节点上保持潜伏，等待合适时机激活。
- 避免过早暴露全部活跃节点，降低被集中清除的风险。
- 在 Random Graph 或长程连接较多的地图中，AI 优先的扫描和传播策略可能更有效。
- 当占领比例达到僵尸军团门槛后，可集中攻击高价值或高防守成本目标。

## 实验与论文扩展方向

项目可用于完成以下实验任务：

1. **基础模型**：在无向图空间 `V` 中设置中立点、防守方点和进攻方点，定义回合流程、冲突解决和胜负条件。
2. **多地图模拟**：在至少四种不同图结构上运行模拟，例如 2D 网格、随机图、小世界图、无标度图或 3D 随机图。
3. **组合策略比较**：设置至少三组“人类策略 + AI 策略”组合，并用胜率表比较不同地图上的表现。
4. **参数敏感性分析**：研究 `kA/kB`、视野半径 `r`、传播能力 `k` 等参数如何影响胜率，并寻找病毒胜率超过 50% 的临界值。
5. **预算分配实验**：比较预算投入到人类手动占领、AI 提升视野 `r`、AI 提升传播能力 `k` 的最佳比例。
6. **强化学习替代启发式策略**：将有限视野编码为固定大小输入向量，并把人类最新操作编码为对特定区域的战术信号。

## 可参考的策略/算法关键词

- Network Centrality Measures
- Firefighter Problem on Graphs
- Information Diffusion in Social Networks
- Game Theory on Graphs
- Heuristic Algorithms for Network Protection
- Monte Carlo Simulation on Graphs
- Reinforcement Learning on Graphs

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

请先安装 Python 3，并确认安装时勾选了 **Add Python to PATH**（Windows）。

### 3. 提示缺少 `networkx` 或 `matplotlib` 怎么办？

可以手动安装：

```bash
pip install networkx matplotlib
```

### 4. 两台电脑无法联机怎么办？

请检查：

- 两台电脑是否处于同一个局域网或同一个 Wi-Fi。
- Join 端输入的是否是 Host 端的局域网 IP。
- 系统防火墙是否拦截了 Python 或局域网端口。
- Host 端是否已经先启动并等待连接。

## 开发说明

- 地图生成与中心性计算建议使用 `networkx`。
- 胜率实验建议使用 Monte Carlo simulation，多次随机开局后统计平均胜率。
- UI 中的节点颜色应清晰区分中立、防守、潜伏感染、活跃感染、废置和加固等状态。
- 若添加新策略，建议保持“策略函数输入当前可见状态，输出行动列表”的结构，便于替换启发式策略或强化学习策略。
