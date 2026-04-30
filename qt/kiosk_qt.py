#!/usr/bin/env python3
import json
import subprocess
import sys

import requests
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


BASE_URL = "http://127.0.0.1"
APP_NAME = "DevBoard Server Console"


class ApiClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Cache-Control": "no-cache"})

    def request(self, method, path, json_body=None):
        response = self.session.request(
            method=method,
            url=f"{self.base_url}{path}",
            json=json_body,
            timeout=8,
        )
        content_type = response.headers.get("content-type", "")
        payload = response.json() if "application/json" in content_type else response.text
        if not response.ok:
            if isinstance(payload, dict) and payload.get("error"):
                raise RuntimeError(payload["error"])
            raise RuntimeError(f"请求失败 {response.status_code}")
        return payload

    def auth_status(self):
        return self.request("GET", "/api/auth/status")

    def workstation(self):
        return self.request("GET", "/api/device/workstation")

    def workstation_status(self):
        return self.request("GET", "/api/device/workstation/status")

    def wake(self):
        return self.request("POST", "/api/device/workstation/wake", {})

    def shutdown(self):
        return self.request("POST", "/api/device/workstation/shutdown", {})

    def sync_status(self):
        return self.request("GET", "/api/syncthing/status")


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.NoFrame)


class QuickActionButton(QPushButton):
    def __init__(self, icon_text, title, subtitle, tone, parent=None):
        super().__init__(parent)
        self.setObjectName(f"quick-{tone}")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        icon = QLabel(icon_text)
        icon.setObjectName("quickIcon")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(42, 42)

        title_label = QLabel(title)
        title_label.setObjectName("quickTitle")

        sub_label = QLabel(subtitle)
        sub_label.setObjectName("quickSubtitle")
        sub_label.setWordWrap(True)

        layout.addWidget(icon, 0, Qt.AlignLeft)
        layout.addWidget(title_label)
        layout.addWidget(sub_label)
        layout.addStretch(1)


