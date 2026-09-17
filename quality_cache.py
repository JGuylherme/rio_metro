"""Content fingerprints for derived datasets; cache presence alone is insufficient."""
import hashlib
import json
from pathlib import Path


def fingerprint(paths,algorithm):
    hashes={}
    for path in paths:
        path=Path(path)
        with path.open('rb') as source:hashes[str(path)]=hashlib.file_digest(source,'sha256').hexdigest()
    return hashlib.sha256(json.dumps({'inputs':hashes,'algorithm':algorithm},sort_keys=True).encode()).hexdigest()
