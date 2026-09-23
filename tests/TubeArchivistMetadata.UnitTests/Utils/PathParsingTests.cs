using Jellyfin.Plugin.TubeArchivistMetadata.Utilities;
using Xunit;

namespace TubeArchivistMetadata.UnitTests;

/// <summary>
/// Unit tests for <see cref="Utils.GetVideoNameFromPath"/> and <see cref="Utils.GetChannelNameFromPath"/>.
/// </summary>
public class PathParsingTests
{
    [Theory]
    [InlineData("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA/video.mkv", "video")]
    [InlineData("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA/subdir/another.mp4", "another")]
    [InlineData("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA/name.with.dots.mp4", "name")]
    [InlineData("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA/name.with.dots.mkv", "name")]
    public void GetVideoNameFromPath_UnixSeparators_ExtractsNameBeforeExtension(string path, string expected)
    {
        Assert.Equal(expected, Utils.GetVideoNameFromPath(path));
    }

    [Theory]
    [InlineData(@"C:\data\TubeArchivist\Fireship\UCsBjURrPoezykLs9EqgamOA\video.mkv", "video")]
    [InlineData(@"C:\data\TubeArchivist\Fireship\UCsBjURrPoezykLs9EqgamOA\subdir\another.mp4", "another")]
    [InlineData(@"C:\data\TubeArchivist\Fireship\UCsBjURrPoezykLs9EqgamOA\name.with.dots.mp4", "name")]
    public void GetVideoNameFromPath_WindowsSeparators_ExtractsNameBeforeExtension(string path, string expected)
    {
        Assert.Equal(expected, Utils.GetVideoNameFromPath(path));
    }

    [Theory]
    [InlineData("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA", "UCsBjURrPoezykLs9EqgamOA")]
    [InlineData("/data/TubeArchivist/Gamers Nexus/UChIs72whgZI9w6d6FhwGGHA", "UChIs72whgZI9w6d6FhwGGHA")]
    public void GetChannelNameFromPath_UnixSeparators_ExtractsLastSegment(string path, string expected)
    {
        Assert.Equal(expected, Utils.GetChannelNameFromPath(path));
    }

    [Theory]
    [InlineData("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA/", "")]
    public void GetChannelNameFromPath_TrailingSlash_ReturnsEmpty(string path, string expected)
    {
        // Documents current behavior: trailing slash → last segment is empty
        Assert.Equal(expected, Utils.GetChannelNameFromPath(path));
    }

    [Theory]
    [InlineData(@"C:\data\TubeArchivist\Fireship\UCsBjURrPoezykLs9EqgamOA", "UCsBjURrPoezykLs9EqgamOA")]
    public void GetChannelNameFromPath_WindowsSeparators_ExtractsLastSegment(string path, string expected)
    {
        Assert.Equal(expected, Utils.GetChannelNameFromPath(path));
    }

    [Theory]
    [InlineData(@"C:\data\TubeArchivist\Fireship\UCsBjURrPoezykLs9EqgamOA\", "")]
    public void GetChannelNameFromPath_TrailingBackslash_ReturnsEmpty(string path, string expected)
    {
        Assert.Equal(expected, Utils.GetChannelNameFromPath(path));
    }

    [Theory]
    // backslashes outnumber forward slashes → backslash is the separator
    [InlineData(@"C:\mixed/path\channel-id", "channel-id")]
    // forward slashes outnumber backslashes → forward slash is the separator
    [InlineData("/mixed\\path/to/channel-id", "channel-id")]
    public void GetChannelNameFromPath_MixedSeparators_UsesMajoritySeparator(string path, string expected)
    {
        Assert.Equal(expected, Utils.GetChannelNameFromPath(path));
    }
}
