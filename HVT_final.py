import os
import random
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from matplotlib.font_manager import FontProperties
import math
import threading


def _detect_matplotlib_cjk_font():
    """尽量为 matplotlib 选择一个可显示中文的字体。"""
    candidate_paths = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/arphic/ukai.ttc",
    ]
    for font_path in candidate_paths:
        if os.path.exists(font_path):
            try:
                return FontProperties(fname=font_path)
            except Exception:
                pass

    candidate_names = [
        "Microsoft YaHei", "SimHei", "SimSun",
        "Noto Sans CJK SC", "Noto Serif CJK SC",
        "WenQuanYi Zen Hei", "PingFang SC", "Heiti SC",
        "Songti SC", "Arial Unicode MS",
    ]
    for name in candidate_names:
        for item in font_manager.fontManager.ttflist:
            if item.name == name:
                try:
                    return FontProperties(fname=item.fname)
                except Exception:
                    pass
    return None


CN_FONT = _detect_matplotlib_cjk_font()
if CN_FONT is not None:
    try:
        rcParams["font.family"] = CN_FONT.get_name()
    except Exception:
        pass
rcParams["axes.unicode_minus"] = False


def _cn_kwargs(**kwargs):
    if CN_FONT is not None:
        kwargs.setdefault("fontproperties", CN_FONT)
    return kwargs


def _apply_button_cn_font(btn, fontsize=11):
    if CN_FONT is not None:
        try:
            btn.label.set_fontproperties(CN_FONT)
        except Exception:
            pass
    try:
        btn.label.set_fontsize(fontsize)
    except Exception:
        pass
    return btn


def _pick_pygame_font_name():
    try:
        import pygame
        names = set(pygame.font.get_fonts())
    except Exception:
        names = set()
    candidates = [
        "microsoftyahei", "simhei", "simsun",
        "notosanscjk", "notosanssc", "wenquanyizenhei", "arial"
    ]
    for name in candidates:
        if name in names:
            return name
    return None


def generate_game_graph(num_nodes=20, edge_prob=0.2, seed=42):
    """
    生成游戏图：
    1. 创建节点
    2. 随机连边
    3. 保证每个点至少有一条边
    4. 保证整张图连通
    5. 返回 G, pos, distances
    """
    random.seed(seed)

    G = nx.Graph()
    nodes = [f"p{i}" for i in range(1, num_nodes + 1)]
    G.add_nodes_from(nodes)

    # 随机生成边
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if random.random() < edge_prob:
                G.add_edge(nodes[i], nodes[j])

    # 保证每个点至少有一条边
    for node in nodes:
        if G.degree(node) == 0:
            other = random.choice([n for n in nodes if n != node])
            G.add_edge(node, other)

    # 如果图不连通，就连接各个连通块
    components = list(nx.connected_components(G))
    for i in range(len(components) - 1):
        node1 = random.choice(list(components[i]))
        node2 = random.choice(list(components[i + 1]))
        G.add_edge(node1, node2)

    # 固定 3D 布局
    pos = nx.spring_layout(G, dim=3, seed=seed)

    # 每个点与其他点的最短路距离
    distances = dict(nx.all_pairs_shortest_path_length(G))

    return G, pos, distances


def get_node_color(display_state):
    """
    根据显示状态返回节点颜色
    """
    color_map = {
        "DD": "white",
        "D": "deepskyblue",
        "H": "yellow",
        "HD": "orange",
        "lurk": "purple",
        "Hlurk": "hotpink",
        "HlurkD": "red",
        "active": "lime",
        "abandoned": "gray"
    }
    return color_map.get(display_state, "white")


class GraphViewer3D:
    """
    让 3D 图窗持续保持响应：
    - 只创建一个 figure，不在每回合反复 close / reopen
    - 主线程交给 matplotlib 的事件循环
    - 游戏逻辑和 input() 放到后台线程执行
    - 定时器检测到状态变化后重绘，但保留当前视角，便于鼠标拖动旋转
    """
    def __init__(self, G, pos, get_display_status_func, title="Cyber Graph", refresh_ms=120):
        self.G = G
        self.pos = pos
        self.get_display_status_func = get_display_status_func
        self.title = title
        self.refresh_ms = refresh_ms
        self.closed = False
        self.dirty = True
        self.lock = threading.Lock()

        self.fig = plt.figure(figsize=(16, 9))
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.fig.canvas.mpl_connect("close_event", self._on_close)


        coords = list(self.pos.values())
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        zs = [p[2] for p in coords]

        x_span = max(xs) - min(xs)
        y_span = max(ys) - min(ys)
        z_span = max(zs) - min(zs)

        pad_ratio = 0.04
        x_pad = max(0.03, x_span * pad_ratio)
        y_pad = max(0.03, y_span * pad_ratio)
        z_pad = max(0.03, z_span * pad_ratio)

        self.xlim = (min(xs) - x_pad, max(xs) + x_pad)
        self.ylim = (min(ys) - y_pad, max(ys) + y_pad)
        self.zlim = (min(zs) - z_pad, max(zs) + z_pad)

        self.timer = self.fig.canvas.new_timer(interval=self.refresh_ms)
        self.timer.add_callback(self._refresh_if_needed)
        self.timer.start()

        self._redraw()

    def _on_close(self, event):
        self.closed = True

    def set_title(self, title):
        with self.lock:
            self.title = title
            self.dirty = True

    def mark_dirty(self):
        with self.lock:
            self.dirty = True

    def _refresh_if_needed(self):
        if self.closed:
            return

        with self.lock:
            if not self.dirty:
                return
            self.dirty = False

        self._redraw()

    def _redraw(self):
        elev = getattr(self.ax, "elev", 30)
        azim = getattr(self.ax, "azim", -60)

        self.ax.cla()

        self.fig.patch.set_facecolor("black")
        self.ax.set_facecolor("black")

        display_snapshot = {
            node: self.get_display_status_func(node)
            for node in self.G.nodes()
        }

        for u, v in self.G.edges():
            x = [self.pos[u][0], self.pos[v][0]]
            y = [self.pos[u][1], self.pos[v][1]]
            z = [self.pos[u][2], self.pos[v][2]]
            self.ax.plot(x, y, z, c="white", linewidth=0.8, alpha=0.6)

        for node, (x, y, z) in self.pos.items():
            display_state = display_snapshot[node]
            color = get_node_color(display_state)

            self.ax.scatter(x, y, z, s=140, c=color, edgecolors="black", linewidths=0.8)
            self.ax.text(x, y, z, f"{node}\n{display_state}", color="white", fontsize=9, **_cn_kwargs())

        self.ax.set_xlim(*self.xlim)
        self.ax.set_ylim(*self.ylim)
        self.ax.set_zlim(*self.zlim)

        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_zticks([])
        self.ax.grid(False)
        self.ax.set_axis_off()
        self.ax.set_box_aspect([
            max(self.xlim[1] - self.xlim[0], 1e-6),
            max(self.ylim[1] - self.ylim[0], 1e-6),
            max(self.zlim[1] - self.zlim[0], 1e-6),
        ])

        self.ax.set_title(self.title, color="white", fontsize=16, **_cn_kwargs())
        self.ax.view_init(elev=elev, azim=azim)

        plt.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.96)

        self.fig.canvas.draw_idle()


def draw_graph_3d(G, pos, get_display_status_func, title="Cyber Graph", old_fig=None):
    """
    兼容旧接口：
    当前版本推荐直接使用 GraphViewer3D。
    """
    viewer = GraphViewer3D(G, pos, get_display_status_func, title=title)
    return viewer.fig


############################################################
# 主代码

# =========================================================
# 全局共享状态
# =========================================================
game_state = {
    "energy": 0,              # 病毒方能量
    "budget": 0,              # 防守方预算
    "key": 0,                 # 防守方获得的 C2 线索
    "c2_silenced_rounds": 0,  # C2 被静默剩余回合
    "c2_move_count": 0        # C2 已迁移次数
}

# =========================================================
# 节点状态字典
# trojan_nodes[node] = [病毒真实状态, 节点基础属性]
#
# 第一位:
#   'DD'     -> 无病毒，仍属防守方
#   'lurk'   -> 潜伏
#   'active' -> 已激活并控制
#
# 第二位:
#   'DD'        -> 普通防守点
#   'D'         -> 加固点
#   'H'         -> 蜜罐
#   'HD'        -> 加固蜜罐
#   'abandoned' -> 废置点
# =========================================================
# 先定义节点数量（和generate_game_graph的num_nodes保持一致）
GAME_NODE_NUM = 20  # 改成你想要的节点数（比如20）

# 动态生成所有节点字典，无需手动列p1-pN
trojan_nodes = {f"p{i}": ['DD', 'DD'] for i in range(1, GAME_NODE_NUM + 1)}
trojan_scanned = {f"p{i}": 'unknown' for i in range(1, GAME_NODE_NUM + 1)}
defender_scanned = {f"p{i}": 'unknown' for i in range(1, GAME_NODE_NUM + 1)}


# 僵尸军团相关全局状态
game_state.setdefault("zombie_used", 0)     # 本局已经发动过几次僵尸军团
game_state.setdefault("zombie_max", 2)      # 本局最多发动次数

# 活跃节点冷却：发动僵尸军团或精准打击后进入冷却
trojan_cooldown = {node: 0 for node in trojan_nodes}


# =========================================================
# 工具函数
# =========================================================

def compute_node_importance(G):
    degree = nx.degree_centrality(G)
    between = nx.betweenness_centrality(G)
    close = nx.closeness_centrality(G)

    node_importance = {}
    for node in G.nodes():
        node_importance[node] = (
            0.35 * degree[node] +
            0.35 * between[node] +
            0.20 * close[node] +
            0.10 * 1.0
        )
    return node_importance

def normalize_trojan_nodes(nodes_dict):
    """
    检查 trojan_nodes 格式是否合法
    """
    valid_real_state = {'DD', 'lurk', 'active'}
    valid_base_state = {'DD', 'D', 'H', 'HD', 'abandoned'}

    for node, value in nodes_dict.items():
        if len(value) != 2:
            raise ValueError(f"{node} 的状态长度不是2")

        if value[0] not in valid_real_state:
            raise ValueError(f"{node} 的病毒真实状态非法: {value[0]}")

        if value[1] not in valid_base_state:
            raise ValueError(f"{node} 的节点基础属性非法: {value[1]}")


def is_hardened(node):
    """
    判断是否为加固类节点
    """
    return trojan_nodes[node][1] in {'D', 'HD'}


def is_honeypot(node):
    """
    判断是否为蜜罐类节点
    """
    return trojan_nodes[node][1] in {'H', 'HD'}


def get_display_status(node):
    """
    根据真实状态 + 基础属性 + defender_scanned
    动态生成你要求输出的状态名

    返回值可能为：
    DD / D / H / HD / lurk / Hlurk / HlurkD / active / abandoned
    """
    real_state = trojan_nodes[node][0]
    base_state = trojan_nodes[node][1]
    detected = defender_scanned[node]

    # 废置节点优先
    if base_state == 'abandoned':
        return 'abandoned'

    # active 单独显示
    if real_state == 'active':
        return 'active'

    # 已经被防守方扫描发现潜伏
    if real_state == 'lurk' and detected == 'lurk':
        if base_state == 'DD':
            return 'lurk'
        elif base_state == 'H':
            return 'Hlurk'
        elif base_state in {'D', 'HD'}:
            return 'HlurkD'

    # 未被发现潜伏，显示为基础属性
    return base_state


def show_all_nodes_status():
    print("=" * 110)
    print(f"{'节点':<8}{'真实病毒状态':<15}{'基础属性':<12}{'显示状态':<12}"
          f"{'冷却':<8}{'病毒扫描':<20}{'防守扫描':<20}")
    print("-" * 110)

    for node in trojan_nodes:
        print(f"{node:<8}"
              f"{trojan_nodes[node][0]:<15}"
              f"{trojan_nodes[node][1]:<12}"
              f"{get_display_status(node):<12}"
              f"{trojan_cooldown[node]:<8}"
              f"{str(trojan_scanned[node]):<20}"
              f"{str(defender_scanned[node]):<20}")

    print("=" * 110)
    print(f"energy={game_state['energy']} | budget={game_state['budget']} | "
          f"key={game_state['key']} | c2_silenced_rounds={game_state['c2_silenced_rounds']} | "
          f"c2_move_count={game_state.get('c2_move_count', 0)} | "
          f"zombie_used={game_state['zombie_used']}/{game_state['zombie_max']}")
    print("=" * 110)



def end_round():
    """
    回合结束处理：
    1. C2 静默回合数减 1
    2. 僵尸军团 / 精准打击参与节点的冷却减 1
    """
    if game_state["c2_silenced_rounds"] > 0:
        game_state["c2_silenced_rounds"] -= 1

    for node in trojan_cooldown:
        if trojan_cooldown[node] > 0:
            trojan_cooldown[node] -= 1



