from streamfetch import core


def test_quality_presets_cover_expected_names():
    for name in ["best", "1080p", "720p", "480p", "360p", "worst"]:
        assert name in core.QUALITY_PRESETS


def test_build_format_selector_best():
    assert core.build_format_selector("best") == "bestvideo*+bestaudio/best"


def test_build_format_selector_height_cap():
    sel = core.build_format_selector("720p")
    assert "height<=720" in sel
    assert sel.startswith("bestvideo[height<=720]")
    assert "/best" in sel


def test_build_format_selector_worst():
    assert "worst" in core.build_format_selector("worst")


def test_build_format_selector_audio_only():
    assert core.build_format_selector("best", audio_only=True) == "bestaudio/best"


def test_build_format_selector_unknown_raises():
    import pytest

    with pytest.raises(ValueError):
        core.build_format_selector("9000p")


def test_media_info_from_ytdlp_flat_entry():
    info = {
        "id": "abc123",
        "title": "A Video",
        "webpage_url": "https://example.com/watch/abc123",
        "extractor_key": "Example",
        "uploader": "Someone",
        "duration": 123.0,
        "thumbnail": "https://example.com/t.jpg",
        "view_count": 42,
    }
    meta = core.MediaInfo.from_ytdlp(info)
    assert meta.id == "abc123"
    assert meta.title == "A Video"
    assert meta.is_playlist is False
    assert meta.entry_count == 1


def test_media_info_detects_playlist():
    info = {"id": "pl", "title": "My Playlist", "_type": "playlist",
            "entries": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}
    meta = core.MediaInfo.from_ytdlp(info)
    assert meta.is_playlist is True
    assert meta.entry_count == 3
