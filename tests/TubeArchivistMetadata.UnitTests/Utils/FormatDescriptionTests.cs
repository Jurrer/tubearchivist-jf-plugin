using Jellyfin.Plugin.TubeArchivistMetadata.Utilities;
using Xunit;

namespace TubeArchivistMetadata.UnitTests;

/// <summary>
/// Unit tests for <see cref="Utils.FormatDescription"/>.
/// Tests run with Plugin.Instance == null (no Jellyfin runtime), so the default max 500 applies.
/// </summary>
public class FormatDescriptionTests
{
    [Fact]
    public void FormatDescription_NullInput_ReturnsEmpty()
    {
        Assert.Equal(string.Empty, Utils.FormatDescription(null!));
    }

    [Fact]
    public void FormatDescription_EmptyString_ReturnsEmpty()
    {
        Assert.Equal(string.Empty, Utils.FormatDescription(string.Empty));
    }

    [Fact]
    public void FormatDescription_ShortString_NoTruncation()
    {
        Assert.Equal("hello", Utils.FormatDescription("hello"));
    }

    [Fact]
    public void FormatDescription_OverMaxLength_TruncatesTo500()
    {
        var input = new string('a', 600);
        var result = Utils.FormatDescription(input);
        Assert.Equal(500, result.Length);
        Assert.Equal(new string('a', 500), result);
    }

    [Fact]
    public void FormatDescription_ExactlyMaxLength_NotTruncated()
    {
        var input = new string('a', 500);
        var result = Utils.FormatDescription(input);
        Assert.Equal(500, result.Length);
    }

    [Fact]
    public void FormatDescription_NewlinesReplacedWithBr()
    {
        Assert.Equal("line1<br>line2<br>line3", Utils.FormatDescription("line1\nline2\nline3"));
    }

    [Fact]
    public void FormatDescription_NoNewlines_Unchanged()
    {
        Assert.Equal("a simple description", Utils.FormatDescription("a simple description"));
    }

    [Fact]
    public void FormatDescription_TruncationHappensBeforeBrReplacement()
    {
        // 600 a's + 2 newlines at the end (positions 600,601). After truncation to 500,
        // the newlines (at 600,601) are cut away, so no <br> should appear.
        var input = new string('a', 600) + "\n\n";
        var result = Utils.FormatDescription(input);
        Assert.Equal(500, result.Length);
        Assert.DoesNotContain("<br>", result);
    }

    [Fact]
    public void FormatDescription_NewlineWithinMaxLength_ReplacedAfterTruncation()
    {
        // newline at position 10, total length well under 500
        var input = "0123456789\nrest";
        Assert.Equal("0123456789<br>rest", Utils.FormatDescription(input));
    }
}
