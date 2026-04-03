from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()

    sizes = [
        (360, 740),
        (768, 900),
        (1024, 768),
        (1280, 800),
        (1440, 900),
    ]
    idx = {"i": 0}

    def tick():
        i = idx["i"] % len(sizes)
        idx["i"] += 1
        ww, hh = sizes[i]
        w.resize(ww, hh)

    t = QTimer()
    t.setInterval(1200)
    t.timeout.connect(tick)
    t.start()
    tick()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

