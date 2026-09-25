# TubeArchivistMetadata Plugin

A Jellyfin plugin that synchronizes metadata, playback progress, watched status, and playlists between a Jellyfin library and a TubeArchivist instance.

## Language

**TubeArchivist (TA)**: The source of truth for downloaded YouTube videos, channels, and playlists. The plugin reads TA's API to populate Jellyfin metadata and writes back playback state. _Avoid_: yt-dlp backend, downloader.

**Channel**: A TA YouTube channel. Maps to a Jellyfin `Series`. _Avoid_: show, series (when discussing the TA side).

**Video**: A single TA-downloaded YouTube video. Maps to a Jellyfin `Episode`. _Avoid_: episode (when discussing the TA side).

**Playlist**: A TA-curated list of videos. Synced bidirectionally with Jellyfin playlists (see [Playlist Sync](#sync-directions)). _Avoid_: collection.

**Collection**: A Jellyfin library folder (named via `CollectionTitle` config) that holds TubeArchivist media. Acts as the sync boundary: only items whose top parent matches the name are synchronized. _Avoid_: library, folder.

**Collection boundary**: The sync guard enforced by matching an item's top-parent name against `CollectionTitle`. Only items inside the Collection boundary are eligible for progress, watched, and playlist sync. Items outside (e.g. in a `Movies` library) are skipped on every sync path. _Avoid_: library filter, scope check.

**TA-provider item**: A Jellyfin `BaseItem` whose `ProviderIds[Constants.ProviderName]` (i.e. `ProviderIds["TubeArchivist"]`) is set. Only TA-provider items are eligible for JF→TA playlist sync — items without a TubeArchivist provider id are skipped with an error log. _Avoid_: tagged item, provider-mapped item.

## Sync directions

**JF→TA Progress Sync**: Pushes Jellyfin playback position and watched status for a configured Jellyfin user (`JFUsernameFrom`) back to TubeArchivist. Triggered by `PlaybackProgress` and `UserDataSaved` events.

**TA→JF Progress Sync**: Pulls playback progress and watched status from TubeArchivist into Jellyfin user data. Runs as a scheduled task.

**Playlist Sync**: Bidirectional. `TAToJellyfinPlaylistsSyncTask` mirrors TA playlists into Jellyfin; `JFToTubeArchivistPlaylistsSyncTask` mirrors Jellyfin playlist changes back to TA. Each TA playlist appears in JF with a name suffixed by its TA playlist id in parentheses — Regular playlists as `Name - Channel (ID)`, Custom playlists as `Name (ID)`.
