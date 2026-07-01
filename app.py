import sys
from PySide6.QtWidgets import QApplication
from start_screen import StartScreen

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("LAADO AI")
    start = StartScreen()
    start.show()
    sys.exit(app.exec())