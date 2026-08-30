# -*- coding: utf-8 -*-
"""Hop thoai 'Explain (AI)': gom ngu canh 1 tin hieu, goi Claude (Agent SDK)
trong LUONG NEN va hien loi giai thich. Dung dang nhap Claude Code co san tren may
(khong can dan token)."""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                               QPushButton, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
import time

from core import ai_explain as AE
from core import ai_client as AC
from core import llm_config as LC
from core import llm_client as LClient

# Cau he thong NGAN cho cac nha cung cap goi qua HTTP. Ban day du da nam san trong
# build_prompt() (phan user), nen o day chi can mot cau neo lai vai tro - dat lai ca
# ban day du vao system la ton ~1.700 token va lap chi dan hai lan.
_SYS_ANCHOR = ("You are a controls engineer assistant for a Toshiba DCS power plant. "
               "Follow the instructions in the user message exactly.")


class _Worker(QThread):
    done = Signal(str)
    step = Signal(str, str)   # (kind, info): tu luong nen -> luong giao dien

    def __init__(self, prompt, model=None, prompt_no_tools=None,
                 provider="claude", use_tools=True):
        super().__init__()
        self.prompt = prompt; self.model = model
        self.prompt_no_tools = prompt_no_tools
        self.provider = provider or "claude"
        self.use_tools = use_tools

    def run(self):
        # step.emit tu luong nen sang luong giao dien la an toan (Qt tu xep hang doi)
        say = lambda k, i: self.step.emit(k, i)
        if self.provider == "claude":
            # Claude di duong RIENG: Agent SDK + dang nhap Claude Code, khong phai HTTP.
            self.done.emit(AC.ask(self.prompt, self.model,
                                  prompt_no_tools=self.prompt_no_tools,
                                  on_event=say))
            return
        cl = None
        try:
            cl = LClient.create_client(self.provider)
            p = self.prompt if self.use_tools else (self.prompt_no_tools or self.prompt)
            self.done.emit(cl.ask(_SYS_ANCHOR, p, use_tools=self.use_tools, on_event=say))
        except Exception as e:
            # Nhieu model KHONG biet goi cong cu va may chu tu choi thang. Bo cong cu
            # roi hoi lai bang ban prompt da kem san du lieu - van co cau tra loi,
            # con hon bat nguoi dung tu doan phai doi model nao.
            if cl is not None and self.use_tools and LClient.is_tool_reject(e):
                say("status", "Model nay khong goi duoc cong cu - dang hoi lai "
                              "bang du lieu gui kem...")
                try:
                    txt = cl.ask(_SYS_ANCHOR, self.prompt_no_tools or self.prompt,
                                 use_tools=False, on_event=say)
                    self.done.emit(
                        "> _Model nay khong tu tra cuu duoc, cau tra loi duoi day chi dua"
                        " tren du lieu gui kem. Muon AI tu tra cuu: chon model khac trong"
                        " 'AI Setting'._\n\n" + txt)
                    return
                except Exception as e2:
                    e = e2
            # Loi mang/key/model phai NOI RA, khong duoc de cua so im lang - nguoi dung
            # khong co cach nao khac de biet vi sao khong co cau tra loi.
            self.done.emit("Khong goi duoc %s.\n\n%s: %s\n\nMo 'AI Setting' tren "
                           "thanh cong cu de kiem tra API key va ten model."
                           % (self.provider, type(e).__name__, e))


# co chu tieu de theo cap: (he so so voi than chu, mau, cach le tren)
# QTextBlockFormat::ProportionalHeight. Phai la SO: PySide6 khong ep duoc enum
# sang int va setLineHeight() thi doi (float, int).
_PROPORTIONAL = 1

_HEAD = {1: (1.55, "#0F172A", 2.0), 2: (1.22, "#1D4ED8", 18.0),
         3: (1.06, "#334155", 12.0)}


