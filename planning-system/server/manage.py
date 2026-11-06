import sys
import json
from .storage import migrate
migrate()
if 'sync-hr' in sys.argv:
    from .reference_manager import ReferenceManagerClient, ReferenceManagerError, refresh_cache
    try:
        print(json.dumps(refresh_cache(ReferenceManagerClient.from_env()), ensure_ascii=False))
    except ReferenceManagerError as exc:
        raise SystemExit(str(exc)) from None
    raise SystemExit(0)
if 'seed' in sys.argv:
    import os
    if os.environ.get('APP_ENV')!='development':raise SystemExit('Seed only in development')
    from .seed import seed
    seed()
print('Migration 001 applied' + ('; synthetic seed applied' if 'seed' in sys.argv else ''))
