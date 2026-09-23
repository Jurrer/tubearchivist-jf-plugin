using Jellyfin.Plugin.TubeArchivistMetadata.Utilities;
using Xunit;

namespace TubeArchivistMetadata.UnitTests;

/// <summary>
/// Unit tests for <see cref="Utils.GetTAPlaylistIdFromName"/> and <see cref="Utils.GetTAPlaylistNameFromName"/>.
/// </summary>
public class PlaylistNameRegexTests
{
    // YouTube (Regular) format: "Name - Channel (ID)"
    [Theory]
    [InlineData("My Playlist - Fireship (PL12345)", "PL12345")]
    [InlineData("Best Videos - Gamers Nexus (PLabc-DEF789)", "PLabc-DEF789")]
    [InlineData("Name with (parens) inside - Channel (PLxyz)", "PLxyz")]
    public void GetTAPlaylistIdFromName_YouTubeFormat_ExtractsId(string playlistName, string expected)
    {
        Assert.Equal(expected, Utils.GetTAPlaylistIdFromName(playlistName));
    }

    // Custom format: "Name (ID)"
    [Theory]
    [InlineData("My Custom Playlist (PLcustom123)", "PLcustom123")]
    [InlineData("Simple (abc-def-456)", "abc-def-456")]
    public void GetTAPlaylistIdFromName_CustomFormat_ExtractsId(string playlistName, string expected)
    {
        Assert.Equal(expected, Utils.GetTAPlaylistIdFromName(playlistName));
    }

    [Fact]
    public void GetTAPlaylistIdFromName_NoParens_ReturnsEmpty()
    {
        Assert.Equal(string.Empty, Utils.GetTAPlaylistIdFromName("PlaylistWithoutId"));
    }

    // YouTube (Regular) format: "Name - Channel (ID)" → returns Name
    [Theory]
    [InlineData("My Playlist - Fireship (PL12345)", "My Playlist")]
    [InlineData("Best Videos - Gamers Nexus (PLabc-DEF789)", "Best Videos")]
    public void GetTAPlaylistNameFromName_YouTubeFormat_ExtractsName(string playlistName, string expected)
    {
        Assert.Equal(expected, Utils.GetTAPlaylistNameFromName(playlistName));
    }

    // Custom format: "Name (ID)" → returns Name
    [Theory]
    [InlineData("My Custom Playlist (PLcustom123)", "My Custom Playlist")]
    [InlineData("Simple (abc-def-456)", "Simple")]
    public void GetTAPlaylistNameFromName_CustomFormat_ExtractsName(string playlistName, string expected)
    {
        Assert.Equal(expected, Utils.GetTAPlaylistNameFromName(playlistName));
    }

    [Theory]
    [InlineData("Name with (parens) inside - Channel (PLxyz)", "Name with (parens) inside")]
    public void GetTAPlaylistNameFromName_NameWithNestedParens_YouTubeFormat(string playlistName, string expected)
    {
        Assert.Equal(expected, Utils.GetTAPlaylistNameFromName(playlistName));
    }

    [Fact]
    public void GetTAPlaylistNameFromName_NoParens_ReturnsEmpty()
    {
        Assert.Equal(string.Empty, Utils.GetTAPlaylistNameFromName("PlaylistWithoutId"));
    }
}