class AIExplainDialog(QDialog):
    def __init__(self, db, sheet, net, cpu_paths=None, parent=None, loopno=None):
        """loopno != None -> che do GIAI THICH CA LOOP (nguyen ly dieu khien cua ca
        mach), thay vi truy nguoc 1 tin hieu. Khi do sheet/net bi bo qua."""
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
                            | Qt.WindowType.WindowMaximizeButtonHint)
        self.resize(720, 640)
        self._loop = loopno
        try:
            if loopno is not None:
                name, ctx = AE.build_loop_context(db, loopno)
            else:
                name, ctx = AE.build_signal_context(db, sheet, net, cpu_paths=cpu_paths)
        except Exception as e:
            name, ctx = (("Loop %s" % loopno) if loopno is not None else net,
                         "(context error: %s)" % e)
        self._name = name; self._ctx = ctx
        self.setWindowTitle("Explain (AI): %s" % name)
        lay = QVBoxLayout(self)
        hdr = QLabel(name); hdr.setStyleSheet("font-size:15px;font-weight:600;")
        lay.addWidget(hdr)

        from ui.status_orb import ClaudeStatusBar
        self.status_bar = ClaudeStatusBar()      # den bao ket noi (tu sang khi login xong)
        lay.addWidget(self.status_bar)
        self.status_lbl = QLabel(""); self.status_lbl.setStyleSheet("font-size:12px;color:#64748B;")
        lay.addWidget(self.status_lbl)

        self.answer = QTextEdit(); self.answer.setReadOnly(True)
        self.answer.setStyleSheet(
            "QTextEdit{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;}")
        self.answer.document().setDocumentMargin(16)
        af = self.answer.font(); af.setFamily("Segoe UI"); af.setPointSizeF(10.5)
        self.answer.setFont(af)
        lay.addWidget(self.answer, 1)

        self._lang = "en"
        bar = QHBoxLayout()
        from PySide6.QtWidgets import QComboBox
        self.cb_prov = QComboBox()
        for k, full in LClient.PROVIDERS:
            # Nut bar hep: hien ten ngan, con "mien phi / tra phi" de vao tooltip.
            self.cb_prov.addItem(LClient.short(k), k)
            self.cb_prov.setItemData(self.cb_prov.count() - 1,
                                     "%s\n%s" % (full, LClient.note(k)),
                                     Qt.ToolTipRole)
        cfg = LC.load_llm_config()
        self.cb_prov.setCurrentIndex(max(0, self.cb_prov.findData(cfg.get("provider", "claude"))))
        self.cb_prov.setToolTip("Nha cung cap AI dung cho Explain")
        self.cb_prov.currentIndexChanged.connect(self._switch_provider)
        bar.addWidget(self.cb_prov)
        self.btn_login = QPushButton("Login to Claude"); self.btn_login.clicked.connect(self._login)
        self.btn_ping = QPushButton("Kiem tra ket noi")
        self.btn_ping.setToolTip("Hoi Claude 1 cau ngan (khong ngu canh, khong cong cu, 45s) "
                                 "de biet loi nam o duong day hay o ngu canh")
        self.btn_ping.clicked.connect(self._ping)
        self.btn_lang = QPushButton("Tiếng Việt"); self.btn_lang.clicked.connect(self._toggle_lang)
        self.btn_lang.setToolTip("Chuyen ngon ngu tra loi (English / Tieng Viet)")
        self.btn_ask = QPushButton("Ask Claude"); self.btn_ask.clicked.connect(self._run)
        bar.addWidget(self.btn_login); bar.addWidget(self.btn_ping); bar.addStretch(1)
        bar.addWidget(self.btn_lang); bar.addWidget(self.btn_ask)
        lay.addLayout(bar)

        self._refresh()

    def _provider(self):
        return self.cb_prov.currentData() or "claude"

    def _switch_provider(self):
        """Ghi lua chon xuong cau hinh ngay: nguoi dung chon o day thi lan sau mo lai
        van la nha cung cap do, khong phai chon di chon lai."""
        p = self._provider()
        try:
            cfg = LC.load_llm_config(); cfg["provider"] = p; LC.save_llm_config(cfg)
        except Exception:
            pass
        self._refresh()

    def reload_provider(self):
        """Cua so chinh vua doi cai dat AI -> cap nhat lai o chon va trang thai."""
        p = LC.load_llm_config().get("provider", "claude")
        i = self.cb_prov.findData(p)
        if i >= 0 and i != self.cb_prov.currentIndex():
            self.cb_prov.setCurrentIndex(i)         # keo theo _refresh
        else:
            self._refresh()

    def _refresh(self):
        p = self._provider()
        name = LClient.short(p)
        self.btn_ask.setText("Ask %s" % name)
        for w in (self.btn_login,):
            w.setVisible(p == "claude")
        if p != "claude":
            self._refresh_http(p, name)
            return
        err = AC.sdk_error(); sdk = err is None; cli = AC.cli_available()
        s = "SDK: " + ("OK" if sdk else ("LOI - %s" % err))
        s += "   |   CLI: " + ("OK" if cli else "chua co")
        self.status_lbl.setText(s)
        try:
            self.status_bar.refresh()
        except Exception:
            pass
        self.btn_ask.setEnabled(sdk)
        if sdk:
            self.answer.setPlaceholderText("Bam 'Ask Claude'. Neu chua dang nhap, bam 'Login to Claude' truoc.")
        else:
            self.answer.setText(AC.setup_hint())

    def _refresh_http(self, p, name):
        """Trang thai cua cac nha cung cap goi qua HTTP: du key + model thi moi hoi duoc."""
        cfg = LC.load_llm_config()
        model = (cfg.get("%s_model" % p) or "").strip()
        need_key = p in LClient.NEEDS_KEY
        key = LC.api_key(p, cfg) if need_key else ""
        ok = bool(model) and (bool(key) or not need_key)
        bits = []
        if need_key:
            bits.append("Key: %s" % LC.mask(key))
        bits.append("Model: %s" % (model or "(chua chon)"))
        self.status_lbl.setText("%s   |   %s" % (name, "   |   ".join(bits)))
        self.btn_ask.setEnabled(ok)
        if ok:
            self.answer.setPlaceholderText("Bam 'Ask %s'." % name)
        else:
            thieu = ("API key" if need_key and not key else "ten model")
            self.answer.setText(
                "Chua dung duoc %s: con thieu %s.\n\n"
                "Tren thanh cong cu cua so chinh, bam 'AI Setting' -> nut xanh "
                "'Lay API key' de tao key, roi 'Tai danh sach model'." % (name, thieu))

    def _login(self):
        ok, msg = AC.start_login()
        QMessageBox.information(self, "Login to Claude", msg)
        # dang nhap xong o cua so ngoai -> den bao tu sang, khong phai mo lai app
        self._refresh()

    def _ping(self):
        """Thu 1 cau ngan (khong ngu canh, khong cong cu) de khoanh vung loi nhanh."""
        if self._provider() != "claude":
            self._ping_http()
            return
        self.btn_ping.setEnabled(False)
        self.answer.setText("Dang thu 1 cau ngan (toi da 45s)...")

        class _P(QThread):
            done = Signal(str)

            def run(self):
                ok, txt = AC.ping()
                self.done.emit(("OK - duong day va dang nhap BINH THUONG.\n"
                                "Claude tra loi: %s\n\n"
                                "Vay loi (neu co) nam o phan ngu canh/cong cu, khong phai "
                                "ket noi." % txt) if ok
                               else ("CHUA goi duoc Claude.\n\n%s" % txt))

        self._p = _P()
        self._p.done.connect(lambda t: (self.answer.setText(t),
                                        self.btn_ping.setEnabled(True)))
        self._p.start()

    def _ping_http(self):
        p = self._provider(); name = LClient.short(p)
        self.btn_ping.setEnabled(False)
        self.answer.setText("Dang thu 1 cau ngan qua %s..." % name)

        class _P(QThread):
            done = Signal(str)

            def run(self):
                try:
                    txt = LClient.ping(p, model=LC.load_llm_config().get("%s_model" % p, ""),
                                       host=LC.load_llm_config().get("ollama_host", ""))
                    self.done.emit("OK - %s tra loi: %s\n\nVay key va model deu chay; "
                                   "loi (neu co) nam o phan ngu canh." % (name, txt))
                except Exception as e:
                    self.done.emit("CHUA goi duoc %s.\n\n%s: %s" % (name, type(e).__name__, e))

        self._p = _P()
        self._p.done.connect(lambda t: (self.answer.setPlainText(t),
                                        self.btn_ping.setEnabled(True)))
        self._p.start()

    def _toggle_lang(self):
        self._lang = "vi" if self._lang == "en" else "en"
        self.btn_lang.setText("English" if self._lang == "vi" else "Tiếng Việt")
        # neu da co cau tra loi thi hoi lai bang ngon ngu moi
        if self.btn_ask.isEnabled():
            self._run()

    def _run(self):
        # _toggle_lang goi thang vao day, ke ca khi luot truoc chua xong -> phai dep
        # dong ho cu, khong thi moi lan doi ngon ngu lai them 1 cai chay song song
        try:
            self._tick.stop()
        except Exception:
            pass
        self.btn_ask.setEnabled(False)
        self._t0 = time.time(); self._ntool = 0; self._live = ""
        self._last = self._t0
        self._reset_answer()
        p = self._provider(); name = LClient.short(p)
        self.answer.setPlaceholderText("Dang hoi %s, chu se hien dan ra day..." % name)
        if self._loop is not None:
            prompt = AE.build_loop_prompt(self._name, self._ctx, lang=self._lang)
            prompt_nt = prompt
        else:
            prompt = AE.build_prompt(self._name, self._ctx, lang=self._lang)
            # ban du phong: neu phai chay lai khong co tool thi noi ro cho AI biet
            prompt_nt = AE.build_prompt(self._name, self._ctx, lang=self._lang,
                                        use_tools=False)
        use_tools = (p == "claude") or bool(LC.load_llm_config().get("use_tools", True))
        self._w = _Worker(prompt, prompt_no_tools=prompt_nt, provider=p, use_tools=use_tools)
        self._w.step.connect(self._step)
        self._w.done.connect(self._show)
        self._w.start()
        # dong ho: de nguoi dung biet no VAN dang chay trong luc AI tra cuu (co the
        # im lang hang chuc giay lien) chu khong phai da treo
        self._tick = QTimer(self); self._tick.timeout.connect(self._beat)
        self._tick.start(1000); self._beat()

    def _step(self, kind, info):
        """Hien NGAY viec AI vua lam. Truoc day cua so dung im toi 4 phut roi moi co
        chu, nen nguoi dung tuong hong va tat di truoc khi cau tra loi kip ve."""
        self._last = time.time()
        if kind == "status":
            self.status_lbl.setText(info)      # bao viec dang lam, khong phai cau tra loi
            return
        if kind == "tool":
            self._ntool += 1
            self.status_lbl.setText("Dang tra cuu lan %d: %s" % (self._ntool, info))
            return
        self._live += info
        self.answer.setPlainText(self._live)
        sb = self.answer.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _beat(self):
        """Dong ho chay LIEN TUC ca khi da co chu. Quan trong: sau luot tra cuu cuoi,
        AI im lang rat lau de soan cau tra loi (do duoc 124s tren MFT) - khong co dong
        ho thi man hinh dung yen y het va nguoi dung tuong da treo."""
        el = int(time.time() - self._t0)
        idle = time.time() - getattr(self, "_last", self._t0)
        if not self._ntool:
            self.status_lbl.setText("Dang doc so do va hoi %s... %ds"
                                    % (LClient.short(self._provider()), el))
        elif idle > 4:
            self.status_lbl.setText(
                "Da tra cuu %d lan, dang soan cau tra loi... %ds  (tin hieu lon nhu "
                "MFT mat khoang 4 phut)" % (self._ntool, el))

    def _trim(self, out):
        """Bo doan AI tu thuat truoc tieu de ('I'll start by loading the tool schemas...').
        Chi cat khi tim thay tieu de '# ' O GAN DAU va phan bo di that su ngan, de khong
        bao gio nuot mat noi dung that."""
        i = out.find("\n# ")
        if 0 < i < 1200 and not out.lstrip().startswith("#"):
            return out[i + 1:]
        return out

    def _reset_answer(self):
        """Xoa han dinh dang cu truoc moi luot hoi. setPlainText("") KHONG xoa char-format
        cua con tro, nen luot sau chu dang chay se bi ke thua co chu tieu de 16pt."""
        from PySide6.QtGui import QTextCharFormat
        self.answer.clear()
        cf = QTextCharFormat()
        cf.setFont(self.answer.font())
        self.answer.setCurrentCharFormat(cf)

    def _polish(self):
        """Markdown cua Qt gan nhu khong phan cap co chu (do duoc H1 11pt so voi than
        10.5pt) va dat cac dong sat nhau. Ham nay dung lai thang bac tieu de + gian dong;
        bo qua o trong bang de bang khong bi keo gian."""
        from PySide6.QtGui import QTextCursor, QTextBlockFormat, QTextCharFormat, QColor
        base = self.answer.font().pointSizeF()
        doc = self.answer.document()
        cur = QTextCursor(doc)
        cur.movePosition(QTextCursor.Start)
        while True:
            if cur.currentTable() is None:
                bf = cur.blockFormat()
                lvl = bf.headingLevel()
                bf.setLineHeight(138.0, _PROPORTIONAL)
                bf.setBottomMargin(7.0)
                if lvl in _HEAD:
                    scale, col, top = _HEAD[lvl]
                    bf.setTopMargin(top)
                    bf.setBottomMargin(6.0)
                    bf.setLineHeight(118.0, _PROPORTIONAL)
                    # chon tuong minh: BlockUnderCursor khong chon duoc khi con tro
                    # dang o dau khoi, nen merge char-format khong an gi
                    sel = QTextCursor(cur)
                    sel.movePosition(QTextCursor.StartOfBlock)
                    sel.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                    cf = QTextCharFormat()
                    cf.setFontPointSize(base * scale)
                    cf.setFontWeight(700)
                    cf.setForeground(QColor(col))
                    sel.mergeCharFormat(cf)
                cur.setBlockFormat(bf)
            if not cur.movePosition(QTextCursor.NextBlock):
                break
        cur.movePosition(QTextCursor.Start)
        self.answer.setTextCursor(cur)

    def _show(self, text):
        try:
            self._tick.stop()
        except Exception:
            pass
        out = (text or self._live).strip()
        if not out:
            self.answer.setPlainText(
                "%s khong tra ve chu nao. Bam 'Kiem tra ket noi' de xem loi nam o "
                "duong day hay o ngu canh." % LClient.short(self._provider()))
            self.btn_ask.setEnabled(True)
            return
        out = self._trim(out)
        # trong luc chay thi hien chu tho cho nhanh; xong moi dung Markdown that (tieu de,
        # bang, chu dam) vi luc do van ban moi tron ven
        try:
            self.answer.setMarkdown(out)
        except Exception:
            self.answer.setPlainText(out)
        else:
            try:
                self._polish()          # chi la gian dong, hong thi van giu ban markdown
            except Exception:
                pass
        self.status_lbl.setText("Xong sau %ds, da tra cuu %d lan."
                                % (int(time.time() - self._t0), self._ntool))
        self.btn_ask.setEnabled(True)
