from datetime import date, timedelta
from scripts.backfill import make_batches, subtract_months

def test_six_months():
    assert subtract_months(date(2026,10,30),6) == date(2026,4,30)

def test_batch_size():
    batches = make_batches(date(2026,4,30),date(2026,10,30))
    assert batches[0][0] == date(2026,4,30)
    assert batches[-1][1] == date(2026,10,30)
    for a,b in batches:
        assert (b-a).days <= 6

def test_continuity():
    batches = make_batches(date(2026,4,30),date(2026,10,30))
    for i in range(1,len(batches)):
        assert batches[i][0] == batches[i-1][1] + timedelta(days=1)
