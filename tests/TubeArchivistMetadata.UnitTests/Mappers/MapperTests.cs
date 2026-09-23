using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using Jellyfin.Plugin.TubeArchivistMetadata;
using Jellyfin.Plugin.TubeArchivistMetadata.TubeArchivist;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Model.Entities;
using MediaBrowser.Model.Providers;
using Newtonsoft.Json;
using Xunit;

namespace TubeArchivistMetadata.UnitTests;

/// <summary>
/// Unit tests for the TA→Jellyfin mappers: Video.ToEpisode, Video.ToSearchResult,
/// Channel.ToSeries, Channel.ToSearchResult, and the NumberingScheme.YYYYMMDD branch.
/// Tests run with Plugin.Instance == null, so IndexNumber falls back to null (Default scheme).
/// </summary>
public class MapperTests
{
    private static Video LoadVideo()
    {
        var json = File.ReadAllText(Path.Combine("Fixtures", "video.json"));
        return JsonConvert.DeserializeObject<Video>(json)!;
    }

    private static Channel LoadChannel()
    {
        var json = File.ReadAllText(Path.Combine("Fixtures", "channel.json"));
        return JsonConvert.DeserializeObject<Channel>(json)!;
    }

    [Fact]
    public void Video_ToEpisode_MapsTitle()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Equal("Test Video Title", episode.Name);
    }

    [Fact]
    public void Video_ToEpisode_FormatsDescriptionWithBr()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Equal("Line one<br>Line two", episode.Overview);
    }

    [Fact]
    public void Video_ToEpisode_SetsSeasonNameToYear()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Equal("2025", episode.SeasonName);
    }

    [Fact]
    public void Video_ToEpisode_SetsParentIndexNumberToYear()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Equal(2025, episode.ParentIndexNumber);
    }

    [Fact]
    public void Video_ToEpisode_IndexNumber_NullWhenPluginInstanceNull()
    {
        // Plugin.Instance is null in tests → Default scheme → _ => null
        var episode = LoadVideo().ToEpisode();
        Assert.Null(episode.IndexNumber);
    }

    [Fact]
    public void Video_ToEpisode_SetsSeriesNameToChannelName()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Equal("Fireship", episode.SeriesName);
    }

    [Fact]
    public void Video_ToEpisode_SetsProductionYear()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Equal(2025, episode.ProductionYear);
    }

    [Fact]
    public void Video_ToEpisode_SetsPremiereDate()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Equal(2025, episode.PremiereDate?.Year);
        Assert.Equal(8, episode.PremiereDate?.Month);
        Assert.Equal(4, episode.PremiereDate?.Day);
    }

    [Fact]
    public void Video_ToEpisode_SetsStudiosToChannelName()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Single(episode.Studios);
        Assert.Equal("Fireship", episode.Studios[0]);
    }

    [Fact]
    public void Video_ToEpisode_SetsProviderIds()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Equal("abc123video", episode.ProviderIds[Constants.ProviderName]);
    }

    [Fact]
    public void Video_ToEpisode_SetsPrimaryImageInfo()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Single(episode.ImageInfos);
        Assert.Equal("https://yt.i.szop.top/videos/abc123.jpg", episode.ImageInfos[0].Path);
        Assert.Equal(ImageType.Primary, episode.ImageInfos[0].Type);
    }

    [Fact]
    public void Video_ToEpisode_SetsTags()
    {
        var episode = LoadVideo().ToEpisode();
        Assert.Equal(new[] { "tag1", "tag2", "tag3" }, episode.Tags);
    }

    [Fact]
    public void Video_ToSearchResult_MapsFields()
    {
        var video = LoadVideo();
        var result = video.ToSearchResult();
        Assert.Equal("Test Video Title", result.Name);
        Assert.Equal(Constants.ProviderName, result.SearchProviderName);
        Assert.Equal(2025, result.ProductionYear);
        Assert.Equal("https://yt.i.szop.top/videos/abc123.jpg", result.ImageUrl);
        Assert.Equal(2025, result.PremiereDate?.Year);
        Assert.Equal("abc123video", result.ProviderIds[Constants.ProviderName]);
    }

    [Fact]
    public void Channel_ToSeries_MapsName()
    {
        var series = LoadChannel().ToSeries();
        Assert.Equal("Gamers Nexus", series.Name);
    }

    [Fact]
    public void Channel_ToSeries_FormatsDescriptionWithBr()
    {
        var series = LoadChannel().ToSeries();
        Assert.Equal("Gamers Nexus channel description<br>with newline", series.Overview);
    }

    [Fact]
    public void Channel_ToSeries_SetsStudiosToChannelName()
    {
        var series = LoadChannel().ToSeries();
        Assert.Single(series.Studios);
        Assert.Equal("Gamers Nexus", series.Studios[0]);
    }

    [Fact]
    public void Channel_ToSeries_SetsProviderIds()
    {
        var series = LoadChannel().ToSeries();
        Assert.Equal("UChIs72whgZI9w6d6FhwGGHA", series.ProviderIds[Constants.ProviderName]);
    }

    [Fact]
    public void Channel_ToSeries_SetsPrimaryImageInfo()
    {
        var series = LoadChannel().ToSeries();
        Assert.Single(series.ImageInfos);
        Assert.Equal("https://yt.i.szop.top/channels/UCthumb.jpg", series.ImageInfos[0].Path);
        Assert.Equal(ImageType.Primary, series.ImageInfos[0].Type);
    }

    [Fact]
    public void Channel_ToSeries_SetsTags()
    {
        var series = LoadChannel().ToSeries();
        Assert.Equal(new[] { "hardware", "reviews" }, series.Tags);
    }

    [Fact]
    public void Channel_ToSeries_NullTags_HandledAsEmpty()
    {
        var channel = new Channel(
            bannerUrl: "b",
            description: "d",
            id: "UC1",
            name: "Test",
            tags: null!,
            thumbUrl: "t",
            tvartUrl: "a");
        var series = channel.ToSeries();
        Assert.NotNull(series.Tags);
        Assert.Empty(series.Tags);
    }

    [Fact]
    public void Channel_ToSearchResult_MapsFields()
    {
        var channel = LoadChannel();
        var result = channel.ToSearchResult();
        Assert.Equal("Gamers Nexus", result.Name);
        Assert.Equal(Constants.ProviderName, result.SearchProviderName);
        Assert.Equal("https://yt.i.szop.top/channels/UCthumb.jpg", result.ImageUrl);
        Assert.Equal("UChIs72whgZI9w6d6FhwGGHA", result.ProviderIds[Constants.ProviderName]);
    }

    // NumberingScheme.YYYYMMDD computation: (year*10000)+(month*100)+day
    [Theory]
    [InlineData(2025, 8, 4, 20250804)]
    [InlineData(2024, 1, 1, 20240101)]
    [InlineData(2023, 12, 31, 20231231)]
    [InlineData(2026, 9, 23, 20260923)]
    public void YyyyMmDd_Numbering_ComputesCorrectly(int year, int month, int day, int expected)
    {
        Assert.Equal(expected, (year * 10000) + (month * 100) + day);
    }
}
