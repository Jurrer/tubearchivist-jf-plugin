using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using Jellyfin.Plugin.TubeArchivistMetadata.TubeArchivist;
using Newtonsoft.Json;
using Xunit;

namespace TubeArchivistMetadata.UnitTests;

/// <summary>
/// Unit tests verifying JSON deserialization of sample TubeArchivist API responses
/// into the plugin's model classes, asserting [JsonProperty] mappings and TagsJsonConverter.
/// </summary>
public class DeserializationTests
{
    private static readonly string FixturesDir = "Fixtures";

    private static string LoadFixture(string name)
    {
        return File.ReadAllText(Path.Combine(FixturesDir, name));
    }

    private static T Deserialize<T>(string name)
    {
        return JsonConvert.DeserializeObject<T>(LoadFixture(name))!;
    }

    [Fact]
    public void Deserialize_Video_MapsAllProperties()
    {
        var video = Deserialize<Video>("video.json");
        Assert.Equal("Test Video Title", video.Title);
        Assert.Equal("Line one\nLine two", video.Description);
        Assert.Equal("https://yt.i.szop.top/videos/abc123.jpg", video.VidThumbUrl);
        Assert.Equal("abc123video", video.YoutubeId);
        Assert.Equal(2025, video.Published.Year);
        Assert.Equal(8, video.Published.Month);
        Assert.Equal(4, video.Published.Day);
        Assert.Equal(3, video.Tags.Count);
        Assert.Equal(new[] { "tag1", "tag2", "tag3" }, video.Tags);
    }

    [Fact]
    public void Deserialize_Video_NestedChannel_MapsCorrectly()
    {
        var video = Deserialize<Video>("video.json");
        Assert.NotNull(video.Channel);
        Assert.Equal("Fireship", video.Channel.Name);
        Assert.Equal("UCsBjURrPoezykLs9EqgamOA", video.Channel.Id);
    }

    [Fact]
    public void Deserialize_Video_NestedPlayer_MapsCorrectly()
    {
        var video = Deserialize<Video>("video.json");
        Assert.NotNull(video.Player);
        Assert.Equal(300, video.Player.Duration);
        Assert.False(video.Player.IsWatched);
        Assert.Equal(0, video.Player.Position);
    }

    [Fact]
    public void Deserialize_Video_TagsJsonConverter_HandlesArray()
    {
        var video = Deserialize<Video>("video.json");
        Assert.IsType<Collection<string>>(video.Tags);
        Assert.Equal("tag2", video.Tags[1]);
    }

    [Fact]
    public void Deserialize_Channel_MapsAllProperties()
    {
        var channel = Deserialize<Channel>("channel.json");
        Assert.Equal("Gamers Nexus", channel.Name);
        Assert.Equal("UChIs72whgZI9w6d6FhwGGHA", channel.Id);
        Assert.Equal("https://yt.i.szop.top/channels/UCbanner.jpg", channel.BannerUrl);
        Assert.Equal("Gamers Nexus channel description\nwith newline", channel.Description);
        Assert.Equal("https://yt.i.szop.top/channels/UCthumb.jpg", channel.ThumbUrl);
        Assert.Equal("https://yt.i.szop.top/channels/UCart.jpg", channel.TvartUrl);
        Assert.Equal(2, channel.Tags.Count);
        Assert.Equal("hardware", channel.Tags[0]);
    }

    [Fact]
    public void Deserialize_Playlist_MapsAllProperties()
    {
        var playlist = Deserialize<Playlist>("playlist.json");
        Assert.True(playlist.IsActive);
        Assert.Equal("Fireship", playlist.Channel);
        Assert.Equal("UCsBjURrPoezykLs9EqgamOA", playlist.ChannelId);
        Assert.Equal("A test playlist", playlist.Description);
        Assert.Equal("PL12345abc", playlist.Id);
        Assert.Equal("Test Playlist", playlist.Name);
        Assert.Equal("https://yt.i.szop.top/playlists/PL12345.jpg", playlist.ThumbnailUrl);
        Assert.Equal(PlaylistType.Regular, playlist.Type);
    }

