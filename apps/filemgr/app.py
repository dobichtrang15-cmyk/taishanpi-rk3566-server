from functools import wraps
from pathlib import Path
import copy
import json
import mimetypes
import re
import secrets
import socket
import subprocess
import shutil
import tempfile
import urllib.error
import urllib.request
from urllib.parse import quote

from flask import Flask, after_this_request, jsonify, request, send_file, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    import paramiko
except ImportError:
    paramiko = None

app = Flask(__name__)

# Restrict file operations to this directory only.
APP_DIR = Path(__file__).resolve().parent
ROOT = Path("/userdata/files").resolve()
USERS_FILE = APP_DIR / "users.json"
SECRET_FILE = APP_DIR / "secret.key"
DEVICES_FILE = APP_DIR / "devices.json"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MAC_RE = re.compile(r"^[0-9A-Fa-f]{12}$")
SYNCTHING_SERVICE = "syncthing@lckfb"
SYNCTHING_GUI_URL = "http://192.168.50.1:8384"
SYNCTHING_API_URL = "http://127.0.0.1:8384"
SYNCTHING_FOLDER_ID = "obsidian-vault"
SYNCTHING_FOLDER_PATH = Path("/userdata/files/obsidian-vault")
SYNCTHING_CONFIG_CANDIDATES = [
    Path("/home/lckfb/.local/state/syncthing/config.xml"),
    Path("/home/lckfb/.config/syncthing/config.xml"),
]
PERMISSION_PROFILES = {
    "viewer": ["list", "download"],
    "editor": ["list", "download", "upload", "mkdir", "delete"],
    "admin": ["list", "download", "upload", "mkdir", "delete", "manage_users", "device_control"],
}
ACCEL_REQUEST_HEADER = "X-Filemgr-Accel-Redirect"
ACCEL_INTERNAL_PREFIX = "/_filemgr_internal"
DEFAULT_DEVICES = {
    "workstation": {
        "name": "主研发工作站",
        "host": "",
        "mac": "",
        "broadcast": "255.255.255.255",
        "ssh_user": "",
        "ssh_password": "",
        "ssh_port": 22,
        "shutdown_command": "shutdown /s /t 0",
    }
}


def ensure_root():
    ROOT.mkdir(parents=True, exist_ok=True)


def ensure_secret_key():
    if SECRET_FILE.exists():
        app.secret_key = SECRET_FILE.read_text(encoding="utf-8").strip()
        return

    secret = secrets.token_hex(32)
    SECRET_FILE.write_text(secret, encoding="utf-8")
    app.secret_key = secret


