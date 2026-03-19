"""Global dark industrial Qt stylesheet."""

STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-size: 14px;
    font-family: "Segoe UI", "Arial", sans-serif;
}
QGroupBox {
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
    color: #00bcd4;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {
    background-color: #2a2a2a;
    border: 1px solid #444;
    border-radius: 3px;
    padding: 6px;
    color: #f0f0f0;
    selection-background-color: #006b7d;
}
QPushButton {
    background-color: #2d3d47;
    color: #e8f7fa;
    border: 1px solid #00a8c8;
    border-radius: 4px;
    padding: 10px 16px;
    min-height: 22px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #34515c;
}
QPushButton:pressed {
    background-color: #1a252b;
}
QPushButton#successBtn {
    border-color: #2e7d32;
    color: #c8e6c9;
}
QPushButton#warnBtn {
    border-color: #f9a825;
    color: #fff3e0;
}
QPushButton#dangerBtn {
    border-color: #c62828;
    color: #ffcdd2;
}
QLabel#headerTitle {
    font-size: 22px;
    font-weight: bold;
    color: #00e5ff;
}
QLabel#statusOk { color: #66bb6a; font-weight: bold; }
QLabel#statusErr { color: #ef5350; font-weight: bold; }
QLabel#statusWarn { color: #ffca28; font-weight: bold; }
QLabel#cardValue {
    font-size: 28px;
    font-weight: bold;
    color: #80deea;
}
QLabel#cardLabel {
    font-size: 13px;
    color: #9e9e9e;
}
QScrollBar:vertical {
    background: #2a2a2a;
    width: 12px;
}
QScrollBar::handle:vertical {
    background: #555;
    min-height: 24px;
    border-radius: 4px;
}
QToolTip {
    background-color: #333;
    color: #fff;
    border: 1px solid #00bcd4;
}
"""
