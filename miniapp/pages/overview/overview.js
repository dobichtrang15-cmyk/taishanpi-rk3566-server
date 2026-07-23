const api = require("../../utils/api");
const auth = require("../../utils/auth");

Page({
  data: {
    user: null,
    filesSummary: null,
    storageSummary: "未读取",
    deviceStatus: null,
    syncStatus: null,
    loaded: false,
    loading: false,
    refreshing: false,
    error: "",
  },

  onShow() {
    wx.setNavigationBarTitle({ title: "控制台" });
    if (!auth.isLoggedIn()) {
      wx.reLaunch({ url: "/pages/login/login" });
      return;
    }
    this.setData({ user: auth.getUser() });
    if (!this.data.loaded) {
      this.loadAll({ silent: false });
    }
  },

  async loadAll(options = {}) {
    const silent = !!options.silent;
    this.setData({
      loading: !silent && !this.data.loaded,
      refreshing: !!this.data.loaded,
      error: "",
    });

    try {
      const [files, device, sync] = await Promise.all([
        api.listFiles("/"),
        api.getWorkstationStatus(),
        api.getSyncthingStatus(),
      ]);

      const storage = files.storage || null;
      const storageSummary = storage
        ? `${storage.used || "-"} / ${storage.total || "-"}`
        : "未提供";

      this.setData({
        filesSummary: {
          current: files.current || "/",
          count: (files.items || []).length,
        },
        storageSummary,
        deviceStatus: device.status || device,
        syncStatus: sync.status || sync,
        loaded: true,
      });
    } catch (error) {
      this.setData({ error: error.message || "加载概览失败" });
    } finally {
      this.setData({ loading: false, refreshing: false });
    }
  },

  refreshAll() {
    this.loadAll({ silent: true });
  },

  goFiles() {
    wx.switchTab({ url: "/pages/files/files" });
  },

  goDevice() {
    wx.switchTab({ url: "/pages/device/device" });
  },

  goSync() {
    wx.switchTab({ url: "/pages/sync/sync" });
  },

  async wake() {
    try {
      const result = await api.wakeWorkstation();
      wx.showToast({
        title: result.message || "已发送唤醒请求",
        icon: "none",
      });
      this.loadAll({ silent: true });
    } catch (error) {
      wx.showToast({ title: error.message || "唤醒失败", icon: "none" });
    }
  },

  shutdown() {
    wx.showModal({
      title: "确认关机",
      content: "确认向 Windows 电脑发送远程关机命令吗？",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          const result = await api.shutdownWorkstation();
          wx.showToast({
            title: result.message || "已发送关机请求",
            icon: "none",
          });
          this.loadAll({ silent: true });
        } catch (error) {
          wx.showToast({ title: error.message || "关机失败", icon: "none" });
        }
      },
    });
  },

  async logout() {
    await api.logout();
    wx.reLaunch({ url: "/pages/login/login" });
  },
});
