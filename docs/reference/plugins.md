# Plugins

Plugins are the per-step loop hook that runs **first** each step, before flows are
computed. Use them to reroute vehicles, gate/close links, run dispatchers, or
implement access policies. `ReroutingPlugin` is the minimal rerouting form. See
[Plugins](../guide/plugins.md).

::: mesoltm.plugins.plugin.Plugin

::: mesoltm.plugins.plugin.FunctionPlugin

::: mesoltm.plugins.plugin.ReroutingPlugin
