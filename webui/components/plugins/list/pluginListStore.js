/**
 * VoiceOS stub for pluginListStore (CLI-only; satisfies legacy import paths).
 * Prevents import failures in plugin installer / discovery modules.
 */
import { createStore } from "/js/AlpineStore.js";

const model = {
  activeTab: "plugins",
  plugins: [],
  loading: false,

  async open(tab = "plugins") {
    this.activeTab = tab;
    document.dispatchEvent(new CustomEvent("voiceos:plugin-tab", { detail: { tab } }));
  },

  async refresh() {
    this.loading = true;
    try {
      const res = await fetch("/api/plugins/list").catch(() => null);
      if (res && res.ok) {
        const data = await res.json();
        this.plugins = data.plugins || data || [];
      }
    } finally {
      this.loading = false;
    }
  },

  openPluginInfo(plugin) {
    console.info("[pluginListStore] openPluginInfo", plugin?.name || plugin);
  },

  async openPluginDoc(pluginInfo, doc) {
    console.info("[pluginListStore] openPluginDoc", pluginInfo?.name, doc);
  },

  async openPluginConfig(pluginName) {
    console.info("[pluginListStore] openPluginConfig", pluginName);
    await this.open("plugins");
  },

  async deletePlugin(pluginInfo) {
    console.warn("[pluginListStore] deletePlugin not fully wired", pluginInfo?.name);
  },
};

const store = createStore("pluginListStore", model);
export { store };
