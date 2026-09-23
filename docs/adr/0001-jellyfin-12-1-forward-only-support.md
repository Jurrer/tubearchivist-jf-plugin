# Forward-only Jellyfin 12.1 support (drop 10.11 ceiling)

Starting with plugin version 1.5.0.0, the plugin targets Jellyfin 12.1 only (`targetAbi: 12.1.0.0`, `Jellyfin.Controller`/`Jellyfin.Model` 12.1.0, `net10.0`). The csproj carries a single package-version pin and cannot express two compatibility ceilings, so 10.11 support is not maintained going forward. Historical manifest entries (1.4.4.0 and below, `targetAbi: 10.11.0.0`) remain installable for 10.11 users.
