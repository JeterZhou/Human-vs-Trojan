# -*- coding: utf-8 -*-
"""
单窗口参考面板版
- 一个 Tk 主窗口
- Notebook 两个页签：攻击方 / 防守方
- 每个页签采用“左图右控件”布局，风格参考用户上传的 HVT_remote_battle.py
- 复用原始脚本中的游戏逻辑，不再使用 pygame 多窗口，也不再弹出独立 matplotlib 窗口
"""
from __future__ import annotations

import importlib.util
import os
import random
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

ORIGINAL_BASENAME = "HVT_dual_panel_3d_ui_ai_seed_cn_fixed.py"


def load_original_module(path: str):
    spec = importlib.util.spec_from_file_location("hvt_original_module", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载原始脚本: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RolePanel(ttk.Frame):
    def __init__(self, master, app: "ReferencePanelApp", role: str):
        super().__init__(master, padding=8)
        self.app = app
        self.role = role
        self.figure = None
        self.ax = None
        self.canvas = None
        self.toolbar = None
        self.node_tree = None
        self.log_text = None
        self.summary_var = tk.StringVar(value="")
        self.round_var = tk.StringVar(value="回合: 0/0")
        self.phase_var = tk.StringVar(value="阶段: setup")
        self.resource_var = tk.StringVar(value="")
        self.turn_hint_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="等待开始")
        self.seed_var = tk.IntVar(value=42)
        self.max_rounds_var = tk.IntVar(value=20)
        self.init_node_var = tk.StringVar()
        self.init_state_var = tk.StringVar(value="active")
        self.source_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.radius_var = tk.IntVar(value=2)
        self.special_mode_var = tk.StringVar(value="convert")
        self.use_all_active_var = tk.BooleanVar(value=True)
        self.participants_var = tk.StringVar(value="")
        self.node_value_var = tk.StringVar(value="1.0")
        self.clean_amount_var = tk.IntVar(value=8)
        self._build_ui()

    def _build_ui(self):
        outer = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        outer.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        left = ttk.Frame(outer, padding=6)
        right = ttk.Frame(outer, padding=6)
        outer.add(left, weight=3)
        outer.add(right, weight=2)

        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        right.rowconfigure(5, weight=1)
        right.rowconfigure(6, weight=1)
        right.columnconfigure(0, weight=1)

        self.figure = Figure(figsize=(9.6, 7.8), facecolor="black")
        self.ax = self.figure.add_subplot(111, projection="3d")
        self.canvas = FigureCanvasTkAgg(self.figure, master=left)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        toolbar_frame = ttk.Frame(left)
        toolbar_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side=tk.LEFT, fill=tk.X)

        legend_text = (
            "颜色说明: 白=普通/未知  紫=lurk  绿=active  灰=abandoned"
            if self.role == "attacker"
            else "颜色说明: DD=白 D=蓝 H=黄 HD=橙 lurk=紫 Hlurk=粉 HlurkD=红 active=绿 abandoned=灰"
        )
        ttk.Label(left, text=legend_text).grid(row=2, column=0, sticky="ew", pady=(8, 0))

        summary_frame = ttk.LabelFrame(right, text="战局信息", padding=8)
        summary_frame.grid(row=0, column=0, sticky="ew")
        summary_frame.columnconfigure(0, weight=1)
        summary_frame.columnconfigure(1, weight=1)
        ttk.Label(summary_frame, textvariable=self.summary_var).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(summary_frame, textvariable=self.round_var, font=("Microsoft YaHei UI", 11, "bold")).grid(row=1, column=0, sticky="w")
        ttk.Label(summary_frame, textvariable=self.phase_var, font=("Microsoft YaHei UI", 11, "bold")).grid(row=1, column=1, sticky="e")
        ttk.Label(summary_frame, textvariable=self.resource_var, wraplength=480).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(summary_frame, textvariable=self.turn_hint_var, foreground="#0a5").grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(summary_frame, textvariable=self.status_var, wraplength=480, foreground="#444").grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        if self.role == "attacker":
            setup_frame = ttk.LabelFrame(right, text="开局设置", padding=8)
            setup_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
            ttk.Label(setup_frame, text="随机种子").grid(row=0, column=0, sticky="w")
            ttk.Spinbox(setup_frame, from_=0, to=999999, textvariable=self.seed_var, width=10).grid(row=0, column=1, sticky="w")
            ttk.Label(setup_frame, text="最大回合").grid(row=0, column=2, sticky="w", padx=(10, 0))
            ttk.Spinbox(setup_frame, from_=1, to=200, textvariable=self.max_rounds_var, width=10).grid(row=0, column=3, sticky="w")

            ttk.Label(setup_frame, text="初始感染点").grid(row=1, column=0, sticky="w", pady=(6, 0))
            self.init_node_combo = ttk.Combobox(setup_frame, textvariable=self.init_node_var, width=10, state="readonly")
            self.init_node_combo.grid(row=1, column=1, sticky="w", pady=(6, 0))
            ttk.Label(setup_frame, text="初始状态").grid(row=1, column=2, sticky="w", padx=(10, 0), pady=(6, 0))
            ttk.Combobox(setup_frame, textvariable=self.init_state_var, values=["active", "lurk"], width=10, state="readonly").grid(row=1, column=3, sticky="w", pady=(6, 0))

            ctrl = ttk.Frame(setup_frame)
            ctrl.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0))
            ctrl.columnconfigure(0, weight=1)
            ctrl.columnconfigure(1, weight=1)
            ctrl.columnconfigure(2, weight=1)
            ttk.Button(ctrl, text="重置地图", command=self.app.reset_game_from_panel).grid(row=0, column=0, sticky="ew")
            ttk.Button(ctrl, text="开始游戏/下一回合", command=self.app.start_round).grid(row=0, column=1, sticky="ew", padx=6)
            ttk.Button(ctrl, text="结束进攻阶段", command=self.app.end_attacker_phase).grid(row=0, column=2, sticky="ew")
        else:
            info_frame = ttk.LabelFrame(right, text="回合控制", padding=8)
            info_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
            ttk.Label(
                info_frame,
                justify=tk.LEFT,
            ).grid(row=0, column=0, columnspan=2, sticky="w")
            ttk.Button(info_frame, text="结束本回合", command=self.app.finish_round).grid(row=1, column=1, sticky="e", pady=(8, 0))
            self.init_node_combo = None

        selection_frame = ttk.LabelFrame(right, text="当前选择", padding=8)
        selection_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(selection_frame, text="source").grid(row=0, column=0, sticky="w")
        self.source_combo = ttk.Combobox(selection_frame, textvariable=self.source_var, width=10, state="readonly")
        self.source_combo.grid(row=0, column=1, sticky="w")
        ttk.Label(selection_frame, text="target").grid(row=0, column=2, sticky="w", padx=(10, 0))
        self.target_combo = ttk.Combobox(selection_frame, textvariable=self.target_var, width=10, state="readonly")
        self.target_combo.grid(row=0, column=3, sticky="w")
        ttk.Label(selection_frame, text="radius").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(selection_frame, from_=1, to=10, textvariable=self.radius_var, width=10).grid(row=1, column=1, sticky="w", pady=(6, 0))

        if self.role == "attacker":
            ttk.Label(selection_frame, text="特攻结果").grid(row=1, column=2, sticky="w", padx=(10, 0), pady=(6, 0))
            ttk.Combobox(selection_frame, textvariable=self.special_mode_var, values=["convert", "destroy"], width=12, state="readonly").grid(row=1, column=3, sticky="w", pady=(6, 0))
            ttk.Checkbutton(selection_frame, text="精准打击使用全部 active 节点", variable=self.use_all_active_var).grid(row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))
            ttk.Label(selection_frame, text="参与节点(逗号分隔)").grid(row=3, column=0, sticky="w", pady=(6, 0))
            ttk.Entry(selection_frame, textvariable=self.participants_var, width=32).grid(row=3, column=1, columnspan=3, sticky="ew", pady=(6, 0))
            ttk.Label(selection_frame, text="节点价值").grid(row=4, column=0, sticky="w", pady=(6, 0))
            ttk.Entry(selection_frame, textvariable=self.node_value_var, width=12).grid(row=4, column=1, sticky="w", pady=(6, 0))
        else:
            ttk.Label(selection_frame, text="清洗投入").grid(row=1, column=2, sticky="w", padx=(10, 0), pady=(6, 0))
            ttk.Combobox(selection_frame, textvariable=self.clean_amount_var, values=[8, 12, 16], width=12, state="readonly").grid(row=1, column=3, sticky="w", pady=(6, 0))
        selection_frame.columnconfigure(3, weight=1)

        action_frame = ttk.LabelFrame(right, text="可执行动作", padding=8)
        action_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.action_buttons = {}
        if self.role == "attacker":
            actions = [
                ("1 激活 lurk\n(C2 命令)", self.app.attacker_activate),
                ("2 休眠 active\n(C2 命令)", self.app.attacker_sleep),
                ("3 扫描节点\n(C2 命令)", self.app.attacker_scan),
                ("4 僵尸军团", self.app.attacker_zombie),
                ("5 精准狙击", self.app.attacker_precise),
                ("6 C2 迁移\n(固定15 human_energy)", self.app.attacker_move_c2),
            ]
            cols = 2
        else:
            actions = [
                ("加固节点", self.app.defender_harden),
                ("扫描节点", self.app.defender_scan),
                ("清除潜伏病毒", self.app.defender_clear),
                ("夺回 active 节点", self.app.defender_recapture),
                ("恢复 abandoned", self.app.defender_restore),
                ("反制 C2", self.app.defender_counter_c2),
                ("流量清洗", self.app.defender_clean),
                ("结束本回合", self.app.finish_round),
            ]
            cols = 2
        for idx, (label, command) in enumerate(actions):
            row = idx // cols
            col = idx % cols
            btn = ttk.Button(action_frame, text=label, command=command)
            btn.grid(row=row, column=col, sticky="ew", padx=4, pady=4)
            action_frame.columnconfigure(col, weight=1)
            self.action_buttons[label] = btn

        table_frame = ttk.LabelFrame(right, text="节点信息", padding=8)
        table_frame.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        if self.role == "attacker":
            cols = ("node", "view", "scan", "remark")
            headings = ("节点", "你的视图", "扫描结果", "备注")
            widths = (60, 90, 240, 120)
        else:
            cols = ("node", "base", "view", "scan")
            headings = ("节点", "基础属性", "你的视图", "扫描记录")
            widths = (60, 90, 90, 260)
        self.node_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=10)
        for c, h, w in zip(cols, headings, widths):
            self.node_tree.heading(c, text=h)
            self.node_tree.column(c, width=w, anchor="center")
        self.node_tree.grid(row=0, column=0, sticky="nsew")
        node_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.node_tree.yview)
        node_scroll.grid(row=0, column=1, sticky="ns")
        self.node_tree.configure(yscrollcommand=node_scroll.set)

        log_frame = ttk.LabelFrame(right, text="日志", padding=8)
        log_frame.grid(row=6, column=0, sticky="nsew", pady=(8, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, wrap="word", height=12)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set, state=tk.DISABLED)

    def append_log(self, msg: str):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def set_node_values(self, values):
        for cb in [getattr(self, name) for name in ["source_combo", "target_combo"]]:
            cb["values"] = values
        if self.role == "attacker" and self.init_node_combo is not None:
            self.init_node_combo["values"] = values
        if values:
            if not self.source_var.get():
                self.source_var.set(values[0])
            if not self.target_var.get():
                self.target_var.set(values[0])
            if self.role == "attacker" and self.init_node_combo is not None and not self.init_node_var.get():
                self.init_node_var.set(values[0])


