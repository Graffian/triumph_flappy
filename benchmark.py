"""
benchmark.py — measure raw WDA screenshot latency. Run this FIRST.

< 60ms median  -> fine at 15+ fps
60-100ms       -> workable, prefetch thread essential
> 100ms        -> tight; lower WDA screenshot quality or use tidevice instead of iproxy
"""

import time

import numpy as np

from wda import get_session, take_screenshot


def main():
    get_session()

    times = []
    for i in range(20):
        t0 = time.perf_counter()
        take_screenshot()
        times.append(time.perf_counter() - t0)
        print(f"  {i+1:02d}: {times[-1]*1000:.0f}ms")

    print(f"\n  Median: {np.median(times)*1000:.0f}ms  ->  ~{1/np.median(times):.1f} fps")
    print(f"  Min:    {min(times)*1000:.0f}ms")
    print(f"  Max:    {max(times)*1000:.0f}ms")


if __name__ == "__main__":
    main()