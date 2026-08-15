import av
import pytest

from pipeline.video_io import normalize_for_opencv


def _make_clip(path, codec, frames=5, size=(64, 48)):
    container = av.open(path, mode="w")
    stream = container.add_stream(codec, rate=25)
    stream.width, stream.height = size
    stream.pix_fmt = "yuv420p"
    for _ in range(frames):
        frame = av.VideoFrame(size[0], size[1], "yuv420p")
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


def test_h264_input_is_returned_unchanged(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_clip(str(clip), "libx264")
    assert normalize_for_opencv(str(clip)) == str(clip)


def test_non_h264_input_is_transcoded_to_h264(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_clip(str(clip), "libx265")

    result_path = normalize_for_opencv(str(clip))
    assert result_path != str(clip)

    result_container = av.open(result_path)
    try:
        assert result_container.streams.video[0].codec_context.name == "h264"
    finally:
        result_container.close()


def test_empty_file_raises_value_error(tmp_path):
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    with pytest.raises(ValueError):
        normalize_for_opencv(str(empty))
