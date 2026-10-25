"""Keep Compose/container diagnostics free of credentials."""
import json
import re
from urllib.parse import quote


def sanitize(text, values):
    for value in sorted({str(v) for v in values if v}, key=len, reverse=True):
        for encoded in {value, quote(value, safe=''), json.dumps(value)[1:-1]}:
            text = text.replace(encoded, '[redacted]')
    text = re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[redacted-jwt]', text)
    return text
