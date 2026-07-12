# -*- coding: utf-8 -*-
"""
Bo mo phong LOGIC BOOLEAN cho khoi hop thanh (MOV...) dua tren netlist
trong macro_behavior.json (chep tu so do noi bo AAxxx trong manual).

Ho tro cong: AND, OR, NOT, SR (chot set/reset), CONST, PARAM_EQ.
Chot SR giu trang thai giua cac lan danh gia (mach tuan tu).
"""
from __future__ import annotations
import os
import json

_BEHAV = None


def load_behavior():
    global _BEHAV
    if _BEHAV is None:
        p = os.path.join(os.path.dirname(__file__), "macro_behavior.json")
        try:
            _BEHAV = json.load(open(p, encoding="utf-8"))
        except Exception:
            _BEHAV = {}
    return _BEHAV


def has_behavior(code):
    return (code or "").upper() in load_behavior()


class LogicSim:
    """Mo phong 1 macro. Giu trang thai chot SR qua nhieu lan set gia tri."""

    def __init__(self, code):
        self.code = (code or "").upper()
        self.spec = load_behavior().get(self.code, {})
        self.inputs = {n: 0 for n in self.spec.get("inputs", [])}
        self.inputs.update({n: 0 for n in self.spec.get("ops", [])})
        self.params = {k: v.get("val", 0) for k, v in self.spec.get("params", {}).items()}
        self.state = {}   # trang thai chot SR: node_name -> 0/1

    # ---- thiet lap dau vao ----
    def set_input(self, name, val):
        if name in self.inputs:
            self.inputs[name] = 1 if val else 0

    def set_param(self, name, val):
        self.params[name] = int(val)

    def all_input_names(self):
        return list(self.spec.get("inputs", [])) + list(self.spec.get("ops", []))

    # ---- danh gia ----
    def evaluate(self):
        """Tra ve dict {ten_output: 0/1}."""
        nodes = self.spec.get("nodes", {})
        memo = {}

        def val(name):
            if name in self.inputs:
                return self.inputs[name]
            if name in memo:
                return memo[name]
            nd = nodes.get(name)
            if nd is None:
                return 0
            op = nd["op"]
            if op == "CONST":
                r = 1 if nd.get("val") else 0
            elif op == "PARAM_EQ":
                r = 1 if int(self.params.get(nd["param"], 0)) == int(nd["val"]) else 0
            elif op == "NOT":
                r = 0 if val(nd["in"][0]) else 1
            elif op == "AND":
                r = 1 if all(val(x) for x in nd["in"]) else 0
            elif op == "OR":
                r = 1 if any(val(x) for x in nd["in"]) else 0
            elif op == "SR":
                s = val(nd["set"]); rst = val(nd["reset"])
                cur = self.state.get(name, 0)
                if nd.get("reset_dominant"):
                    nv = 0 if rst else (1 if s else cur)
                else:
                    nv = 1 if s else (0 if rst else cur)
                self.state[name] = nv
                r = nv
            else:
                r = 0
            memo[name] = r
            return r

        out = {}
        for o, node in self.spec.get("out_map", {}).items():
            out[o] = val(node)
        return out


if __name__ == "__main__":
    # Kiem thu nhanh MOV2-NSH
    sim = LogicSim("8204")
    def show(tag):
        print("  %-28s -> %s" % (tag, sim.evaluate()))
    # 1) Vao Auto, ra lenh mo tu Auto OP
    sim.set_input("OPS.Auto", 1); sim.evaluate(); sim.set_input("OPS.Auto", 0)
    sim.set_input("Auto OP", 1)
    show("Auto + Auto OP (mong: OP CMD=1)")
    # 2) Cam mo
    sim.set_input("OP INH", 1)
    show("them OP INH=1 (mong: OP CMD=0)")
    sim.set_input("OP INH", 0)
    # 3) Local chan het
    sim.set_input("Local", 1)
    show("them Local=1 (mong: OP CMD=0)")
    sim.set_input("Local", 0)
    # 4) Khoa cheo: yeu cau dong
    sim.set_input("Auto CL", 1)
    show("them Auto CL=1 (khoa cheo: OP=0, CL=0)")
    sim.set_input("Auto CL", 0)
    # 5) Su co
    sim.set_input("E-FAIL", 1)
    show("E-FAIL=1 (mong: ABN=1)")
    sim.set_input("E-FAIL", 0)
    # 6) Qua momen theo Soft SW
    sim.set_input("OV TRQ", 1); sim.set_input("Closed", 1)
    print("  SW=0 (position seating):"); show("OV TRQ + Closed (mong: ABN=1)")
    sim.set_param("SW", 1)
    print("  SW=1 (torque seating):"); show("OV TRQ + Closed (mong: ABN=0)")