    [Fact]
    public void Deserialize_Playlist_EntriesMapped()
    {
        var playlist = Deserialize<Playlist>("playlist.json");
        Assert.Equal(2, playlist.Entries.Count);
        Assert.Equal("vid1", playlist.Entries[0].YoutubeId);
        Assert.Equal("First Video", playlist.Entries[0].Title);
        Assert.Equal("Fireship", playlist.Entries[0].Uploader);
        Assert.Equal(0, playlist.Entries[0].Index);
        Assert.True(playlist.Entries[0].IsDownloaded);
        Assert.False(playlist.Entries[1].IsDownloaded);
    }

    [Fact]
    public void Deserialize_PlaylistsPaginated_MapsDataAndPaginate()
    {
        var container = Deserialize<ResponseContainer<Collection<Playlist>>>("playlists_paginated.json");
        Assert.NotNull(container.Data);
        Assert.Equal(2, container.Data.Count);
        Assert.Equal("First Playlist", container.Data[0].Name);
        Assert.Equal(PlaylistType.Custom, container.Data[1].Type);
        Assert.NotNull(container.Paginate);
        Assert.Equal(25, container.Paginate.PageSize);
        Assert.Equal(1, container.Paginate.CurrentPage);
        Assert.Equal(2, container.Paginate.LastPage);
        Assert.Equal(43, container.Paginate.TotalHits);
        Assert.Equal(new[] { 2 }, container.Paginate.NextPages);
        Assert.Empty(container.Paginate.PrevPages);
    }

    [Fact]
    public void Deserialize_PingResponse_MapsAllProperties()
    {
        var ping = Deserialize<PingResponse>("ping.json");
        Assert.Equal("pong", ping.Response);
        Assert.Equal(1, ping.User);
        Assert.Equal("v0.5.0", ping.Version);
    }

    [Fact]
    public void Deserialize_Progress_MapsAllProperties()
    {
        var progress = Deserialize<Progress>("progress.json");
        Assert.Equal("abc123video", progress.YoutubeId);
        Assert.Equal(1, progress.UserId);
        Assert.Equal(120, progress.Position);
    }

    [Fact]
    public void Deserialize_Watched_MapsAllProperties()
    {
        var watched = Deserialize<Watched>("watched.json");
        Assert.Equal("abc123video", watched.Id);
        Assert.True(watched.IsWatched);
    }

    [Fact]
    public void Deserialize_Player_MapsAllProperties()
    {
        var player = Deserialize<Player>("player.json");
        Assert.True(player.IsWatched);
        Assert.Equal(600, player.Duration);
        Assert.Equal(150.5, player.Position);
    }

    [Fact]
    public void Deserialize_CustomPlaylistCreation_SerializesToJson()
    {
        var creation = new CustomPlaylistCreation("My Custom List");
        var json = JsonConvert.SerializeObject(creation);
        Assert.Contains("\"playlist_name\":\"My Custom List\"", json);
    }

    [Fact]
    public void Deserialize_CustomPlaylistEntryAction_SerializesLowercaseAction()
    {
        var action = new CustomPlaylistEntryAction(CustomPlaylistAction.Top, "vid123");
        var json = JsonConvert.SerializeObject(action);
        Assert.Contains("\"action\":\"top\"", json);
        Assert.Contains("\"video_id\":\"vid123\"", json);
    }

    [Fact]
    public void Deserialize_CustomPlaylistEntryAction_AllActionsLowercase()
    {
        Assert.Equal("create", new CustomPlaylistEntryAction(CustomPlaylistAction.Create, "v").Action);
        Assert.Equal("remove", new CustomPlaylistEntryAction(CustomPlaylistAction.Remove, "v").Action);
        Assert.Equal("top", new CustomPlaylistEntryAction(CustomPlaylistAction.Top, "v").Action);
        Assert.Equal("bottom", new CustomPlaylistEntryAction(CustomPlaylistAction.Bottom, "v").Action);
        Assert.Equal("up", new CustomPlaylistEntryAction(CustomPlaylistAction.Up, "v").Action);
        Assert.Equal("down", new CustomPlaylistEntryAction(CustomPlaylistAction.Down, "v").Action);
    }
}
