import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from main_window import AnritsuScenarioViewerWindow

def main():
    app = QApplication(sys.argv)
    
    # Modern High DPI Scaling
    app.setStyle("Fusion")

    default_file = None
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        default_file = sys.argv[1]

    window = AnritsuScenarioViewerWindow(default_file=default_file)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