# =========================================================
# 病毒方
# =========================================================
class TrojanHorse:
    """
    病毒方
    """
    def __init__(self, G, trojan_nodes, trojan_scanned, defender_scanned, game_state):
        self.G = G
        self.trojan_nodes = trojan_nodes
        self.trojan_scanned = trojan_scanned
        self.defender_scanned = defender_scanned
        self.game_state = game_state
        self.distances = dict(nx.all_pairs_shortest_path_length(G))

    def _result(self, ok, msg, **kwargs):
        ans = {"ok": ok, "msg": msg}
        ans.update(kwargs)
        return ans

    def _distance(self, u, v):
        return self.distances.get(u, {}).get(v, float("inf"))

    def _is_infected(self, node):
        return self.trojan_nodes[node][0] in {"lurk", "active"}

    def _consume_energy(self, amount):
        if self.game_state["energy"] < amount:
            return False
        self.game_state["energy"] -= amount
        return True

    def _c2_available(self):
        return self.game_state["c2_silenced_rounds"] <= 0

    def move_c2(self, cost=15, clear_silence=True, reset_keys=True):
        """
        C2 迁移：
        - 消耗病毒能量进行迁移
        - 迁移后立即摆脱当前已生效的 C2 静默
        - 防守方此前通过蜜罐/侦测积攒的 key 失效，重新从 0 开始积攒

        说明：
        这里把 C2 迁移视为一次基础设施重定位动作，因此即使当前处于静默，
        也允许病毒方用资源强行迁移来恢复后续指令能力。
        """
        if not self._consume_energy(cost):
            return self._result(False, f"能量不足，C2 迁移需要 {cost}")

        old_silence = self.game_state.get("c2_silenced_rounds", 0)
        old_key = self.game_state.get("key", 0)

        if clear_silence:
            self.game_state["c2_silenced_rounds"] = 0
        if reset_keys:
            self.game_state["key"] = 0

        self.game_state["c2_move_count"] = self.game_state.get("c2_move_count", 0) + 1

        return self._result(
            True,
            "C2 已完成迁移，现有反制效果失效，防守方需重新积攒 key",
            old_silence=old_silence,
            old_key=old_key,
            c2_move_count=self.game_state["c2_move_count"]
        )

    def gain_energy_per_round(self, lurk_income=2, active_income=4, base_recover=2):
        """
        病毒方每回合能量结算：
        - 自然恢复 base_recover
        - 每个 lurk 点提供 lurk_income
        - 每个 active 点提供 active_income

        注意：
        lurk 的“偷取能量”不会减少防守方 budget，
        只是病毒方自己的额外收益。
        """
        lurk_nodes = [
            node for node in self.trojan_nodes
            if self.trojan_nodes[node][0] == "lurk"
        ]
        active_nodes = [
            node for node in self.trojan_nodes
            if self.trojan_nodes[node][0] == "active"
        ]

        gained_from_base = base_recover
        gained_from_lurk = len(lurk_nodes) * lurk_income
        gained_from_active = len(active_nodes) * active_income
        total_gain = gained_from_base + gained_from_lurk + gained_from_active

        self.game_state["energy"] += total_gain
        self.game_state["stolen_energy_total"] = self.game_state.get("stolen_energy_total", 0) + gained_from_lurk
        self.game_state["occupied_energy_total"] = self.game_state.get("occupied_energy_total", 0) + gained_from_active

        return self._result(
            True,
            f"本回合病毒方获得 {total_gain} 点 energy "
            f"(自然恢复 {gained_from_base} + 潜伏收益 {gained_from_lurk} + 占领收益 {gained_from_active})",
            lurk_nodes=lurk_nodes,
            active_nodes=active_nodes,
            gained_from_base=gained_from_base,
            gained_from_lurk=gained_from_lurk,
            gained_from_active=gained_from_active,
            total_gain=total_gain,
            stolen_energy_total=self.game_state["stolen_energy_total"],
            occupied_energy_total=self.game_state["occupied_energy_total"]
        )

    def seed_initial_node(self, node, state="active"):
        """
        初始投毒点
        """
        if state not in {"lurk", "active"}:
            return self._result(False, "初始状态只能是 lurk 或 active")

        if self.trojan_nodes[node][1] == "abandoned":
            return self._result(False, "废置点不能作为初始感染点")

        self.trojan_nodes[node][0] = state
        return self._result(True, f"{node} 已被设为初始感染点，状态={state}")

    def spread_neighbour(self, source, target, base_success=0.60, cost=1):
        """
        邻接传播：
        - 起点必须已感染
        - 目标必须相邻
        - 成功后 target -> lurk
        - 加固点成功率下降 30%
        - 新增：拦截已感染（lurk/active）的目标
        """
        if source == target:
            return self._result(False, "source 与 target 不能相同")

        if not self._is_infected(source):
            return self._result(False, "起点未感染，不能传播")

        # 核心修复：拦截所有已感染的目标（lurk/active）
        if self._is_infected(target):
            return self._result(False, f"目标 {target} 已处于 {self.trojan_nodes[target][0]} 状态，无需传播")

        if self.trojan_nodes[target][1] == "abandoned":
            return self._result(False, "废置点无法传播")

        if self._distance(source, target) != 1:
            return self._result(False, "邻接传播只能攻击相邻节点")

        if not self._consume_energy(cost):
            return self._result(False, "能量不足")

        success_prob = base_success
        if is_hardened(target):
            success_prob *= 0.7

        if random.random() < success_prob:
            self.trojan_nodes[target][0] = "lurk"

            if is_honeypot(target):
                self.defender_scanned[target] = "lurk"

            return self._result(True, "邻接传播成功", target=target, success_prob=success_prob)

        return self._result(False, "邻接传播失败", target=target, success_prob=success_prob)

    def spread_far(self, source, target, radius=2, beta=0.60, cscan=2):
        """
        远程传播：
        - 需要 C2 可用
        - 成功率 = beta / distance
        - 消耗 = cscan * distance
        - 成功后 target -> lurk
        - 新增：拦截已感染（lurk/active）的目标
        """
        if not self._c2_available():
            return self._result(False, "C2 被静默，无法远程传播")

        # 核心修复：拦截所有已感染的目标（lurk/active）
        if self._is_infected(target):
            return self._result(False, f"目标 {target} 已处于 {self.trojan_nodes[target][0]} 状态，无需传播")

        if source == target:
            return self._result(False, "source 与 target 不能相同")

        if not self._is_infected(source):
            return self._result(False, "起点未感染，不能传播")

        if self.trojan_nodes[target][1] == "abandoned":
            return self._result(False, "废置点无法传播")

        distance = self._distance(source, target)
        if distance > radius or distance == 0:
            return self._result(False, f"远程传播范围超限（radius={radius}，distance={distance}）")

        cost = cscan * distance
        if not self._consume_energy(cost):
            return self._result(False, f"能量不足（需要 {cost}，当前 {self.game_state['energy']}）")

        success_prob = beta / distance
        if is_hardened(target):
            success_prob *= 0.7

        if random.random() < success_prob:
            self.trojan_nodes[target][0] = "lurk"

            if is_honeypot(target):
                self.defender_scanned[target] = "lurk"

            return self._result(True, f"远程传播成功（距离={distance}，成功率={success_prob:.2f}）",
                               target=target, success_prob=success_prob, distance=distance)

        return self._result(False, f"远程传播失败（距离={distance}，成功率={success_prob:.2f}）",
                           target=target, success_prob=success_prob, distance=distance)

    def activate(self, node, cost=1):
        """
        激活潜伏点：lurk -> active
        """
        if not self._c2_available():
            return self._result(False, "C2 被静默，无法激活")

        if self.trojan_nodes[node][0] != "lurk":
            return self._result(False, "目标不是 lurk，无法激活")

        if not self._consume_energy(cost):
            return self._result(False, "能量不足")

        choose_number = random.randint(1,100)


        if trojan_nodes[node][1] == 'DD':
            # 潜伏普通攻击成功率15%
            if choose_number <= 15:
                trojan_nodes[node][0] = 'active'
                return self._result(True, '入侵成功')
            else:
                return self._result(False, '入侵失败')
        elif trojan_nodes[node][1] == 'D':
            # 加固的点潜伏成功率5%
            if choose_number <= 5:
                trojan_nodes[node][0] = 'active'
                return self._result(True, '入侵成功')
            else:
                return self._result(False, '入侵失败')
        elif trojan_nodes[node][1] == 'H':
            # 蜜罐成功率15%
            if choose_number <= 15:
                trojan_nodes[node][0] = 'active'
                self.game_state["key"] += 1
                return self._result(True, '入侵成功')
            else:
                return self._result(False, '入侵失败')
        elif trojan_nodes[node][1] == 'HD':
            # 加固的蜜罐成功率15%
            if choose_number <= 15:
                trojan_nodes[node][0] = 'active'
                self.game_state["key"] += 1
                return self._result(True, '入侵成功')
            else:
                return self._result(False, '入侵失败')


        self.trojan_nodes[node][0] = "active"
        return self._result(True, f"{node} 激活成功")

    def sleep(self, node, cost=1):
        """
        休眠：active -> lurk
        """
        if not self._c2_available():
            return self._result(False, "C2 被静默，无法休眠")

        if self.trojan_nodes[node][0] != "active":
            return self._result(False, "目标不是 active，无法休眠")

        if not self._consume_energy(cost):
            return self._result(False, "能量不足")

        self.trojan_nodes[node][0] = "lurk"
        return self._result(True, f"{node} 已转回 lurk")

    def scan_node(self, source, target, cost=1, radius=None):
        """
        病毒方扫描
        """
        if not self._c2_available():
            return self._result(False, "C2 被静默，无法扫描")

        if not self._is_infected(source):
            return self._result(False, "扫描源未感染")

        dist = self._distance(source, target)
        if dist == float("inf"):
            return self._result(False, "目标不可达")

        if radius is not None and dist > radius:
            return self._result(False, f"超出扫描半径 radius={radius}")

        if not self._consume_energy(cost):
            return self._result(False, "能量不足")

        self.trojan_scanned[target] = {
            "distance": dist,
            "real_state": self.trojan_nodes[target][0],
            "base_state": self.trojan_nodes[target][1],
            "display_state": get_display_status(target),
            "neighbors": list(self.G.neighbors(target))
        }
        return self._result(True, "扫描成功", target=target, info=self.trojan_scanned[target])

    def normal_attack(self, source, target, cost=4):
        """
        普通攻击：
        - 只能打相邻点
        - 普通点成功率 30%
        - 加固点成功率 15%
        - 如果目标已经 lurk，则 +10%
        - 成功后 target -> active
        - 触碰蜜罐则增加 key，并会被标记为已发现潜伏
        """
        if not self._c2_available():
            return self._result(False, "C2 被静默，无法普通攻击")

        if source == target:
            return self._result(False, "不能攻击自己")

        if not self._is_infected(source):
            return self._result(False, "攻击源未感染")

        if self._distance(source, target) != 1:
            return self._result(False, "普通攻击只能攻击相邻节点")

        if self.trojan_nodes[target][1] == "abandoned":
            return self._result(False, "废置点不能攻击")

        if not self._consume_energy(cost):
            return self._result(False, "能量不足")

        # 攻击一旦发起，源点暴露为 active
        self.trojan_nodes[source][0] = "active"

        # 基础成功率
        if self.trojan_nodes[target][1] in {"DD", "H"}:
            success_prob = 0.30
        elif self.trojan_nodes[target][1] in {"D", "HD"}:
            success_prob = 0.15
        else:
            return self._result(False, "目标节点状态非法")

        # 潜伏加成
        if self.trojan_nodes[target][0] == "lurk":
            success_prob += 0.10

        if random.random() < success_prob:
            self.trojan_nodes[target][0] = "active"

            if is_honeypot(target):
                self.game_state["key"] += 1
                self.defender_scanned[target] = "lurk"

            return self._result(True, "普通攻击成功", target=target, success_prob=success_prob)

        return self._result(False, "普通攻击失败", target=target, success_prob=success_prob)

    def _available_active_nodes(self):
        """
        返回当前可参与集中攻击的 active 节点：
        - 必须是 active
        - 冷却必须为 0
        """
        return [
            node for node in self.trojan_nodes
            if self.trojan_nodes[node][0] == "active" and trojan_cooldown[node] == 0
        ]

    def _infected_count(self):
        """
        返回当前感染节点总数（lurk + active）
        """
        return sum(
            1 for node in self.trojan_nodes
            if self.trojan_nodes[node][0] in {"lurk", "active"}
        )

    def _target_defense_strength(self, target, extra_defense=0.0):
        """
        计算目标节点当前的防御强度
        extra_defense 用来给你以后接防守方 clean_traffic / 临时防御加成
        """
        base_state = self.trojan_nodes[target][1]
        real_state = self.trojan_nodes[target][0]

        if base_state in {"DD", "H"}:
            defense = 1.0
        elif base_state in {"D", "HD"}:
            defense = 1.5
        else:
            defense = 999.0  # abandoned 理论上不应成为有效攻击目标

        # 若目标已被潜伏，则说明内部已有渗透，防御强度稍弱
        if real_state == "lurk":
            defense -= 0.3

        defense += extra_defense
        return max(defense, 0.1)

    def _set_cooldown(self, participants, rounds=1):
        """
        让一组参与攻击的节点进入冷却
        """
        for node in participants:
            trojan_cooldown[node] = max(trojan_cooldown[node], rounds)

    def _trigger_honeypot_if_needed(self, target):
        """
        如果目标是蜜罐或加固蜜罐，则：
        - 防守方获得一条 C2 线索
        - 防守方视为已经探测到该点潜伏痕迹
        """
        if is_honeypot(target):
            self.game_state["key"] += 1
            if self.trojan_nodes[target][0] == "lurk":
                self.defender_scanned[target] = "lurk"

    def zombie_legion(
            self,
            target,
            theta=0.20,
            cost=8,
            alpha_attack=1.0,
            cooldown_rounds=1,
            extra_defense=0.0,
            success_mode="convert"
    ):
        """
        僵尸军团（集中攻击）

        参数：
        - target: 攻击目标
        - theta: 触发阈值，占感染节点数比例（默认 20%）
        - cost: 发动大招的能量消耗
        - alpha_attack: 单个 active 节点提供的单位攻击力
        - cooldown_rounds: 参与者冷却回合
        - extra_defense: 防守方临时防御加成（便于以后接 clean_traffic）
        - success_mode:
            "convert" -> 成功后目标变为病毒 active 控制
            "destroy" -> 成功后目标变为 abandoned
        """
        if not self._c2_available():
            return self._result(False, "C2 被静默，无法发动僵尸军团")

        if self.game_state["zombie_used"] >= self.game_state["zombie_max"]:
            return self._result(False, "本局僵尸军团发动次数已用尽")

        if self.trojan_nodes[target][1] == "abandoned":
            return self._result(False, "废置节点不能作为僵尸军团目标")

        if self.trojan_nodes[target][0] == "active":
            return self._result(False, "目标已经被病毒控制，无需发动僵尸军团")

        total_nodes = len(self.trojan_nodes)
        infected_nodes = self._infected_count()

        if infected_nodes < max(1, int(theta * total_nodes)):
            return self._result(
                False,
                f"感染规模不足，当前仅 {infected_nodes}/{total_nodes}，未达到阈值"
            )

        participants = self._available_active_nodes()
        if len(participants) == 0:
            return self._result(False, "当前没有可参与僵尸军团的 active 节点")

        if not self._consume_energy(cost):
            return self._result(False, "能量不足，无法发动僵尸军团")

        attack_strength = len(participants) * alpha_attack
        defense_strength = self._target_defense_strength(target, extra_defense=extra_defense)

        # 参与节点进入冷却
        self._set_cooldown(participants, rounds=cooldown_rounds)

        # 记录本局使用次数
        self.game_state["zombie_used"] += 1

        if attack_strength > defense_strength:
            if success_mode == "convert":
                self.trojan_nodes[target][0] = "active"
                self._trigger_honeypot_if_needed(target)
                return self._result(
                    True,
                    "僵尸军团攻击成功，目标已转为 active",
                    target=target,
                    participants=participants,
                    attack_strength=attack_strength,
                    defense_strength=defense_strength
                )

            elif success_mode == "destroy":
                self.trojan_nodes[target][0] = "DD"
                self.trojan_nodes[target][1] = "abandoned"
                self.defender_scanned[target] = "unknown"
                self.trojan_scanned[target] = "unknown"
                return self._result(
                    True,
                    "僵尸军团攻击成功，目标被破坏为 abandoned",
                    target=target,
                    participants=participants,
                    attack_strength=attack_strength,
                    defense_strength=defense_strength
                )

            else:
                return self._result(False, "success_mode 参数非法，只能是 convert 或 destroy")

        return self._result(
            False,
            "僵尸军团攻击失败",
            target=target,
            participants=participants,
            attack_strength=attack_strength,
            defense_strength=defense_strength
        )

    def precise_strike(
            self,
            target,
            participants=None,
            cost=12,
            alpha_attack=1.2,
            precision_bonus=1.5,
            cooldown_rounds=1,
            extra_defense=0.0,
            success_mode="convert",
            node_importance=None
    ):
        if not self._c2_available():
            return self._result(False, "C2 被静默，无法发动精准打击")

        if participants is None:
            participants = self._available_active_nodes()

        if len(participants) == 0:
            return self._result(False, "没有可参与精准打击的节点")

        importance = 1.0
        if node_importance is not None:
            importance = node_importance.get(target, 1.0)

        actual_cost = cost + 3 * importance
        if not self._consume_energy(actual_cost):
            return self._result(False, f"能量不足，精准打击需要 {actual_cost:.2f}")

        attack_strength = len(participants) * alpha_attack * precision_bonus
        defense_strength = self._target_defense_strength(target, extra_defense=extra_defense)

        # 重要节点更难打
        defense_strength += 2 * importance

        self._set_cooldown(participants, rounds=cooldown_rounds)

        if attack_strength > defense_strength:
            if success_mode == "destroy":
                self.trojan_nodes[target][0] = "DD"
                self.trojan_nodes[target][1] = "abandoned"
                return self._result(True, f"精准打击成功，{target} 被摧毁")
            else:
                self.trojan_nodes[target][0] = "active"
                return self._result(True, f"精准打击成功，{target} 被占领")

        return self._result(False, f"精准打击失败")

    def destroy_node(self, node, base_cost=4, gamma=1.0, node_value=1.0):
        """
        破坏节点（非传播性恶意行为）

        规则：
        - 只能破坏当前已被病毒 active 控制的节点
        - 破坏后节点变为 abandoned
        - 病毒失去该节点的控制
        - 成本与节点价值成正比：
            total_cost = base_cost + gamma * node_value
        """
        if not self._c2_available():
            return self._result(False, "C2 被静默，无法执行破坏节点")

        if self.trojan_nodes[node][0] != "active":
            return self._result(False, "只有 active 节点才能执行破坏")

        if self.trojan_nodes[node][1] == "abandoned":
            return self._result(False, "该节点已经是废置状态")

        total_cost = base_cost + gamma * node_value

        if not self._consume_energy(total_cost):
            return self._result(False, f"能量不足，破坏节点需要 {total_cost}")

        # 节点被破坏：失去控制，基础属性变废置
        self.trojan_nodes[node][0] = "DD"
        self.trojan_nodes[node][1] = "abandoned"

        # 清空双方对此节点的扫描记录
        self.trojan_scanned[node] = "unknown"
        self.defender_scanned[node] = "unknown"

        # 冷却清零（已经废了，不该再有冷却残留）
        trojan_cooldown[node] = 0

        return self._result(
            True,
            f"{node} 已被成功破坏为 abandoned",
            node=node,
            total_cost=total_cost
        )


