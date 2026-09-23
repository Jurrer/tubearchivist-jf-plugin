using Jellyfin.Plugin.TubeArchivistMetadata.Utilities;
using Xunit;

namespace TubeArchivistMetadata.UnitTests;

/// <summary>
/// Unit tests for <see cref="Utils.SanitizeUrl"/>.
/// </summary>
public class SanitizeUrlTests
{
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void SanitizeUrl_NullOrWhitespace_ReturnsEmpty(string? input)
    {
        Assert.Equal(string.Empty, Utils.SanitizeUrl(input!));
    }

    [Theory]
    [InlineData("http://example.com", "http://example.com/")]
    [InlineData("https://example.com", "https://example.com/")]
    [InlineData("HTTPS://example.com", "HTTPS://example.com/")]
    [InlineData("Http://Example.Com", "Http://Example.Com/")]
    public void SanitizeUrl_PreservesSchemaAndCase(string input, string expected)
    {
        Assert.Equal(expected, Utils.SanitizeUrl(input));
    }

    [Theory]
    [InlineData("http://example.com//path", "http://example.com/path/")]
    [InlineData("http://example.com///a//b///c", "http://example.com/a/b/c/")]
    [InlineData("http://example.com/path/", "http://example.com/path/")]
    [InlineData("http://example.com/path//", "http://example.com/path/")]
    [InlineData("http://example.com/ /path", "http://example.com/path/")]
    [InlineData("http://example.com/ / /path", "http://example.com/path/")]
    public void SanitizeUrl_CollapsesDoubleSlashesAndSpaces(string input, string expected)
    {
        Assert.Equal(expected, Utils.SanitizeUrl(input));
    }

    [Theory]
    [InlineData("http://example.com/path", "http://example.com/path/")]
    [InlineData("http://example.com/path/", "http://example.com/path/")]
    [InlineData("http://example.com/path///", "http://example.com/path/")]
    public void SanitizeUrl_AddsTrailingSlashWhenNoQueryOrFragment(string input, string expected)
    {
        Assert.Equal(expected, Utils.SanitizeUrl(input));
    }

    [Theory]
    [InlineData("http://example.com/path?q=1", "http://example.com/path?q=1")]
    [InlineData("http://example.com/path/?q=1", "http://example.com/path/?q=1")]
    [InlineData("http://example.com/path#frag", "http://example.com/path#frag")]
    [InlineData("http://example.com/path/#frag", "http://example.com/path/#frag")]
    public void SanitizeUrl_DoesNotAddTrailingSlashWhenQueryOrFragmentPresent(string input, string expected)
    {
        Assert.Equal(expected, Utils.SanitizeUrl(input));
    }

    [Theory]
    [InlineData("http://example.com/path?q=1&r=2", "http://example.com/path?q=1&r=2")]
    [InlineData("http://example.com/path#section", "http://example.com/path#section")]
    [InlineData("http://example.com/path?q=1#frag", "http://example.com/path?q=1#frag")]
    [InlineData("http://example.com/path#frag?q=1", "http://example.com/path#frag?q=1")]
    public void SanitizeUrl_PreservesQueryAndFragment(string input, string expected)
    {
        Assert.Equal(expected, Utils.SanitizeUrl(input));
    }

    [Theory]
    [InlineData("example.com/path", "example.com/path/")]
    [InlineData("example.com//path", "example.com/path/")]
    [InlineData("example.com/path?q=1", "example.com/path?q=1")]
    public void SanitizeUrl_NoSchema_TreatsWholeStringAsPath(string input, string expected)
    {
        Assert.Equal(expected, Utils.SanitizeUrl(input));
    }
}
