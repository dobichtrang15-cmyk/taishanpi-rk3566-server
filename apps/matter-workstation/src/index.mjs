#!/usr/bin/env node

import {
  DeviceTypeId,
  Endpoint,
  Environment,
  ServerNode,
  VendorId,
} from "@matter/main";
import { OnOffServer } from "@matter/main/behaviors";
import { OnOffPlugInUnitDevice } from "@matter/main/devices";

const API_BASE_URL = (process.env.WORKSTATION_API_URL || "http://127.0.0.1:5000").replace(/\/$/, "");
const POLL_INTERVAL_MS = numberEnv("WORKSTATION_POLL_INTERVAL_MS", 5000, 1000, 300000);
const ACTION_TIMEOUT_MS = numberEnv("WORKSTATION_ACTION_TIMEOUT_MS", 25000, 1000, 120000);
const TRANSITION_GRACE_MS = numberEnv("WORKSTATION_TRANSITION_GRACE_MS", 45000, 0, 300000);

let transitionUntil = 0;
let transitionTarget;
let endpoint;

class WorkstationPowerServer extends OnOffServer {
  async on() {
    await invokeAction("wake");
    transitionTarget = true;
    transitionUntil = Date.now() + TRANSITION_GRACE_MS;
    this.state.onOff = true;
  }

  async off() {
    await invokeAction("shutdown");
    transitionTarget = false;
    transitionUntil = Date.now() + TRANSITION_GRACE_MS;
    this.state.onOff = false;
  }

  async toggle() {
    if (this.state.onOff) {
      await this.off();
    } else {
      await this.on();
    }
  }
}

const WorkstationDevice = OnOffPlugInUnitDevice.with(WorkstationPowerServer);
const environment = Environment.default;
const passcode = numberEnv("MATTER_PASSCODE", 20202021, 1, 99999998);
const discriminator = numberEnv("MATTER_DISCRIMINATOR", 3840, 0, 4095);
const vendorId = numberEnv("MATTER_VENDOR_ID", 0xfff1, 0, 0xffff);
const productId = numberEnv("MATTER_PRODUCT_ID", 0x8001, 0, 0xffff);
const port = numberEnv("MATTER_PORT", 5540, 1, 65535);
const uniqueId = process.env.MATTER_UNIQUE_ID || "taishanpi-workstation-power";
const deviceName = process.env.MATTER_DEVICE_NAME || "Windows电脑";

const server = await ServerNode.create({
  id: uniqueId,
  network: { port },
  commissioning: { passcode, discriminator },
  productDescription: {
    name: deviceName,
    deviceType: DeviceTypeId(WorkstationDevice.deviceType),
  },
  basicInformation: {
    vendorName: "TaishanPi",
    vendorId: VendorId(vendorId),
    nodeLabel: deviceName,
    productName: "TaishanPi Workstation Power",
    productLabel: deviceName,
    productId,
    serialNumber: `${uniqueId}-01`,
    uniqueId,
  },
});

endpoint = new Endpoint(WorkstationDevice, { id: "workstation-power" });
await server.add(endpoint);

endpoint.events.onOff.onOff$Changed.on(value => {
  console.log(`[matter] workstation power is now ${value ? "ON" : "OFF"}`);
});

server.lifecycle.commissioned.on(() => console.log("[matter] commissioned successfully"));
server.lifecycle.decommissioned.on(() => console.log("[matter] decommissioned"));
server.lifecycle.online.on(() => console.log("[matter] server online"));

const initialOnline = await readOnlineStatus().catch(error => {
  console.warn(`[status] initial query failed: ${error.message}`);
  return false;
});
await setMatterState(initialOnline);

await server.start();
console.log(`[matter] ${deviceName} started; API=${API_BASE_URL}; poll=${POLL_INTERVAL_MS}ms`);

if (!server.lifecycle.isCommissioned) {
  const { qrPairingCode, manualPairingCode } = server.state.commissioning.pairingCodes;
  console.log(`[matter] QR payload: ${qrPairingCode}`);
  console.log(`[matter] manual pairing code: ${manualPairingCode}`);
}

const pollTimer = setInterval(pollWorkstationStatus, POLL_INTERVAL_MS);
pollTimer.unref();

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, async () => {
    clearInterval(pollTimer);
    await server.close();
    process.exit(0);
  });
}

async function pollWorkstationStatus() {
  try {
    const online = await readOnlineStatus();
    if (Date.now() < transitionUntil && online !== transitionTarget) return;
    transitionTarget = undefined;
    transitionUntil = 0;
    await setMatterState(online);
  } catch (error) {
    console.warn(`[status] query failed: ${error.message}`);
  }
}

async function setMatterState(online) {
  if (endpoint.state.onOff.onOff === online) return;
  await endpoint.set({ onOff: { onOff: online } });
}

async function readOnlineStatus() {
  const payload = await apiRequest("/api/device/workstation/status", "GET");
  return Boolean(payload?.status?.online);
}

async function invokeAction(action) {
  const payload = await apiRequest(`/api/device/workstation/${action}`, "POST");
  console.log(`[action] ${payload.message || action}`);
}

async function apiRequest(path, method) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ACTION_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    });
    const text = await response.text();
    let payload = {};
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        throw new Error(`API returned non-JSON response (${response.status})`);
      }
    }
    if (!response.ok) {
      throw new Error(payload.error || `API request failed (${response.status})`);
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError") throw new Error(`API request timed out after ${ACTION_TIMEOUT_MS}ms`);
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function numberEnv(name, fallback, min, max) {
  const raw = process.env[name];
  if (raw === undefined || raw === "") return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < min || value > max) {
    throw new Error(`${name} must be an integer between ${min} and ${max}`);
  }
  return value;
}
