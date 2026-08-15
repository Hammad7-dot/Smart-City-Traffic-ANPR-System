# implements FR8 — upload-path robustness (see decisions.md D-017)
"""Normalize uploaded video codecs so OpenCV/Ultralytics can read them.

OpenCV's Windows pip wheels bundle a minimal FFMPEG build with no HEVC/H.265
decoder, so phone-recorded uploads (the common HEVC default) silently fail
cv2.VideoCapture.isOpened(). PyAV wraps a fuller FFMPEG build, so it's used
here to re-encode anything that isn't already H.264 before the pipeline
touches it.
"""

import os
import tempfile

import av


def normalize_for_opencv(input_path: str) -> str:
    """Returns a path to an H.264 .mp4 that cv2.VideoCapture can open.

    If `input_path` is already H.264, returns it unchanged. Otherwise
    transcodes to a new temp .mp4 and returns that path instead.
    """
    if os.path.getsize(input_path) == 0:
        raise ValueError(f"Video file is empty: {input_path}")

    in_container = av.open(input_path)
    try:
        in_stream = in_container.streams.video[0]
        if in_stream.codec_context.name == "h264":
            return input_path

        out_fd, out_path = tempfile.mkstemp(suffix=".mp4")
        os.close(out_fd)

        out_container = av.open(out_path, mode="w")
        try:
            out_stream = out_container.add_stream("libx264", rate=in_stream.average_rate)
            out_stream.width = in_stream.codec_context.width
            out_stream.height = in_stream.codec_context.height
            out_stream.pix_fmt = "yuv420p"

            for frame in in_container.decode(in_stream):
                for packet in out_stream.encode(frame):
                    out_container.mux(packet)

            for packet in out_stream.encode():
                out_container.mux(packet)
        finally:
            out_container.close()

        return out_path
    finally:
        in_container.close()
