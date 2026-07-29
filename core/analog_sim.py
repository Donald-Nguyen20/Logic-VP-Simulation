# -*- coding: utf-8 -*-
"""
Bo mo phong ANALOG (gia tri lien tuc, co buoc thoi gian) cho cac khoi dieu
khien: MV/SV Station, PID, I (tich phan), LLG (lead/lag)...
Moi lan goi step() = 1 chu ky dt.
"""
from __future__ import annotations
import os
import json

_ANALOG = None


def load_analog():
    global _ANALOG
    if _ANALOG is None:
        p = os.path.join(os.path.dirname(__file__), "macro_analog.json")
        try:
            _ANALOG = json.load(open(p, encoding="utf-8"))
        except Exception:
            _ANALOG = {}
    return _ANALOG


def has_analog(code):
    return (code or "").upper() in load_analog()


class AnalogSim:
    def __init__(self, code):
        self.code = (code or "").upper()
        self.spec = load_analog().get(self.code, {})
        self.dt = float(self.spec.get("dt", 0.5))
        self.inputs = {}
        for n, meta in self.spec.get("inputs", {}).items():
            self.inputs[n] = float(meta.get("init", 0.0))
        self.params = {k: float(v.get("val", 0.0)) for k, v in self.spec.get("params", {}).items()}
        self.state = {}
        self._pid_prev = {}
        self.last_memo = {}          # gia tri tung node o buoc step() gan nhat (cho xem so do)

    def set_input(self, name, val):
        if name in self.inputs:
            self.inputs[name] = float(val)

    def set_param(self, name, val):
        if name in self.params:
            self.params[name] = float(val)

    def reset(self):
        self.state = {}
        self._pid_prev = {}

    def input_meta(self):
        return self.spec.get("inputs", {})

    def _P(self, x):
        if isinstance(x, (int, float)):
            return float(x)
        if x in self.params:
            return self.params[x]
        if x in self.inputs:
            return self.inputs[x]
        try:
            return float(x)
        except Exception:
            return 0.0

    def step(self):
        nodes = self.spec.get("nodes", {})
        memo = {}
        dt = self.dt

        def val(name):
            if name in self.inputs:
                return self.inputs[name]
            if name in self.params:
                return self.params[name]
            if name in memo:
                return memo[name]
            nd = nodes.get(name)
            if nd is None:
                try:
                    return float(name)
                except Exception:
                    return 0.0
            op = nd["op"]
            if op in ("IN", "BOOL"):
                r = self.inputs.get(nd.get("name", name), 0.0)
            elif op == "CONST":
                r = float(nd.get("val", 0.0))
            elif op == "REF":
                r = self._P(nd["ref"])
            elif op == "SUB":
                r = val(nd["in"][0]) - val(nd["in"][1])
            elif op == "SUM":
                r = sum(val(x) for x in nd["in"])
            elif op == "GAIN":
                r = val(nd["in"][0]) * self._P(nd.get("k", 1.0))
            elif op == "MUL":
                r = 1.0
                for x in nd["in"]:
                    r *= val(x)
            elif op == "SELECT":
                r = val(nd["a"]) if val(nd["sel"]) > 0.5 else val(nd["b"])
            elif op == "OR":
                r = 1.0 if any(val(x) > 0.5 for x in nd["in"]) else 0.0
            elif op == "NOT":
                r = 0.0 if val(nd["in"][0]) > 0.5 else 1.0
            elif op == "GT":
                r = 1.0 if val(nd["in"][0]) > val(nd["in"][1]) else 0.0
            elif op == "CLAMP":
                v = val(nd["in"][0])
                hi = self._P(nd.get("hi", 1e12)); lo = self._P(nd.get("lo", -1e12))
                r = min(max(v, lo), hi)
            elif op == "RATELIM":
                target = val(nd["in"][0])
                rate = self._P(nd.get("rate", 1.0)) * dt
                cur = self.state.get(name, target if nd.get("init_track") else self._P(nd.get("init", 0.0)))
                if nd.get("hold") and val(nd["hold"]) > 0.5:
                    pass                                    # Hold=1: giu nguyen, khong doi toc do
                elif target > cur:
                    cur = min(target, cur + rate)
                else:
                    cur = max(target, cur - rate)
                self.state[name] = cur
                r = cur
            elif op == "INTEG":
                x = val(nd["in"][0])
                if "ti" in nd:
                    ti = self._P(nd["ti"]); rate = (x / ti) if ti else 0.0
                else:
                    rate = x * self._P(nd.get("ki", 1.0))
                hi = self._P(nd.get("hi", 1e12)); lo = self._P(nd.get("lo", -1e12))
                cur = self.state.get(name, self._P(nd.get("init", 0.0)))
                if nd.get("preset") and val(nd["preset"]) > 0.5:
                    cur = self._P(nd.get("preset_val", 0.0))
                elif not (nd.get("hold") and val(nd["hold"]) > 0.5):
                    cur = cur + rate * dt
                cur = min(max(cur, lo), hi)
                self.state[name] = cur
                r = cur
            elif op == "LEADLAG":
                x = val(nd["in"][0])
                tle = self._P(nd.get("tle", 0.0)); tla = self._P(nd.get("tla", 0.0))
                if nd.get("sw") is not None and val(nd["sw"]) < 0.5:
                    r = x
                else:
                    yprev = self.state.get(name, x)
                    xprev = self.state.get(name + ".x", x)
                    denom = tla + dt
                    r = ((tla * yprev + (tle + dt) * x - tle * xprev) / denom) if denom > 0 else x
                    self.state[name] = r
                self.state[name + ".x"] = x
            elif op == "DERIV":
                x = val(nd["in"][0])
                td = self._P(nd.get("td", 1.0)); gg = self._P(nd.get("g", 1.0))
                if nd.get("sw") is not None and val(nd["sw"]) < 0.5:
                    r = x                                   # SW=0: bypass Y=X
                    self.state[name] = 0.0
                    self.state[name + ".dx"] = x
                else:
                    dprev = self.state.get(name, 0.0)
                    xprev = self.state.get(name + ".dx", x)
                    a = td / (td + dt) if (td + dt) > 0 else 0.0
                    d = a * (dprev + x - xprev)             # loc thong cao: TD*s/(1+TD*s)
                    self.state[name] = d
                    self.state[name + ".dx"] = x
                    r = gg * d
                    hi = self._P(nd.get("hi", 1e12)); lo = self._P(nd.get("lo", -1e12))
                    r = min(max(r, lo), hi)
            elif op == "PID":
                sv = val(nd["sv"]); pv = val(nd["pv"])
                kp = self._P(nd.get("kp", 1.0)); ti = self._P(nd.get("ti", 0.0))
                td = self._P(nd.get("td", 0.0))
                hi = self._P(nd.get("hi", 100.0)); lo = self._P(nd.get("lo", 0.0))
                auto = (val(nd["auto"]) > 0.5) if nd.get("auto") else True
                e = sv - pv
                integ = self.state.get(name + ".I", 0.0)
                eprev = self._pid_prev.get(name, e)
                if auto:
                    if ti > 0:
                        integ = integ + (kp / ti) * e * dt
                    deriv = kp * td * (e - eprev) / dt if dt > 0 else 0.0
                    out = kp * e + integ + deriv
                    out = min(max(out, lo), hi)
                    integ = min(max(integ, lo - kp * e), hi - kp * e)
                else:
                    out = min(max(kp * e + integ, lo), hi)
                self.state[name + ".I"] = integ
                self._pid_prev[name] = e
                r = out
            elif op == "ABS":
                r = abs(val(nd["in"][0]))
            elif op == "AND":
                r = 1.0 if all(val(x) > 0.5 for x in nd["in"]) else 0.0
            elif op == "SRLATCH":
                # chot nho: S=1 -> bat (1); R=1 -> tat (0); R uu tien hon S neu ca hai cung 1
                s = val(nd["s"]); r_ = val(nd["r"])
                cur = self.state.get(name, self._P(nd.get("init", 0.0)))
                if r_ > 0.5:
                    cur = 0.0
                elif s > 0.5:
                    cur = 1.0
                self.state[name] = cur
                r = cur
            elif op == "DELAY":
                # Z^-1: tre 1 chu ky quet (gia tri buoc truoc)
                x = val(nd["in"][0])
                r = self.state.get(name, self._P(nd.get("init", x)))
                self.state[name] = x
            elif op == "TON":
                # bo tre bat (dropout filter): dau ra=1 chi khi dau vao=1 lien tuc >= T giay;
                # dau vao ve 0 la reset bo dem ngay (khong tre khi tat)
                x = val(nd["in"][0])
                T = self._P(nd.get("t", 0.0))
                if x > 0.5:
                    acc = self.state.get(name + ".acc", 0.0) + dt
                    self.state[name + ".acc"] = acc
                    r = 1.0 if acc >= T else 0.0
                else:
                    self.state[name + ".acc"] = 0.0
                    r = 0.0
            else:
                r = 0.0
            memo[name] = r
            return r

        out = {}
        for o, node in self.spec.get("out_map", {}).items():
            out[o] = val(node)
        for nm in nodes:                    # dam bao MOI node deu co gia tri (cho xem so do noi bo)
            if nm not in memo:
                val(nm)
        self.last_memo = memo               # snapshot gia tri tung node trong buoc nay
        return out


if __name__ == "__main__":
    print("== I (406C): X=2, TI=5, 15 buoc ==")
    s = AnalogSim("406C"); s.set_input("X", 2)
    for i in range(1, 16):
        o = s.step()
    print("  Y=%.2f (mong X/TI*dt*15 = 2/5*0.5*15 = 3.0)" % o["Y"])
    s.set_input("SW", 1); s.set_input("T", 30)
    print("  SW=1,T=30 -> Y=%.1f (mong 30)" % s.step()["Y"])
    print("== LLG (4040): X 0->10, Tle=2 Tla=5 ==")
    g = AnalogSim("4040")
    for i in range(3): g.step()
    g.set_input("X", 10)
    ys = [g.step()["Y"] for _ in range(12)]
    print("  Y buoc 1,2,4,8,12: %.2f %.2f %.2f %.2f %.2f" % (ys[0], ys[1], ys[3], ys[7], ys[11]))