############################################################################
class Defender:
    """
    防守方
    默认所有预算都记录在 game_state["budget"] 里
    """

    def __init__(self, G, trojan_nodes, defender_scanned, game_state):
        self.G = G
        self.trojan_nodes = trojan_nodes
        self.defender_scanned = defender_scanned
        self.game_state = game_state
        self.distances = dict(nx.all_pairs_shortest_path_length(G))

    def _result(self, ok, msg, **kwargs):
        ans = {"ok": ok, "msg": msg}
        ans.update(kwargs)
        return ans

    def _consume_budget(self, amount):
        if self.game_state["budget"] < amount:
            return False
        self.game_state["budget"] -= amount
        return True

    def auto_increase_budget_per_round(self, amount=2):
        """
        每回合基础恢复预算
        """
        self.game_state["budget"] += amount
        return self._result(True, f"防守方恢复 {amount} 点 budget")

    def increase_budget_from_capture(self, income_per_node=1):
        """
        所有未被 active 占领、且不是废置点的节点都继续给防守方提供预算
        """
        valid_nodes = [
            n for n in self.trojan_nodes
            if self.trojan_nodes[n][0] != "active" and self.trojan_nodes[n][1] != "abandoned"
        ]
        gained = len(valid_nodes) * income_per_node
        self.game_state["budget"] += gained
        return self._result(
            True,
            f"防守方从可用节点获得 {gained} 点 budget",
            valid_nodes=valid_nodes,
            gained=gained
        )

    def show_budget(self):
        return self.game_state["budget"]

    def apply_hardening(self, choice_point, cost=1):
        """
        加固节点：
        DD -> D
        H  -> HD
        """
        if not self._consume_budget(cost):
            return self._result(False, "预算不足，无法加固")

        if self.trojan_nodes[choice_point][0] == "active":
            return self._result(False, "该节点已被病毒占领，不能加固")

        if self.trojan_nodes[choice_point][1] == "abandoned":
            return self._result(False, "废置节点不能加固")

        if self.trojan_nodes[choice_point][1] in {"D", "HD"}:
            return self._result(False, "该节点已经加固过")

        if self.trojan_nodes[choice_point][1] == "H":
            self.trojan_nodes[choice_point][1] = "HD"
        else:
            self.trojan_nodes[choice_point][1] = "D"

        return self._result(True, f"{choice_point} 加固成功")

    def deploy_honeypot(self, choice_point, cost=1, max_honeypots=3):
        """
        部署蜜罐：
        DD -> H
        D  -> HD
        最多同时存在 max_honeypots 个
        """
        if not self._consume_budget(cost):
            return self._result(False, "预算不足，无法部署蜜罐")

        current_honeypots = sum(
            1 for i in self.trojan_nodes.values()
            if i[1] in {"H", "HD"}
        )
        if current_honeypots >= max_honeypots:
            return self._result(False, f"当前最多只能存在 {max_honeypots} 个蜜罐")

        if self.trojan_nodes[choice_point][0] == "active":
            return self._result(False, "active 节点不能部署蜜罐")

        if self.trojan_nodes[choice_point][1] == "abandoned":
            return self._result(False, "废置节点不能部署蜜罐")

        if self.trojan_nodes[choice_point][1] in {"H", "HD"}:
            return self._result(False, "该节点已经是蜜罐")

        if self.trojan_nodes[choice_point][1] == "D":
            self.trojan_nodes[choice_point][1] = "HD"
        else:
            self.trojan_nodes[choice_point][1] = "H"

        return self._result(True, f"{choice_point} 蜜罐部署成功")

    def counter_c2(self, need_key=3, cost=5, silence_rounds=2):
        """
        反制 C2：
        拥有足够 key 后，消耗预算使 C2 静默
        """
        if self.game_state["key"] < need_key:
            return self._result(
                False,
                f"C2 线索不足，当前仅有 {self.game_state['key']}/{need_key}"
            )

        if not self._consume_budget(cost):
            return self._result(False, "预算不足，无法反制 C2")

        self.game_state["key"] -= need_key
        self.game_state["c2_silenced_rounds"] += silence_rounds
        return self._result(True, f"C2 已被静默 {silence_rounds} 回合")

    def scan_nodes(self, choice_point, cost=1):
        """
        防守方扫描：
        - lurk -> 标记为 lurk
        - active -> 标记为 active
        - DD -> 标记为 DD
        """
        if not self._consume_budget(cost):
            return self._result(False, "预算不足，无法扫描")

        if self.trojan_nodes[choice_point][1] == "abandoned":
            return self._result(False, "废置节点无法扫描")

        if self.trojan_nodes[choice_point][0] == "lurk":
            self.defender_scanned[choice_point] = "lurk"
            return self._result(True, f"{choice_point} 扫描发现潜伏病毒")

        elif self.trojan_nodes[choice_point][0] == "active":
            self.defender_scanned[choice_point] = "active"
            return self._result(True, f"{choice_point} 扫描发现 active 病毒占领")

        else:
            self.defender_scanned[choice_point] = "DD"
            return self._result(True, f"{choice_point} 未发现病毒")

    def clear_virus(self, choice_point, cost=3):
        """
        清除潜伏病毒：
        只能清除已经确认的 lurk
        """
        if not self._consume_budget(cost):
            return self._result(False, "预算不足，无法清除")

        if self.defender_scanned[choice_point] != "lurk":
            return self._result(False, "只能清除已确认的 lurk 节点")

        self.defender_scanned[choice_point] = "DD"
        self.trojan_nodes[choice_point][0] = "DD"
        return self._result(True, f"{choice_point} 的潜伏病毒已被清除")

    def recapture_lost_nodes(self, choice_point, cost=7, success_prob=0.30):
        """
        夺回 active 节点
        """
        if not self._consume_budget(cost):
            return self._result(False, "预算不足，无法夺回")

        if self.trojan_nodes[choice_point][0] != "active":
            return self._result(False, "该节点不是 active，无法夺回")

        if random.random() < success_prob:
            self.trojan_nodes[choice_point][0] = "DD"
            self.defender_scanned[choice_point] = "DD"
            return self._result(True, f"{choice_point} 夺回成功")

        return self._result(False, f"{choice_point} 夺回失败")

    def restore_abandoned(self, choice_point, cost=4):
        """
        恢复废置节点：
        abandoned -> DD
        """
        if not self._consume_budget(cost):
            return self._result(False, "预算不足，无法恢复废置节点")

        if self.trojan_nodes[choice_point][1] != "abandoned":
            return self._result(False, "该节点不是废置状态")

        self.trojan_nodes[choice_point][0] = "DD"
        self.trojan_nodes[choice_point][1] = "DD"
        self.defender_scanned[choice_point] = "DD"
        return self._result(True, f"{choice_point} 已从废置状态恢复")

    def clean_traffic(self, target_node, attack_strength, base_cost=20, efficiency=0.7):
        """
        流量清洗：
        对“僵尸军团 / 精准打击”提供额外防御值
        """
        print(f"\n[NETWORK ALERT] 节点 {target_node} 正遭受大规模网络攻击")
        print(f"Incoming Attack Strength = {attack_strength:.2f}")

        confirm = input("是否部署流量清洗？(y/n): ").strip().lower()
        if confirm != "y":
            print("未部署流量清洗")
            return 0.0

        if self.game_state["budget"] < base_cost:
            print("预算不足，无法启动流量清洗")
            return 0.0

        try:
            invest = int(input(f"投入多少预算？(当前预算 {self.game_state['budget']}): "))
        except ValueError:
            invest = 0

        invest = max(0, min(invest, self.game_state["budget"]))
        self.game_state["budget"] -= invest

        extra_defense = max(0, invest - base_cost) * efficiency
        print(f"流量清洗部署成功，额外防御值 +{extra_defense:.2f}")
        return extra_defense

#######################################################################################################