def ensure_users():
    if USERS_FILE.exists():
        return

    default_users = {
        "admin": {
            "password_hash": generate_password_hash("112233"),
            "role": "admin",
            "permissions": PERMISSION_PROFILES["admin"],
        }
    }
    USERS_FILE.write_text(
        json.dumps(default_users, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def ensure_devices():
    if DEVICES_FILE.exists():
        return
    DEVICES_FILE.write_text(
        json.dumps(DEFAULT_DEVICES, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def load_users():
    ensure_users()
    with USERS_FILE.open("r", encoding="utf-8") as f:
        raw_users = json.load(f)

    users = {}
    changed = False
    for username, user in raw_users.items():
        role = user.get("role", "viewer")
        if role not in PERMISSION_PROFILES:
            role = "viewer"
            changed = True
        permissions = user.get("permissions") or PERMISSION_PROFILES[role]
        permissions = sorted({p for p in permissions if p in {x for xs in PERMISSION_PROFILES.values() for x in xs}})
        normalized = {
            "password_hash": user["password_hash"],
            "role": role,
            "permissions": permissions or PERMISSION_PROFILES[role],
        }
        if normalized != user:
            changed = True
        users[username] = normalized

    if changed:
        save_users(users)
    return users


def save_users(users):
    USERS_FILE.write_text(
        json.dumps(users, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def normalize_mac(mac: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", (mac or "").strip()).upper()
    if not cleaned:
        return ""
    if not MAC_RE.fullmatch(cleaned):
        raise ValueError("invalid mac")
    return ":".join(cleaned[i:i + 2] for i in range(0, 12, 2))


def normalize_device(device: dict) -> dict:
    return {
        "name": (device.get("name") or "主研发工作站").strip(),
        "host": (device.get("host") or "").strip(),
        "mac": normalize_mac(device.get("mac") or ""),
        "broadcast": (device.get("broadcast") or "255.255.255.255").strip(),
        "ssh_user": (device.get("ssh_user") or "").strip(),
        "ssh_password": str(device.get("ssh_password") or ""),
        "ssh_port": int(device.get("ssh_port") or 22),
        "shutdown_command": (device.get("shutdown_command") or "shutdown /s /t 0").strip(),
    }


def load_devices():
    ensure_devices()
    with DEVICES_FILE.open("r", encoding="utf-8") as f:
        raw_devices = json.load(f)
    devices = {}
    changed = False
    for key, value in DEFAULT_DEVICES.items():
        current = raw_devices.get(key, value)
        normalized = normalize_device(current)
        devices[key] = normalized
        if current != normalized:
            changed = True
    if changed:
        save_devices(devices)
    return devices


def save_devices(devices):
    DEVICES_FILE.write_text(
        json.dumps(devices, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def get_device(name="workstation"):
    devices = load_devices()
    return devices, devices[name]


def device_status(device: dict) -> dict:
    host = device.get("host", "").strip()
    if not host:
        return {"configured": False, "online": False, "message": "未配置主机地址"}
    port = int(device.get("ssh_port") or 22)
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
        online = True
    except OSError:
        online = False
    return {
        "configured": True,
        "online": online,
        "message": f"SSH 在线({host}:{port})" if online else f"SSH 离线({host}:{port})",
    }


def send_magic_packet(mac: str, broadcast: str):
    normalized = normalize_mac(mac).replace(":", "")
    payload = bytes.fromhex("FF" * 6 + normalized * 16)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(payload, (broadcast or "255.255.255.255", 9))
        sock.sendto(payload, (broadcast or "255.255.255.255", 7))
    finally:
        sock.close()


def run_remote_shutdown(device: dict):
    host = device.get("host", "").strip()
    user = device.get("ssh_user", "").strip()
    password = str(device.get("ssh_password") or "")
    command = device.get("shutdown_command", "").strip()
    port = int(device.get("ssh_port") or 22)
    if not host or not user or not command:
        raise ValueError("device shutdown config incomplete")
    if password:
        if paramiko is None:
            raise RuntimeError("password ssh requires python3-paramiko")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                look_for_keys=False,
                allow_agent=False,
                timeout=8,
                auth_timeout=8,
                banner_timeout=8,
            )
            _stdin, stdout, stderr = client.exec_command(command, timeout=15)
            exit_status = stdout.channel.recv_exit_status()
            output = (stdout.read() + stderr.read()).decode("utf-8", errors="ignore").strip()
            if exit_status != 0:
                raise RuntimeError(output or f"ssh shutdown failed with code {exit_status}")
            return
        except Exception as error:
            raise RuntimeError(str(error))
        finally:
            client.close()
    result = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "ConnectTimeout=8",
            "-p",
            str(port),
            f"{user}@{host}",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "ssh shutdown failed").strip()
        raise RuntimeError(detail)


def run_command(args, timeout=8):
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def systemctl_value(*args) -> str:
    result = run_command(["systemctl", *args, SYNCTHING_SERVICE], timeout=5)
    return (result.stdout or result.stderr or "").strip()


def syncthing_config_path():
    for path in SYNCTHING_CONFIG_CANDIDATES:
        if path.exists():
            return path
    return None


def syncthing_listen_address() -> str:
    config_path = syncthing_config_path()
    if not config_path:
        return ""
    try:
        text = config_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    match = re.search(r"<gui[^>]*>.*?<address>(.*?)</address>", text, re.S)
    return match.group(1).strip() if match else ""


def syncthing_port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8384), timeout=1.5):
            return True
    except OSError:
        return False


def syncthing_version() -> str:
    try:
        result = run_command(["syncthing", "--version"], timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip().splitlines()[0]


def syncthing_status() -> dict:
    active = systemctl_value("is-active")
    enabled = systemctl_value("is-enabled")
    config_path = syncthing_config_path()
    port_open = syncthing_port_open()
    running = active == "active"
    return {
        "service": SYNCTHING_SERVICE,
        "running": running,
        "active": active,
        "enabled": enabled,
        "gui_reachable": port_open,
        "gui_url": SYNCTHING_GUI_URL,
        "local_url": "http://127.0.0.1:8384",
        "listen_address": syncthing_listen_address(),
        "config_path": str(config_path) if config_path else "",
        "version": syncthing_version(),
        "message": "Syncthing 正在运行" if running and port_open else "Syncthing 未就绪",
    }


def syncthing_api_key() -> str:
    config_path = syncthing_config_path()
    if not config_path:
        return ""
    try:
        text = config_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    match = re.search(r"<apikey>(.*?)</apikey>", text, re.S)
    return match.group(1).strip() if match else ""


def syncthing_api(path: str, method="GET", payload=None, timeout=8):
    api_key = syncthing_api_key()
    if not api_key:
        raise RuntimeError("syncthing api key not found")
    data = None
    headers = {"X-API-Key": api_key}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request_obj = urllib.request.Request(
        f"{SYNCTHING_API_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=timeout) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore").strip()
        raise RuntimeError(detail or f"syncthing api failed with {error.code}")
    except urllib.error.URLError as error:
        raise RuntimeError(str(error.reason))
    if not body:
        return None
    text = body.decode("utf-8", errors="ignore")
    if "application/json" in content_type:
        return json.loads(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def syncthing_conflicts(limit=20):
    if not SYNCTHING_FOLDER_PATH.exists():
        return []
    matches = []
    for path in SYNCTHING_FOLDER_PATH.rglob("*sync-conflict*"):
        if len(matches) >= limit:
            break
        try:
            rel = "/" + str(path.relative_to(SYNCTHING_FOLDER_PATH)).replace("\\", "/")
            stat = path.stat()
        except OSError:
            continue
        matches.append({"path": rel, "size": stat.st_size, "mtime": int(stat.st_mtime)})
    return matches


def syncthing_overview() -> dict:
    status = syncthing_status()
    if not status["gui_reachable"]:
        return {"status": status, "folder": None, "devices": [], "conflicts": []}
    system_status = syncthing_api("/rest/system/status")
    connections = syncthing_api("/rest/system/connections")
    config = syncthing_api("/rest/config")
    folder_status = None
    try:
        folder_status = syncthing_api(f"/rest/db/status?folder={quote(SYNCTHING_FOLDER_ID)}")
    except RuntimeError:
        folder_status = None
    my_id = system_status.get("myID", "")
    connection_map = connections.get("connections", {})
    devices = []
    for device in config.get("devices", []):
        device_id = device.get("deviceID", "")
        if not device_id or device_id == my_id:
            continue
        conn = connection_map.get(device_id, {})
        devices.append(
            {
                "deviceID": device_id,
                "name": device.get("name") or device_id[:7],
                "connected": bool(conn.get("connected")),
                "paused": bool(device.get("paused")),
                "address": conn.get("address", ""),
                "clientVersion": conn.get("clientVersion", ""),
            }
        )
    return {
        "status": status,
        "myID": my_id,
        "folder": folder_status,
        "devices": devices,
        "conflicts": syncthing_conflicts(),
    }


def default_syncthing_device(config: dict, device_id: str, name: str) -> dict:
    template = copy.deepcopy((config.get("devices") or [{}])[0])
    template.update(
        {
            "deviceID": device_id,
            "name": name or device_id[:7],
            "addresses": ["dynamic"],
            "compression": "metadata",
            "certName": "",
            "introducer": False,
            "skipIntroductionRemovals": False,
            "introducedBy": "",
            "paused": False,
            "allowedNetworks": [],
            "autoAcceptFolders": False,
            "maxSendKbps": 0,
            "maxRecvKbps": 0,
            "ignoredFolders": [],
        }
    )
    return template


def add_syncthing_device(device_id: str, name: str, share_obsidian=True):
    device_id = (device_id or "").strip().upper()
    name = (name or "").strip()
    if len(device_id) < 40 or not re.fullmatch(r"[A-Z0-9-]+", device_id):
        raise ValueError("invalid syncthing device id")
    config = syncthing_api("/rest/config")
    devices = config.setdefault("devices", [])
    if not any(item.get("deviceID") == device_id for item in devices):
        devices.append(default_syncthing_device(config, device_id, name))
    if share_obsidian:
        for folder in config.get("folders", []):
            if folder.get("id") != SYNCTHING_FOLDER_ID:
                continue
            folder_devices = folder.setdefault("devices", [])
            if not any(item.get("deviceID") == device_id for item in folder_devices):
                template = copy.deepcopy((folder_devices or [{"introducedBy": "", "encryptionPassword": ""}])[0])
                template["deviceID"] = device_id
                template["introducedBy"] = ""
                template["encryptionPassword"] = ""
                folder_devices.append(template)
            break
    syncthing_api("/rest/config", method="PUT", payload=config, timeout=15)
    return syncthing_overview()


def valid_username(username: str) -> bool:
    return bool(USERNAME_RE.fullmatch((username or "").strip()))


def set_session_user(username: str, user: dict):
    session["username"] = username
    session["role"] = user.get("role", "viewer")
    session["permissions"] = user.get("permissions") or PERMISSION_PROFILES[session["role"]]


def current_permissions():
    return session.get("permissions") or PERMISSION_PROFILES.get(session.get("role", "viewer"), [])


def permission_required(permission: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not session.get("username"):
                return jsonify({"error": "auth required"}), 401
            if permission not in current_permissions():
                return jsonify({"error": "permission denied"}), 403
            return func(*args, **kwargs)

        return wrapper

    return decorator


def admin_count(users: dict) -> int:
    return sum(1 for user in users.values() if user.get("role") == "admin")


def safe_path(rel_path: str = "/") -> Path:
    rel_path = (rel_path or "/").strip().lstrip("/")
    target = (ROOT / rel_path).resolve()
    if target != ROOT and ROOT not in target.parents:
        raise ValueError("invalid path")
    return target


def safe_relative_path(rel_path: str) -> Path:
    parts = []
    for raw_part in Path(rel_path).parts:
        if raw_part in ("", ".", "..", "/"):
            continue
        safe_part = secure_filename(raw_part)
        if safe_part:
            parts.append(safe_part)
    if not parts:
        raise ValueError("invalid relative path")
    return Path(*parts)


def file_type(path: Path) -> str:
    if path.is_dir():
        return "Folder"
    ext = path.suffix.lower()
    mapping = {
        ".pdf": "PDF",
        ".doc": "Word",
        ".docx": "Word",
        ".xls": "Excel",
        ".xlsx": "Excel",
        ".jpg": "Image",
        ".jpeg": "Image",
        ".png": "Image",
        ".gif": "Image",
        ".txt": "Text",
        ".md": "Markdown",
        ".mp4": "Video",
        ".mov": "Video",
        ".zip": "Archive",
    }
    return mapping.get(ext, "File")


def finalize_file_response(response):
    response.headers.setdefault("Accept-Ranges", "bytes")
    response.headers.setdefault("X-Accel-Buffering", "no")
    response.headers["Cache-Control"] = "private, no-cache, no-store, max-age=0"
    return response


def build_content_disposition(filename: str, as_attachment: bool) -> str:
    ascii_name = secure_filename(filename) or "download"
    encoded = quote(filename, safe="")
    mode = "attachment" if as_attachment else "inline"
    return f"{mode}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


def accel_enabled(path: Path) -> bool:
    if request.headers.get(ACCEL_REQUEST_HEADER, "").lower() != "on":
        return False
    return path == ROOT or ROOT in path.parents


def send_via_accel(path: Path, filename: str, as_attachment: bool, mimetype: str = None):
    relative = path.relative_to(ROOT).as_posix()
    response = app.response_class()
    response.headers["X-Accel-Redirect"] = f"{ACCEL_INTERNAL_PREFIX}/{quote(relative)}"
    response.headers["Content-Disposition"] = build_content_disposition(filename, as_attachment)
    if mimetype:
        response.headers["Content-Type"] = mimetype
    response.headers["Content-Length"] = str(path.stat().st_size)
    return finalize_file_response(response)


def send_attachment(path: Path, download_name: str = None):
    filename = download_name or path.name
    if accel_enabled(path):
        return send_via_accel(path, filename, True)
    try:
        response = send_file(path, as_attachment=True, download_name=filename, conditional=True)
    except TypeError:
        response = send_file(path, as_attachment=True, attachment_filename=filename, conditional=True)
    return finalize_file_response(response)


def send_inline(path: Path):
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if accel_enabled(path):
        return send_via_accel(path, path.name, False, mime)
    try:
        response = send_file(path, as_attachment=False, download_name=path.name, mimetype=mime, conditional=True)
    except TypeError:
        response = send_file(path, as_attachment=False, attachment_filename=path.name, mimetype=mime, conditional=True)
    return finalize_file_response(response)


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("username"):
            return jsonify({"error": "auth required"}), 401
        return func(*args, **kwargs)

    return wrapper


@app.errorhandler(ValueError)
def handle_value_error(_error):
    return jsonify({"error": "invalid path"}), 400


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    username = session.get("username")
    if not username:
        return jsonify({"authenticated": False, "username": None, "role": None, "permissions": []})

    users = load_users()
    user = users.get(username)
    if not user:
        session.clear()
        return jsonify({"authenticated": False, "username": None, "role": None, "permissions": []})

    set_session_user(username, user)
    return jsonify(
        {
            "authenticated": True,
            "username": username,
            "role": user.get("role", "viewer"),
            "permissions": user.get("permissions", []),
        }
    )


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    users = load_users()
    user = users.get(username)
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401

    set_session_user(username, user)
    return jsonify(
        {
            "ok": True,
            "username": username,
            "role": user.get("role", "viewer"),
            "permissions": user.get("permissions", []),
        }
    )


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/account", methods=["POST"])
@login_required
def update_account():
    data = request.get_json(force=True, silent=True) or {}
    new_username = (data.get("new_username") or "").strip()
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""
    target_username = session.get("username")

    username = session.get("username")
    users = load_users()
    user = users.get(username)
    if not user or not check_password_hash(user["password_hash"], current_password):
        return jsonify({"error": "current password is incorrect"}), 400

    if new_username:
        if not valid_username(new_username):
            return jsonify({"error": "username must be 3-32 characters: letters, numbers, _, ., -"}), 400
        if new_username != username and new_username in users:
            return jsonify({"error": "username already exists"}), 409
        target_username = new_username

    if new_password:
        if len(new_password) < 6:
            return jsonify({"error": "new password must be at least 6 characters"}), 400
        user["password_hash"] = generate_password_hash(new_password)

    if target_username != username:
        users[target_username] = user
        del users[username]
    else:
        users[username] = user

    save_users(users)
    set_session_user(target_username, user)
    return jsonify(
        {
            "ok": True,
            "username": target_username,
            "role": user.get("role", "viewer"),
            "permissions": user.get("permissions", []),
        }
    )


@app.route("/api/change-password", methods=["POST"])
@login_required
def change_password_compat():
    return update_account()


@app.route("/api/users", methods=["GET"])
@permission_required("manage_users")
def list_users():
    users = load_users()
    rows = []
    for username, user in sorted(users.items(), key=lambda item: item[0].lower()):
        rows.append(
            {
                "username": username,
                "role": user.get("role", "viewer"),
                "permissions": user.get("permissions", []),
            }
        )
    return jsonify({"items": rows})


@app.route("/api/users", methods=["POST"])
@permission_required("manage_users")
def create_user():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = (data.get("role") or "viewer").strip()

    if role not in PERMISSION_PROFILES:
        return jsonify({"error": "invalid role"}), 400
    if not valid_username(username):
        return jsonify({"error": "username must be 3-32 characters: letters, numbers, _, ., -"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    users = load_users()
    if username in users:
        return jsonify({"error": "username already exists"}), 409

    users[username] = {
        "password_hash": generate_password_hash(password),
        "role": role,
        "permissions": PERMISSION_PROFILES[role],
    }
    save_users(users)
    return jsonify({"ok": True})


@app.route("/api/users/<username>", methods=["PATCH"])
@permission_required("manage_users")
def update_user(username):
    users = load_users()
    user = users.get(username)
    if not user:
        return jsonify({"error": "user not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    new_username = (data.get("new_username") or "").strip()
    new_password = data.get("new_password") or ""
    role = (data.get("role") or user.get("role", "viewer")).strip()

    if role not in PERMISSION_PROFILES:
        return jsonify({"error": "invalid role"}), 400
    if new_username:
        if not valid_username(new_username):
            return jsonify({"error": "username must be 3-32 characters: letters, numbers, _, ., -"}), 400
        if new_username != username and new_username in users:
            return jsonify({"error": "username already exists"}), 409
    else:
        new_username = username

    if user.get("role") == "admin" and role != "admin" and admin_count(users) <= 1:
        return jsonify({"error": "at least one admin account must remain"}), 400
    if new_password and len(new_password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    user["role"] = role
    user["permissions"] = PERMISSION_PROFILES[role]
    if new_password:
        user["password_hash"] = generate_password_hash(new_password)

    if new_username != username:
        users[new_username] = user
        del users[username]
    else:
        users[username] = user

    save_users(users)
    if session.get("username") == username:
        set_session_user(new_username, user)
    return jsonify({"ok": True})


@app.route("/api/users/<username>", methods=["DELETE"])
@permission_required("manage_users")
def delete_user(username):
    users = load_users()
    user = users.get(username)
    if not user:
        return jsonify({"error": "user not found"}), 404
    if username == session.get("username"):
        return jsonify({"error": "cannot delete current user"}), 400
    if user.get("role") == "admin" and admin_count(users) <= 1:
        return jsonify({"error": "at least one admin account must remain"}), 400

    del users[username]
    save_users(users)
    return jsonify({"ok": True})


@app.route("/api/device/workstation", methods=["GET"])
@permission_required("device_control")
def get_workstation():
    _devices, device = get_device()
    return jsonify({"item": device, "status": device_status(device)})


@app.route("/api/device/workstation", methods=["POST"])
@permission_required("device_control")
def save_workstation():
    data = request.get_json(force=True, silent=True) or {}
    devices, _device = get_device()
    updated = normalize_device(
        {
            "name": data.get("name"),
            "host": data.get("host"),
            "mac": data.get("mac"),
            "broadcast": data.get("broadcast"),
            "ssh_user": data.get("ssh_user"),
            "ssh_password": data.get("ssh_password"),
            "ssh_port": data.get("ssh_port"),
            "shutdown_command": data.get("shutdown_command"),
        }
    )
    devices["workstation"] = updated
    save_devices(devices)
    return jsonify({"ok": True, "item": updated, "status": device_status(updated)})


@app.route("/api/device/workstation/status", methods=["GET"])
@permission_required("device_control")
def workstation_status():
    _devices, device = get_device()
    return jsonify({"status": device_status(device)})


@app.route("/api/device/workstation/wake", methods=["POST"])
@permission_required("device_control")
def workstation_wake():
    _devices, device = get_device()
    if not device.get("mac"):
        return jsonify({"error": "device mac not configured"}), 400
    send_magic_packet(device["mac"], device.get("broadcast") or "255.255.255.255")
    return jsonify({"ok": True, "message": f"已向 {device['name']} 发送网络唤醒包"})


@app.route("/api/device/workstation/shutdown", methods=["POST"])
@permission_required("device_control")
def workstation_shutdown():
    _devices, device = get_device()
    try:
        run_remote_shutdown(device)
    except ValueError as error:
        app.logger.error("workstation shutdown config error: %s", error)
        return jsonify({"error": str(error)}), 400
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        app.logger.exception("workstation shutdown failed")
        return jsonify({"error": str(error)}), 500
    return jsonify({"ok": True, "message": f"已向 {device['name']} 发送关机命令"})


@app.route("/api/syncthing/status", methods=["GET"])
@permission_required("device_control")
def get_syncthing_status():
    try:
        return jsonify(syncthing_overview())
    except RuntimeError as error:
        return jsonify({"status": syncthing_status(), "folder": None, "devices": [], "conflicts": [], "error": str(error)})


@app.route("/api/syncthing/<action>", methods=["POST"])
@permission_required("device_control")
def control_syncthing(action):
    if action not in {"start", "stop", "restart"}:
        return jsonify({"error": "unsupported syncthing action"}), 400
    try:
        result = run_command(["sudo", "-n", "systemctl", action, SYNCTHING_SERVICE], timeout=20)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "systemctl command timed out"}), 500
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "systemctl command failed").strip()
        return jsonify({"error": detail}), 500
    return jsonify({"ok": True, "action": action, "status": syncthing_status()})


@app.route("/api/syncthing/logs", methods=["GET"])
@permission_required("device_control")
def syncthing_logs():
    try:
        result = run_command(["journalctl", "-u", SYNCTHING_SERVICE, "-n", "80", "--no-pager"], timeout=10)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "journalctl command timed out"}), 500
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "journalctl command failed").strip()
        return jsonify({"error": detail}), 500
    return jsonify({"logs": result.stdout or ""})


@app.route("/api/syncthing/devices", methods=["POST"])
@permission_required("device_control")
def create_syncthing_device():
    data = request.get_json(force=True, silent=True) or {}
    try:
        overview = add_syncthing_device(
            data.get("device_id") or data.get("deviceID"),
            data.get("name") or "",
            bool(data.get("share_obsidian", True)),
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 500
    return jsonify({"ok": True, **overview})


@app.route("/api/files", methods=["GET"])
@permission_required("list")
def list_files():
    ensure_root()
    path = safe_path(request.args.get("path", "/"))
    if not path.exists():
        return jsonify({"error": "path not found"}), 404
    if not path.is_dir():
        return jsonify({"error": "target is not a folder"}), 400

    items = []
    for entry in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        stat = entry.stat()
        rel = "/" + str(entry.relative_to(ROOT)).replace("\\", "/")
        items.append(
            {
                "name": entry.name,
                "path": rel,
                "is_dir": entry.is_dir(),
                "size": 0 if entry.is_dir() else stat.st_size,
                "mtime": int(stat.st_mtime),
                "type": file_type(entry),
                "mime": mimetypes.guess_type(entry.name)[0] or "application/octet-stream",
            }
        )

    usage = shutil.disk_usage(str(ROOT))
    current = "/" if path == ROOT else "/" + str(path.relative_to(ROOT)).replace("\\", "/")
    return jsonify(
        {
            "current": current,
            "items": items,
            "storage": {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
            },
        }
    )


@app.route("/api/download", methods=["GET"])
@permission_required("download")
def download():
    path = safe_path(request.args.get("path", "/"))
    if not path.exists():
        return jsonify({"error": "file not found"}), 404

    if path.is_file():
        if (request.args.get("inline") or "").lower() in {"1", "true", "yes"}:
            return send_inline(path)
        return send_attachment(path)

    temp_dir = Path(tempfile.mkdtemp(prefix="filemgr-download-"))
    archive_base = temp_dir / secure_filename(path.name or "folder")
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=path, base_dir="."))

    @after_this_request
    def cleanup_archive(response):
        try:
            archive_path.unlink(missing_ok=True)
        except TypeError:
            if archive_path.exists():
                archive_path.unlink()
        shutil.rmtree(temp_dir, ignore_errors=True)
        return response

    return send_attachment(archive_path, f"{path.name or 'folder'}.zip")


@app.route("/api/upload", methods=["POST"])
@permission_required("upload")
def upload():
    ensure_root()
    path = safe_path(request.args.get("path", "/"))
    if not path.exists() or not path.is_dir():
        return jsonify({"error": "upload folder not found"}), 404

    files = request.files.getlist("files")
    relative_paths = request.form.getlist("relative_paths")

    if not files:
        legacy_file = request.files.get("file")
        if legacy_file is not None and legacy_file.filename:
            files = [legacy_file]
            relative_paths = [legacy_file.filename]

    if not files:
        return jsonify({"error": "missing file"}), 400

    if relative_paths and len(relative_paths) != len(files):
        return jsonify({"error": "upload payload mismatch"}), 400

    saved_paths = []
    for index, file in enumerate(files):
        original_name = relative_paths[index] if relative_paths else (file.filename or "")
        rel_target = safe_relative_path(original_name)
        target = (path / rel_target).resolve()
        if target != path and path not in target.parents:
            raise ValueError("invalid path")
        target.parent.mkdir(parents=True, exist_ok=True)
        file.save(str(target))
        saved_paths.append("/" + str(target.relative_to(ROOT)).replace("\\", "/"))

    return jsonify({"ok": True, "paths": saved_paths})


@app.route("/api/mkdir", methods=["POST"])
@permission_required("mkdir")
def mkdir():
    ensure_root()
    data = request.get_json(force=True, silent=True) or {}
    path = safe_path(data.get("path", "/"))
    if not path.exists() or not path.is_dir():
        return jsonify({"error": "target folder not found"}), 404

    name = secure_filename((data.get("name") or "").strip())
    if not name:
        return jsonify({"error": "invalid folder name"}), 400

    target = path / name
    if target.exists():
        return jsonify({"error": "folder already exists"}), 409

    target.mkdir()
    return jsonify({"ok": True})


@app.route("/api/delete", methods=["POST"])
@permission_required("delete")
def delete():
    data = request.get_json(force=True, silent=True) or {}
    path = safe_path(data.get("path", "/"))
    if path == ROOT:
        return jsonify({"error": "cannot delete root"}), 400
    if not path.exists():
        return jsonify({"error": "target not found"}), 404

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return jsonify({"ok": True})


if __name__ == "__main__":
    ensure_secret_key()
    ensure_users()
    ensure_root()
    app.run(host="127.0.0.1", port=5000, debug=False)
