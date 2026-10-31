import os
from datetime import date, timedelta
from bdshare import get_basic_historical_data

end = date.today() - timedelta(days=3)
start = end - timedelta(days=7)

for source in ("new", "legacy"):
    print(f"\nTesting source: {source}")
    try:
        from bdshare.util import vars as config
        config.DSE_SOURCE = source

        df = get_basic_historical_data(
            str(start), str(end), "GP"
        )

        print("Rows:", len(df))
        print("Columns:", list(df.columns))
        print(df.head(3).to_string())
    except Exception as exc:
        print("FAILED:", type(exc).__name__, str(exc)[:500])
