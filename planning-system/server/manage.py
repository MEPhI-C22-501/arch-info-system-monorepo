import sys
from .storage import migrate
migrate()
if 'seed' in sys.argv:
    import os
    if os.environ.get('APP_ENV')!='development':raise SystemExit('Seed only in development')
    from .seed import seed
    seed()
print('Migration 001 applied' + ('; synthetic seed applied' if 'seed' in sys.argv else ''))