class ReferencePanelApp(tk.Tk):
    def __init__(self, module, original_path: str):
        super().__init__()
        self.m = module
        self.original_path = original_path
        self.title("HVT 单窗口参考面板版")
        self.geometry("1850x1050")
        self.minsize(1500, 900)
        self.phase = "setup"
        self.current_round = 0
        self.max_rounds = 20
        self.pending_special_attack = None
        self.special_mode = "convert"
        self.extra_defense = 0.0
        self.winner = None
        self.awaiting_defender_entry_prompt = False
        self._build_ui()
        self.reset_game(seed=42, max_rounds=20)
        self.after(200, self.periodic_refresh)

    def _build_ui(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        top = ttk.Frame(self, padding=(8, 6))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(3, weight=1)
        ttk.Label(top, text="原始逻辑文件:").grid(row=0, column=0, sticky="w")
        self.path_var = tk.StringVar(value=self.original_path)
        ttk.Entry(top, textvariable=self.path_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=(6, 6))
        ttk.Button(top, text="重新选择原脚本", command=self.reload_original_script).grid(row=0, column=2, sticky="w")
        self.global_var = tk.StringVar(value="已加载。")
        ttk.Label(top, textvariable=self.global_var, foreground="#444").grid(row=0, column=3, sticky="e")

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.attacker_panel = RolePanel(self.notebook, self, "attacker")
        self.defender_panel = RolePanel(self.notebook, self, "defender")
        self.notebook.add(self.attacker_panel, text="攻击方")
        self.notebook.add(self.defender_panel, text="防守方")
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def reload_original_script(self):
        path = filedialog.askopenfilename(
            title="选择原始 HVT 脚本",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.m = load_original_module(path)
            self.original_path = path
            self.path_var.set(path)
            self.reset_game(seed=self.attacker_panel.seed_var.get(), max_rounds=self.attacker_panel.max_rounds_var.get())
            self.global_var.set("已重新加载原始脚本。")
        except Exception as exc:
            messagebox.showerror("加载失败", str(exc), parent=self)

    def on_tab_changed(self, event=None):
        if self.notebook.select() == str(self.defender_panel) and self.awaiting_defender_entry_prompt:
            self.awaiting_defender_entry_prompt = False
            self.prompt_pre_ai_honeypot()
            self.run_defender_ai_phase()


    def reset_game_from_panel(self):
        self.reset_game(seed=int(self.attacker_panel.seed_var.get()), max_rounds=int(self.attacker_panel.max_rounds_var.get()))

    def reset_game(self, seed=42, max_rounds=20):
        m = self.m
        self.phase = "setup"
        self.current_round = 0
        self.max_rounds = int(max_rounds)
        self.pending_special_attack = None
        self.special_mode = "convert"
        self.extra_defense = 0.0
        self.winner = None
        self.awaiting_defender_entry_prompt = False
        G, pos3d, _ = m.generate_game_graph(num_nodes=15, edge_prob=0.2, seed=int(seed))
        self.G = G
        self.pos3d = pos3d
        self.node_importance = m.compute_node_importance(G)
        for node in m.trojan_nodes:
            m.trojan_nodes[node][0] = "DD"
            m.trojan_nodes[node][1] = "DD"
            m.trojan_scanned[node] = "unknown"
            m.defender_scanned[node] = "unknown"
            m.trojan_cooldown[node] = 0
        m.game_state["attacker_human_energy"] = 5
        m.game_state["attacker_ai_energy"] = 5
        m.game_state["attacker_energy_mode"] = "ai"
        m.game_state["defender_budget_mode"] = "ai"
        m.game_state["budget"] = 5
        m.game_state["key"] = 0
        m.game_state["c2_silenced_rounds"] = 0
        m.game_state["c2_move_count"] = 0
        m.game_state["zombie_used"] = 0
        m.game_state["zombie_max"] = 2
        self.attacker = m.TrojanHorse(G, m.trojan_nodes, m.trojan_scanned, m.defender_scanned, m.game_state)
        self.defender = m.Defender(G, m.trojan_nodes, m.defender_scanned, m.game_state)
        values = list(G.nodes())
        self.attacker_panel.set_node_values(values)
        self.defender_panel.set_node_values(values)
        self.attacker_panel.seed_var.set(int(seed))
        self.attacker_panel.max_rounds_var.set(int(max_rounds))
        self.defender_panel.seed_var.set(int(seed))
        self.defender_panel.max_rounds_var.set(int(max_rounds))
        self.attacker_panel.clear_log()
        self.defender_panel.clear_log()
        self.attacker_panel.status_var.set("请选择初始感染点和初始状态，然后点击‘开始游戏/下一回合’。")
        self.defender_panel.status_var.set("等待攻击方完成开局。")
        self.global_var.set(f"地图已按 seed={seed} 重置。")
        self.refresh_all()

    def msg(self, res):
        return res.get("msg", str(res)) if isinstance(res, dict) else str(res)

    def attacker_view_state(self, node):
        real_state, base_state = self.m.trojan_nodes[node]
        if base_state == "abandoned":
            return "abandoned"
        if real_state == "active":
            return "active"
        if real_state == "lurk":
            return "lurk"
        return "DD"

    def defender_view_state(self, node):
        return self.m.get_display_status(node)

    def refresh_figure(self, panel: RolePanel):
        ax = panel.ax
        elev = getattr(ax, "elev", 30)
        azim = getattr(ax, "azim", -60)
        ax.cla()
        panel.figure.patch.set_facecolor("black")
        ax.set_facecolor("black")
        state_getter = self.attacker_view_state if panel.role == "attacker" else self.defender_view_state
        for u, v in self.G.edges():
            x = [self.pos3d[u][0], self.pos3d[v][0]]
            y = [self.pos3d[u][1], self.pos3d[v][1]]
            z = [self.pos3d[u][2], self.pos3d[v][2]]
            ax.plot(x, y, z, c="white", linewidth=0.8, alpha=0.55)
        coords = list(self.pos3d.values())
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        zs = [p[2] for p in coords]
        pad = 0.15
        for node, (x, y, z) in self.pos3d.items():
            state = state_getter(node)
            color = self.m.get_node_color(state)
            ax.scatter(x, y, z, s=150, c=color, edgecolors="black", linewidths=0.7)
            ax.text(x, y, z, f"{node}\n{state}", color="white", fontsize=9)
        ax.set_xlim(min(xs) - pad, max(xs) + pad)
        ax.set_ylim(min(ys) - pad, max(ys) + pad)
        ax.set_zlim(min(zs) - pad, max(zs) + pad)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])
        ax.grid(False)
        ax.set_axis_off()
        ax.set_box_aspect([1, 1, 1])
        title = ("攻击方" if panel.role == "attacker" else "防守方") + f" 3D 视图 | R{self.current_round} | {self.phase}"
        ax.set_title(title, color="white", fontsize=13)
        ax.view_init(elev=elev, azim=azim)
        panel.figure.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.94)
        panel.canvas.draw_idle()

    def refresh_summary(self, panel: RolePanel):
        gs = self.m.game_state
        panel.round_var.set(f"回合: {self.current_round}/{self.max_rounds}")
        panel.phase_var.set(f"阶段: {self.phase}")
        panel.summary_var.set("单窗口参考面板模式，左图右控件。")
        if panel.role == "attacker":
            panel.resource_var.set(
                f"人类 Energy={gs.get('attacker_human_energy', 0)} | AI Energy={gs.get('attacker_ai_energy', 0)} | C2静默={gs.get('c2_silenced_rounds', 0)}"
            )
            panel.turn_hint_var.set("人类只负责：激活 / 休眠 / 扫描 / 僵尸军团 / 精准狙击 / C2迁移；其他进攻动作交给 AI。")
        else:
            panel.resource_var.set(
                f"Budget={gs.get('budget', 0)} | Key={gs.get('key', 0)} | 僵尸军团={gs.get('zombie_used', 0)}/{gs.get('zombie_max', 0)}"
            )
            panel.turn_hint_var.set("人类只负责：加固 / 扫描 / 清除 / 夺回 / 恢复 / 流量清洗 / 反击C2。蜜罐不在技能列表中，只会在切入防守方页签时询问一次，并由 AI 预测节点自动布置。")

    def refresh_tables(self):
        for panel in [self.attacker_panel, self.defender_panel]:
            tree = panel.node_tree
            for item in tree.get_children():
                tree.delete(item)
            for node in self.G.nodes():
                if panel.role == "attacker":
                    view = self.attacker_view_state(node)
                    scan = self.m.trojan_scanned.get(node, "unknown")
                    if isinstance(scan, dict):
                        scan_text = f"dist={scan.get('distance')} base={scan.get('base_state')}"
                    else:
                        scan_text = str(scan)
                    real, base = self.m.trojan_nodes[node]
                    remark = f"真实={real}" if real in {"lurk", "active"} else base
                    tree.insert("", tk.END, values=(node, view, scan_text, remark))
                else:
                    base = self.m.trojan_nodes[node][1]
                    view = self.defender_view_state(node)
                    scan = self.m.defender_scanned.get(node, "unknown")
                    tree.insert("", tk.END, values=(node, base, view, str(scan)))

    def refresh_info_only(self):
        for panel in [self.attacker_panel, self.defender_panel]:
            self.refresh_summary(panel)
        self.refresh_tables()

    def refresh_all(self, refresh_figures=True):
        for panel in [self.attacker_panel, self.defender_panel]:
            self.refresh_summary(panel)
            if refresh_figures:
                self.refresh_figure(panel)
        self.refresh_tables()

    def periodic_refresh(self):
        try:
            self.refresh_info_only()
        finally:
            self.after(250, self.periodic_refresh)

    def log_a(self, msg):
        self.attacker_panel.append_log(msg)

    def log_d(self, msg):
        self.defender_panel.append_log(msg)

    # ---------------- 流程 ----------------
    def start_round(self):
        if self.phase == "setup":
            init_node = self.attacker_panel.init_node_var.get().strip()
            init_state = self.attacker_panel.init_state_var.get().strip() or "active"
            if not init_node:
                self.attacker_panel.status_var.set("请先选择初始感染点。")
                return
            res = self.attacker.seed_initial_node(init_node, init_state)
            msg = self.msg(res)
            self.log_a(msg)
            self.attacker_panel.status_var.set(msg)
            if not res.get("ok"):
                return
            self.phase = "round_ready"

        infected = [n for n in self.m.trojan_nodes if self.m.trojan_nodes[n][0] in {"lurk", "active"}]
        if not infected:
            self.global_var.set("请先设置初始感染点。")
            return
        if self.phase not in {"round_ready", "setup"}:
            self.global_var.set("当前阶段不能开始下一回合。")
            return
        if self.current_round >= self.max_rounds:
            self.winner = "defender"
            self.phase = "game_over"
            self.global_var.set(f"达到最大回合数 {self.max_rounds}，防守方胜利。")
            return

        self.current_round += 1
        self.pending_special_attack = None
        self.special_mode = "convert"
        self.extra_defense = 0.0
        res = self.attacker.gain_energy_per_round(base_recover=2)
        self.log_a(f"R{self.current_round} 回能: {self.msg(res)}")
        self.log_d(f"R{self.current_round} 进攻方回能完成")
        self.log_d(self.msg(self.defender.auto_increase_budget_per_round(amount=2)))
        self.log_d(self.msg(self.defender.increase_budget_from_capture(income_per_node=1)))
        ai_logs = self.m.attacker_ai_operational_phase(self.attacker, self.node_importance)
        for tag, payload in ai_logs:
            self.log_a(f"{tag}: {self.msg(payload)}")
            self.log_d("进攻方 AI 已执行常规动作")
        self.phase = "attacker_human"
        self.attacker_panel.status_var.set("攻击方人工阶段：只保留 激活 / 休眠 / 扫描 / 僵尸军团 / 精准狙击 / C2迁移。")
        self.defender_panel.status_var.set("等待攻击方结束进攻阶段。")
        self.global_var.set(f"第 {self.current_round} 回合已开始。")
        self.refresh_all()

    def end_attacker_phase(self):
        if self.phase != "attacker_human":
            self.global_var.set("当前不是攻击方阶段。")
            return
        self.phase = "defender_wait_tab"
        self.awaiting_defender_entry_prompt = True
        self.attacker_panel.status_var.set("攻击方阶段结束，等待切到防守方页签。")
        self.defender_panel.status_var.set("请切换到防守方页签；切过去时会先询问是否允许 AI 预测并预部署一个蜜罐。")
        self.global_var.set("请切换到防守方页签继续。")
        self.notebook.select(self.defender_panel)
        self.refresh_all()

    def run_defender_ai_phase(self):
        extra, logs = self.m.defender_ai_phase_ui(
            self.defender,
            pending_special_attack=self.pending_special_attack,
            node_importance=self.node_importance,
            want_honeypot=False,
        )
        self.extra_defense += extra
        for tag, payload in logs:
            self.log_d(f"{tag}: {self.msg(payload)}")
        self.phase = "defender_human"
        self.attacker_panel.status_var.set("防守 AI 已自动行动。")
        self.defender_panel.status_var.set("防守方人工阶段：可继续执行 7 个手动动作，然后点击‘结束本回合’。")
        self.global_var.set("已切换到防守方人工阶段。")
        self.refresh_all()


    def finish_round(self):
        if self.phase != "defender_human":
            self.global_var.set("当前还不能结束回合。")
            return
        if self.pending_special_attack is not None:
            self.m._set_attacker_mode(self.attacker, "human")
            result = self.m.resolve_pending_special_attack(
                self.attacker,
                self.pending_special_attack,
                extra_defense=self.extra_defense,
                success_mode=self.special_mode,
            )
            msg = self.msg(result)
            self.log_a(f"特殊攻击结算: {msg}")
            self.log_d(f"特殊攻击结算: {msg}")
        self.m.end_round()
        game_over, winner, msg = self.m.check_win_condition(self.m.trojan_nodes, self.max_rounds, self.current_round)
        self.log_a(msg)
        self.log_d(msg)
        self.attacker_panel.status_var.set(msg)
        self.defender_panel.status_var.set(msg)
        if game_over:
            self.winner = winner
            self.phase = "game_over"
            self.global_var.set(f"游戏结束，胜者：{winner}")
        else:
            self.phase = "round_ready"
            self.global_var.set("本回合已结束，可开始下一回合。")
        self.refresh_all()

    def predict_honeypot_target(self):
        candidates = self.m._best_honeypot_candidates(self.defender, node_importance=self.node_importance)
        return candidates[0] if candidates else None

    def prompt_pre_ai_honeypot(self):
        if not messagebox.askyesno(
            "防守方预部署蜜罐",
            "已切换到防守方页签。\n是否允许防守方 AI 基于当前进攻位置与已知线索，自动预测一个高风险节点并预部署蜜罐？",
            parent=self,
        ):
            self.log_d("人类选择：本回合不进行 AI 预测蜜罐预部署。")
            self.defender_panel.status_var.set("本回合已跳过 AI 预测蜜罐预部署。")
            return

        target = self.predict_honeypot_target()
        if not target:
            msg = "当前没有适合预部署蜜罐的可用节点，已跳过。"
            self.log_d(msg)
            self.defender_panel.status_var.set(msg)
            return

        self.m._set_defender_mode(self.defender, "human")
        res = self.defender.deploy_honeypot(target)
        self.m._set_defender_mode(self.defender, "ai")
        msg = f"AI 预测蜜罐预部署 -> {target}: " + self.msg(res)
        self.log_d(msg)
        self.defender_panel.status_var.set(msg)

    # ---------------- 参数读取 ----------------
    def a_source(self):
        return self.attacker_panel.source_var.get().strip()

    def a_target(self):
        return self.attacker_panel.target_var.get().strip()

    def d_target(self):
        return self.defender_panel.target_var.get().strip() or self.defender_panel.source_var.get().strip()

    # ---------------- 攻击方动作 ----------------
    def attacker_spread_neighbour(self):
        if self.phase != "attacker_human":
            return
        self.m._set_attacker_mode(self.attacker, "human")
        res = self.attacker.spread_neighbour(self.a_source(), self.a_target())
        msg = self.msg(res)
        self.log_a(msg)
        self.attacker_panel.status_var.set(msg)
        self.refresh_all()

    def attacker_spread_far(self):
        if self.phase != "attacker_human":
            return
        self.m._set_attacker_mode(self.attacker, "human")
        res = self.attacker.spread_far(self.a_source(), self.a_target(), radius=int(self.attacker_panel.radius_var.get()))
        msg = self.msg(res)
        self.log_a(msg)
        self.attacker_panel.status_var.set(msg)
        self.refresh_all()

    def attacker_activate(self):
        if self.phase != "attacker_human":
            return
        self.m._set_attacker_mode(self.attacker, "human")
        res = self.attacker.activate(self.a_target() or self.a_source())
        msg = self.msg(res)
        self.log_a(msg)
        self.attacker_panel.status_var.set(msg)
        self.refresh_all()

    def attacker_sleep(self):
        if self.phase != "attacker_human":
            return
        self.m._set_attacker_mode(self.attacker, "human")
        res = self.attacker.sleep(self.a_target() or self.a_source())
        msg = self.msg(res)
        self.log_a(msg)
        self.attacker_panel.status_var.set(msg)
        self.refresh_all()

    def attacker_scan(self):
        if self.phase != "attacker_human":
            return
        self.m._set_attacker_mode(self.attacker, "human")
        res = self.attacker.scan_node(self.a_source(), self.a_target(), radius=int(self.attacker_panel.radius_var.get()))
        msg = self.msg(res)
        self.log_a(msg)
        self.attacker_panel.status_var.set(msg)
        self.refresh_all()

    def attacker_normal_attack(self):
        if self.phase != "attacker_human":
            return
        self.m._set_attacker_mode(self.attacker, "human")
        res = self.attacker.normal_attack(self.a_source(), self.a_target())
        msg = self.msg(res)
        self.log_a(msg)
        self.attacker_panel.status_var.set(msg)
        self.refresh_all()

    def attacker_zombie(self):
        if self.phase != "attacker_human":
            return
        self.m._set_attacker_mode(self.attacker, "human")
        self.special_mode = self.attacker_panel.special_mode_var.get().strip() or "convert"
        self.pending_special_attack, res = self.m.prepare_zombie_legion(self.attacker, self.a_target())
        msg = self.msg(res)
        self.log_a(msg)
        self.attacker_panel.status_var.set(msg)
        self.refresh_all()

    def attacker_precise(self):
        if self.phase != "attacker_human":
            return
        self.m._set_attacker_mode(self.attacker, "human")
        self.special_mode = self.attacker_panel.special_mode_var.get().strip() or "convert"
        participants = None
        if not self.attacker_panel.use_all_active_var.get():
            raw = self.attacker_panel.participants_var.get().strip()
            participants = [x.strip() for x in raw.split(",") if x.strip()]
        self.pending_special_attack, res = self.m.prepare_precise_strike(self.attacker, self.a_target(), participants=participants)
        msg = self.msg(res)
        self.log_a(msg)
        self.attacker_panel.status_var.set(msg)
        self.refresh_all()

    def attacker_destroy_node(self):
        if self.phase != "attacker_human":
            return
        self.m._set_attacker_mode(self.attacker, "human")
        try:
            node_value = float(self.attacker_panel.node_value_var.get().strip() or "1.0")
        except ValueError:
            node_value = 1.0
        res = self.attacker.destroy_node(self.a_target() or self.a_source(), node_value=node_value)
        msg = self.msg(res)
        self.log_a(msg)
        self.attacker_panel.status_var.set(msg)
        self.refresh_all()

    def attacker_move_c2(self):
        if self.phase != "attacker_human":
            return
        res = self.attacker.move_c2()
        msg = self.msg(res)
        self.log_a(msg)
        self.attacker_panel.status_var.set(msg)
        self.refresh_all()

    # ---------------- 防守方动作 ----------------
    def defender_harden(self):
        if self.phase != "defender_human":
            return
        self.m._set_defender_mode(self.defender, "human")
        res = self.defender.apply_hardening(self.d_target())
        self._defender_action_done(res)


    def defender_scan(self):
        if self.phase != "defender_human":
            return
        self.m._set_defender_mode(self.defender, "human")
        res = self.defender.scan_nodes(self.d_target())
        self._defender_action_done(res)

    def defender_clear(self):
        if self.phase != "defender_human":
            return
        self.m._set_defender_mode(self.defender, "human")
        res = self.defender.clear_virus(self.d_target())
        self._defender_action_done(res)

    def defender_recapture(self):
        if self.phase != "defender_human":
            return
        self.m._set_defender_mode(self.defender, "human")
        res = self.defender.recapture_lost_nodes(self.d_target())
        self._defender_action_done(res)

    def defender_restore(self):
        if self.phase != "defender_human":
            return
        self.m._set_defender_mode(self.defender, "human")
        res = self.defender.restore_abandoned(self.d_target())
        self._defender_action_done(res)

    def defender_counter_c2(self):
        if self.phase != "defender_human":
            return
        self.m._set_defender_mode(self.defender, "human")
        res = self.defender.counter_c2()
        self._defender_action_done(res)

    def defender_clean(self):
        if self.phase != "defender_human":
            return
        if self.pending_special_attack is None:
            msg = "当前没有待响应的特殊攻击，无法进行流量清洗。"
            self.log_d(msg)
            self.defender_panel.status_var.set(msg)
            return
        eq_invest = int(self.defender_panel.clean_amount_var.get())
        actual_cost = eq_invest * 3
        if self.m.game_state.get("budget", 0) < actual_cost:
            msg = f"budget 不足，清洗 {eq_invest} 需要 {actual_cost} budget。"
            self.log_d(msg)
            self.defender_panel.status_var.set(msg)
            return
        self.m.game_state["budget"] -= actual_cost
        added = max(0.0, eq_invest - 8) * 0.7
        self.extra_defense += added
        msg = f"人类部署流量清洗成功，花费 {actual_cost} budget（AI 等效 {eq_invest}），额外防御 +{added:.2f}"
        self.log_d(msg)
        self.defender_panel.status_var.set(msg)
        self.refresh_all()

    def _defender_action_done(self, res):
        self.m._set_defender_mode(self.defender, "ai")
        msg = self.msg(res)
        self.log_d(msg)
        self.defender_panel.status_var.set(msg)
        self.refresh_all()


def find_default_original():
    candidates = [
        os.path.join(os.getcwd(), ORIGINAL_BASENAME),
        os.path.join(os.path.dirname(__file__), ORIGINAL_BASENAME),
        "/mnt/data/HVT_dual_panel_3d_ui_ai_seed_cn_fixed.py",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def main():
    original = find_default_original()
    if not original:
        root = tk.Tk()
        root.withdraw()
        original = filedialog.askopenfilename(
            title="选择原始 HVT 脚本",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
        )
        root.destroy()
        if not original:
            print("未选择原始脚本，程序退出。")
            return
    module = load_original_module(original)
    app = ReferencePanelApp(module, original)
    app.mainloop()


if __name__ == "__main__":
    main()
