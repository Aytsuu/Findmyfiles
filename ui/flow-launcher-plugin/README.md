# Findmyfiles Flow Launcher Plugin

This plugin connects Flow Launcher to the local `findmyfiles` HTTP API.

## Behavior

- Action keyword: `fmf`
- Empty query:
  - shows a usage hint
  - checks service health at `http://127.0.0.1:7474/health`
- Search query:
  - sends `POST /search`
  - opens the selected file on `Enter`
- Context menu actions:
  - open file
  - reveal in Explorer
  - copy path
  - re-index the selected file with `POST /index`

## Build

```powershell
dotnet build ui\flow-launcher-plugin\Findmyfiles.csproj
```

## Install Into Flow Launcher

Build output is written to:

```text
ui\flow-launcher-plugin\bin\Debug\net8.0-windows\
```

To install manually, copy the plugin output directory contents into a Flow Launcher plugin directory, for example:

```text
%APPDATA%\FlowLauncher\Plugins\Findmyfiles\
```

The plugin folder must contain:

- `Findmyfiles.FlowLauncher.Plugin.dll`
- `plugin.json`
- dependency assemblies copied by the build output

## Runtime Requirements

- Flow Launcher installed
- local `findmyfiles` API running on `http://127.0.0.1:7474`
- indexed content already available for meaningful search results
