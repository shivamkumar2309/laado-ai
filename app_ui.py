import threading
import webbrowser
import math
import datetime

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from speak import speak
from listen import listen, calibrate_noise_floor
import listen as listen_module
from brain import think, is_wake_word


# ──────────────────────────────────────────
#  Animated sonar ring
# ──────────────────────────────────────────
class SonarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 260)
        self._angle = 0
        self._rings = []
        self._mode = "idle"
        self._pulse = 0.0
        self._pulse_dir = 1

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_mode(self, mode: str):
        self._mode = mode
        if mode == "listening":
            self._emit_ring()

    def _emit_ring(self):
        self._rings.append([10, 200])

    def _tick(self):
        self._angle = (self._angle + 1.5) % 360
        self._pulse += 0.03 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse_dir = 1

        new_rings = []
        for r in self._rings:
            r[0] += 2
            r[1] -= 4
            if r[1] > 0:
                new_rings.append(r)
        self._rings = new_rings

        if self._mode == "listening" and len(self._rings) == 0:
            self._emit_ring()

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(130, 130)

        mode_colors = {
            "idle":      (88, 166, 255),
            "listening": (56, 211, 159),
            "thinking":  (240, 180, 40),
            "speaking":  (255, 120, 80),
        }
        r, g, b = mode_colors.get(self._mode, (88, 166, 255))
        pulse_a = int(80 + 80 * self._pulse)

        for ring in self._rings:
            ra, alpha = ring
            pen = QPen(QColor(r, g, b, min(alpha, 200)))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(0, 0), ra, ra)

        pen = QPen(QColor(r, g, b, 60))
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(0, 0), 120, 120)

        pen2 = QPen(QColor(r, g, b, 80))
        pen2.setWidth(1)
        painter.setPen(pen2)
        for i in range(36):
            a = math.radians(i * 10)
            r1 = 115 if i % 3 == 0 else 118
            painter.drawLine(
                QPointF(r1 * math.cos(a), r1 * math.sin(a)),
                QPointF(120 * math.cos(a), 120 * math.sin(a))
            )

        pen3 = QPen(QColor(r, g, b, 200))
        pen3.setWidth(3)
        pen3.setCapStyle(Qt.RoundCap)
        painter.setPen(pen3)
        sweep_rect = QRectF(-95, -95, 190, 190)
        painter.drawArc(sweep_rect, int(self._angle * 16), 80 * 16)

        pen4 = QPen(QColor(r, g, b, 120))
        pen4.setWidth(2)
        painter.setPen(pen4)
        rect2 = QRectF(-70, -70, 140, 140)
        painter.drawArc(rect2, int(-self._angle * 0.7 * 16), 50 * 16)

        pen5 = QPen(QColor(r, g, b, pulse_a))
        pen5.setWidth(2)
        painter.setPen(pen5)
        orbit_r = 45
        for i in range(8):
            a = math.radians(self._angle * 0.6 + i * 45)
            x = orbit_r * math.cos(a)
            y = orbit_r * math.sin(a)
            size = 3 if i % 2 == 0 else 1.5
            painter.drawEllipse(QPointF(x, y), size, size)

        painter.setBrush(QBrush(QColor(r, g, b, pulse_a)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(0, 0), 10, 10)

        painter.end()


def h_line():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #1a2a3a;")
    return line


class AppUI(QWidget):
    update_signal = Signal(str, str)
    text_signal   = Signal(str)     # ← live streaming text updates
    close_signal  = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAADO — AI SYSTEM")
        self.showMaximized()
        self.setStyleSheet("""
            QWidget {
                background-color: #060a0f;
                color: #c9d1d9;
                font-family: 'Courier New', monospace;
            }
        """)

        self._build_ui()
        self.update_signal.connect(self._on_update)
        self.text_signal.connect(self.text_label.setText)
        self.close_signal.connect(self.close)

        threading.Thread(target=self._run_laado, daemon=True).start()

    # ── Build layout ──────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left panel
        left = QFrame()
        left.setFixedWidth(220)
        left.setStyleSheet("background-color: #080d14; border-right: 1px solid #0d1f30;")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 24, 16, 24)
        left_layout.setSpacing(12)

        title = QLabel("L A A D O")
        title.setStyleSheet("color: #58a6ff; font-size: 16px; letter-spacing: 8px; font-weight: bold;")
        left_layout.addWidget(title)

        version = QLabel("AI SYSTEM v2.1")
        version.setStyleSheet("color: #3a6ea8; font-size: 10px; letter-spacing: 2px;")
        left_layout.addWidget(version)

        left_layout.addWidget(h_line())
        left_layout.addSpacing(8)

        stat_label = QLabel("SYSTEM STATUS")
        stat_label.setStyleSheet("color: #3a6ea8; font-size: 9px; letter-spacing: 3px;")
        left_layout.addWidget(stat_label)

        for key, val in [("CORE", "ONLINE"), ("VOICE", "ACTIVE"), ("MEMORY", "LOADED"), ("LLM", "GROQ")]:
            row = QHBoxLayout()
            k = QLabel(key)
            k.setStyleSheet("color: #58a6ff; font-size: 10px;")
            v = QLabel(val)
            v.setStyleSheet("color: #3fb950; font-size: 10px;")
            row.addWidget(k)
            row.addStretch()
            row.addWidget(v)
            left_layout.addLayout(row)

        left_layout.addSpacing(16)
        left_layout.addWidget(h_line())
        left_layout.addSpacing(8)

        clk_lbl = QLabel("LOCAL TIME")
        clk_lbl.setStyleSheet("color: #3a6ea8; font-size: 9px; letter-spacing: 3px;")
        left_layout.addWidget(clk_lbl)

        self._clock = QLabel("--:--:--")
        self._clock.setStyleSheet("color: #58a6ff; font-size: 20px; letter-spacing: 2px;")
        left_layout.addWidget(self._clock)

        self._date_lbl = QLabel("")
        self._date_lbl.setStyleSheet("color: #3a6ea8; font-size: 10px;")
        left_layout.addWidget(self._date_lbl)

        left_layout.addStretch()

        esc_lbl = QLabel("ESC to close")
        esc_lbl.setStyleSheet("color: #1f4070; font-size: 9px;")
        esc_lbl.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(esc_lbl)

        root.addWidget(left)

        # Center panel
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(40, 40, 40, 40)
        center_layout.setSpacing(20)
        center_layout.setAlignment(Qt.AlignCenter)

        self.sonar = SonarWidget()
        center_layout.addWidget(self.sonar, alignment=Qt.AlignCenter)

        self.mode_label = QLabel("INITIALIZING")
        self.mode_label.setAlignment(Qt.AlignCenter)
        self.mode_label.setStyleSheet("color: #58a6ff; font-size: 13px; letter-spacing: 5px;")
        center_layout.addWidget(self.mode_label)

        center_layout.addWidget(h_line())

        self.text_label = QLabel("...")
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("color: #8b949e; font-size: 13px; line-height: 1.6; padding: 0 20px;")
        center_layout.addWidget(self.text_label)

        root.addWidget(center, 1)

        # Right panel
        right = QFrame()
        right.setFixedWidth(220)
        right.setStyleSheet("background-color: #080d14; border-left: 1px solid #0d1f30;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 24, 16, 24)
        right_layout.setSpacing(8)

        log_lbl = QLabel("ACTIVITY LOG")
        log_lbl.setStyleSheet("color: #3a6ea8; font-size: 9px; letter-spacing: 3px;")
        right_layout.addWidget(log_lbl)
        right_layout.addWidget(h_line())

        self._log_labels = []
        for _ in range(8):
            lbl = QLabel("")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #3a6ea8; font-size: 10px; padding: 2px 0;")
            right_layout.addWidget(lbl)
            self._log_labels.append(lbl)

        right_layout.addStretch()
        root.addWidget(right)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    def _on_update(self, mode: str, text: str):
        colors = {
            "idle":      "#58a6ff",
            "listening": "#3fb950",
            "thinking":  "#e3b341",
            "speaking":  "#f0883e",
            "error":     "#f85149",
        }
        color = colors.get(mode, "#58a6ff")
        self.mode_label.setText(text.upper())
        self.mode_label.setStyleSheet(f"color: {color}; font-size: 13px; letter-spacing: 5px;")
        self.sonar.set_mode(mode)
        self._log(text)

    def _log(self, text: str):
        for i in range(len(self._log_labels) - 1, 0, -1):
            self._log_labels[i].setText(self._log_labels[i - 1].text())
        now = datetime.datetime.now().strftime("%H:%M")
        self._log_labels[0].setText(f"[{now}] {text[:28]}")

    def _update_clock(self):
        now = datetime.datetime.now()
        self._clock.setText(now.strftime("%H:%M:%S"))
        self._date_lbl.setText(now.strftime("%d %b %Y"))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    # ── Main loop ────────────────────────
    def _run_laado(self):
        state = "active"
        self.update_signal.emit("idle", "Calibrating mic")
        suggested = calibrate_noise_floor()
        listen_module.SILENCE_THRESH = max(suggested, 600)   # safety floor
        print(f"[LAADO] Using silence threshold: {listen_module.SILENCE_THRESH:.0f}")

        self.update_signal.emit("idle", "Starting up")
        speak("Hello Sir, I'm LAADO. How can I help you?", "caring")

        while True:
            try:
                # ════════ DORMANT — wake word only ════════
                if state == "dormant":
                    self.update_signal.emit("idle", "Say Wake Up to resume")
                    self.text_label.setText("Dormant — say 'Wake Up' to activate")

                    user_text = listen()

                    if user_text and is_wake_word(user_text):
                        state = "active"
                        self.update_signal.emit("listening", "Activated")
                        speak("I'm back, Sir. Go ahead.", "caring")
                    continue

                # ════════ ACTIVE — normal conversation ════════
                self.update_signal.emit("listening", "Listening")
                user_text = listen()

                if not user_text:
                    self.update_signal.emit("idle", "Going dormant")
                    speak("I'm here Sir, just say wake up when you need me.", "caring")
                    state = "dormant"
                    continue

                # ── User text shows instantly ──
                self.text_signal.emit(f'"{user_text}"')
                self.update_signal.emit("thinking", "Processing")

                result = think(user_text)
                reply   = result.get("reply", "")
                tone    = result.get("tone", "normal")
                action  = result.get("action")
                is_exit = result.get("exit", False)

                if reply:
                    self.text_signal.emit(reply)
                    self.update_signal.emit("speaking", "Speaking")
                    speak(reply, tone)

                # ── EXIT — close the app cleanly ──
                if is_exit:
                    self.update_signal.emit("idle", "Shutting down")
                    self.close_signal.emit()
                    return

                if action:
                    if action["type"] == "youtube":
                        webbrowser.open(
                            f"https://www.youtube.com/results?search_query={action['query']}"
                        )
                    elif action["type"] == "open_site":
                        webbrowser.open(action["url"])

                self.update_signal.emit("idle", "Ready")

            except Exception as e:
                print("Laado error:", e)
                self.update_signal.emit("error", "Error occurred")