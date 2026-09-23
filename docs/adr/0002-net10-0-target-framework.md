# Target net10.0, not net9.0, for the 12.1 bump

Jellyfin 12.1's server builds on the .NET 10 SDK (global.json: SDK 10.0.0). The official jellyfin-plugin-template still pins `net9.0`, which would let the plugin load on both 10.11 and 12.1 via roll-forward. We chose `net10.0` instead because we already decided (see ADR-0001) to go forward-only on 12.1, so cross-compat with 10.11 is explicitly forgone. If the build surfaces a net10.0-specific issue the template authors avoided by staying on net9.0, that's a signal we want to see now rather than hide behind net9.0.
