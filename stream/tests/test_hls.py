from app import hls


def test_first_connection_is_capped_and_never_upscaled(monkeypatch):
    monkeypatch.setattr(hls.settings, "video_height", 1080)
    assert "min(1080,max(ih,iw*9/16))" in hls.video_filter(None)


def test_known_size_is_kept():
    # 854x480 comes out in 852x478: the width must not be worked out again from the height
    assert hls.video_filter((852, 478)).startswith("scale=852:478:")
    assert "pad=852:478:" in hls.video_filter((852, 478))
