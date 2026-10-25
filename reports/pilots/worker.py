"""A sequential ETL schedule: no overlap, no catch-up bursts, graceful stop."""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def healthy(path, max_age):
    try:
        state = json.loads(Path(path).read_text())
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(state['completed_at'])).total_seconds()
        return state['status'] == 'LOADED' and 0 <= age <= max_age
    except (OSError, ValueError, KeyError, TypeError):
        return False


def repeat(job, every, stop, *, max_runs=0, state_file=None, clock=time.monotonic):
    if every <= 0 or max_runs < 0:
        raise ValueError('Positive interval and nonnegative run limit required')
    deadline, runs, result = clock(), 0, None
    while not stop.is_set():
        try:
            result = job()
        except Exception:
            # Dependency exception strings can include DSNs. Keep them private.
            result = {'status': 'REJECTED', 'error': 'DEPENDENCY_UNAVAILABLE'}
        if state_file:
            target = Path(state_file)
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps({'completed_at': datetime.now(timezone.utc).isoformat(),
                                             'status': result['status']}))
            temporary.replace(target)
        print(json.dumps(result), flush=True)
        runs += 1
        if max_runs and runs >= max_runs:
            return 0 if result['status'] == 'LOADED' else 1
        deadline += every
        current = clock()
        if deadline <= current:
            deadline = current+every  # Missed ticks are skipped, not replayed.
        stop.wait(deadline-current)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--health', required=True)
    parser.add_argument('--max-age', type=float, default=180)
    args = parser.parse_args()
    sys.exit(0 if healthy(args.health, args.max_age) else 1)