def prepare_zombie_legion(attacker, target, theta=0.20, cost=8, alpha_attack=1.0, cooldown_rounds=1):
    """
    先准备僵尸军团，不立即结算，等待防守方 clean_traffic 后再结算
    """
    if not attacker._c2_available():
        return None, {"ok": False, "msg": "C2 被静默，无法发动僵尸军团"}

    if attacker.game_state["zombie_used"] >= attacker.game_state["zombie_max"]:
        return None, {"ok": False, "msg": "本局僵尸军团次数已耗尽"}

    infected_count = sum(
        1 for n in attacker.trojan_nodes
        if attacker.trojan_nodes[n][0] in {"lurk", "active"}
    )
    threshold = max(1, math.ceil(theta * len(attacker.trojan_nodes)))

    if infected_count < threshold:
        return None, {"ok": False, "msg": f"感染规模不足，当前 {infected_count}/{threshold}"}

    participants = [
        n for n in attacker.trojan_nodes
        if attacker.trojan_nodes[n][0] == "active" and trojan_cooldown[n] == 0
    ]
    if not participants:
        return None, {"ok": False, "msg": "没有可参与僵尸军团的 active 节点"}

    if not attacker._consume_energy(cost):
        return None, {"ok": False, "msg": "能量不足，无法发动僵尸军团"}

    attack_strength = len(participants) * alpha_attack
    pending = {
        "type": "zombie",
        "target": target,
        "participants": participants,
        "attack_strength": attack_strength,
        "cooldown_rounds": cooldown_rounds
    }
    attacker.game_state["zombie_used"] += 1
    return pending, {
        "ok": True,
        "msg": f"僵尸军团已发动，目标 {target}，攻击强度 {attack_strength:.2f}",
        "participants": participants,
        "attack_strength": attack_strength
    }


def prepare_precise_strike(attacker, target, participants=None, cost=12,
                           alpha_attack=1.2, precision_bonus=1.5, cooldown_rounds=1):
    """
    先准备精准打击，不立即结算
    """
    if not attacker._c2_available():
        return None, {"ok": False, "msg": "C2 被静默，无法发动精准打击"}

    if participants is None:
        participants = [
            n for n in attacker.trojan_nodes
            if attacker.trojan_nodes[n][0] == "active" and trojan_cooldown[n] == 0
        ]
    else:
        for node in participants:
            if attacker.trojan_nodes[node][0] != "active":
                return None, {"ok": False, "msg": f"{node} 不是 active，不能参与精准打击"}
            if trojan_cooldown[node] > 0:
                return None, {"ok": False, "msg": f"{node} 正处于冷却中"}

    if not participants:
        return None, {"ok": False, "msg": "没有可参与精准打击的 active 节点"}

    if target in participants:
        return None, {"ok": False, "msg": "目标节点不能同时作为参与者"}

    if not attacker._consume_energy(cost):
        return None, {"ok": False, "msg": "能量不足，无法发动精准打击"}

    attack_strength = len(participants) * alpha_attack * precision_bonus
    if attacker.trojan_nodes[target][0] == "lurk":
        attack_strength += 0.5

    pending = {
        "type": "precise",
        "target": target,
        "participants": participants,
        "attack_strength": attack_strength,
        "cooldown_rounds": cooldown_rounds
    }
    return pending, {
        "ok": True,
        "msg": f"精准打击已发动，目标 {target}，攻击强度 {attack_strength:.2f}",
        "participants": participants,
        "attack_strength": attack_strength
    }

def resolve_pending_special_attack(attacker, pending_attack, extra_defense=0.0, success_mode="convert"):
    """
    在防守方行动后结算僵尸军团/精准打击
    """
    if pending_attack is None:
        return {"ok": False, "msg": "没有待结算的特殊攻击"}

    target = pending_attack["target"]
    participants = pending_attack["participants"]
    attack_strength = pending_attack["attack_strength"]

    # 参与者进入冷却
    for node in participants:
        trojan_cooldown[node] = max(trojan_cooldown[node], pending_attack["cooldown_rounds"])

    # 计算目标防御值
    defense_strength = attacker._target_defense_strength(target, extra_defense=extra_defense)

    if attack_strength > defense_strength:
        if success_mode == "destroy":
            attacker.trojan_nodes[target][0] = "DD"
            attacker.trojan_nodes[target][1] = "abandoned"
            defender_scanned[target] = "unknown"
            trojan_scanned[target] = "unknown"
            return {
                "ok": True,
                "msg": f"{pending_attack['type']} 攻击成功，{target} 被摧毁为 abandoned",
                "attack_strength": attack_strength,
                "defense_strength": defense_strength
            }

        # 默认 convert
        attacker.trojan_nodes[target][0] = "active"

        # 如果目标是蜜罐，仍然会暴露一条 key
        if attacker.trojan_nodes[target][1] in {"H", "HD"}:
            attacker.game_state["key"] += 1
            if attacker.trojan_nodes[target][0] == "lurk":
                defender_scanned[target] = "lurk"

        return {
            "ok": True,
            "msg": f"{pending_attack['type']} 攻击成功，{target} 转为 active",
            "attack_strength": attack_strength,
            "defense_strength": defense_strength
        }

    return {
        "ok": False,
        "msg": f"{pending_attack['type']} 攻击失败",
        "attack_strength": attack_strength,
        "defense_strength": defense_strength
    }

#########################################################

def check_win_condition(trojan_nodes, max_rounds, current_round):
    total_nodes = len(trojan_nodes)
    active_count = sum(1 for n in trojan_nodes if trojan_nodes[n][0] == "active")
    infected_count = sum(1 for n in trojan_nodes if trojan_nodes[n][0] in {"lurk", "active"})

    attacker_threshold = math.ceil(total_nodes / 3)

    if active_count >= attacker_threshold:
        return True, "virus", f"病毒方胜利：active 节点数达到 {active_count}/{total_nodes}（阈值 {attacker_threshold}）"

    if infected_count == 0:
        return True, "defender", "防守方胜利：所有病毒节点已被清除"

    if current_round >= max_rounds:
        return True, "defender", f"防守方时间胜利：达到最大回合数 {max_rounds}"

    return False, None, "游戏继续"

########################################################

def virus_action_phase(attacker):
    """
    病毒行动阶段
    返回:
    - pending_special_attack: 若本回合发动僵尸军团/精准打击，则返回待结算攻击
    - special_mode: convert / destroy
    """
    pending_special_attack = None
    special_mode = "convert"

    print("\n===== 病毒行动阶段 =====")
    print("1 邻接传播")
    print("2 远程传播")
    print("3 激活 lurk")
    print("4 休眠 active")
    print("5 扫描节点")
    print("6 普通攻击")
    print("7 僵尸军团")
    print("8 精准打击")
    print("9 破坏节点")
    print("10 C2 迁移")
    print("0 跳过")

    choice = input("请选择病毒行动: ").strip()

    if choice == "1":
        s = input("source: ").strip()
        t = input("target: ").strip()
        print(attacker.spread_neighbour(s, t))

    elif choice == "2":
        s = input("source: ").strip()
        t = input("target: ").strip()
        print(attacker.spread_far(s, t))

    elif choice == "3":
        node = input("要激活的节点: ").strip()
        print(attacker.activate(node))

    elif choice == "4":
        node = input("要休眠的节点: ").strip()
        print(attacker.sleep(node))

    elif choice == "5":
        s = input("scan source: ").strip()
        t = input("scan target: ").strip()
        print(attacker.scan_node(s, t))

    elif choice == "6":
        s = input("attack source: ").strip()
        t = input("attack target: ").strip()
        print(attacker.normal_attack(s, t))

    elif choice == "7":
        t = input("僵尸军团目标: ").strip()
        mode = input("成功后是占领还是摧毁？(convert/destroy): ").strip().lower()
        if mode in {"convert", "destroy"}:
            special_mode = mode
        pending_special_attack, msg = prepare_zombie_legion(attacker, t)
        print(msg)

    elif choice == "8":
        t = input("精准打击目标: ").strip()
        use_all = input("是否使用所有可用 active 节点？(y/n): ").strip().lower()
        participants = None
        if use_all != "y":
            raw = input("请输入参与节点，逗号分隔: ").strip()
            participants = [x.strip() for x in raw.split(",") if x.strip()]
        mode = input("成功后是占领还是摧毁？(convert/destroy): ").strip().lower()
        if mode in {"convert", "destroy"}:
            special_mode = mode
        pending_special_attack, msg = prepare_precise_strike(attacker, t, participants=participants)
        print(msg)

    elif choice == "9":
        node = input("要破坏的 active 节点: ").strip()
        try:
            node_value = float(input("该节点价值 node_value（默认 1.0）: ").strip())
        except ValueError:
            node_value = 1.0
        print(attacker.destroy_node(node, node_value=node_value))

    elif choice == "10":
        raw_cost = input("C2 迁移消耗（默认 3）: ").strip()
        try:
            move_cost = int(raw_cost) if raw_cost else 3
        except ValueError:
            move_cost = 3
        print(attacker.move_c2(cost=max(0, move_cost)))

    else:
        print("病毒方本回合跳过行动")

    return pending_special_attack, special_mode

def defender_action_phase(defender, pending_special_attack=None):
    """
    防守行动阶段
    返回:
    - extra_defense: 若对特殊攻击做了流量清洗，则返回额外防御值
    """
    extra_defense = 0.0

    print("\n===== 防守行动阶段 =====")
    print("1 加固节点")
    print("2 部署蜜罐")
    print("3 扫描节点")
    print("4 清除潜伏病毒")
    print("5 夺回 active 节点")
    print("6 恢复 abandoned 节点")
    print("7 反制 C2")
    print("8 流量清洗")
    print("0 跳过")

    choice = input("请选择防守行动: ").strip()

    if choice == "1":
        node = input("要加固的节点: ").strip()
        print(defender.apply_hardening(node))

    elif choice == "2":
        node = input("要部署蜜罐的节点: ").strip()
        print(defender.deploy_honeypot(node))

    elif choice == "3":
        node = input("要扫描的节点: ").strip()
        print(defender.scan_nodes(node))

    elif choice == "4":
        node = input("要清除潜伏病毒的节点: ").strip()
        print(defender.clear_virus(node))

    elif choice == "5":
        node = input("要夺回的 active 节点: ").strip()
        print(defender.recapture_lost_nodes(node))

    elif choice == "6":
        node = input("要恢复的 abandoned 节点: ").strip()
        print(defender.restore_abandoned(node))

    elif choice == "7":
        print(defender.counter_c2())

    elif choice == "8":
        if pending_special_attack is None:
            print("本回合没有待响应的特殊攻击，无法进行流量清洗")
        else:
            extra_defense = defender.clean_traffic(
                pending_special_attack["target"],
                pending_special_attack["attack_strength"]
            )

    else:
        print("防守方本回合跳过行动")

    return extra_defense

###################################################################

def run_game(max_rounds=30, seed=42):
    """
    修复版主循环：
    - 图形界面由主线程负责，保持窗口可交互
    - 游戏逻辑与 input() 在后台线程运行
    - 每当状态变化时，只重绘同一个 figure，而不是反复关闭/新建窗口
    """
    global G, distances

    G, pos, distances = generate_game_graph(num_nodes=15, edge_prob=0.2, seed=seed)

    normalize_trojan_nodes(trojan_nodes)

    game_state["energy"] = 20
    game_state["budget"] = 5
    game_state["key"] = 0
    game_state["c2_silenced_rounds"] = 0
    game_state["c2_move_count"] = 0
    game_state["zombie_used"] = 0
    game_state.setdefault("zombie_max", 2)
    game_state["stolen_energy_total"] = 0
    game_state["occupied_energy_total"] = 0

    attacker = TrojanHorse(G, trojan_nodes, trojan_scanned, defender_scanned, game_state)
    defender = Defender(G, trojan_nodes, defender_scanned, game_state)

    viewer = GraphViewer3D(G, pos, get_display_status, title="Initial Map")
    result_holder = {"winner": None}

    def update_view(title):
        if not viewer.closed:
            viewer.set_title(title)
            viewer.mark_dirty()

    def game_loop():
        init_node = input("请输入病毒初始感染点（例如 p1）: ").strip()
        init_state = input("初始状态 active 还是 lurk？(active/lurk): ").strip().lower()
        if init_state not in {"active", "lurk"}:
            init_state = "active"

        print(attacker.seed_initial_node(init_node, init_state))
        update_view("Round 0 - Initial Infection")

        current_round = 1

        while current_round <= max_rounds:
            print(f"\n\n================ 第 {current_round} 回合 ================")
            update_view(f"Round {current_round} - Start")

            print("\n[阶段1] 病毒回能")
            print(attacker.gain_energy_per_round(lurk_income=1, active_income=2, base_recover=2))

            print("\n[阶段2] 防守方回预算")
            print(defender.auto_increase_budget_per_round(amount=2))
            print(defender.increase_budget_from_capture(income_per_node=1))

            show_all_nodes_status()

            print("\n[阶段3] 病毒行动")
            pending_special_attack, special_mode = virus_action_phase(attacker)

            print("\n[阶段4] 防守行动")
            extra_defense = defender_action_phase(defender, pending_special_attack=pending_special_attack)

            if pending_special_attack is not None:
                print("\n[阶段5] 特殊攻击结算")
                result = resolve_pending_special_attack(
                    attacker,
                    pending_special_attack,
                    extra_defense=extra_defense,
                    success_mode=special_mode
                )
                print(result)

            update_view(f"Round {current_round} - After Actions")
            show_all_nodes_status()

            print("\n[阶段6] 冷却结算")
            end_round()
            print("冷却与 C2 静默结算完成")

            print("\n[阶段7] 胜负判定")
            game_over, winner, msg = check_win_condition(trojan_nodes, max_rounds, current_round)
            print(msg)

            if game_over:
                update_view(f"Game Over - Winner: {winner}")
                print("\n================ 游戏结束 ================")
                print(f"胜者：{winner}")
                show_all_nodes_status()
                result_holder["winner"] = winner
                return

            current_round += 1

        update_view("Game Over - Defender Wins by Time")
        print("\n================ 游戏结束 ================")
        print("达到最大回合数，默认防守方胜利")
        result_holder["winner"] = "defender"

    game_thread = threading.Thread(target=game_loop, daemon=False)
    game_thread.start()

    plt.show()
    game_thread.join()

    return result_holder["winner"]



