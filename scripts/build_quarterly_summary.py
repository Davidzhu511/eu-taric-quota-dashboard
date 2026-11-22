"""Preserve opening-day allocation evidence; never infer allocation from utilisation."""
import argparse
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [('1A', '099600', 'Other countries'), ('2', '099602', 'Other countries'), ('4A', '099605', 'Other countries'), ('4B', '099838', 'China')]


def period_start(period):
    try:
        return datetime.strptime(period.split(' - ')[0], '%d-%m-%Y').date().isoformat()
    except (ValueError, AttributeError):
        return None


def opening_record(item, code, origin, period, start):
    percentage = item.get('allocated_percentage')
    opening_date = datetime.fromisoformat(start).strftime('%d-%m-%Y')
    return (item.get('code') == code and item.get('validity_period') == period
            and item.get('origin') == origin and not item.get('stale') and not item.get('error')
            and item.get('balance_kg') == 0 and item.get('exhaustion_date') == opening_date
            and item.get('last_import_date') == opening_date
            and isinstance(percentage, (int, float)) and 0 < percentage <= 100
            and bool(item.get('last_allocation_date')))


def summarize(eu, snapshots, uk):
    period = eu.get('meta', {}).get('validity_period', '')
    start = period_start(period)
    rows = []
    for category, code, origin in TARGETS:
        evidence = []
        for file, data in snapshots:
            official = data.get('meta', {}).get('official_update_date')
            if not start or not official or official < start:
                continue
            for item in data.get('items', []):
                if opening_record(item, code, origin, period, start):
                    evidence.append((official, file, item))
        evidence.sort(key=lambda x: (x[0], x[1]))
        row = dict(category=category, code=code, origin=origin, declaration_date=start,
                   validity_period=period, allocation_pct=None, weighted_duty_pct=None, status='unavailable', evidence=[])
        # Different positive ratios require review; latest zero does not erase earlier evidence.
        if evidence and len({Decimal(str(x[2]['allocated_percentage'])) for x in evidence}) == 1:
            official, file, item = evidence[0]
            p = Decimal(str(item['allocated_percentage']))
            row.update(allocation_pct=float(p), weighted_duty_pct=float((100-p)*Decimal('0.5')),
                       status='historical_allocation', allocation_date=item['last_allocation_date'],
                       official_update_date=official, checked_at=None,
                       evidence=[{'file': f, 'official_update_date': o, 'detail_url': i.get('detail_url', '')} for o, f, i in evidence])
        elif evidence:
            row['status'] = 'conflicting_evidence'
        rows.append(row)
    ukrow = dict(category='4', code='058608', origin='Other countries',
                 validity_period=uk.get('meta', {}).get('validity_period'),
                 declaration_date=next((x.get('validity_start_date') for x in uk.get('items', []) if x.get('code')=='058608'), None),
                 allocation_pct=None, weighted_duty_pct=None, status='allocation_not_published', evidence=[])
    return {'eu': rows, 'uk': [ukrow], 'out_of_quota_duty_pct': 50}


def preserve_previous(data, previous):
    """Keep opening quantities that a same-date refresh replaced in the daily archive."""
    meta = previous['meta']
    period = meta.get('validity_period')
    start = period_start(period)
    official = meta.get('official_update_date')
    if not start or not official or official < start:
        return
    current_file = data / 'history' / f'{official}.json'
    current_rows = json.loads(current_file.read_text())['items'] if current_file.is_file() else []
    retained = {(r['code'], r.get('validity_period'), r.get('allocated_percentage'), r.get('last_allocation_date'))
                for r in current_rows if not r.get('stale') and not r.get('error')}
    rows = [row for row in previous['items']
            if any(opening_record(row, code, origin, period, start) for _, code, origin in TARGETS)
            and (row['code'], period, row['allocated_percentage'], row['last_allocation_date']) not in retained]
    if rows:
        content = json.dumps({'meta': meta, 'items': rows}, ensure_ascii=False, indent=2) + '\n'
        fingerprint = hashlib.sha256(content.encode()).hexdigest()[:16]
        folder = data / 'history' / 'opening-evidence'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f'{official}-{fingerprint}.json').write_text(content, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--previous', type=Path)
    args = parser.parse_args()
    data = ROOT/'data'
    if args.previous:
        preserve_previous(data, json.loads(args.previous.read_text()))
    eu=json.loads((data/'current.json').read_text())
    uk=json.loads((data/'uk/current.json').read_text())
    history = data / 'history'
    snapshots = [(str(p.relative_to(history)), json.loads(p.read_text()))
                 for p in sorted(history.rglob('*.json')) if p.name != 'index.json']
    result=summarize(eu,snapshots,uk)
    (data/'quarterly-summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')

if __name__ == '__main__':
    main()
