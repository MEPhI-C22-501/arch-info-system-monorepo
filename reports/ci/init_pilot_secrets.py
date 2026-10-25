"""Initialize missing local-demo credentials only in ~/secrets.env.

Existing values and unrelated keys are preserved. Values never reach stdout,
argv, project files or workflow artifacts. This is not a production issuer.
"""
import fcntl
import os
import secrets
import sys
from pathlib import Path
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'pilots'))
from launch import REQUIRED


def initialize():
    path = Path.home()/'secrets.env'
    descriptor = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        text = stream.read()
        stream.seek(0)
        values = dotenv_values(stream=stream)
        missing = [name for name in REQUIRED if not values.get(name)]
        os.fchmod(stream.fileno(), 0o600)
        if missing:
            if text and not text.endswith('\n'): stream.write('\n')
            for name in missing: stream.write(name+'='+secrets.token_urlsafe(48)+'\n')
            stream.flush(); os.fsync(stream.fileno())
    print('Local pilot credentials initialized; added keys: '+str(len(missing)))
    return len(missing)


if __name__ == '__main__': initialize()
