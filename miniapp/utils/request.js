const auth = require("./auth");
const config = require("../config");

const BASE_URL = String(config.BASE_URL || "").replace(/\/$/, "");

if (!/^https:\/\//.test(BASE_URL)) {
  throw new Error("miniapp/config.js BASE_URL must be an HTTPS URL");
}

function buildHeaders(extra = {}) {
  const cookie = auth.getCookie();
  const token = auth.getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(cookie ? { Cookie: cookie } : {}),
    ...extra,
  };
}

function captureCookie(header = {}) {
  const cookie = header["Set-Cookie"] || header["set-cookie"];
  if (cookie) {
    auth.setCookie(cookie);
  }
}

function request({ url, method = "GET", data, header = {} }) {
  return new Promise((resolve, reject) => {
    const fullUrl = `${BASE_URL}${url}`;
    const startedAt = Date.now();
    wx.request({
      url: fullUrl,
      method,
      data,
      header: buildHeaders(header),
      timeout: 15000,
      success(res) {
        console.log("[miniapp] request success", {
          url: fullUrl,
          method,
          statusCode: res.statusCode,
          durationMs: Date.now() - startedAt,
        });
        captureCookie(res.header);
        if (res.statusCode === 401) {
          auth.clearCookie();
          auth.clearToken();
          auth.clearUser();
          wx.reLaunch({ url: "/pages/login/login" });
          reject(new Error("请先登录"));
          return;
        }
        if (res.statusCode >= 400) {
          reject(new Error((res.data && res.data.error) || `请求失败(${res.statusCode})`));
          return;
        }
        resolve(res.data);
      },
      fail(err) {
        console.error("[miniapp] request fail", {
          url: fullUrl,
          method,
          durationMs: Date.now() - startedAt,
          err,
        });
        reject(new Error(err.errMsg || "网络请求失败"));
      },
    });
  });
}

function uploadFile({ filePath, path = "/", relativePath = "" }) {
  return new Promise((resolve, reject) => {
    const fullUrl = `${BASE_URL}/api/upload?path=${encodeURIComponent(path)}`;
    const startedAt = Date.now();
    wx.uploadFile({
      url: fullUrl,
      filePath,
      name: "files",
      formData: {
        relative_paths: relativePath || filePath.split("/").pop(),
      },
      header: {
        ...(auth.getToken() ? { Authorization: `Bearer ${auth.getToken()}` } : {}),
        ...(auth.getCookie() ? { Cookie: auth.getCookie() } : {}),
      },
      timeout: 20000,
      success(res) {
        console.log("[miniapp] upload success", {
          url: fullUrl,
          statusCode: res.statusCode,
          durationMs: Date.now() - startedAt,
        });
        let data = {};
        try {
          data = JSON.parse(res.data || "{}");
        } catch (_e) {
          data = {};
        }
        if (res.statusCode >= 400) {
          reject(new Error(data.error || `上传失败(${res.statusCode})`));
          return;
        }
        resolve(data);
      },
      fail(err) {
        console.error("[miniapp] upload fail", {
          url: fullUrl,
          durationMs: Date.now() - startedAt,
          err,
        });
        reject(new Error(err.errMsg || "上传失败"));
      },
    });
  });
}

function downloadFile({ path }) {
  return new Promise((resolve, reject) => {
    const fullUrl = `${BASE_URL}/api/download?path=${encodeURIComponent(path)}`;
    const startedAt = Date.now();
    wx.downloadFile({
      url: fullUrl,
      header: {
        ...(auth.getToken() ? { Authorization: `Bearer ${auth.getToken()}` } : {}),
        ...(auth.getCookie() ? { Cookie: auth.getCookie() } : {}),
      },
      timeout: 20000,
      success(res) {
        console.log("[miniapp] download success", {
          url: fullUrl,
          statusCode: res.statusCode,
          durationMs: Date.now() - startedAt,
        });
        if (res.statusCode >= 400) {
          reject(new Error(`下载失败(${res.statusCode})`));
          return;
        }
        resolve(res.tempFilePath);
      },
      fail(err) {
        console.error("[miniapp] download fail", {
          url: fullUrl,
          durationMs: Date.now() - startedAt,
          err,
        });
        reject(new Error(err.errMsg || "下载失败"));
      },
    });
  });
}

module.exports = {
  BASE_URL,
  request,
  uploadFile,
  downloadFile,
};
