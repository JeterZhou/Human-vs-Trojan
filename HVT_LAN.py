from __future__ import annotations

import argparse
import importlib.util
import json
import os
import queue
import random
import socket
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Optional

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

DEFAULT_LOGIC_BASENAME = "HVT_final.py"
DEFAULT_PORT = 23333


def load_module(path: str):
    spec = importlib.util.spec_from_file_location("hvt_logic_module", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载逻辑脚本: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


class JsonLineSocket:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.lock = threading.Lock()
        self.file = sock.makefile("r", encoding="utf-8", newline="\n")

    def send(self, data: dict[str, Any]):
        text = json.dumps(data, ensure_ascii=False) + "\n"
        raw = text.encode("utf-8")
        with self.lock:
            self.sock.sendall(raw)

    def recv(self) -> Optional[dict[str, Any]]:
        line = self.file.readline()
        if not line:
            return None
        return json.loads(line)

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


@dataclass
class EngineState:
    phase: str = "setup"
    current_round: int = 0
    max_rounds: int = 20
    pending_special_attack: Optional[dict[str, Any]] = None
    special_mode: str = "convert"
    extra_defense: float = 0.0
    winner: Optional[str] = None
    awaiting_defender_prompt: bool = False
    logs_attacker: list[str] = field(default_factory=list)
    logs_defender: list[str] = field(default_factory=list)
    status_attacker: str = "请选择初始感染点和初始状态，然后点击开始。"
    status_defender: str = "等待攻击方完成开局。"
    global_status: str = "已加载。"
    seed: int = 43


class HostGameEngine:
    def __init__(self, module, logic_path: str):
        self.m = module
        self.logic_path = logic_path
        self.state = EngineState()
        self.G = None
        self.pos3d = None
        self.node_importance = None
        self.attacker = None
        self.defender = None
        self.last_prompt_round_handled = -1
        self.reset_game(seed=43, max_rounds=20)

    def _validate_node(self, node: str) -> tuple[bool, str]:
        node = str(node).strip()
        if not node:
            return False, "节点不能为空"

        valid_nodes = [str(n) for n in self.G.nodes()]
        if node not in valid_nodes:
            return False, f"无效节点: {node}，当前地图节点范围是 {', '.join(sorted(valid_nodes))}"

        return True, ""

    def log_a(self, msg: str):
        self.state.logs_attacker.append(msg)
        self.state.logs_attacker = self.state.logs_attacker[-200:]

    def log_d(self, msg: str):
        self.state.logs_defender.append(msg)
        self.state.logs_defender = self.state.logs_defender[-200:]

    def msg(self, res: Any) -> str:
        return res.get("msg", str(res)) if isinstance(res, dict) else str(res)

    def reset_game(self, seed: int, max_rounds: int):
        m = self.m
        self.state = EngineState(max_rounds=int(max_rounds), seed=int(seed))
        G, pos3d, _ = m.generate_game_graph(num_nodes=m.GAME_NODE_NUM, edge_prob=0.2, seed=int(seed))

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
        m.game_state["attacker_ai_energy"] = 20
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
        self.state.status_attacker = "请选择初始感染点和初始状态，然后点击开始。"
        self.state.status_defender = "等待攻击方完成开局。"
        self.state.global_status = f"地图已按 seed={seed} 重置。"

    def attacker_view_state(self, node: str) -> str:
        real_state, base_state = self.m.trojan_nodes[node]
        if base_state == "abandoned":
            return "abandoned"
        if real_state == "active":
            return "active"
        if real_state == "lurk":
            return "lurk"
        return "DD"

    def defender_view_state(self, node: str) -> str:
        return self.m.get_display_status(node)

    def predict_honeypot_target(self) -> Optional[str]:
        candidates = self.m._best_honeypot_candidates(self.defender, node_importance=self.node_importance)
        return candidates[0] if candidates else None

    def run_defender_ai_phase(self):
        extra, logs = self.m.defender_ai_phase_ui(
            self.defender,
            pending_special_attack=self.state.pending_special_attack,
            node_importance=self.node_importance,
            want_honeypot=False,
        )
        self.state.extra_defense += extra
        for tag, payload in logs:
            self.log_d(f"{tag}: {self.msg(payload)}")
        self.state.phase = "defender_human"
        self.state.status_attacker = "防守 AI 已自动行动。"
        self.state.status_defender = "防守方人工阶段：可继续执行手动动作，然后点击‘结束本回合’。"
        self.state.global_status = "已切换到防守方人工阶段。"

    def start_round(self, init_node: str = "", init_state: str = "active") -> tuple[bool, str]:
        if not init_node:
            return False, "请先选择初始感染点。"

        ok, err = self._validate_node(init_node)
        if not ok:
            return False, err

        if self.state.phase == "setup":
            if not init_node:
                return False, "请先选择初始感染点。"
            res = self.attacker.seed_initial_node(init_node, init_state or "active")
            msg = self.msg(res)
            self.log_a(msg)
            self.state.status_attacker = msg
            if not res.get("ok"):
                return False, msg
            self.state.phase = "round_ready"

        infected = [n for n in self.m.trojan_nodes if self.m.trojan_nodes[n][0] in {"lurk", "active"}]
        if not infected:
            return False, "请先设置初始感染点。"
        if self.state.phase not in {"round_ready", "setup"}:
            return False, "当前阶段不能开始下一回合。"
        if self.state.current_round >= self.state.max_rounds:
            self.state.winner = "defender"
            self.state.phase = "game_over"
            self.state.global_status = f"达到最大回合数 {self.state.max_rounds}，防守方胜利。"
            return False, self.state.global_status

        self.state.current_round += 1
        self.state.pending_special_attack = None
        self.state.special_mode = "convert"
        self.state.extra_defense = 0.0
        res = self.attacker.gain_energy_per_round(base_recover=2)
        self.log_a(f"R{self.state.current_round} 回能: {self.msg(res)}")
        self.log_d(f"R{self.state.current_round} 进攻方回能完成")
        self.log_d(self.msg(self.defender.auto_increase_budget_per_round(amount=2)))
        self.log_d(self.msg(self.defender.increase_budget_from_capture(income_per_node=1)))

        self.m._set_attacker_mode(self.attacker, "ai")
        ai_logs = self.m.attacker_ai_operational_phase(self.attacker, self.node_importance)

        for tag, payload in ai_logs:
            self.log_a(f"{tag}: {self.msg(payload)}")
            self.log_d("进攻方 AI 已执行常规动作")
        self.state.phase = "attacker_human"
        self.state.status_attacker = "攻击方人工阶段：只保留 激活 / 休眠 / 扫描 / 僵尸军团 / 精准狙击 / C2迁移。"
        self.state.status_defender = "等待攻击方结束进攻阶段。"
        self.state.global_status = f"第 {self.state.current_round} 回合已开始。"
        return True, self.state.global_status

    def end_attacker_phase(self) -> tuple[bool, str]:
        if self.state.phase != "attacker_human":
            return False, "当前不是攻击方阶段。"
        self.state.phase = "defender_prompt"
        self.state.awaiting_defender_prompt = True
        self.state.status_attacker = "攻击方阶段结束，等待防守方确认是否让 AI 预测并预部署蜜罐。"
        self.state.status_defender = "请先确认是否允许 AI 预测并预部署一个蜜罐。"
        self.state.global_status = "等待防守方确认蜜罐预部署。"
        return True, self.state.global_status

    def answer_honeypot_prompt(self, allow: bool) -> tuple[bool, str]:
        if self.state.phase != "defender_prompt":
            return False, "当前不是防守方蜜罐确认阶段。"

        self.state.awaiting_defender_prompt = False

        if allow:
            target = self.predict_honeypot_target()
            if target:
                self.m._set_defender_mode(self.defender, "human")
                res = self.defender.deploy_honeypot(target)
                self.m._set_defender_mode(self.defender, "ai")
                msg = f"AI 预测蜜罐预部署 -> {target}: {self.msg(res)}"
            else:
                msg = "当前没有适合预部署蜜罐的可用节点，已跳过。"
        else:
            msg = "人类选择：本回合不进行 AI 预测蜜罐预部署。"

        self.log_d(msg)
        self.state.phase = "defender_human"
        self.state.status_attacker = "已进入防守方人工阶段，等待防守方行动。"
        self.state.status_defender = "防守方人工阶段：请先执行手动动作，完成后点击‘结束本回合’。"
        self.state.global_status = "防守方已完成蜜罐确认，当前为人工阶段。"
        return True, msg

    def finish_round(self) -> tuple[bool, str]:
        if self.state.phase != "defender_human":
            return False, "当前还不能结束回合。"

        # 先执行防守 AI 常规动作
        extra, logs = self.m.defender_ai_phase_ui(
            self.defender,
            pending_special_attack=self.state.pending_special_attack,
            node_importance=self.node_importance,
            want_honeypot=False,
        )
        self.state.extra_defense += extra
        for tag, payload in logs:
            self.log_d(f"{tag}: {self.msg(payload)}")

        # 再结算特殊攻击
        if self.state.pending_special_attack is not None:
            self.m._set_attacker_mode(self.attacker, "human")
            result = self.m.resolve_pending_special_attack(
                self.attacker,
                self.state.pending_special_attack,
                extra_defense=self.state.extra_defense,
                success_mode=self.state.special_mode,
            )
            msg = self.msg(result)
            self.log_a(f"特殊攻击结算: {msg}")
            self.log_d(f"特殊攻击结算: {msg}")

        self.m.end_round()
        game_over, winner, msg = self.m.check_win_condition(
            self.m.trojan_nodes,
            self.state.max_rounds,
            self.state.current_round
        )

        self.log_a(msg)
        self.log_d(msg)
        self.state.status_attacker = msg
        self.state.status_defender = msg

        if game_over:
            self.state.winner = winner
            self.state.phase = "game_over"
            self.state.global_status = f"游戏结束，胜者：{winner}"
        else:
            self.state.phase = "round_ready"
            self.state.global_status = "本回合已结束，可开始下一回合。"

        return True, self.state.global_status

    def attacker_action(self, action: str, params: dict[str, Any]) -> tuple[bool, str]:
        if self.state.phase != "attacker_human":
            return False, "当前不是攻击方人类操作阶段。"

        self.m._set_attacker_mode(self.attacker, "human")

        a_source = str(params.get("source", "")).strip()
        a_target = str(params.get("target", "")).strip()
        radius = int(params.get("radius", 2) or 2)

        for n in [a_source, a_target]:
            if n:
                ok, err = self._validate_node(n)
                if not ok:
                    self.m._set_attacker_mode(self.attacker, "ai")
                    return False, err

        if action == "activate":
            res = self.attacker.activate(a_target or a_source)
        elif action == "sleep":
            res = self.attacker.sleep(a_target or a_source)
        elif action == "scan":
            res = self.attacker.scan_node(a_source, a_target, radius=radius)
        elif action == "zombie":
            self.state.special_mode = str(params.get("special_mode", "convert") or "convert")
            self.state.pending_special_attack, res = self.m.prepare_zombie_legion(self.attacker, a_target)
        elif action == "precise":
            self.state.special_mode = str(params.get("special_mode", "convert") or "convert")
            participants = None
            if not bool(params.get("use_all_active", True)):
                raw = str(params.get("participants", ""))
                participants = [x.strip() for x in raw.split(",") if x.strip()]
            self.state.pending_special_attack, res = self.m.prepare_precise_strike(
                self.attacker, a_target, participants=participants
            )
        elif action == "move_c2":
            res = self.attacker.move_c2()
        else:
            return False, f"未知攻击方动作: {action}"

        msg = self.msg(res)
        self.log_a(msg)
        self.state.status_attacker = msg
        return bool(getattr(res, "get", lambda *a, **k: True)("ok", True) if isinstance(res, dict) else True), msg

    def defender_action(self, action: str, params: dict[str, Any]) -> tuple[bool, str]:
        if self.state.phase != "defender_human":
            return False, "当前不是防守方人类操作阶段。"

        target = str(params.get("target", "")).strip() or str(params.get("source", "")).strip()
        self.m._set_defender_mode(self.defender, "human")

        if action in {"harden", "scan", "clear", "recapture", "restore"}:
            if not target:
                self.m._set_defender_mode(self.defender, "ai")
                return False, "请选择目标节点。"

            ok, err = self._validate_node(target)
            if not ok:
                self.m._set_defender_mode(self.defender, "ai")
                return False, err

        if action == "harden":
            res = self.defender.apply_hardening(target)
        elif action == "scan":
            res = self.defender.scan_nodes(target)
        elif action == "clear":
            res = self.defender.clear_virus(target)
        elif action == "recapture":
            res = self.defender.recapture_lost_nodes(target)
        elif action == "restore":
            res = self.defender.restore_abandoned(target)
        elif action == "counter_c2":
            res = self.defender.counter_c2()
        elif action == "clean":
            if self.state.pending_special_attack is None:
                self.m._set_defender_mode(self.defender, "ai")
                msg = "当前没有待响应的特殊攻击，无法进行流量清洗。"
                self.log_d(msg)
                self.state.status_defender = msg
                return False, msg

            eq_invest = int(params.get("clean_amount", 8) or 8)
            actual_cost = eq_invest * 3

            if self.m.game_state.get("budget", 0) < actual_cost:
                self.m._set_defender_mode(self.defender, "ai")
                msg = f"budget 不足，清洗 {eq_invest} 需要 {actual_cost} budget。"
                self.log_d(msg)
                self.state.status_defender = msg
                return False, msg

            self.m.game_state["budget"] -= actual_cost
            added = max(0.0, eq_invest - 8) * 0.7
            self.state.extra_defense += added
            self.m._set_defender_mode(self.defender, "ai")
            msg = f"人类部署流量清洗成功，花费 {actual_cost} budget（AI 等效 {eq_invest}），额外防御 +{added:.2f}"
            self.log_d(msg)
            self.state.status_defender = msg
            return True, msg
        else:
            self.m._set_defender_mode(self.defender, "ai")
            return False, f"未知防守方动作: {action}"

        self.m._set_defender_mode(self.defender, "ai")
        msg = self.msg(res)
        self.log_d(msg)
        self.state.status_defender = msg
        ok = res.get("ok", True) if isinstance(res, dict) else True
        return ok, msg

    def snapshot_for(self, role: str) -> dict[str, Any]:
        gs = self.m.game_state
        nodes: list[dict[str, Any]] = []
        for node in self.G.nodes():
            if role == "attacker":
                scan = self.m.trojan_scanned.get(node, "unknown")
                if isinstance(scan, dict):
                    scan_text = f"dist={scan.get('distance')} base={scan.get('base_state')}"
                else:
                    scan_text = str(scan)
                real, base = self.m.trojan_nodes[node]
                remark = f"真实={real}" if real in {"lurk", "active"} else base
                nodes.append({
                    "node": node,
                    "state": self.attacker_view_state(node),
                    "scan": scan_text,
                    "remark": remark,
                })
            else:
                nodes.append({
                    "node": node,
                    "base": self.m.trojan_nodes[node][1],
                    "state": self.defender_view_state(node),
                    "scan": str(self.m.defender_scanned.get(node, "unknown")),
                })
        return {
            "role": role,
            "phase": self.state.phase,
            "current_round": self.state.current_round,
            "max_rounds": self.state.max_rounds,
            "winner": self.state.winner,
            "seed": self.state.seed,
            "logic_path": self.logic_path,
            "global_status": self.state.global_status,
            "status": self.state.status_attacker if role == "attacker" else self.state.status_defender,
            "resources": {
                "attacker_human_energy": gs.get("attacker_human_energy", 0),
                "attacker_ai_energy": gs.get("attacker_ai_energy", 0),
                "budget": gs.get("budget", 0),
                "key": gs.get("key", 0),
                "c2_silenced_rounds": gs.get("c2_silenced_rounds", 0),
                "zombie_used": gs.get("zombie_used", 0),
                "zombie_max": gs.get("zombie_max", 0),
            },
            "turn_hint": (
                "人类只负责：激活 / 休眠 / 扫描 / 僵尸军团 / 精准狙击 / C2迁移；其他进攻动作交给 AI。"
                if role == "attacker"
                else "人类只负责：加固 / 扫描 / 清除 / 夺回 / 恢复 / 流量清洗 / 反击C2。蜜罐不在技能列表中。"
            ),
            "nodes": nodes,
            "node_names": list(self.G.nodes()),
            "positions": {n: [float(v) for v in self.pos3d[n]] for n in self.G.nodes()},
            "edges": [[u, v] for u, v in self.G.edges()],
            "pending_special_attack": self.state.pending_special_attack if role == "defender" else None,
            "awaiting_defender_prompt": bool(self.state.awaiting_defender_prompt and role == "defender"),
            "logs": self.state.logs_attacker if role == "attacker" else self.state.logs_defender,
        }


class HostNetworkController:
    def __init__(self, engine: HostGameEngine, local_role: str, port: int, ui_queue: queue.Queue):
        self.engine = engine
        self.local_role = local_role
        self.remote_role = "defender" if local_role == "attacker" else "attacker"
        self.port = port
        self.ui_queue = ui_queue
        self.listener = None
        self.remote_conn: Optional[JsonLineSocket] = None
        self.running = True
        self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.accept_thread.start()

    def _accept_loop(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("", self.port))
        srv.listen(1)
        self.listener = srv
        self.ui_queue.put({"type": "host_listening", "ip": get_local_ip(), "port": self.port})
        while self.running:
            try:
                client, addr = srv.accept()
                client.settimeout(None)
            except OSError:
                break
            try:
                conn = JsonLineSocket(client)
                hello = conn.recv()
                if not hello or hello.get("type") != "hello":
                    conn.close()
                    continue
                requested_role = hello.get("role")
                if requested_role != self.remote_role:
                    conn.send({"type": "error", "message": f"该房间主机本地角色为 {self.local_role}，远端必须使用 {self.remote_role}。"})
                    conn.close()
                    continue
                self.remote_conn = conn
                conn.send({"type": "welcome", "role": self.remote_role, "peer_role": self.local_role})
                self.send_state_to_remote()
                self.ui_queue.put({"type": "peer_connected", "addr": addr, "role": self.remote_role})
                threading.Thread(target=self._remote_recv_loop, args=(conn,), daemon=True).start()
                break
            except Exception as exc:
                self.ui_queue.put({
                    "type": "network_error",
                    "message": f"{type(exc).__name__}: {exc}"
                })

    def _remote_recv_loop(self, conn: JsonLineSocket):
        while self.running:
            try:
                msg = conn.recv()
            except Exception as exc:
                self.ui_queue.put({
                    "type": "network_error",
                    "message": f"{type(exc).__name__}: {exc}"
                })

                break
            if msg is None:
                self.ui_queue.put({"type": "peer_disconnected"})
                break
            if msg.get("type") == "action":
                self.apply_action(msg.get("role"), msg.get("action"), msg.get("params") or {})
        try:
            conn.close()
        except Exception:
            pass
        self.remote_conn = None

    def apply_action(self, role: str, action: str, params: dict[str, Any]) -> tuple[bool, str]:
        if role not in {"attacker", "defender"}:
            return False, "非法角色。"
        if action == "start_round":
            ok, msg = self.engine.start_round(params.get("init_node", ""), params.get("init_state", "active"))
        elif action == "end_attacker_phase":
            ok, msg = self.engine.end_attacker_phase()
        elif action == "honeypot_prompt":
            ok, msg = self.engine.answer_honeypot_prompt(bool(params.get("allow", False)))
        elif action == "finish_round":
            ok, msg = self.engine.finish_round()
        elif role == "attacker":
            ok, msg = self.engine.attacker_action(action, params)
        else:
            ok, msg = self.engine.defender_action(action, params)
        self.ui_queue.put({"type": "local_state", "snapshot": self.engine.snapshot_for(self.local_role), "message": msg, "ok": ok})
        self.send_state_to_remote()
        return ok, msg

    def send_state_to_remote(self):
        if not self.remote_conn:
            return
        try:
            self.remote_conn.send({"type": "state", "state": self.engine.snapshot_for(self.remote_role)})
        except Exception as exc:
            self.ui_queue.put({"type": "network_error", "message": f"发送状态失败: {exc}"})

    def close(self):
        self.running = False
        if self.remote_conn:
            self.remote_conn.close()
        if self.listener:
            try:
                self.listener.close()
            except Exception:
                pass


class ClientNetworkController:
    def __init__(self, host: str, port: int, role: str, ui_queue: queue.Queue):
        self.host = host
        self.port = port
        self.role = role
        self.ui_queue = ui_queue
        self.conn: Optional[JsonLineSocket] = None
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            sock = socket.create_connection((self.host, self.port), timeout=8)
            sock.settimeout(None)  # 连接成功后恢复为阻塞模式
            self.conn = JsonLineSocket(sock)

            self.conn.send({"type": "hello", "role": self.role})
            welcome = self.conn.recv()
            if not welcome:
                self.ui_queue.put({"type": "network_error", "message": "主机没有响应。"})
                return
            if welcome.get("type") == "error":
                self.ui_queue.put({"type": "network_error", "message": welcome.get("message", "连接被拒绝。")})
                return
            self.ui_queue.put({"type": "connected", "role": self.role, "peer_role": welcome.get("peer_role")})
            while self.running:
                msg = self.conn.recv()
                if msg is None:
                    self.ui_queue.put({"type": "peer_disconnected"})
                    break
                if msg.get("type") == "state":
                    self.ui_queue.put({"type": "remote_state", "snapshot": msg.get("state")})
                elif msg.get("type") == "error":
                    self.ui_queue.put({"type": "network_error", "message": msg.get("message", "网络错误")})
        except Exception as exc:
            self.ui_queue.put({"type": "network_error", "message": f"连接失败: {exc}"})

    def send_action(self, action: str, params: dict[str, Any]):
        if not self.conn:
            raise RuntimeError("尚未连接到主机。")
        self.conn.send({"type": "action", "role": self.role, "action": action, "params": params})

    def close(self):
        self.running = False
        if self.conn:
            self.conn.close()


class StartupDialog(tk.Toplevel):
    def __init__(self, master, default_logic: str):
        super().__init__(master)
        self.title("HVT 局域网联机设置")
        self.resizable(False, False)
        self.result = None
        self.mode_var = tk.StringVar(value="host")
        self.role_var = tk.StringVar(value="attacker")
        self.host_var = tk.StringVar(value=get_local_ip())
        self.port_var = tk.IntVar(value=DEFAULT_PORT)
        self.logic_var = tk.StringVar(value=default_logic)
        self._build()
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.update_idletasks()
        self.lift()
        self.focus_force()


    def _browse(self):
        path = filedialog.askopenfilename(title="选择逻辑文件", filetypes=[("Python files", "*.py"), ("All files", "*.*")], parent=self)
        if path:
            self.logic_var.set(path)

    def _build(self):
        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frm, text="模式").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(frm, text="主机", value="host", variable=self.mode_var).grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(frm, text="加入", value="client", variable=self.mode_var).grid(row=0, column=2, sticky="w")
        ttk.Label(frm, text="本机角色").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Radiobutton(frm, text="攻击方", value="attacker", variable=self.role_var).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Radiobutton(frm, text="防守方", value="defender", variable=self.role_var).grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="主机 IP").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=self.host_var, width=24).grid(row=2, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(frm, text="端口").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=self.port_var, width=12).grid(row=3, column=1, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="逻辑文件").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=self.logic_var, width=42).grid(row=4, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(frm, text="浏览", command=self._browse).grid(row=4, column=2, sticky="ew", pady=(8, 0))
        ttk.Button(frm, text="启动", command=self._ok).grid(row=5, column=1, sticky="ew", pady=(12, 0))
        ttk.Button(frm, text="取消", command=self._cancel).grid(row=5, column=2, sticky="ew", pady=(12, 0))

    def _ok(self):
        path = self.logic_var.get().strip()
        if not os.path.exists(path):
            messagebox.showerror("错误", "逻辑文件不存在。", parent=self)
            return
        self.result = {
            "mode": self.mode_var.get(),
            "role": self.role_var.get(),
            "host": self.host_var.get().strip(),
            "port": int(self.port_var.get()),
            "logic_path": path,
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class LanRoleApp(tk.Tk):
    def __init__(self, config: dict[str, Any], module):
        super().__init__()
        self.config_data = config
        self.role = config["role"]
        self.module = module
        self.logic_path = config["logic_path"]
        self.title(f"HVT 局域网联机版 - {'攻击方' if self.role == 'attacker' else '防守方'}")
        self.geometry("1600x980")
        self.minsize(1280, 860)
        self.queue: queue.Queue = queue.Queue()
        self.snapshot: Optional[dict[str, Any]] = None
        self.last_prompt_round = -1
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.controller = None
        self.engine = None
        if config["mode"] == "host":
            self.engine = HostGameEngine(module, self.logic_path)
            self.controller = HostNetworkController(self.engine, self.role, int(config["port"]), self.queue)
            self.snapshot = self.engine.snapshot_for(self.role)
        else:
            self.controller = ClientNetworkController(config["host"], int(config["port"]), self.role, self.queue)

        self._build_ui()
        if self.snapshot:
            self.apply_snapshot(self.snapshot)
        self.after(120, self.process_queue)

    def _build_ui(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        top = ttk.Frame(self, padding=(8, 6))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(3, weight=1)
        ttk.Label(top, text="逻辑文件:").grid(row=0, column=0, sticky="w")
        self.logic_var = tk.StringVar(value=self.logic_path)
        ttk.Entry(top, textvariable=self.logic_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=(6, 6))
        self.net_var = tk.StringVar(value="正在建立联机...")
        ttk.Label(top, textvariable=self.net_var).grid(row=0, column=2, sticky="w")
        self.global_var = tk.StringVar(value="等待同步。")
        ttk.Label(top, textvariable=self.global_var, foreground="#444").grid(row=0, column=3, sticky="e")

        outer = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        outer.grid(row=1, column=0, sticky="nsew")
        left = ttk.Frame(outer, padding=8)
        right = ttk.Frame(outer, padding=8)
        outer.add(left, weight=3)
        outer.add(right, weight=2)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)
        right.rowconfigure(5, weight=1)
        right.columnconfigure(0, weight=1)

        self.figure = Figure(figsize=(9.2, 7.6), facecolor="black")
        self.ax = self.figure.add_subplot(111, projection="3d")
        self.canvas = FigureCanvasTkAgg(self.figure, master=left)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        toolbar_frame = ttk.Frame(left)
        toolbar_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side=tk.LEFT, fill=tk.X)

        summary = ttk.LabelFrame(right, text="战局信息", padding=8)
        summary.grid(row=0, column=0, sticky="ew")
        summary.columnconfigure(0, weight=1)
        summary.columnconfigure(1, weight=1)
        self.round_var = tk.StringVar(value="回合: 0/0")
        self.phase_var = tk.StringVar(value="阶段: setup")
        self.resource_var = tk.StringVar(value="")
        self.turn_hint_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="等待开始")
        ttk.Label(summary, text=("攻击方控制台" if self.role == "attacker" else "防守方控制台"), font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.round_var).grid(row=1, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.phase_var).grid(row=1, column=1, sticky="e")
        ttk.Label(summary, textvariable=self.resource_var, wraplength=480).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(summary, textvariable=self.turn_hint_var, foreground="#0a5", wraplength=480).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.status_var, wraplength=480, foreground="#444").grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        control = ttk.LabelFrame(right, text="操作", padding=8)
        control.grid(row=1, column=0, sticky="ew", pady=(8, 0))
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
        self.clean_amount_var = tk.IntVar(value=8)

        row = 0
        if self.role == "attacker":
            ttk.Label(control, text="随机种子").grid(row=row, column=0, sticky="w")
            ttk.Spinbox(control, from_=0, to=999999, textvariable=self.seed_var, width=10).grid(row=row, column=1, sticky="w")
            ttk.Label(control, text="最大回合").grid(row=row, column=2, sticky="w")
            ttk.Spinbox(control, from_=1, to=200, textvariable=self.max_rounds_var, width=10).grid(row=row, column=3, sticky="w")
            row += 1
            ttk.Label(control, text="初始感染点").grid(row=row, column=0, sticky="w", pady=(6, 0))
            self.init_node_combo = ttk.Combobox(control, textvariable=self.init_node_var, width=10, state="readonly")
            self.init_node_combo.grid(row=row, column=1, sticky="w", pady=(6, 0))
            ttk.Label(control, text="初始状态").grid(row=row, column=2, sticky="w", pady=(6, 0))
            ttk.Combobox(control, textvariable=self.init_state_var, values=["active", "lurk"], width=10, state="readonly").grid(row=row, column=3, sticky="w", pady=(6, 0))
            row += 1
            ttk.Button(control, text="开始游戏/下一回合", command=self.on_start_round).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
            ttk.Button(control, text="结束进攻阶段", command=self.on_end_attacker_phase).grid(row=row, column=2, columnspan=2, sticky="ew", pady=(8, 0))
            row += 1
        else:
            ttk.Label(control, text="本回合蜜罐不在技能列表中；会在需要时自动弹一次确认。", wraplength=460).grid(row=row, column=0, columnspan=4, sticky="w")
            row += 1

        ttk.Label(control, text="source").grid(row=row, column=0, sticky="w", pady=(8, 0))
        self.source_combo = ttk.Combobox(control, textvariable=self.source_var, width=10, state="readonly")
        self.source_combo.grid(row=row, column=1, sticky="w", pady=(8, 0))
        ttk.Label(control, text="target").grid(row=row, column=2, sticky="w", pady=(8, 0))
        self.target_combo = ttk.Combobox(control, textvariable=self.target_var, width=10, state="readonly")
        self.target_combo.grid(row=row, column=3, sticky="w", pady=(8, 0))
        row += 1
        ttk.Label(control, text="radius").grid(row=row, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(control, from_=1, to=10, textvariable=self.radius_var, width=10).grid(row=row, column=1, sticky="w", pady=(6, 0))
        if self.role == "attacker":
            ttk.Label(control, text="特攻结果").grid(row=row, column=2, sticky="w", pady=(6, 0))
            ttk.Combobox(control, textvariable=self.special_mode_var, values=["convert", "destroy"], width=10, state="readonly").grid(row=row, column=3, sticky="w", pady=(6, 0))
            row += 1
            ttk.Checkbutton(control, text="精准打击使用全部 active 节点", variable=self.use_all_active_var).grid(row=row, column=0, columnspan=4, sticky="w", pady=(6, 0))
            row += 1
            ttk.Label(control, text="参与节点").grid(row=row, column=0, sticky="w", pady=(6, 0))
            ttk.Entry(control, textvariable=self.participants_var, width=28).grid(row=row, column=1, columnspan=3, sticky="ew", pady=(6, 0))
            row += 1
        else:
            ttk.Label(control, text="清洗投入").grid(row=row, column=2, sticky="w", pady=(6, 0))
            ttk.Combobox(control, textvariable=self.clean_amount_var, values=[8, 12, 16], width=10, state="readonly").grid(row=row, column=3, sticky="w", pady=(6, 0))
            row += 1

        action = ttk.LabelFrame(right, text="可执行动作", padding=8)
        action.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        actions = []
        if self.role == "attacker":
            actions = [
                ("1 激活 lurk\n(C2 命令)", lambda: self.send_action("activate")),
                ("2 休眠 active\n(C2 命令)", lambda: self.send_action("sleep")),
                ("3 扫描节点\n(C2 命令)", lambda: self.send_action("scan")),
                ("4 僵尸军团", lambda: self.send_action("zombie")),
                ("5 精准狙击", lambda: self.send_action("precise")),
                ("6 C2 迁移\n(固定15 human_energy)", lambda: self.send_action("move_c2")),
            ]
        else:
            actions = [
                ("1 加固节点\n(人类成本3)", lambda: self.send_action("harden")),
                ("2 扫描节点\n(人类成本3)", lambda: self.send_action("scan")),
                ("3 清除潜伏病毒\n(人类成本9)", lambda: self.send_action("clear")),
                ("4 夺回 active 节点\n(人类成本21)", lambda: self.send_action("recapture")),
                ("5 恢复 abandoned 节点\n(人类成本12)", lambda: self.send_action("restore")),
                ("6 流量清洗", lambda: self.send_action("clean")),
                ("7 反击 C2\n(固定15 budget)", lambda: self.send_action("counter_c2")),
                ("0 手动结束本回合", self.on_finish_round),
            ]
        for idx, (label, cmd) in enumerate(actions):
            r = idx // 2
            c = idx % 2
            ttk.Button(action, text=label, command=cmd).grid(row=r, column=c, sticky="ew", padx=4, pady=4)
            action.columnconfigure(c, weight=1)

        table = ttk.LabelFrame(right, text="节点信息", padding=8)
        table.grid(row=4, column=0, sticky="nsew", pady=(8, 0))
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        if self.role == "attacker":
            cols = ("node", "view", "scan", "remark")
            widths = (70, 90, 220, 120)
            titles = ("节点", "你的视图", "扫描结果", "备注")
        else:
            cols = ("node", "base", "view", "scan")
            widths = (70, 90, 90, 240)
            titles = ("节点", "基础属性", "你的视图", "扫描记录")
        self.node_tree = ttk.Treeview(table, columns=cols, show="headings", height=12)
        for c, t, w in zip(cols, titles, widths):
            self.node_tree.heading(c, text=t)
            self.node_tree.column(c, width=w, anchor="center")
        self.node_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(table, orient="vertical", command=self.node_tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.node_tree.configure(yscrollcommand=sb.set)

        logf = ttk.LabelFrame(right, text="日志", padding=8)
        logf.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
        logf.rowconfigure(0, weight=1)
        logf.columnconfigure(0, weight=1)
        self.log_text = tk.Text(logf, wrap="word", height=12)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        lsb = ttk.Scrollbar(logf, orient="vertical", command=self.log_text.yview)
        lsb.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=lsb.set, state=tk.DISABLED)

    def collect_params(self) -> dict[str, Any]:
        return {
            "init_node": self.init_node_var.get().strip(),
            "init_state": self.init_state_var.get().strip() or "active",
            "source": self.source_var.get().strip(),
            "target": self.target_var.get().strip(),
            "radius": int(self.radius_var.get() or 2),
            "special_mode": self.special_mode_var.get().strip() or "convert",
            "use_all_active": bool(self.use_all_active_var.get()),
            "participants": self.participants_var.get().strip(),
            "clean_amount": int(self.clean_amount_var.get() or 8),
        }

    def on_start_round(self):
        self.send_action("start_round", include_all=True)

    def on_end_attacker_phase(self):
        self.send_action("end_attacker_phase")

    def on_finish_round(self):
        self.send_action("finish_round")

    def send_action(self, action: str, include_all: bool = False):
        params = self.collect_params() if include_all else self.collect_params()
        try:
            if isinstance(self.controller, HostNetworkController):
                ok, msg = self.controller.apply_action(self.role, action, params)
                self.global_var.set(msg)
            else:
                self.controller.send_action(action, params)
                self.global_var.set(f"已发送动作：{action}")
        except Exception as exc:
            messagebox.showerror("发送失败", str(exc), parent=self)

    def append_logs(self, logs: list[str]):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        for line in logs[-200:]:
            self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def apply_snapshot(self, snapshot: dict[str, Any]):
        self.snapshot = snapshot
        self.round_var.set(f"回合: {snapshot['current_round']}/{snapshot['max_rounds']}")
        self.phase_var.set(f"阶段: {snapshot['phase']}")
        r = snapshot["resources"]
        if self.role == "attacker":
            self.resource_var.set(f"人类 Energy={r['attacker_human_energy']} | AI Energy={r['attacker_ai_energy']} | C2静默={r['c2_silenced_rounds']}")
        else:
            self.resource_var.set(f"Budget={r['budget']} | Key={r['key']} | 僵尸军团={r['zombie_used']}/{r['zombie_max']}")
        self.turn_hint_var.set(snapshot.get("turn_hint", ""))
        self.status_var.set(snapshot.get("status", ""))
        self.global_var.set(snapshot.get("global_status", ""))
        values = snapshot.get("node_names", [])
        self.source_combo["values"] = values
        self.target_combo["values"] = values
        if self.role == "attacker":
            self.init_node_combo["values"] = values
        if values and not self.source_var.get():
            self.source_var.set(values[0])
            self.target_var.set(values[0])
            if self.role == "attacker" and not self.init_node_var.get():
                self.init_node_var.set(values[0])
        self.seed_var.set(int(snapshot.get("seed", 42)))
        self.max_rounds_var.set(int(snapshot.get("max_rounds", 20)))
        self.refresh_figure(snapshot)
        for item in self.node_tree.get_children():
            self.node_tree.delete(item)
        for node in snapshot.get("nodes", []):
            if self.role == "attacker":
                self.node_tree.insert("", tk.END, values=(node["node"], node["state"], node["scan"], node["remark"]))
            else:
                self.node_tree.insert("", tk.END, values=(node["node"], node["base"], node["state"], node["scan"]))
        self.append_logs(snapshot.get("logs", []))
        if self.role == "defender" and snapshot.get("awaiting_defender_prompt") and snapshot.get("current_round", -1) != self.last_prompt_round:
            self.last_prompt_round = snapshot.get("current_round", -1)
            self.after(100, self.ask_honeypot_prompt)

    def refresh_figure(self, snapshot: dict[str, Any]):
        ax = self.ax
        elev = getattr(ax, "elev", 30)
        azim = getattr(ax, "azim", -60)
        ax.cla()
        self.figure.patch.set_facecolor("black")
        ax.set_facecolor("black")
        positions = snapshot.get("positions", {})
        edges = snapshot.get("edges", [])
        by_node = {n["node"]: n for n in snapshot.get("nodes", [])}
        for u, v in edges:
            pu = positions[u]
            pv = positions[v]
            ax.plot([pu[0], pv[0]], [pu[1], pv[1]], [pu[2], pv[2]], c="white", linewidth=0.8, alpha=0.55)
        xs = [positions[n][0] for n in positions]
        ys = [positions[n][1] for n in positions]
        zs = [positions[n][2] for n in positions]
        pad = 0.15
        for node, p in positions.items():
            state = by_node.get(node, {}).get("state", "DD")
            color = self.module.get_node_color(state)
            ax.scatter(p[0], p[1], p[2], s=150, c=color, edgecolors="black", linewidths=0.7)
            ax.text(p[0], p[1], p[2], f"{node}\n{state}", color="white", fontsize=9)
        if xs:
            ax.set_xlim(min(xs) - pad, max(xs) + pad)
            ax.set_ylim(min(ys) - pad, max(ys) + pad)
            ax.set_zlim(min(zs) - pad, max(zs) + pad)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])
        ax.grid(False)
        ax.set_axis_off()
        ax.set_box_aspect([1, 1, 1])
        title = ("攻击方" if self.role == "attacker" else "防守方") + f" 3D 视图 | R{snapshot['current_round']} | {snapshot['phase']}"
        ax.set_title(title, color="white", fontsize=13)
        ax.view_init(elev=elev, azim=azim)
        self.figure.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.94)
        self.canvas.draw_idle()

    def ask_honeypot_prompt(self):
        allow = messagebox.askyesno(
            "防守方预部署蜜罐",
            "是否允许防守方 AI 基于当前进攻位置与已知线索，自动预测一个高风险节点并预部署蜜罐？",
            parent=self,
        )
        try:
            if isinstance(self.controller, HostNetworkController):
                self.controller.apply_action("defender", "honeypot_prompt", {"allow": allow})
            else:
                self.controller.send_action("honeypot_prompt", {"allow": allow})
        except Exception as exc:
            messagebox.showerror("发送失败", str(exc), parent=self)

    def process_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                mtype = msg.get("type")
                if mtype == "host_listening":
                    self.net_var.set(f"主机已监听: {msg['ip']}:{msg['port']} | 你是{self.role}")
                elif mtype == "peer_connected":
                    self.net_var.set(f"已连接对手 {msg['addr'][0]} | 对手角色={msg['role']}")
                elif mtype == "connected":
                    self.net_var.set(f"已连接主机 {self.config_data['host']}:{self.config_data['port']} | 你是{self.role}")
                elif mtype in {"remote_state", "local_state"}:
                    self.apply_snapshot(msg["snapshot"])
                elif mtype == "peer_disconnected":
                    self.net_var.set("对方已断开连接。")
                elif mtype == "network_error":
                    self.net_var.set(msg.get("message", "网络错误"))
                    messagebox.showerror("网络错误", msg.get("message", "网络错误"), parent=self)
        except queue.Empty:
            pass
        self.after(120, self.process_queue)

    def on_close(self):
        try:
            self.controller.close()
        except Exception:
            pass
        self.destroy()


def find_default_logic() -> str:
    candidates = [
        os.path.join(os.getcwd(), DEFAULT_LOGIC_BASENAME),
        os.path.join(os.path.dirname(__file__), DEFAULT_LOGIC_BASENAME),
        "/mnt/data/HVT_final.py",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HVT 局域网联机版")
    parser.add_argument("--mode", choices=["host", "client"], default=None)
    parser.add_argument("--role", choices=["attacker", "defender"], default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--logic", default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    root = tk.Tk()
    logic_path = args.logic or find_default_logic()
    config = None

    if args.mode and args.role:
        root.withdraw()
        config = {
            "mode": args.mode,
            "role": args.role,
            "host": args.host or get_local_ip(),
            "port": int(args.port),
            "logic_path": logic_path,
        }
    else:
        dialog = StartupDialog(root, logic_path)
        dialog.update_idletasks()
        dialog.lift()
        dialog.focus_force()
        root.wait_window(dialog)
        config = dialog.result

    root.destroy()
    if not config:
        return

    module = load_module(config["logic_path"])
    app = LanRoleApp(config, module)
    app.mainloop()



if __name__ == "__main__":
    main()
