const api = require("../../utils/api");
const auth = require("../../utils/auth");

function emptyDevice() {
  return {
    name: "",
    host: "",
    mac: "",
    broadcast: "255.255.255.255",
    ssh_user: "",
    ssh_password: "",
    ssh_port: 22,
    shutdown_command: "shutdown /s /f /t 0",
  };
}

Page({
  data: {
    device: emptyDevice(),
    status: null,
    loaded: false,
    loading: false,
    refreshing: false,
    error: "",
  },

  onShow() {
    wx.setNavigationBarTitle({ title: "设备" });
    if (!auth.isLoggedIn()) {
      wx.reLaunch({ url: "/pages/login/login" });
      return;
    }
    if (!this.data.loaded) {
      this.loadDevice({ silent: false });
    }
  },

  async loadDevice(options = {}) {
    const silent = !!options.silent;
    this.setData({
      loading: !silent && !this.data.loaded,
      refreshing: !!this.data.loaded,
      error: "",
    });
    try {
      const data = await api.getWorkstation();
      this.setData({
        device: { ...emptyDevice(), ...(data.item || {}) },
        status: data.status || null,
        loaded: true,
      });
    } catch (error) {
      this.setData({ error: error.message || "读取设备配置失败" });
    } finally {
      this.setData({ loading: false, refreshing: false });
    }
  },

  refreshDevice() {
    this.loadDevice({ silent: true });
  },

  bindField(e) {
    const { key } = e.currentTarget.dataset;
    let value = e.detail.value;
    if (key === "ssh_port") {
      value = Number(value || 22);
    }
    this.setData({
      [`device.${key}`]: value,
    });
  },

  async save() {
    try {
      await api.saveWorkstation(this.data.device);
      wx.showToast({ title: "保存成功", icon: "success" });
      this.refreshDevice();
    } catch (error) {
      wx.showToast({ title: error.message || "保存失败", icon: "none" });
    }
  },

  async refreshStatus() {
    try {
      const data = await api.getWorkstationStatus();
      this.setData({ status: data.status || data });
    } catch (error) {
      wx.showToast({ title: error.message || "检测失败", icon: "none" });
    }
  },

  async wake() {
    try {
      const result = await api.wakeWorkstation();
      wx.showToast({
        title: result.message || "已发送唤醒请求",
        icon: "none",
      });
      this.refreshStatus();
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
        } catch (error) {
          wx.showToast({ title: error.message || "关机失败", icon: "none" });
        }
      },
    });
  },
});
