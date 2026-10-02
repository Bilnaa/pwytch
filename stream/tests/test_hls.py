from app import hls


def test_first_connection_is_capped_and_never_upscaled(monkeypatch):
    monkeypatch.setattr(hls.settings, "video_height", 1080)
    assert "min(1080,max(ih,iw*9/16))" in hls.video_filter(None)


def test_known_size_is_kept():
    assert hls.video_filter(720).startswith("scale=1280:720:")
    assert "pad=1280:720:" in hls.video_filter(720)
