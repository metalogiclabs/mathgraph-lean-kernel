"""Small Linux command runner retaining exact commands and per-process resources."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def run(command, log, cwd=None, env=None, timeout=600):
    """wait4 supplies this command's CPU/RSS rather than cumulative child maxima."""
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    timed_out = False
    with log.with_suffix('.stdout').open('wb') as stdout, log.with_suffix('.stderr').open('wb') as stderr:
        process = subprocess.Popen([str(x) for x in command], cwd=cwd, env=env,
                                   stdout=stdout, stderr=stderr, start_new_session=True)
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.perf_counter() - start > timeout:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                _, status, usage = os.wait4(process.pid, 0)
                break
            time.sleep(0.01)
        process.returncode = os.waitstatus_to_exitcode(status)
    record = dict(command=[str(x) for x in command], cwd=str(cwd) if cwd else None,
                  returncode=process.returncode, timed_out=timed_out,
                  wall_seconds=time.perf_counter() - start,
                  cpu_seconds=usage.ru_utime + usage.ru_stime, max_rss_kib=usage.ru_maxrss,
                  stdout_path=str(log.with_suffix('.stdout')), stderr_path=str(log.with_suffix('.stderr')))
    log.with_suffix('.json').write_text(json.dumps(record, indent=2) + '\n')
    return record