# =========================================================
# 覆盖式补丁：AI 资源体系 / 双窗口 UI / 双 3D 视图
# =========================================================

def _attacker_energy_key(game_state):
    mode = game_state.get('attacker_energy_mode', 'ai')
    return 'attacker_human_energy' if mode == 'human' else 'attacker_ai_energy'


def _set_attacker_mode(attacker, mode):
    attacker.game_state['attacker_energy_mode'] = mode


def _patched_consume_energy(self, amount):
    key = _attacker_energy_key(self.game_state)
    if self.game_state.get(key, 0) < amount:
        return False
    self.game_state[key] -= amount
    return True


def _patched_c2_available(self):
    if self.game_state.get('attacker_energy_mode', 'ai') == 'ai':
        return True
    return self.game_state.get('c2_silenced_rounds', 0) <= 0


def _patched_move_c2(self, cost=15, clear_silence=True, reset_keys=True):
    _set_attacker_mode(self, 'human')
    fixed_cost = 15
    if not self._consume_energy(fixed_cost):
        return self._result(False, f'人类玩家 energy 不足，C2 迁移固定需要 {fixed_cost}')

    old_silence = self.game_state.get('c2_silenced_rounds', 0)
    old_key = self.game_state.get('key', 0)

    if clear_silence:
        self.game_state['c2_silenced_rounds'] = 0
    if reset_keys:
        self.game_state['key'] = 0

    self.game_state['c2_move_count'] = self.game_state.get('c2_move_count', 0) + 1
    return self._result(
        True,
        'C2 已完成迁移，现有反制效果失效，防守方需重新积攒 key',
        old_silence=old_silence,
        old_key=old_key,
        c2_move_count=self.game_state['c2_move_count'],
        fixed_cost=fixed_cost,
    )


def _patched_gain_energy_per_round(self, *args, base_recover=2, human_ratio=0.30, ai_ratio=0.70, **kwargs):
    infected_count = sum(1 for n in self.trojan_nodes if self.trojan_nodes[n][0] in {'lurk', 'active'})
    human_gain = base_recover + math.floor(infected_count * human_ratio)
    ai_gain = base_recover + math.ceil(infected_count * ai_ratio)
    self.game_state['attacker_human_energy'] = self.game_state.get('attacker_human_energy', 0) + human_gain
    self.game_state['attacker_ai_energy'] = self.game_state.get('attacker_ai_energy', 0) + ai_gain
    return self._result(
        True,
        f'本回合进攻方获得 energy：人类 +{human_gain}，AI +{ai_gain}',
        infected_count=infected_count,
        human_gain=human_gain,
        ai_gain=ai_gain,
    )


TrojanHorse._consume_energy = _patched_consume_energy
TrojanHorse._c2_available = _patched_c2_available
TrojanHorse.move_c2 = _patched_move_c2
TrojanHorse.gain_energy_per_round = _patched_gain_energy_per_round


# -------------------- Defender budget mode patch --------------------

def _set_defender_mode(defender, mode):
    defender.game_state['defender_budget_mode'] = mode


def _patched_consume_budget(self, amount):
    mode = self.game_state.get('defender_budget_mode', 'ai')
    actual = amount * (3 if mode == 'human' else 1)
    if self.game_state.get('budget', 0) < actual:
        return False
    self.game_state['budget'] -= actual
    return True


Defender._consume_budget = _patched_consume_budget


# -------------------- AI heuristics --------------------

def _node_degree_score(G, node):
    return G.degree(node)


def _target_base_penalty(node):
    base = trojan_nodes[node][1]
    if base == 'abandoned':
        return 999.0
    if base in {'D', 'HD'}:
        return 2.3
    if base in {'H'}:
        return 0.9
    return 0.0


def _target_lurk_bonus(node):
    return 1.2 if trojan_nodes[node][0] == 'lurk' else 0.0


def _score_for_spread(G, source, target, node_importance, distance_weight=1.0):
    importance = node_importance.get(target, 1.0)
    degree_score = _node_degree_score(G, target)
    dist = nx.shortest_path_length(G, source=source, target=target)
    return (
        3.0 * importance
        + 0.55 * degree_score
        + _target_lurk_bonus(target)
        - distance_weight * dist
        - _target_base_penalty(target)
    )


def _score_for_attack(G, source, target, node_importance):
    importance = node_importance.get(target, 1.0)
    degree_score = _node_degree_score(G, target)
    return 3.2 * importance + 0.5 * degree_score + 1.6 * _target_lurk_bonus(target) - _target_base_penalty(target)


def attacker_ai_operational_phase(attacker, node_importance, max_actions=200):
    """
    进攻方 AI：
    - 默认以扩散为主
    - 当感染率（lurk+active）>= 70% 时，普通攻击优先级最高
    - AI energy 充足时，同回合允许多次行动（攻击 + 扩散混合）
    """
    _set_attacker_mode(attacker, 'ai')
    logs = []

    if "ai_tried_targets" not in attacker.game_state:
        attacker.game_state["ai_tried_targets"] = []

    total_nodes = len(attacker.trojan_nodes)
    infected_nodes = [
        n for n in attacker.trojan_nodes
        if attacker.trojan_nodes[n][0] in {"lurk", "active"}
    ]
    lurk_nodes = [
        n for n in attacker.trojan_nodes
        if attacker.trojan_nodes[n][0] == "lurk"
    ]
    active_nodes = [
        n for n in attacker.trojan_nodes
        if attacker.trojan_nodes[n][0] == "active"
    ]

    infected_ratio = len(infected_nodes) / max(1, total_nodes)
    high_pressure_mode = infected_ratio >= 0.70

    tried_this_round = set()

    def available_spread_targets():
        targets = [
            node for node in attacker.trojan_nodes
            if attacker.trojan_nodes[node][0] == "DD"
            and attacker.trojan_nodes[node][1] != "abandoned"
            and node not in tried_this_round
        ]
        return sorted(
            targets,
            key=lambda n: node_importance.get(n, 0.0),
            reverse=True
        )

    def best_spread_action():
        candidates = []
        infected_sources_local = [
            s for s in attacker.trojan_nodes
            if attacker._is_infected(s)
        ]
        if not infected_sources_local:
            return None

        for target in available_spread_targets():
            for source in infected_sources_local:
                dist = attacker._distance(source, target)
                if dist == 1:
                    score = (
                        3.2 * node_importance.get(target, 1.0)
                        + 0.55 * attacker.G.degree(target)
                        - 0.2 * dist
                    )
                    candidates.append(("spread_neighbour", score, source, target))
                elif 1 < dist <= 5:
                    score = (
                        2.7 * node_importance.get(target, 1.0)
                        + 0.45 * attacker.G.degree(target)
                        - 0.45 * dist
                    )
                    candidates.append(("spread_far", score, source, target))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]

    def best_attack_action():
        candidates = []

        # 普通攻击必须从已感染节点出发，打相邻节点
        infected_sources_local = [
            s for s in attacker.trojan_nodes
            if attacker._is_infected(s)
        ]
        if not infected_sources_local:
            return None

        for source in infected_sources_local:
            for target in attacker.G.neighbors(source):
                if attacker.trojan_nodes[target][1] == "abandoned":
                    continue
                if target == source:
                    continue

                # 普通攻击更适合打 DD / D / H / HD / lurk
                if attacker.trojan_nodes[target][0] == "active":
                    continue

                base_bonus = 0.0
                if attacker.trojan_nodes[target][0] == "lurk":
                    base_bonus += 1.6
                if attacker.trojan_nodes[target][1] in {"H", "HD"}:
                    base_bonus += 0.3

                score = (
                    3.8 * node_importance.get(target, 1.0)
                    + 0.55 * attacker.G.degree(target)
                    + base_bonus
                )
                candidates.append(("normal_attack", score, source, target))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]

    def ai_energy():
        return attacker.game_state.get("attacker_ai_energy", 0)

    for step in range(max_actions):
        action_candidates = []

        # 模式1：感染率不足 70%，优先扩散
        if not high_pressure_mode:
            spread_action = best_spread_action()
            attack_action = best_attack_action()

            if spread_action is not None:
                action_candidates.append((0, spread_action))  # 最高优先
            if attack_action is not None and ai_energy() >= 10:
                action_candidates.append((1, attack_action))  # energy 多时允许顺手攻击

        # 模式2：感染率达到 70%，优先普通攻击，其次扩散
        else:
            attack_action = best_attack_action()
            spread_action = best_spread_action()

            if attack_action is not None:
                action_candidates.append((0, attack_action))  # 最高优先
            if spread_action is not None:
                action_candidates.append((1, spread_action))  # 其次扩散

        if not action_candidates:
            break

        action_candidates.sort(key=lambda x: x[0])
        _, chosen = action_candidates[0]
        action_type, _, source, target = chosen

        res = None

        if action_type == "normal_attack":
            if ai_energy() < 4:
                logs.append(("AI提示", {"ok": False, "msg": "AI energy 不足，无法继续普通攻击"}))
                break
            res = attacker.normal_attack(source, target)
            logs.append(("AI普通攻击", res))

        elif action_type == "spread_neighbour":
            if ai_energy() < 1:
                logs.append(("AI提示", {"ok": False, "msg": "AI energy 不足，无法继续邻接传播"}))
                break
            res = attacker.spread_neighbour(source, target)
            logs.append(("AI邻接传播", res))

        elif action_type == "spread_far":
            dist = attacker._distance(source, target)
            need_cost = max(1, 2 * dist)
            if ai_energy() < need_cost:
                logs.append(("AI提示", {"ok": False, "msg": f"AI energy 不足，无法继续远程传播（需要 {need_cost}）"}))
                break
            res = attacker.spread_far(source, target, radius=5)
            logs.append(("AI远程传播", res))

        tried_this_round.add(target)

        if isinstance(res, dict) and not res.get("ok", False):
            msg = str(res.get("msg", ""))
            if "能量不足" in msg:
                break

        # 避免本回合同一个目标反复尝试
        attacker.game_state["ai_tried_targets"].append(target)

        # energy 太少时停止连招
        if ai_energy() <= 0:
            break

        # 低感染阶段，energy 不高时只打一两手，避免过猛
        if (not high_pressure_mode) and ai_energy() < 4 and step >= 1:
            break

    if not logs:
        logs.append(("AI提示", {"ok": False, "msg": "本回合 AI 未找到可执行动作"}))

    mode_text = "攻击优先" if high_pressure_mode else "扩散优先"
    logs.insert(0, ("AI策略", {"ok": True, "msg": f"当前感染率 {infected_ratio:.0%}，执行模式：{mode_text}"}))
    return logs



def _predicted_risk_score(G, node, node_importance=None):
    imp = 1.0 if node_importance is None else node_importance.get(node, 1.0)
    deg = G.degree(node)
    suspicious_bonus = 0.0
    for nbr in G.neighbors(node):
        if trojan_nodes[nbr][0] in {'lurk', 'active'}:
            suspicious_bonus += 1.6
        if defender_scanned.get(nbr) in {'lurk', 'active'}:
            suspicious_bonus += 1.2
    return 2.5 * imp + 0.45 * deg + suspicious_bonus


def _best_scan_candidates(defender, node_importance=None, scanned_this_round=None):
    scanned_this_round = scanned_this_round or set()
    candidates = []
    for node in defender.G.nodes():
        if node in scanned_this_round:
            continue
        if trojan_nodes[node][1] == 'abandoned':
            continue
        if defender_scanned.get(node) in {'lurk', 'active'}:
            continue
        score = _predicted_risk_score(defender.G, node, node_importance=node_importance)
        if defender_scanned.get(node) == 'unknown':
            score += 1.0
        candidates.append((score, node))
    candidates.sort(reverse=True)
    return [node for _, node in candidates]


def _best_harden_candidates(defender, node_importance=None):
    candidates = []
    for node in defender.G.nodes():
        if trojan_nodes[node][1] in {'D', 'HD', 'abandoned'}:
            continue
        if trojan_nodes[node][0] == 'active':
            continue
        score = _predicted_risk_score(defender.G, node, node_importance=node_importance)
        candidates.append((score, node))
    candidates.sort(reverse=True)
    return [node for _, node in candidates]


def _best_honeypot_candidates(defender, node_importance=None):
    current = sum(1 for v in trojan_nodes.values() if v[1] in {'H', 'HD'})
    if current >= 3:
        return []
    candidates = []
    for node in defender.G.nodes():
        if trojan_nodes[node][1] in {'H', 'HD', 'abandoned'}:
            continue
        if trojan_nodes[node][0] == 'active':
            continue
        score = _predicted_risk_score(defender.G, node, node_importance=node_importance) + 0.8
        candidates.append((score, node))
    candidates.sort(reverse=True)
    return [node for _, node in candidates]


