import os
import sys

PERF = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [PERF, os.path.join(PERF, "job")]
