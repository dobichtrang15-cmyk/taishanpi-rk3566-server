const { request, uploadFile, downloadFile } = require("./request");
const auth = require("./auth");

async function login(username, password) {
  const data = await request({
    url: "/api/login",
    method: "POST",
    data: { username, password },
  });
  if (data.token) {
    auth.setToken(data.token);
  }
  auth.setUser({
    username: data.username,
    role: data.role,
    permissions: data.permissions || [],
  });
  return data;
}

async function logout() {
  try {
    await request({ url: "/api/logout", method: "POST" });
  } finally {
    auth.clearCookie();
    auth.clearToken();
    auth.clearUser();
  }
}

function authStatus() {
  return request({ url: "/api/auth/status" });
}

function listFiles(path = "/") {
  return request({ url: `/api/files?path=${encodeURIComponent(path)}` });
}

function mkdir(path, name) {
  return request({
    url: "/api/mkdir",
    method: "POST",
    data: { path, name },
  });
}

function removePath(path) {
  return request({
    url: "/api/delete",
    method: "POST",
    data: { path },
  });
}

function uploadSingleFile(filePath, path = "/") {
  return uploadFile({ filePath, path });
}

function downloadPath(path) {
  return downloadFile({ path });
}

function getWorkstation() {
  return request({ url: "/api/device/workstation" });
}

function saveWorkstation(payload) {
  return request({
    url: "/api/device/workstation",
    method: "POST",
    data: payload,
  });
}

function getWorkstationStatus() {
  return request({ url: "/api/device/workstation/status" });
}

function wakeWorkstation() {
  return request({ url: "/api/device/workstation/wake", method: "POST" });
}

function shutdownWorkstation() {
  return request({ url: "/api/device/workstation/shutdown", method: "POST" });
}

function getSyncthingStatus() {
  return request({ url: "/api/syncthing/status" });
}

function controlSyncthing(action) {
  return request({ url: `/api/syncthing/${action}`, method: "POST" });
}

function getSyncthingLogs() {
  return request({ url: "/api/syncthing/logs" });
}

module.exports = {
  login,
  logout,
  authStatus,
  listFiles,
  mkdir,
  removePath,
  uploadSingleFile,
  downloadPath,
  getWorkstation,
  saveWorkstation,
  getWorkstationStatus,
  wakeWorkstation,
  shutdownWorkstation,
  getSyncthingStatus,
  controlSyncthing,
  getSyncthingLogs,
};