def defender_ai_phase_ui(defender, pending_special_attack=None, node_importance=None, want_honeypot=False, max_actions=200):
    logs = []
    extra_defense = 0.0
    scanned_this_round = set()
    _set_defender_mode(defender, 'ai')

    reserve_budget = 3
    for _ in range(max_actions):
        budget = defender.game_state.get('budget', 0)
        if budget <= 0:
            break

        executed = False

        # 特殊攻击响应：AI 只在预算较宽松时做清洗
        if pending_special_attack is not None and budget - reserve_budget >= 8 and extra_defense <= 0.0:
            invest = min(12, max(8, budget - reserve_budget))
            defender.game_state['budget'] -= invest
            added = max(0.0, invest - 8) * 0.7
            extra_defense += added
            logs.append(('AI流量清洗', {'ok': True, 'msg': f'AI 自动投入 {invest} budget 进行流量清洗，额外防御 +{added:.2f}'}))
            executed = True
        if executed:
            continue

        # 已确认 lurk 优先清除
        clear_targets = [n for n in defender.G.nodes() if defender_scanned.get(n) == 'lurk']
        clear_targets.sort(key=lambda n: node_importance.get(n, 1.0) if node_importance else 1.0, reverse=True)
        for node in clear_targets:
            if defender.game_state.get('budget', 0) - reserve_budget < 3:
                break
            res = defender.clear_virus(node)
            logs.append(('AI清除潜伏', res))
            executed = True
            break
        if executed:
            continue

        # 可见 active 其次尝试夺回
        active_targets = [n for n in defender.G.nodes() if trojan_nodes[n][0] == 'active']
        active_targets.sort(key=lambda n: node_importance.get(n, 1.0) if node_importance else 1.0, reverse=True)
        for node in active_targets:
            if defender.game_state.get('budget', 0) - reserve_budget < 7:
                break
            res = defender.recapture_lost_nodes(node)
            logs.append(('AI夺回节点', res))
            executed = True
            break
        if executed:
            continue

        # 扫描：本回合同一节点只扫一次
        for node in _best_scan_candidates(defender, node_importance=node_importance, scanned_this_round=scanned_this_round):
            if defender.game_state.get('budget', 0) - reserve_budget < 1:
                break
            scanned_this_round.add(node)
            res = defender.scan_nodes(node)
            logs.append(('AI扫描', res))
            executed = True
            break
        if executed:
            continue

        # 加固高风险点
        for node in _best_harden_candidates(defender, node_importance=node_importance):
            if defender.game_state.get('budget', 0) - reserve_budget < 1:
                break
            res = defender.apply_hardening(node)
            if res.get('ok'):
                logs.append(('AI加固', res))
                executed = True
                break
        if executed:
            continue

        # 根据预测放蜜罐
        if want_honeypot:
            for node in _best_honeypot_candidates(defender, node_importance=node_importance):
                if defender.game_state.get('budget', 0) - reserve_budget < 1:
                    break
                res = defender.deploy_honeypot(node)
                if res.get('ok'):
                    logs.append(('AI部署蜜罐', res))
                    executed = True
                    break
        if executed:
            continue

        break

    return extra_defense, logs


class UIButton:
    def __init__(self, rect, label, action, color=(55, 65, 85), active_color=(85, 110, 155), enabled=True):
        self.rect = rect
        self.label = label
        self.action = action
        self.color = color
        self.active_color = active_color
        self.enabled = enabled

    def draw(self, surface, font, is_active=False):
        import pygame
        if not self.enabled:
            color = tuple(max(30, c - 28) for c in self.color)
            border = (90, 96, 108)
            text_color = (150, 156, 168)
        else:
            color = self.active_color if is_active else self.color
            border = (180, 190, 210)
            text_color = (240, 245, 255)
        pygame.draw.rect(surface, color, self.rect, border_radius=10)
        pygame.draw.rect(surface, border, self.rect, 1, border_radius=10)
        text = font.render(self.label, True, text_color)
        text_rect = text.get_rect(center=self.rect.center)
        surface.blit(text, text_rect)

    def hit(self, pos):
        return self.enabled and self.rect.collidepoint(pos)


