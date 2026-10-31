"""DSE Trading Calendar and Holiday Management.

Dhaka Stock Exchange (DSE) trading schedule:
- Trading days: Sunday through Thursday
- Weekend (closed): Friday and Saturday
- Trading hours: 10:00 to 14:30 Asia/Dhaka
- Market holidays: Government holidays, religious holidays (Eid, Puja), and Bank holidays.
"""

from datetime import date, datetime, timedelta
from typing import List, Set, Tuple
from zoneinfo import ZoneInfo

DHAKA_TZ = ZoneInfo("Asia/Dhaka")

# Official Bangladesh / DSE Holidays for 2026 (YYYY-MM-DD)
DSE_HOLIDAYS_2026 = {
    # New Year / Shab-e-Barat / Language Day
    "2026-02-04",  # Shab-e-Barat (tentative)
    "2026-02-21",  # Martyrs' Day & International Mother Language Day
    "2026-03-17",  # Father of the Nation birth anniversary / Children's Day
    "2026-03-20",  # Shab-e-Qadr
    "2026-03-21",  # Jumatul Wida
    "2026-03-22", "2026-03-23", "2026-03-24",  # Eid-ul-Fitr holidays
    "2026-03-26",  # Independence & National Day
    "2026-04-14",  # Bengali New Year (Pohela Boishakh)
    "2026-05-01",  # May Day (also a Friday in 2026)
    "2026-05-04",  # Buddha Purnima
    # Eid-ul-Adha 2026
    "2026-05-25", "2026-05-26", "2026-05-27", "2026-05-28", "2026-05-29", "2026-05-30", "2026-05-31",
    # Half-yearly Bank Holiday
    "2026-07-01",
    # Ashura
    "2026-07-16",
    # National Revolution / Mass Uprising Day
    "2026-08-05",
    # National Mourning Day / Janmashtami
    "2026-08-15",
    "2026-08-26",  # Janmashtami
    # Eid-e-Miladunnabi
    "2026-09-04",
    # Durga Puja (Maha Ashtami / Bijoya Dashami)
    "2026-10-20", "2026-10-21", "2026-10-22",
    # Victory Day & Christmas & Year-end Bank Holiday
    "2026-12-16",  # Victory Day
    "2026-12-25",  # Christmas
    "2026-12-31",  # Year-end Bank Holiday
}

KNOWN_HOLIDAYS = set(DSE_HOLIDAYS_2026)

def is_dse_weekend(d: date) -> bool:
    """Return True if d falls on a DSE weekend (Friday=4 or Saturday=5)."""
    return d.weekday() in (4, 5)

def is_dse_holiday(d: date, holidays: Set[str] = None) -> bool:
    """Return True if d is a known holiday."""
    h_set = holidays if holidays is not None else KNOWN_HOLIDAYS
    return d.isoformat() in h_set

def is_trading_day(d: date, holidays: Set[str] = None) -> bool:
    """Return True if d is a valid DSE trading day (Sunday-Thursday and not a holiday)."""
    if is_dse_weekend(d):
        return False
    if is_dse_holiday(d, holidays):
        return False
    return True

def get_trading_days(start: date, end: date, holidays: Set[str] = None) -> List[date]:
    """Return list of all scheduled DSE trading days in [start, end]."""
    cur = start
    trading_days = []
    while cur <= end:
        if is_trading_day(cur, holidays):
            trading_days.append(cur)
        cur += timedelta(days=1)
    return trading_days

def audit_trading_days(stored_dates: Set[str], start: date, end: date) -> Tuple[List[str], List[str]]:
    """Compare stored date strings with expected DSE trading calendar.
    
    Returns:
        (missing_trading_days, verified_holidays_in_range)
    """
    missing = []
    holidays = []
    cur = start
    while cur <= end:
        iso = cur.isoformat()
        if not is_dse_weekend(cur):
            if is_dse_holiday(cur):
                holidays.append(iso)
            elif iso not in stored_dates:
                missing.append(iso)
        cur += timedelta(days=1)
    return missing, holidays

