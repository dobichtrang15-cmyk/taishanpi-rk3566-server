const COOKIE_KEY = "filemgr_cookie";
const TOKEN_KEY = "filemgr_token";
const USER_KEY = "filemgr_user";

function getCookie() {
  return wx.getStorageSync(COOKIE_KEY) || "";
}

function setCookie(cookie) {
  if (!cookie) return;
  wx.setStorageSync(COOKIE_KEY, cookie);
}

function clearCookie() {
  wx.removeStorageSync(COOKIE_KEY);
}

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || "";
}

function setToken(token) {
  if (!token) return;
  wx.setStorageSync(TOKEN_KEY, token);
}

function clearToken() {
  wx.removeStorageSync(TOKEN_KEY);
}

function getUser() {
  return wx.getStorageSync(USER_KEY) || null;
}

function setUser(user) {
  wx.setStorageSync(USER_KEY, user || null);
}

function clearUser() {
  wx.removeStorageSync(USER_KEY);
}

function isLoggedIn() {
  return !!(getToken() || getCookie());
}

module.exports = {
  getCookie,
  setCookie,
  clearCookie,
  getToken,
  setToken,
  clearToken,
  getUser,
  setUser,
  clearUser,
  isLoggedIn,
};