class CyberGameUI:
    def __init__(self, max_rounds=20, seed=42):
        try:
            import pygame
            from pygame._sdl2 import Window, Renderer, Texture
        except ImportError as exc:
            raise RuntimeError('未安装 pygame 或当前 pygame 不支持多窗口。请先执行: pip install pygame') from exc

        self.pygame = pygame
        self.Window = Window
        self.Renderer = Renderer
        self.Texture = Texture

        pygame.init()
        pygame.display.init()
        pygame.font.init()

        self.clock = pygame.time.Clock()
        font_name = _pick_pygame_font_name()
        self.font = pygame.font.SysFont(font_name, 18)
        self.small_font = pygame.font.SysFont(font_name, 15)
        self.title_font = pygame.font.SysFont(font_name, 26)
        self.mono_font = pygame.font.SysFont('consolas,couriernew,arial', 14)

        self.max_rounds = max_rounds
        self.seed = seed
        self.running = True
        self.winner = None
        self.current_round = 0
        self.phase = 'setup'

        self.attacker_status = '请在攻击方战术地图上点击一个节点，然后点击“初始 Active”或“初始 Lurk”。'
        self.defender_status = '等待进攻方完成开局。'
        self.selected_attacker_node = None
        self.selected_defender_node = None
        self.current_attacker_action = None
        self.current_defender_action = None
        self.scan_source_attacker = None
        self.pending_special_attack = None
        self.special_mode = 'convert'
        self.extra_defense = 0.0
        self.want_honeypot_ai = True
        self.selected_seed = int(seed)
        self.attacker_logs = []
        self.defender_logs = []
        self.attacker_log_height = 220
        self.defender_log_height = 220
        self.attacker_log_collapsed = False
        self.defender_log_collapsed = False

        self.attacker_window = self.Window('攻击方控制台', size=(920, 980), position=(40, 40))
        self.defender_window = self.Window('防守方控制台', size=(920, 980), position=(1010, 40))
        self.attacker_window.resizable = True
        self.defender_window.resizable = True
        self.attacker_renderer = self.Renderer(self.attacker_window)
        self.defender_renderer = self.Renderer(self.defender_window)
        self.attacker_surface = None
        self.defender_surface = None
        self.attacker_layout = None
        self.defender_layout = None

        self.attacker_viewer = None
        self.defender_viewer = None

        self._reset_game()
        self._create_3d_viewers()
        self._mark_views_dirty()

    def _reset_game(self):
        global G, distances
        self.seed = int(self.selected_seed)
        G, pos3d, distances = generate_game_graph(num_nodes=15, edge_prob=0.2, seed=self.seed)
        normalize_trojan_nodes(trojan_nodes)
        for node in trojan_nodes:
            trojan_nodes[node][0] = 'DD'
            trojan_nodes[node][1] = 'DD'
            trojan_scanned[node] = 'unknown'
            defender_scanned[node] = 'unknown'
            trojan_cooldown[node] = 0

        game_state['attacker_human_energy'] = 5
        game_state['attacker_ai_energy'] = 5
        game_state['attacker_energy_mode'] = 'ai'
        game_state['defender_budget_mode'] = 'ai'
        game_state['budget'] = 5
        game_state['key'] = 0
        game_state['c2_silenced_rounds'] = 0
        game_state['c2_move_count'] = 0
        game_state['zombie_used'] = 0
        game_state['zombie_max'] = 2

        self.G = G
        self.pos3d = pos3d
        self.layout2d = nx.spring_layout(G, dim=2, seed=self.seed)
        self.attacker = TrojanHorse(G, trojan_nodes, trojan_scanned, defender_scanned, game_state)
        self.defender = Defender(G, trojan_nodes, defender_scanned, game_state)
        self.node_importance = compute_node_importance(G)

    def _set_seed_value(self, delta=None, randomize=False):
        if self.phase not in {'setup', 'round_ready'}:
            msg = '只有在开局前或回合待开始时才能切换地图种子。'
            self.attacker_status = msg
            self.add_attacker_log(msg)
            return
        if randomize:
            self.selected_seed = random.randint(0, 999999)
        elif delta is not None:
            self.selected_seed = max(0, int(self.selected_seed) + int(delta))
        msg = f'当前待应用地图种子：{self.selected_seed}。点击“应用种子”生成对应地图。'
        self.attacker_status = msg
        self.add_attacker_log(msg)

    def _apply_selected_seed(self):
        if self.phase not in {'setup', 'round_ready'}:
            msg = '只有在开局前或回合待开始时才能应用新地图种子。'
            self.attacker_status = msg
            self.add_attacker_log(msg)
            return
        self.selected_attacker_node = None
        self.selected_defender_node = None
        self.current_attacker_action = None
        self.current_defender_action = None
        self.scan_source_attacker = None
        self.current_round = 0
        self.winner = None
        self.phase = 'setup'
        self.attacker_logs = []
        self.defender_logs = []
        self.pending_special_attack = None
        self.special_mode = 'convert'
        self.extra_defense = 0.0
        self._reset_game()
        self._create_3d_viewers()
        msg = f'已应用地图种子 {self.selected_seed}。相同种子会生成同一张地图。'
        self.attacker_status = msg
        self.defender_status = '地图已重置，等待进攻方重新设置初始感染点。'
        self.add_attacker_log(msg)
        self.add_defender_log(msg)
        self._mark_views_dirty()

    def _safe_destroy_viewer(self, viewer):
        if viewer is None:
            return
        try:
            viewer.closed = True
            viewer.timer.stop()
        except Exception:
            pass
        try:
            plt.close(viewer.fig)
        except Exception:
            pass

    def _create_3d_viewers(self):
        self._safe_destroy_viewer(self.attacker_viewer)
        self._safe_destroy_viewer(self.defender_viewer)
        plt.ion()
        self.attacker_viewer = GraphViewer3D(self.G, self.pos3d, self.attacker_view_state, title='攻击方 3D 视图', refresh_ms=140)
        self.defender_viewer = GraphViewer3D(self.G, self.pos3d, self.defender_view_state, title='防守方 3D 视图', refresh_ms=140)
        try:
            plt.show(block=False)
        except Exception:
            pass

    def _mark_views_dirty(self):
        suffix = f'R{self.current_round} | {self.phase}'
        for viewer, title in [
            (self.attacker_viewer, f'攻击方 3D 视图 | {suffix}'),
            (self.defender_viewer, f'防守方 3D 视图 | {suffix}'),
        ]:
            if viewer is None or getattr(viewer, 'closed', False):
                continue
            viewer.set_title(title)
            viewer.mark_dirty()

    def add_attacker_log(self, msg):
        self.attacker_logs.append(msg)
        self.attacker_logs = self.attacker_logs[-120:]

    def add_defender_log(self, msg):
        self.defender_logs.append(msg)
        self.defender_logs = self.defender_logs[-120:]

    def _result_msg(self, res):
        if isinstance(res, dict):
            return res.get('msg', str(res))
        return str(res)

    def attacker_view_state(self, node):
        real_state, base_state = trojan_nodes[node]
        if base_state == 'abandoned':
            return 'abandoned'
        if real_state == 'active':
            return 'active'
        if real_state == 'lurk':
            return 'lurk'
        return 'DD'

    def defender_view_state(self, node):
        return get_display_status(node)

    def _wrap_text(self, font, text, max_width):
        if not text:
            return ['']
        lines = []
        current = ''
        for ch in text:
            trial = current + ch
            if font.size(trial)[0] <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = ch
        if current:
            lines.append(current)
        return lines

    def _fit_layout_positions(self, rect):
        xs = [self.layout2d[n][0] for n in self.G.nodes()]
        ys = [self.layout2d[n][1] for n in self.G.nodes()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max(max_x - min_x, 1e-6)
        height = max(max_y - min_y, 1e-6)
        positions = {}
        for node, (x, y) in self.layout2d.items():
            px = rect.x + 38 + (x - min_x) / width * (rect.width - 76)
            py = rect.y + 52 + (y - min_y) / height * (rect.height - 92)
            positions[node] = (int(px), int(py))
        return positions

    def _build_layout(self, side, size):
        pygame = self.pygame
        w, h = int(size[0]), int(size[1])
        margin = 16
        header_h = 98
        log_collapsed = self.attacker_log_collapsed if side == 'attacker' else self.defender_log_collapsed
        desired_log_h = self.attacker_log_height if side == 'attacker' else self.defender_log_height
        log_h = 42 if log_collapsed else max(150, min(desired_log_h, h // 2))

        header = pygame.Rect(margin, margin, w - 2 * margin, header_h)
        log_rect = pygame.Rect(margin, h - margin - log_h, w - 2 * margin, log_h)
        status_rect = pygame.Rect(margin, log_rect.y - 12 - 64, w - 2 * margin, 64)
        main_top = header.bottom + 12
        main_h = status_rect.y - 12 - main_top
        map_w = min(510, max(360, int((w - 3 * margin) * 0.56)))
        map_rect = pygame.Rect(margin, main_top, map_w, main_h)
        actions_rect = pygame.Rect(map_rect.right + 12, main_top, w - margin - (map_rect.right + 12), main_h)
        colors = {
            'panel_bg': (19, 24, 32) if side == 'attacker' else (26, 28, 22),
            'line': (82, 96, 120) if side == 'attacker' else (112, 118, 86),
            'accent': (74, 108, 168) if side == 'attacker' else (120, 126, 88),
        }
        layout = {
            'header': header,
            'map': map_rect,
            'actions': actions_rect,
            'status': status_rect,
            'log': log_rect,
            'positions': self._fit_layout_positions(map_rect),
            'log_collapsed': log_collapsed,
            **colors,
        }
        layout['sections'] = self._build_buttons(side, actions_rect)
        layout['log_buttons'] = self._build_log_buttons(side, log_rect)
        return layout

    def _make_button_grid(self, x, y, width, items, side, cols=2, row_h=42, gap=8, enabled=None):
        pygame = self.pygame
        buttons = []
        btn_w = (width - gap * (cols - 1)) // cols
        base_color, active_color = ((49, 66, 94), (82, 112, 170)) if side == 'attacker' else ((82, 86, 60), (128, 134, 92))
        for idx, (label, action) in enumerate(items):
            row = idx // cols
            col = idx % cols
            rect = pygame.Rect(x + col * (btn_w + gap), y + row * (row_h + gap), btn_w, row_h)
            is_enabled = True if enabled is None else enabled(action)
            buttons.append(UIButton(rect, label, action, color=base_color, active_color=active_color, enabled=is_enabled))
        rows = (len(items) + cols - 1) // cols if items else 0
        used_h = rows * row_h + max(0, rows - 1) * gap
        return buttons, used_h

    def _build_buttons(self, side, rect):
        pygame = self.pygame
        x = rect.x + 12
        y = rect.y + 16
        width = rect.width - 24

        def attack_enabled(action):
            if action in {'seed_active', 'seed_lurk'}:
                return self.phase == 'setup'
            if action in {'seed_minus', 'seed_plus', 'seed_random', 'seed_apply'}:
                return self.phase in {'setup', 'round_ready'}
            if action == 'start_round':
                return self.phase in {'setup', 'round_ready'}
            if action == 'end_attacker_phase':
                return self.phase == 'attacker_human'
            return self.phase == 'attacker_human'

        def defend_enabled(action):
            if action == 'toggle_ai_honeypot':
                return True
            return self.phase == 'defender_human'

        if side == 'attacker':
            spec = [
                ('开局 / 回合', [('初始 Active', 'seed_active'), ('初始 Lurk', 'seed_lurk'), ('开始回合', 'start_round'), ('结束攻击阶段', 'end_attacker_phase')]),
                ('地图种子', [('种子-1', 'seed_minus'), ('种子+1', 'seed_plus'), ('随机种子', 'seed_random'), ('应用种子', 'seed_apply')]),
                ('C2 指令', [('激活', 'activate'), ('休眠', 'sleep'), ('扫描', 'scan'), ('C2 迁移', 'move_c2')]),
                ('战略打击', [('僵尸占领', 'zombie_convert'), ('僵尸摧毁', 'zombie_destroy'), ('狙击占领', 'precise_convert'), ('狙击摧毁', 'precise_destroy')]),
            ]
            enabled_fn = attack_enabled
        else:
            spec = [
                ('AI / 回合', [('AI 蜜罐开关', 'toggle_ai_honeypot'), ('反击 C2', 'counter_c2'), ('结束回合', 'end_round')]),
                ('常规防守', [('加固', 'harden'), ('蜜罐', 'honeypot'), ('扫描', 'scan'), ('清除', 'clear'), ('夺回', 'recapture'), ('恢复', 'restore')]),
                ('流量清洗', [('清洗 8', 'clean_8'), ('清洗 12', 'clean_12'), ('清洗 16', 'clean_16')]),
            ]
            enabled_fn = defend_enabled

        sections = []
        for title, items in spec:
            buttons, used_h = self._make_button_grid(x, y + 28, width, items, side, enabled=enabled_fn)
            sections.append({'title': title, 'title_rect': pygame.Rect(x, y, width, 22), 'buttons': buttons})
            y += 28 + used_h + 18
        return sections

    def _build_log_buttons(self, side, rect):
        pygame = self.pygame
        collapsed = self.attacker_log_collapsed if side == 'attacker' else self.defender_log_collapsed
        base_color, active_color = ((49, 66, 94), (82, 112, 170)) if side == 'attacker' else ((82, 86, 60), (128, 134, 92))
        x = rect.right - 102
        y = rect.y + 8
        return [
            UIButton(pygame.Rect(x, y, 28, 24), '−', 'log_minus', color=base_color, active_color=active_color),
            UIButton(pygame.Rect(x + 34, y, 28, 24), '+', 'log_plus', color=base_color, active_color=active_color),
            UIButton(pygame.Rect(x + 68, y, 34, 24), '展' if collapsed else '收', 'log_toggle', color=base_color, active_color=active_color),
        ]

    def _draw_card(self, surface, rect, title, value, accent):
        pygame = self.pygame
        pygame.draw.rect(surface, (24, 28, 36), rect, border_radius=10)
        pygame.draw.rect(surface, accent, rect, 1, border_radius=10)
        surface.blit(self.small_font.render(title, True, (170, 180, 196)), (rect.x + 10, rect.y + 8))
        surface.blit(self.font.render(str(value), True, (240, 245, 255)), (rect.x + 10, rect.y + 30))

    def _draw_header(self, surface, side, layout):
        pygame = self.pygame
        header = layout['header']
        pygame.draw.rect(surface, (22, 26, 34), header, border_radius=14)
        pygame.draw.rect(surface, layout['line'], header, 1, border_radius=14)
        title = '攻击方控制台' if side == 'attacker' else '防守方控制台'
        subtitle = '隐藏防守预算 / 蜜罐 / 加固信息' if side == 'attacker' else '隐藏进攻方预算与未暴露 lurk'
        surface.blit(self.title_font.render(title, True, (244, 248, 255)), (header.x + 16, header.y + 12))
        surface.blit(self.small_font.render(subtitle, True, (180, 190, 206)), (header.x + 18, header.y + 48))

        cards = [
            ('回合', f'{self.current_round}/{self.max_rounds}'),
            ('阶段', self.phase),
            ('地图种子', self.selected_seed),
        ]
        if side == 'attacker':
            cards += [
                ('人类 Energy', game_state.get('attacker_human_energy', 0)),
                ('AI Energy', game_state.get('attacker_ai_energy', 0)),
                ('C2 静默', game_state.get('c2_silenced_rounds', 0)),
            ]
        else:
            cards += [
                ('Budget', game_state.get('budget', 0)),
                ('Key', game_state.get('key', 0)),
                ('AI 蜜罐', '开' if self.want_honeypot_ai else '关'),
            ]
        card_w = 112
        start_x = header.right - 16 - len(cards) * (card_w + 8) + 8
        for idx, (t, v) in enumerate(cards):
            rect = pygame.Rect(start_x + idx * (card_w + 8), header.y + 14, card_w, 62)
            self._draw_card(surface, rect, t, v, layout['accent'])

    def _draw_map(self, surface, side, layout):
        pygame = self.pygame
        rect = layout['map']
        positions = layout['positions']
        pygame.draw.rect(surface, (16, 20, 28), rect, border_radius=14)
        pygame.draw.rect(surface, layout['line'], rect, 1, border_radius=14)
        surface.blit(self.font.render('战术地图（点击节点交互）', True, (232, 238, 248)), (rect.x + 14, rect.y + 10))
        surface.blit(self.small_font.render('独立 3D 图窗可自由旋转，本处用于点选节点与隐藏信息', True, (176, 186, 202)), (rect.x + 14, rect.y + 34))
        for u, v in self.G.edges():
            pygame.draw.line(surface, (88, 98, 114), positions[u], positions[v], 1)
        color_map = {
            'DD': (230, 232, 238), 'D': (70, 165, 255), 'H': (240, 200, 70), 'HD': (255, 140, 70),
            'lurk': (162, 90, 205), 'Hlurk': (235, 95, 178), 'HlurkD': (220, 70, 70),
            'active': (90, 220, 110), 'abandoned': (110, 110, 110),
        }
        selected = self.selected_attacker_node if side == 'attacker' else self.selected_defender_node
        for node, pos in positions.items():
            state = self.attacker_view_state(node) if side == 'attacker' else self.defender_view_state(node)
            color = color_map.get(state, (230, 232, 238))
            radius = 18 if node == selected else 15
            pygame.draw.circle(surface, color, pos, radius)
            pygame.draw.circle(surface, (18, 18, 20), pos, radius, 2)
            label = self.small_font.render(node, True, (12, 12, 16))
            surface.blit(label, label.get_rect(center=pos))

    def _draw_actions(self, surface, layout, side):
        pygame = self.pygame
        rect = layout['actions']
        pygame.draw.rect(surface, (16, 20, 28), rect, border_radius=14)
        pygame.draw.rect(surface, layout['line'], rect, 1, border_radius=14)
        for section in layout['sections']:
            surface.blit(self.font.render(section['title'], True, (236, 240, 248)), (section['title_rect'].x, section['title_rect'].y))
            for btn in section['buttons']:
                active = (self.current_attacker_action == btn.action) if side == 'attacker' else (self.current_defender_action == btn.action)
                if side == 'defender' and btn.action == 'toggle_ai_honeypot' and self.want_honeypot_ai:
                    active = True
                btn.draw(surface, self.small_font, is_active=active)

    def _draw_status(self, surface, side, layout):
        pygame = self.pygame
        rect = layout['status']
        pygame.draw.rect(surface, (20, 24, 32), rect, border_radius=12)
        pygame.draw.rect(surface, layout['line'], rect, 1, border_radius=12)
        pygame.draw.rect(surface, layout['accent'], (rect.x, rect.y, 6, rect.height), border_top_left_radius=12, border_bottom_left_radius=12)
        surface.blit(self.small_font.render('状态', True, (188, 198, 214)), (rect.x + 14, rect.y + 8))
        msg = self.attacker_status if side == 'attacker' else self.defender_status
        wrapped = self._wrap_text(self.small_font, msg, rect.width - 40)[:2]
        for i, line in enumerate(wrapped):
            surface.blit(self.small_font.render(line, True, (244, 246, 252)), (rect.x + 14, rect.y + 28 + i * 18))
        if self.winner is not None:
            surface.blit(self.font.render(f'胜者：{self.winner}', True, (255, 190, 130)), (rect.right - 140, rect.y + 18))

    def _draw_logs(self, surface, side, layout):
        pygame = self.pygame
        rect = layout['log']
        pygame.draw.rect(surface, (18, 20, 26), rect, border_radius=12)
        pygame.draw.rect(surface, layout['line'], rect, 1, border_radius=12)
        title = '攻击方日志' if side == 'attacker' else '防守方日志'
        surface.blit(self.font.render(title, True, (236, 240, 248)), (rect.x + 12, rect.y + 8))
        for btn in layout['log_buttons']:
            btn.draw(surface, self.small_font)
        if layout['log_collapsed']:
            return
        logs = self.attacker_logs if side == 'attacker' else self.defender_logs
        available_h = rect.height - 42
        line_h = 18
        max_lines = max(1, available_h // line_h)
        for idx, line in enumerate(logs[-max_lines:]):
            surface.blit(self.mono_font.render(line[:118], True, (196, 206, 220)), (rect.x + 12, rect.y + 40 + idx * line_h))

    def _draw_window(self, side):
        size = self.attacker_window.size if side == 'attacker' else self.defender_window.size
        size = (int(size[0]), int(size[1]))
        surface_attr = 'attacker_surface' if side == 'attacker' else 'defender_surface'
        renderer = self.attacker_renderer if side == 'attacker' else self.defender_renderer
        layout = self._build_layout(side, size)
        if side == 'attacker':
            self.attacker_layout = layout
        else:
            self.defender_layout = layout

        surface = getattr(self, surface_attr)
        if surface is None or surface.get_size() != size:
            surface = self.pygame.Surface(size)
            setattr(self, surface_attr, surface)
        surface.fill(layout['panel_bg'])
        self._draw_header(surface, side, layout)
        self._draw_map(surface, side, layout)
        self._draw_actions(surface, layout, side)
        self._draw_status(surface, side, layout)
        self._draw_logs(surface, side, layout)

        renderer.clear()
        texture = self.Texture.from_surface(renderer, surface)
        texture.draw()
        renderer.present()
        del texture

    def start_round(self):
        if self.winner is not None:
            return
        if self.current_round >= self.max_rounds:
            self.winner = 'defender'
            self.phase = 'game_over'
            self.attacker_status = f'达到最大回合数 {self.max_rounds}，防守方胜利。'
            self.defender_status = self.attacker_status
            self._mark_views_dirty()
            return
        self.current_round += 1
        self.pending_special_attack = None
        self.special_mode = 'convert'
        self.extra_defense = 0.0
        self.current_attacker_action = None
        self.current_defender_action = None
        self.scan_source_attacker = None
        self.selected_attacker_node = None
        self.selected_defender_node = None

        res = self.attacker.gain_energy_per_round(base_recover=2)
        self.add_attacker_log(f'R{self.current_round} 回能: {self._result_msg(res)}')
        self.add_defender_log(f'R{self.current_round} 进攻方回能已完成')
        self.add_defender_log(self._result_msg(self.defender.auto_increase_budget_per_round(amount=2)))
        self.add_defender_log(self._result_msg(self.defender.increase_budget_from_capture(income_per_node=1)))
        ai_logs = attacker_ai_operational_phase(self.attacker, self.node_importance)
        if ai_logs:
            for tag, msg in ai_logs:
                line = f'{tag}: {self._result_msg(msg)}'
                self.add_attacker_log(line)
                self.add_defender_log('进攻方 AI 已执行常规动作')
            self.attacker_status = f'第 {self.current_round} 回合：进攻方 AI 已自动执行 {len(ai_logs)} 次常规动作，请继续执行战略技能或结束攻击阶段。'
        else:
            self.attacker_status = f'第 {self.current_round} 回合：本回合 AI 未找到可执行的常规动作，请执行战略技能或结束攻击阶段。'
        self.phase = 'attacker_human'
        self.defender_status = f'第 {self.current_round} 回合：等待攻击方完成战略行动。'
        self._mark_views_dirty()

    def run_defender_ai(self):
        extra, logs = defender_ai_phase_ui(self.defender, pending_special_attack=self.pending_special_attack, node_importance=self.node_importance, want_honeypot=self.want_honeypot_ai)
        self.extra_defense += extra
        if logs:
            for tag, msg in logs:
                self.add_defender_log(f'{tag}: {self._result_msg(msg)}')
            self.defender_status = f'防守方 AI 已自动执行 {len(logs)} 次常规动作。现在可以继续手动防守，然后点击“结束回合”。'
        else:
            self.defender_status = '防守方 AI 本回合未找到可执行动作。现在可以继续手动防守，然后点击“结束回合”。'
        self.phase = 'defender_human'
        self.attacker_status = '防守方 AI 已自动行动，等待防守方手动收尾。'
        self._mark_views_dirty()

    def finish_round(self):
        if self.pending_special_attack is not None:
            _set_attacker_mode(self.attacker, 'human')
            result = resolve_pending_special_attack(self.attacker, self.pending_special_attack, extra_defense=self.extra_defense, success_mode=self.special_mode)
            self.add_attacker_log(f'特殊攻击结算: {self._result_msg(result)}')
            self.add_defender_log(f'特殊攻击结算: {self._result_msg(result)}')
        end_round()
        game_over, winner, msg = check_win_condition(trojan_nodes, self.max_rounds, self.current_round)
        self.attacker_status = msg
        self.defender_status = msg
        self.add_attacker_log(msg)
        self.add_defender_log(msg)
        if game_over:
            self.winner = winner
            self.phase = 'game_over'
        else:
            self.phase = 'round_ready'
        self._mark_views_dirty()

    def _apply_attacker_action(self, action, node):
        _set_attacker_mode(self.attacker, 'human')
        if action == 'activate':
            res = self.attacker.activate(node)
        elif action == 'sleep':
            res = self.attacker.sleep(node)
        elif action == 'zombie_convert':
            self.special_mode = 'convert'
            self.pending_special_attack, res = prepare_zombie_legion(self.attacker, node)
        elif action == 'zombie_destroy':
            self.special_mode = 'destroy'
            self.pending_special_attack, res = prepare_zombie_legion(self.attacker, node)
        elif action == 'precise_convert':
            self.special_mode = 'convert'
            self.pending_special_attack, res = prepare_precise_strike(self.attacker, node, participants=None)
        elif action == 'precise_destroy':
            self.special_mode = 'destroy'
            self.pending_special_attack, res = prepare_precise_strike(self.attacker, node, participants=None)
        else:
            return
        msg = self._result_msg(res)
        self.add_attacker_log(msg)
        self.attacker_status = msg
        self.current_attacker_action = None
        self._mark_views_dirty()

    def _apply_defender_action(self, action, node):
        _set_defender_mode(self.defender, 'human')
        if action == 'harden':
            res = self.defender.apply_hardening(node)
        elif action == 'honeypot':
            res = self.defender.deploy_honeypot(node)
        elif action == 'scan':
            res = self.defender.scan_nodes(node)
        elif action == 'clear':
            res = self.defender.clear_virus(node)
        elif action == 'recapture':
            res = self.defender.recapture_lost_nodes(node)
        elif action == 'restore':
            res = self.defender.restore_abandoned(node)
        else:
            return
        msg = self._result_msg(res)
        self.add_defender_log(msg)
        self.defender_status = msg
        self.current_defender_action = None
        _set_defender_mode(self.defender, 'ai')
        self._mark_views_dirty()

    def _apply_defender_clean_traffic(self, eq_invest):
        if self.pending_special_attack is None:
            msg = '当前没有待响应的特殊攻击，无法进行流量清洗。'
            self.defender_status = msg
            self.add_defender_log(msg)
            return
        actual_cost = eq_invest * 3
        if game_state.get('budget', 0) < actual_cost:
            msg = f'budget 不足，清洗 {eq_invest} 需要 {actual_cost} budget。'
            self.defender_status = msg
            self.add_defender_log(msg)
            return
        game_state['budget'] -= actual_cost
        added = max(0.0, eq_invest - 8) * 0.7
        self.extra_defense += added
        msg = f'人类部署流量清洗成功，花费 {actual_cost} budget（AI 等效 {eq_invest}），额外防御 +{added:.2f}'
        self.defender_status = msg
        self.add_defender_log(msg)
        self._mark_views_dirty()

    def _apply_counter_c2(self):
        need_key = 3
        actual_cost = 15
        if game_state.get('key', 0) < need_key:
            msg = f'C2 线索不足，当前仅有 {game_state.get("key", 0)}/{need_key}。'
            self.defender_status = msg
            self.add_defender_log(msg)
            return
        if game_state.get('budget', 0) < actual_cost:
            msg = f'budget 不足，人类反击 C2 需要 {actual_cost}。'
            self.defender_status = msg
            self.add_defender_log(msg)
            return
        game_state['budget'] -= actual_cost
        game_state['key'] -= need_key
        game_state['c2_silenced_rounds'] += 2
        msg = '人类成功反击 C2，已静默 2 回合。'
        self.defender_status = msg
        self.add_defender_log(msg)
        self._mark_views_dirty()

    def handle_attacker_button(self, action):
        if action == 'log_toggle':
            self.attacker_log_collapsed = not self.attacker_log_collapsed
            return
        if action == 'log_plus':
            self.attacker_log_height = min(420, self.attacker_log_height + 50)
            return
        if action == 'log_minus':
            self.attacker_log_height = max(120, self.attacker_log_height - 50)
            return
        if action in {'seed_active', 'seed_lurk'}:
            if self.phase != 'setup':
                self.attacker_status = '初始感染只能在游戏开始前设置。'
                return
            if not self.selected_attacker_node:
                self.attacker_status = '请先点选一个初始感染节点。'
                return
            state = 'active' if action == 'seed_active' else 'lurk'
            res = self.attacker.seed_initial_node(self.selected_attacker_node, state)
            msg = self._result_msg(res)
            self.add_attacker_log(msg)
            self.attacker_status = msg + ' 然后点击“开始回合”。'
            self.phase = 'round_ready'
            self._mark_views_dirty()
            return
        if action == 'seed_minus':
            self._set_seed_value(delta=-1)
            self._mark_views_dirty()
            return
        if action == 'seed_plus':
            self._set_seed_value(delta=1)
            self._mark_views_dirty()
            return
        if action == 'seed_random':
            self._set_seed_value(randomize=True)
            self._mark_views_dirty()
            return
        if action == 'seed_apply':
            self._apply_selected_seed()
            return
        if action == 'start_round':
            if self.phase not in {'setup', 'round_ready'}:
                self.attacker_status = '当前不能开始新回合。'
                return
            infected = [n for n in trojan_nodes if trojan_nodes[n][0] in {'lurk', 'active'}]
            if not infected:
                self.attacker_status = '请先设置初始感染点。'
                return
            self.start_round()
            return
        if self.phase != 'attacker_human':
            self.attacker_status = '当前不是攻击方人类操作阶段。'
            return
        if action == 'move_c2':
            res = self.attacker.move_c2()
            msg = self._result_msg(res)
            self.add_attacker_log(msg)
            self.attacker_status = msg
            self._mark_views_dirty()
            return
        if action == 'end_attacker_phase':
            self.run_defender_ai()
            return
        self.current_attacker_action = action
        self.scan_source_attacker = None
        tips = {
            'activate': '请选择一个 lurk 节点进行激活。',
            'sleep': '请选择一个 active 节点进行休眠。',
            'scan': '请先点击扫描源节点，再点击目标节点。',
            'zombie_convert': '请选择僵尸军团的目标节点（成功后占领）。',
            'zombie_destroy': '请选择僵尸军团的目标节点（成功后摧毁）。',
            'precise_convert': '请选择精准狙击的目标节点（成功后占领）。',
            'precise_destroy': '请选择精准狙击的目标节点（成功后摧毁）。',
        }
        self.attacker_status = tips.get(action, '请选择节点。')

    def handle_defender_button(self, action):
        if action == 'log_toggle':
            self.defender_log_collapsed = not self.defender_log_collapsed
            return
        if action == 'log_plus':
            self.defender_log_height = min(420, self.defender_log_height + 50)
            return
        if action == 'log_minus':
            self.defender_log_height = max(120, self.defender_log_height - 50)
            return
        if action == 'toggle_ai_honeypot':
            self.want_honeypot_ai = not self.want_honeypot_ai
            msg = f'防守方 AI 蜜罐预测已切换为：{"开启" if self.want_honeypot_ai else "关闭"}'
            self.defender_status = msg
            self.add_defender_log(msg)
            return
        if self.phase != 'defender_human':
            self.defender_status = '当前不是防守方人类操作阶段。'
            return
        if action == 'end_round':
            self.finish_round()
            return
        if action == 'counter_c2':
            self._apply_counter_c2()
            return
        if action == 'clean_8':
            self._apply_defender_clean_traffic(8)
            return
        if action == 'clean_12':
            self._apply_defender_clean_traffic(12)
            return
        if action == 'clean_16':
            self._apply_defender_clean_traffic(16)
            return
        self.current_defender_action = action
        tips = {
            'harden': '请选择一个节点进行加固。',
            'honeypot': '请选择一个节点部署蜜罐。',
            'scan': '请选择一个节点进行扫描。',
            'clear': '请选择一个已确认 lurk 的节点进行清除。',
            'recapture': '请选择一个 active 节点进行夺回。',
            'restore': '请选择一个 abandoned 节点进行恢复。',
        }
        self.defender_status = tips.get(action, '请选择节点。')

    def _node_hit(self, pos, positions):
        for node, (x, y) in positions.items():
            if (pos[0] - x) ** 2 + (pos[1] - y) ** 2 <= 19 ** 2:
                return node
        return None

    def handle_attacker_node_click(self, node):
        self.selected_attacker_node = node
        if self.phase in {'setup', 'round_ready'}:
            self.attacker_status = f'已选中初始节点 {node}。请选择“初始 Active”或“初始 Lurk”。'
            return
        if self.phase != 'attacker_human':
            return
        action = self.current_attacker_action
        if not action:
            self.attacker_status = f'已选中 {node}。请选择一个战略技能按钮。'
            return
        if action == 'scan':
            if self.scan_source_attacker is None:
                self.scan_source_attacker = node
                self.attacker_status = f'扫描源已选择 {node}，请再点击扫描目标。'
            else:
                _set_attacker_mode(self.attacker, 'human')
                res = self.attacker.scan_node(self.scan_source_attacker, node)
                msg = self._result_msg(res)
                self.add_attacker_log(msg)
                self.attacker_status = msg
                self.scan_source_attacker = None
                self.current_attacker_action = None
                self._mark_views_dirty()
            return
        self._apply_attacker_action(action, node)

    def handle_defender_node_click(self, node):
        self.selected_defender_node = node
        if self.phase != 'defender_human':
            self.defender_status = f'防守方面板选中 {node}。当前还不能进行人工防守操作。'
            return
        action = self.current_defender_action
        if not action:
            self.defender_status = f'已选中 {node}。请选择一个防守操作按钮。'
            return
        self._apply_defender_action(action, node)

    def _event_window_id(self, event):
        for name in ('window', 'windowID', 'window_id'):
            if hasattr(event, name):
                value = getattr(event, name)
                if isinstance(value, int):
                    return value
        if hasattr(event, 'dict') and isinstance(event.dict, dict):
            for name in ('window', 'windowID', 'window_id'):
                if name in event.dict:
                    return event.dict[name]
        return None

    def _which_side(self, window_id):
        if window_id == self.attacker_window.id:
            return 'attacker'
        if window_id == self.defender_window.id:
            return 'defender'
        return None

    def _handle_click(self, side, pos):
        layout = self.attacker_layout if side == 'attacker' else self.defender_layout
        if layout is None:
            return
        for btn in layout['log_buttons']:
            if btn.hit(pos):
                (self.handle_attacker_button if side == 'attacker' else self.handle_defender_button)(btn.action)
                return
        for section in layout['sections']:
            for btn in section['buttons']:
                if btn.hit(pos):
                    (self.handle_attacker_button if side == 'attacker' else self.handle_defender_button)(btn.action)
                    return
        node = self._node_hit(pos, layout['positions'])
        if node is not None:
            if side == 'attacker':
                self.handle_attacker_node_click(node)
            else:
                self.handle_defender_node_click(node)

    def run(self):
        pygame = self.pygame
        windowclose_evt = getattr(pygame, 'WINDOWCLOSE', None)
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif windowclose_evt is not None and event.type == windowclose_evt:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
                    side = self._which_side(self._event_window_id(event))
                    if side is not None:
                        self._handle_click(side, event.pos)
            self._draw_window('attacker')
            self._draw_window('defender')
            try:
                plt.pause(0.001)
            except Exception:
                pass
            self.clock.tick(30)
        self._safe_destroy_viewer(self.attacker_viewer)
        self._safe_destroy_viewer(self.defender_viewer)
        pygame.quit()
        return self.winner


def run_game_pygame(max_rounds=20, seed=43):
    ui = CyberGameUI(max_rounds=max_rounds, seed=seed)
    return ui.run()


if __name__ == '__main__':
    import sys

    seed = 43
    max_rounds = 20
    args = list(sys.argv[1:])
    if '--seed' in args:
        try:
            idx = args.index('--seed')
            seed = int(args[idx + 1])
        except Exception:
            print('警告：--seed 参数无效，已回退到默认种子 42。')
            seed = 43
    if '--rounds' in args:
        try:
            idx = args.index('--rounds')
            max_rounds = int(args[idx + 1])
        except Exception:
            print('警告：--rounds 参数无效，已回退到默认回合数 20。')
            max_rounds = 20
    use_cli = '--cli' in args
    if not use_cli:
        try:
            winner = run_game_pygame(max_rounds=max_rounds, seed=seed)
            print('最终胜者：', winner)
        except Exception as exc:
            print('pygame UI 启动失败，已回退到命令行模式：', exc)
            winner = run_game(max_rounds=max_rounds, seed=seed)
            print('最终胜者：', winner)
    else:
        winner = run_game(max_rounds=max_rounds, seed=seed)
        print('最终胜者：', winner)
