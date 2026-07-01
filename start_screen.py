from app_ui import AppUI
import sys
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QApplication
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property, QObject
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QBrush, QConicalGradient
from PySide6.QtCore import QRectF, QPointF
import math


class RingWidget(QWidget):
    """Animated rotating ring — Jarvis style"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(320, 320)
        self._angle = 0
        self._pulse = 0.0
        self._pulse_dir = 1

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    def _tick(self):
        self._angle = (self._angle + 1.2) % 360
        self._pulse += 0.02 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse_dir = 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(160, 160)

        cx, cy = 0, 0
        pulse_alpha = int(80 + 80 * self._pulse)

        # Outer ring (rotating dashes)
        pen = QPen(QColor(88, 166, 255, 160))
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawEllipse(QRectF(-140, -140, 280, 280))

        # Rotating arc
        pen2 = QPen(QColor(88, 166, 255, 220))
        pen2.setWidth(3)
        pen2.setCapStyle(Qt.RoundCap)
        painter.setPen(pen2)
        rect = QRectF(-130, -130, 260, 260)
        painter.drawArc(rect, int(self._angle * 16), 100 * 16)
        painter.drawArc(rect, int((self._angle + 180) * 16), 60 * 16)

        # Middle ring (counter-rotating)
        pen3 = QPen(QColor(56, 139, 253, 180))
        pen3.setWidth(2)
        painter.setPen(pen3)
        rect2 = QRectF(-100, -100, 200, 200)
        painter.drawArc(rect2, int(-self._angle * 16 * 0.6), 130 * 16)
        painter.drawArc(rect2, int((-self._angle * 0.6 + 200) * 16), 50 * 16)

        # Inner ring (dots)
        pen4 = QPen(QColor(88, 166, 255, pulse_alpha))
        pen4.setWidth(2)
        painter.setPen(pen4)
        r = 60
        for i in range(12):
            a = math.radians(self._angle * 0.5 + i * 30)
            x = r * math.cos(a)
            y = r * math.sin(a)
            size = 3 if i % 3 == 0 else 1.5
            painter.drawEllipse(QPointF(x, y), size, size)

        # Core glow
        core_color = QColor(88, 166, 255, pulse_alpha)
        painter.setBrush(QBrush(core_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(0, 0), 8, 8)

        # Tick marks on outer ring
        pen5 = QPen(QColor(88, 166, 255, 100))
        pen5.setWidth(1)
        painter.setPen(pen5)
        for i in range(36):
            a = math.radians(i * 10)
            r_inner = 132 if i % 3 == 0 else 135
            x1 = r_inner * math.cos(a)
            y1 = r_inner * math.sin(a)
            x2 = 140 * math.cos(a)
            y2 = 140 * math.sin(a)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        painter.end()


class StartScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAADO AI")
        self.setFixedSize(600, 500)
        self.setStyleSheet("background-color: #060a0f;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(0)

        # Ring
        self.ring = RingWidget(self)
        layout.addWidget(self.ring, alignment=Qt.AlignCenter)

        layout.addSpacing(10)

        # Title
        self.title = QLabel("L A A D O")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("""
            color: #58a6ff;
            font-size: 32px;
            font-family: 'Courier New', monospace;
            letter-spacing: 12px;
            font-weight: bold;
        """)
        layout.addWidget(self.title)

        layout.addSpacing(6)

        # Subtitle
        self.subtitle = QLabel("PERSONAL AI SYSTEM — ONLINE")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setStyleSheet("""
            color: #3a6ea8;
            font-size: 11px;
            font-family: 'Courier New', monospace;
            letter-spacing: 4px;
        """)
        layout.addWidget(self.subtitle)

        layout.addSpacing(30)

        # Start button
        self.start_button = QPushButton("▶  INITIALIZE")
        self.start_button.setFixedSize(200, 48)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #58a6ff;
                font-size: 13px;
                font-family: 'Courier New', monospace;
                letter-spacing: 3px;
                border: 1px solid #1f4070;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0d2137;
                border-color: #58a6ff;
                color: #a0c4ff;
            }
            QPushButton:pressed {
                background-color: #1f4070;
            }
        """)
        layout.addWidget(self.start_button, alignment=Qt.AlignCenter)

        self.start_button.clicked.connect(self.on_start_clicked)

        # Blink subtitle
        self._blink_state = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(800)

    def _blink(self):
        self._blink_state = not self._blink_state
        color = "#3a6ea8" if self._blink_state else "#1a3050"
        self.subtitle.setStyleSheet(f"""
            color: {color};
            font-size: 11px;
            font-family: 'Courier New', monospace;
            letter-spacing: 4px;
        """)

    def on_start_clicked(self):
        from app_ui import AppUI
        self.app_ui = AppUI()
        self.app_ui.show()
        self.close()