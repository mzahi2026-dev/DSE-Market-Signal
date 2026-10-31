from datetime import date, timedelta
from backend.collector import collect
from backend.db import connect

end = date.today() - timedelta(days=3)
start = end - timedelta(days=6)

print("\n=== DSE MANUAL SCRAPING TEST ===")
print("Stock: GP")
print("Start:", start)
print("End:", end)

try:
    result = collect("GP", str(start), str(end))
    print("\nCollection Result:", result)

    with connect() as con:
        count = con.execute(
            "SELECT COUNT(*) FROM prices WHERE symbol=?",
            ("GP",)
        ).fetchone()[0]

        rows = con.execute(
            """SELECT date, close, volume
               FROM prices WHERE symbol=?
               ORDER BY date DESC LIMIT 5""",
            ("GP",)
        ).fetchall()

    print("Total GP rows in database:", count)
    print("Recent stored records:", rows)

    if result["fetched"] > 0 and count > 0:
        print("\nPASS: REAL DATA COLLECTED AND STORED")
    else:
        print("\nFAIL: NO REAL DATA COLLECTED")

except Exception as exc:
    print("\nFAIL:", type(exc).__name__, str(exc))
