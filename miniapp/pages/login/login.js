const api = require("../../utils/api");
const auth = require("../../utils/auth");

Page({
  data: {
    username: "",
    password: "",
    loading: false,
    error: "",
  },

  onShow() {
    if (auth.isLoggedIn()) {
      wx.switchTab({ url: "/pages/overview/overview" });
    }
  },

  onUsernameInput(e) {
    this.setData({ username: e.detail.value });
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value });
  },

  async submit() {
    const { username, password } = this.data;
    if (!username || !password) {
      this.setData({ error: "请输入用户名和密码" });
      return;
    }
    this.setData({ loading: true, error: "" });
    try {
      await api.login(username, password);
      wx.switchTab({ url: "/pages/overview/overview" });
    } catch (error) {
      this.setData({ error: error.message || "登录失败" });
    } finally {
      this.setData({ loading: false });
    }
  },
});