class InfoRow(QWidget):
    def __init__(self, label, value="", value_style="muted", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        self.label = QLabel(label)
        self.label.setObjectName("rowLabel")
        self.value = QLabel(value)
        self.value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value.setObjectName("rowValue" if value_style == "strong" else "rowMuted")

        layout.addWidget(self.label)
        layout.addStretch(1)
        layout.addWidget(self.value)

    def set_value(self, value, strong=False):
        self.value.setText(str(value))
        self.value.setObjectName("rowValue" if strong else "rowMuted")
        self.style().unpolish(self.value)
        self.style().polish(self.value)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = ApiClient()
        self.state = {
            "auth": None,
            "device": None,
            "device_status": None,
            "sync": None,
        }

        self.setWindowTitle(APP_NAME)
        self.resize(1024, 640)
        self.setMinimumSize(800, 480)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        hero = self.build_hero()
        root_layout.addWidget(hero)

        body = QGridLayout()
        body.setHorizontalSpacing(16)
        body.setVerticalSpacing(16)
        body.addWidget(self.build_network_card(), 0, 0)
        body.addWidget(self.build_direct_card(), 0, 1)
        body.addWidget(self.build_arch_card(), 1, 0, 2, 1)
        body.addWidget(self.build_actions_card(), 1, 1)
        body.addWidget(self.build_storage_card(), 2, 1)
        root_layout.addLayout(body)

        shell = QScrollArea()
        shell.setWidgetResizable(True)
        content = QWidget()
        content.setLayout(root_layout)
        shell.setWidget(content)
        self.setCentralWidget(shell)

        self.apply_styles()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(15000)
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.refresh_timer.start()

        self.refresh_all()

    def build_hero(self):
        card = Card()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        icon_box = QLabel("CPU")
        icon_box.setObjectName("heroIcon")
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setFixedSize(52, 52)
        layout.addWidget(icon_box, 0, Qt.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        self.hero_status = QLabel("Server Online")
        self.hero_status.setObjectName("heroStatus")
        self.hero_title = QLabel("DevBoard Server")
        self.hero_title.setObjectName("heroTitle")
        self.hero_subtitle = QLabel("本地 Qt 控制台")
        self.hero_subtitle.setObjectName("heroSubtitle")
        text_col.addWidget(self.hero_status)
        text_col.addWidget(self.hero_title)
        text_col.addWidget(self.hero_subtitle)
        layout.addLayout(text_col)
        layout.addStretch(1)

        self.auth_badge = QLabel("未检测")
        self.auth_badge.setObjectName("badge")
        layout.addWidget(self.auth_badge, 0, Qt.AlignTop)
        return card

    def build_network_card(self):
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        self.net_title = QLabel("wlan0 / Tunnel")
        self.net_title.setObjectName("smallTitle")
        self.net_value = QLabel("检测中")
        self.net_value.setObjectName("ipValue")
        self.net_status = QLabel("等待刷新")
        self.net_status.setObjectName("smallMuted")

        layout.addWidget(self.net_title)
        layout.addStretch(1)
        layout.addWidget(self.net_value)
        layout.addWidget(self.net_status)
        return card

    def build_direct_card(self):
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        self.direct_title = QLabel("eth0 / Direct")
        self.direct_title.setObjectName("smallTitle")
        self.direct_value = QLabel("192.168.50.1")
        self.direct_value.setObjectName("ipValue")
        self.direct_status = QLabel("Windows 直连链路")
        self.direct_status.setObjectName("smallMuted")

        layout.addWidget(self.direct_title)
        layout.addStretch(1)
        layout.addWidget(self.direct_value)
        layout.addWidget(self.direct_status)
        return card

    def build_arch_card(self):
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Web Architecture")
        title.setObjectName("sectionTitle")
        self.arch_value = QLabel("Nginx Gateway")
        self.arch_value.setObjectName("archValue")

        self.arch_front = InfoRow("Frontend", "Port 80")
        self.arch_api = InfoRow("Flask API", "检测中", value_style="strong")
        self.arch_qt = InfoRow("PyQt5 UI", "LOCAL")

        layout.addWidget(title)
        layout.addWidget(self.arch_value)
        layout.addWidget(self.arch_front)
        layout.addWidget(self.arch_api)
        layout.addWidget(self.arch_qt)
        layout.addStretch(1)
        return card

    def build_actions_card(self):
        card = Card()
        layout = QGridLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        wake = QuickActionButton("W", "WOL 唤醒", "向工作站发送网络唤醒", "orange")
        shutdown = QuickActionButton("P", "SSH 关机", "通过后端执行远程关机", "red")
        refresh = QuickActionButton("R", "刷新状态", "重新读取系统状态与在线状态", "gray")
        sync = QuickActionButton("S", "同步状态", "刷新 Syncthing 当前结果", "blue")

        wake.clicked.connect(self.wake_pc)
        shutdown.clicked.connect(self.shutdown_pc)
        refresh.clicked.connect(self.refresh_all)
        sync.clicked.connect(self.load_sync)

        layout.addWidget(wake, 0, 0)
        layout.addWidget(shutdown, 0, 1)
        layout.addWidget(refresh, 1, 0)
        layout.addWidget(sync, 1, 1)
        return card

    def build_storage_card(self):
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Storage Sync")
        title.setObjectName("sectionTitle")
        path_label = QLabel("/userdata/files")
        path_label.setObjectName("pathLabel")

        self.sync_row = InfoRow("Syncthing", "检测中", value_style="strong")
        self.obsidian_row = InfoRow("Obsidian", "同步目录", value_style="strong")

        self.raw_panel = QTextEdit()
        self.raw_panel.setReadOnly(True)
        self.raw_panel.setMinimumHeight(90)
        self.raw_panel.setObjectName("rawPanel")

        layout.addWidget(title)
        layout.addWidget(path_label)
        layout.addWidget(self.sync_row)
        layout.addWidget(self.obsidian_row)
        layout.addWidget(self.raw_panel)
        return card

    def apply_styles(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #F2F2F7;
                color: #1C1C1E;
                font-family: "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif;
                font-size: 14px;
            }
            QScrollArea {
                border: 0;
                background: transparent;
            }
            QFrame#card {
                background: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.04);
                border-radius: 28px;
            }
            #heroIcon {
                background: rgba(0, 0, 0, 0.05);
                border-radius: 14px;
                font-size: 15px;
                font-weight: 700;
                color: #1C1C1E;
            }
            #heroStatus {
                color: #34C759;
                font-size: 14px;
                font-weight: 700;
            }
            #heroTitle {
                font-size: 34px;
                font-weight: 800;
                letter-spacing: 0;
            }
            #heroSubtitle {
                color: #8E8E93;
                font-size: 15px;
            }
            #badge {
                padding: 8px 14px;
                background: #F2F2F7;
                border-radius: 12px;
                color: #1C1C1E;
                font-size: 13px;
                font-weight: 600;
            }
            #smallTitle {
                color: #8E8E93;
                font-size: 13px;
                font-weight: 700;
                text-transform: uppercase;
            }
            #ipValue {
                font-size: 28px;
                font-weight: 800;
            }
            #smallMuted {
                color: #8E8E93;
                font-size: 13px;
            }
            #sectionTitle {
                color: #8E8E93;
                font-size: 13px;
                font-weight: 700;
                text-transform: uppercase;
            }
            #archValue {
                font-size: 24px;
                font-weight: 800;
            }
            #rowLabel {
                font-size: 14px;
                font-weight: 600;
                color: #1C1C1E;
            }
            #rowValue {
                font-size: 13px;
                font-weight: 700;
                color: #1C1C1E;
            }
            #rowMuted {
                font-size: 13px;
                font-weight: 600;
                color: #8E8E93;
            }
            #pathLabel {
                color: #8E8E93;
                font-size: 13px;
                font-family: Consolas, monospace;
            }
            QTextEdit#rawPanel {
                border: 0;
                border-radius: 14px;
                background: #F2F2F7;
                padding: 12px;
                color: #1C1C1E;
            }
            QPushButton {
                border: 0;
                border-radius: 20px;
                text-align: left;
            }
            QPushButton#quick-orange {
                background: #FFF4E5;
                color: #FF9500;
            }
            QPushButton#quick-red {
                background: #FFE9E8;
                color: #FF3B30;
            }
            QPushButton#quick-blue {
                background: #E5F1FF;
                color: #007AFF;
            }
            QPushButton#quick-gray {
                background: #F2F2F7;
                color: #1C1C1E;
            }
            QPushButton#quick-orange:pressed,
            QPushButton#quick-red:pressed,
            QPushButton#quick-blue:pressed,
            QPushButton#quick-gray:pressed {
                background: #E9E9EE;
            }
            #quickIcon {
                background: rgba(255, 255, 255, 0.75);
                border-radius: 12px;
                font-size: 15px;
                font-weight: 800;
            }
            #quickTitle {
                font-size: 16px;
                font-weight: 800;
                color: #1C1C1E;
            }
            #quickSubtitle {
                font-size: 12px;
                color: #6E6E73;
            }
            """
        )

    def notify(self, text):
        QMessageBox.information(self, "提示", text)

    def error(self, text):
        QMessageBox.warning(self, "错误", text)

    def safe_json(self, data):
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return str(data)

    def short_service_status(self, service):
        try:
            result = subprocess.run(
                f"systemctl is-active {service}",
                shell=True,
                text=True,
                capture_output=True,
                timeout=2,
            )
            status = result.stdout.strip()
            return "ACTIVE" if status == "active" else (status or "unknown").upper()
        except Exception:
            return "UNKNOWN"

    def read_online_status(self, data):
        if not isinstance(data, dict):
            return None
        for key in ("online", "oline", "ssh_online", "reachable", "is_online", "connected"):
            value = data.get(key)
            if isinstance(value, bool):
                return value
        for key in ("data", "device", "workstation", "result"):
            nested = data.get(key)
            if isinstance(nested, dict):
                nested_value = self.read_online_status(nested)
                if nested_value is not None:
                    return nested_value
        text = self.safe_json(data)
        if any(token in text for token in ("在线", "可达", "成功", "SSH在线")):
            return True
        if any(token in text for token in ("离线", "不可达", "失败", "SSH离线")):
            return False
        return None

    def refresh_all(self):
        self.load_auth()
        self.load_network()
        self.load_device()
        self.load_sync()

    def load_auth(self):
        try:
            auth = self.api.auth_status()
            self.state["auth"] = auth
            if auth.get("authenticated"):
                username = auth.get("username") or "已登录"
                self.auth_badge.setText(username)
            else:
                self.auth_badge.setText("未登录")
        except Exception:
            self.auth_badge.setText("认证未知")

    def load_network(self):
        self.net_value.setText("127.0.0.1 / Tunnel")
        self.net_status.setText(f"Nginx {self.short_service_status('nginx')} · Flask {self.short_service_status('filemgr')}")
        self.direct_value.setText("192.168.50.1")
        self.direct_status.setText("eth0-direct " + self.short_service_status("eth0-direct"))
        self.arch_api.set_value(self.short_service_status("filemgr"), strong=True)

    def load_device(self):
        try:
            device = self.api.workstation()
            status = self.api.workstation_status()
            self.state["device"] = device
            self.state["device_status"] = status

            online = self.read_online_status(status)
            if online is True:
                self.hero_status.setText("Server Online")
                self.hero_status.setStyleSheet("color: #34C759;")
            elif online is False:
                self.hero_status.setText("Workstation Offline")
                self.hero_status.setStyleSheet("color: #FF3B30;")
            else:
                self.hero_status.setText("Status Unknown")
                self.hero_status.setStyleSheet("color: #FF9500;")
        except Exception as exc:
            self.hero_status.setText("Device API Error")
            self.hero_status.setStyleSheet("color: #FF3B30;")
            self.raw_panel.setPlainText(str(exc))

    def load_sync(self):
        try:
            data = self.api.sync_status()
            self.state["sync"] = data
            if isinstance(data, dict):
                sync_text = str(data.get("status") or data.get("state") or "已读取")
                self.sync_row.set_value(sync_text, strong=True)
            else:
                self.sync_row.set_value(str(data), strong=True)
            self.raw_panel.setPlainText(self.safe_json(data))
        except Exception as exc:
            self.sync_row.set_value("读取失败", strong=True)
            self.raw_panel.setPlainText(str(exc))

    def wake_pc(self):
        if QMessageBox.question(self, "确认", "确认唤醒电脑吗？") != QMessageBox.Yes:
            return
        try:
            self.api.wake()
            self.notify("唤醒命令已发送")
            QTimer.singleShot(1200, self.load_device)
        except Exception as exc:
            self.error(str(exc))

    def shutdown_pc(self):
        if QMessageBox.question(self, "确认", "确认关闭电脑吗？") != QMessageBox.Yes:
            return
        try:
            self.api.shutdown()
            self.notify("关机命令已发送")
            QTimer.singleShot(1200, self.load_device)
        except Exception as exc:
            self.error(str(exc))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)
    window = MainWindow()
    window.showFullScreen()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
