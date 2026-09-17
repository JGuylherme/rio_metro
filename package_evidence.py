"""Bundle review evidence after validation; keep it separate from game assets."""
import hashlib
import json
import zipfile
from map_settings import ROOT


def main():
    report=json.loads((ROOT/'validation_report.json').read_text())
    archive=ROOT/'dist/RIO.zip'
    if archive.stat().st_size!=report['archive']['bytes']:
        raise ValueError('Release differs from the validated archive; validate again')
    with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    metadata={'version':report['version'],'map_archive_sha256':digest,
        'map_archive_bytes':archive.stat().st_size,'purpose':'Review evidence only; not a game asset'}
    (ROOT/'dist/release_integrity.json').write_text(json.dumps(metadata,indent=2)+'\n')
    names=['METHODOLOGY.md','QUALITY_REVIEW.md','REGISTRY_DESCRIPTION.md','REVIEW_REQUEST.md',
        'RELEASE_NOTES.md','EMPLOYMENT.md','SPECIAL_DEMAND.md','PIPELINE_AUDIT.md',
        'data-quality.proposed.json','quality_config.json','special_demand_sites.json',
        'validation_report.json','quality_score.py']
    files=[ROOT/name for name in names]+sorted((ROOT/'reports/quality').glob('*'))
    files+=sorted((ROOT/'sources').glob('quality_downloads_*.json'))
    files+=[ROOT/'dist/special_demand_report.json',ROOT/'dist/release_integrity.json']
    target=ROOT/'dist/quality-evidence.zip';temporary=target.with_suffix('.tmp')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for path in files:
            if path.is_file():output.write(path,str(path.relative_to(ROOT)))
    with zipfile.ZipFile(temporary) as output:
        if output.testzip() is not None:raise ValueError('Evidence ZIP failed integrity check')
    temporary.replace(target)
    print(f'Review evidence: {target} ({target.stat().st_size:,} bytes)')


if __name__=='__main__':main()
