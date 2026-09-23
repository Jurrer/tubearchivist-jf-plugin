# TubeArchivistMetadata Plugin

A Jellyfin plugin that synchronizes metadata, playback progress, watched status, and playlists between a Jellyfin library and a TubeArchivist instance.

## Language

**TubeArchivist (TA)**:
The source of truth for downloaded YouTube videos, channels, and playlists. The plugin reads TA's API to populate Jellyfin metadata and writes back playback state.
_Avoid_: yt-dlp backend, the downloader

**Channel**:
A TA YouTube channel. Maps to a Jellyfin `Series`.
_Avoid_: show, series (when discussing the TA side)

**Video**:
A single TA-downloaded YouTube video. Maps to a Jellyfin `Episode`.
_Avoid_: episode (when discussing the TA side)

**Playlist**:
A TA-curated list of videos. Synced bidirectionally with Jellyfin playlists (see [Playlist Sync]).
_Avoid_: collection

**Collection**:
The Jellyfin library folder (named via `CollectionTitle` config) that holds the TubeArchivist media. Acts as the sync boundary: only items whose top parent matches this name are synchronized.
_Avoid_: library, folder

## Sync directions

**JF→TA Progress Sync**:
Pushes Jellyfin playback position and watched status for the configured Jellyfin user (`JFUsernameFrom`) back to TubeArchivist. Triggered by `PlaybackProgress` and `UserDataSaved` events.

**TA→JF Progress Sync**:
Pulls playback progress and watched status from TubeArchivist into Jellyfin user data. Runs as a scheduled task.

**Playlist Sync**:
Bidirectional. `TAToJellyfinPlaylistsSyncTask` mirrors TA playlists into Jellyfin; `JFToTubeArchivistPlaylistsSyncTask` mirrors Jellyfin playlist changes back to TA.
