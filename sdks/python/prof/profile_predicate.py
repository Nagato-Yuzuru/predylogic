# /// script
# requires-python = ">=3.10,<=3.13"
# dependencies = []
# ///


import argparse
import contextlib
import sys
import time

from benchmarks.predicate.utils import ClosureFactory, CurrentFactory, LogicFactory


def run_workload(factory: LogicFactory, depth: int, iterations: int):
    rule = factory.make_chain(depth)
    duration = 5.0
    start_time = time.perf_counter()
    while iterations > 0 or time.perf_counter() - start_time < duration:
        with contextlib.suppress(RecursionError):
            rule("obj")
        iterations -= 1


def main():
    parser = argparse.ArgumentParser(description="Profile predicate logic")
    parser.add_argument("--depth", type=int, default=1500, help="Recursion depth (default: 1500)")
    parser.add_argument("--iter", type=int, default=1000, help="Number of execution iterations")
    parser.add_argument("--mode", choices=["closure", "current"], default="closure", help="Engine mode")

    args = parser.parse_args()
    sys.setrecursionlimit(max(sys.getrecursionlimit(), args.depth + 500))

    factory = ClosureFactory() if args.mode == "closure" else CurrentFactory()

    print(f"Starting Profile: Mode={args.mode}, Depth={args.depth}")

    run_workload(factory, args.depth, args.iter)
    print("Profile target finished.")


if __name__ == "__main__":
    main()
