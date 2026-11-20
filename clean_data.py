"""Clean the OLA dataset and load it into SQLite.

Usage:  python clean_data.py [path/to/OLA_DataSet.xlsx]
Output: data/ola_clean.csv, data/ola.db (table `rides`), data/vehicle_icons.csv
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("OLA_DataSet.xlsx")
OUT = Path("data")
OUT.mkdir(exist_ok=True)

raw = pd.read_excel(SRC, sheet_name="July")
print(f"Loaded {len(raw):,} rows, {raw.shape[1]} columns")

df = raw.copy()
df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

# 1. Standardize text
text_cols = df.select_dtypes(include=["object", "string"]).columns
for c in text_cols:
    df[c] = df[c].astype("string").str.strip()

# 2. Data types and derived time features
df["booking_date"] = pd.to_datetime(df["date"]).dt.normalize()
df["booking_time"] = df["time"].astype(str)
df["hour"] = pd.to_datetime(df["booking_time"], format="%H:%M:%S").dt.hour
df["day_name"] = df["booking_date"].dt.day_name()
df["is_weekend"] = df["booking_date"].dt.dayofweek.isin([5, 6]).map({True: "Weekend", False: "Weekday"})
df["time_of_day"] = pd.cut(
    df["hour"], bins=[-1, 5, 11, 16, 20, 23],
    labels=["Night", "Morning", "Afternoon", "Evening", "Late evening"],
).astype(str)

# 3. Missing values
#    - Categorical fields are blank when the field does not apply to the booking
#      (e.g. payment method for a cancelled ride): label them explicitly.
cat_fill = {
    "canceled_rides_by_customer": "Not Applicable",
    "canceled_rides_by_driver": "Not Applicable",
    "incomplete_rides": "Not Applicable",
    "incomplete_rides_reason": "Not Applicable",
    "payment_method": "Not Applicable",
}
for c, v in cat_fill.items():
    df[c] = df[c].fillna(v)
#    - Numeric fields (ratings, turnaround times) are left as NULL: imputing a rating
#      for a ride that never happened would distort averages.

# 4. Validation
assert df["booking_id"].is_unique, "duplicate booking ids"
assert df["driver_ratings"].dropna().between(1, 5).all()
assert df["customer_rating"].dropna().between(1, 5).all()
assert (df["booking_value"] > 0).all()

df = df.rename(columns={
    "canceled_rides_by_customer": "cancel_reason_customer",
    "canceled_rides_by_driver": "cancel_reason_driver",
    "incomplete_rides": "incomplete_ride",
    "driver_ratings": "driver_rating",
})
cols = [
    "booking_id", "booking_date", "booking_time", "hour", "day_name", "is_weekend", "time_of_day",
    "booking_status", "customer_id", "vehicle_type", "pickup_location", "drop_location",
    "v_tat", "c_tat", "cancel_reason_customer", "cancel_reason_driver",
    "incomplete_ride", "incomplete_rides_reason", "booking_value", "payment_method",
    "ride_distance", "driver_rating", "customer_rating",
]
df = df[cols].rename(columns={"incomplete_rides_reason": "incomplete_reason"})
df["booking_date"] = df["booking_date"].dt.strftime("%Y-%m-%d")

# 5. Vehicle icons (Sheet2 has no header row)
icons = pd.read_excel(SRC, sheet_name="Sheet2", header=None, names=["vehicle_type", "icon_url"])
icons.to_csv(OUT / "vehicle_icons.csv", index=False)

df.to_csv(OUT / "ola_clean.csv", index=False)
with sqlite3.connect(OUT / "ola.db") as con:
    df.to_sql("rides", con, if_exists="replace", index=False)
    con.execute("CREATE INDEX idx_status ON rides(booking_status)")
    con.execute("CREATE INDEX idx_vehicle ON rides(vehicle_type)")
    con.execute("CREATE INDEX idx_customer ON rides(customer_id)")
    con.execute("CREATE INDEX idx_date ON rides(booking_date)")
print(f"Saved {len(df):,} clean rows -> {OUT}/ola.db and {OUT}/ola_clean.csv")
print(df["booking_status"].value_counts().to_string())
