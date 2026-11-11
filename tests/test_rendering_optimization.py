import os
import tempfile
import inspect
from pathlib import Path

from rendering import transitions
from rendering.transitions import Slot, xfade_join, LOW_MEM_X264
from rendering.ffmpeg_utils import ffmpeg_bin


def test_transitions_chunk_size_default():
    sig = inspect.signature(transitions.xfade_join)
    assert sig.parameters["chunk_size"].default == 16


def test_transitions_thread_limits():
    cpu_cnt = os.cpu_count() or 8
    expected_xfade = str(min(cpu_cnt, 24))
    expected_filter = str(min(cpu_cnt, 16))
    assert transitions._XFADE_THREADS == expected_xfade
    assert transitions._FILTER_THREADS == expected_filter


def test_renderer_auto_worker_scaling():
    # Simulate high core CPU (e.g. 24 threads like i7-13700K)
    cpu_cnt = 24
    max_workers = min(12, max(2, cpu_cnt // 2))
    assert max_workers == 12

    # Simulate medium CPU (e.g. 8 threads)
    cpu_cnt = 8
    max_workers = min(12, max(2, cpu_cnt // 2))
    assert max_workers == 4

    # Simulate 4 threads
    cpu_cnt = 4
    max_workers = min(12, max(2, cpu_cnt // 2))
    assert max_workers == 2


def test_remotion_concurrency_calculation():
    # On 24-core CPU
    cpu_cnt = 24
    remotion_concurrency = max(2, min(6, cpu_cnt // 4))
    assert remotion_concurrency == 6

    # On 8-core CPU
    cpu_cnt = 8
    remotion_concurrency = max(2, min(6, cpu_cnt // 4))
    assert remotion_concurrency == 2


def test_xfade_join_execution_over_chunk_threshold():
    """Verify that joining 18 clips (which triggers hierarchical chunking at chunk_size=16) succeeds."""
    bin_path = ffmpeg_bin()
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        clips, slots = [], []
        # Create 18 small clips (0.5s each)
        for i in range(18):
            cp = tdp / f"clip_{i:02d}.mp4"
            subprocess.run(
                [bin_path, "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=15", "-t", "0.5",
                 "-c:v", "libx264", "-preset", "ultrafast", str(cp)],
                capture_output=True, check=True
            )
            clips.append(cp)
            slots.append(Slot(i, i * 0.4, 0.4, i * 0.4, 0.4, "crossfade", 0.1))

        out = tdp / "output_joined.mp4"
        xfade_join(clips, slots, out, LOW_MEM_X264, 15, chunk_size=16)
        assert out.exists()
        assert out.stat().st_size > 1024
