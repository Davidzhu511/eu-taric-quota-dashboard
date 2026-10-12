"""Preserve opening-day allocation evidence; never infer allocation from utilisation."""
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
                p = item.get('allocated_percentage')
                if (item.get('code') == code and item.get('validity_period') == period
                    and item.get('origin') == origin and not item.get('stale') and not item.get('error')
                    and item.get('balance_kg') == 0 and item.get('exhaustion_date') == datetime.fromisoformat(start).strftime('%d-%m-%Y')
                    and item.get('last_import_date') == item.get('exhaustion_date')
                    and isinstance(p, (int, float)) and 0 < p <= 100 and item.get('last_allocation_date')):
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


def main():
    data = ROOT/'data'
    eu=json.loads((data/'current.json').read_text())
    uk=json.loads((data/'uk/current.json').read_text())
    snapshots=[(p.name, json.loads(p.read_text())) for p in sorted((data/'history').glob('*.json')) if p.name!='index.json']
    result=summarize(eu,snapshots,uk)
    (data/'quarterly-summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')

if __name__ == '__main__':
    main()
