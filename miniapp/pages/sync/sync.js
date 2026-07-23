const api = require("../../utils/api");
const auth = require("../../utils/auth");

Page({
  data: {
    status: null,
    folder: null,
    devices: [],
    conflicts: [],
    logs: "",
    loaded: false,
    loading: false,
    refreshing: false,
    error: "",
  },

  onShow() {
    wx.setNavigationBarTitle({ title: "同步" });
    if (!auth.isLoggedIn()) {
      wx.reLaunch({ url: "/pages/login/login" });
      return;
    }
    if (!this.data.loaded) {
      this.loadStatus({ silent: false });
    }
  },

  async loadStatus(options = {}) {
    const silent = !!options.silent;
    this.setData({
      loading: !silent && !this.data.loaded,
      refreshing: !!this.data.loaded,
      error: "",
    });
    try {
      const data = await api.getSyncthingStatus();
      this.setData({
        status: data.status || null,
        folder: data.folder || null,
        devices: data.devices || [],
        conflicts: data.conflicts || [],
        loaded: true,
      });
    } catch (error) {
      this.setData({ error: error.message || "读取同步状态失败" });
    } finally {
      this.setData({ loading: false, refreshing: false });
    }
  },

  refreshSync() {
    this.loadStatus({ silent: true });
  },

  async control(e) {
    const action = e.currentTarget.dataset.action;
    try {
      await api.controlSyncthing(action);
      const labels = {
        start: "启动",
        restart: "重启",
        stop: "停止",
      };
      wx.showToast({
        title: `${labels[action] || action}请求已发送`,
        icon: "none",
      });
      this.loadStatus({ silent: true });
    } catch (error) {
      wx.showToast({ title: error.message || "操作失败", icon: "none" });
    }
  },

  async loadLogs() {
    try {
      const data = await api.getSyncthingLogs();
      this.setData({ logs: data.logs || "" });
    } catch (error) {
      wx.showToast({ title: error.message || "读取日志失败", icon: "none" });
    }
  },
});
