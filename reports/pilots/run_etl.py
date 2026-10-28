"""Run an adapter using only credentials explicitly stored in ~/secrets.env."""
import os
import sys
from pathlib import Path
from dotenv import dotenv_values
import etl

if __name__ == '__main__':
    path = Path.home() / 'secrets.env'
    values = dotenv_values(path) if path.is_file() else {}
    if not values.get('REPORTS_DATABASE_URL'):
        print('Missing REPORTS_DATABASE_URL in ~/secrets.env')
        sys.exit(2)
    for name in ['REPORTS_DATABASE_URL', 'REPORTS_SOURCE_TOKEN']:
        os.environ.pop(name, None)
        if values.get(name): os.environ[name] = values[name]
    sys.exit(etl.main())
