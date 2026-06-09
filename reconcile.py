#!/usr/bin/env python3
"""Reconciliation script for Ein Sprung bot - checks financial integrity."""

import argparse
import sqlite3
import sys
from datetime import datetime
from config import DBPATH

def reconcile(fix=False):
    conn = sqlite3.connect(DBPATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Expected fees from tasks
    cur.execute("""
        SELECT COALESCE(SUM(ROUND(rewardgross - rewardnet, 8)), 0.0) as expected_fees,
               COUNT(*) as task_count
        FROM tasks 
        WHERE status IN ('completed')
    """)
    row = cur.fetchone()
    expected = round(row["expected_fees"], 8)
    task_count = row["task_count"]

    # Actual collected
    cur.execute("SELECT totalcollectedfees FROM adminrevenue WHERE id=1")
    actual_row = cur.fetchone()
    actual = round(actual_row["totalcollectedfees"], 8) if actual_row else 0.0

    print(f"\n{'='*60}")
    print("EIN SPRUNG — FINANCIAL RECONCILIATION")
    print(f"{'='*60}")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {DBPATH}\n")

    print(f"Tasks processed (completed): {task_count}")
    print(f"Expected fees (gross - net): {expected:.8f} USDT")
    print(f"Actual collected in adminrevenue: {actual:.8f} USDT")

    diff = round(expected - actual, 8)

    if abs(diff) < 1e-6:
        print("\n✅ PERFECT MATCH - No discrepancies found.")
    else:
        print(f"\n⚠️  DISCREPANCY: {diff:+.8f} USDT")
        if diff > 0:
            print("   → Missing fees in admin table")
        else:
            print("   → Over-collected fees")

        # Show suspect tasks
        cur.execute("""
            SELECT taskid, clientid, executorid, rewardgross, rewardnet, status, completedat
            FROM tasks 
            WHERE status = 'completed'
            ORDER BY taskid DESC LIMIT 20
        """)
        print("\nRecent completed tasks:")
        for t in cur.fetchall():
            fee = round(t["rewardgross"] - t["rewardnet"], 8)
            print(f"  #{t['taskid']} | {fee:.2f} USDT | {t['status']}")

    if fix and abs(diff) > 1e-6 and diff > 0:
        print(f"\n🔧 Auto-fixing: Adding missing {diff:.8f} USDT to adminrevenue...")
        cur.execute(
            "UPDATE adminrevenue SET totalcollectedfees = totalcollectedfees + ? WHERE id=1",
            (diff,)
        )
        conn.commit()
        print("✅ Fixed.")
    elif fix and diff < 0:
        print("\n⚠️ Negative discrepancy - manual review recommended.")

    conn.close()
    return abs(diff) < 1e-6


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ein Sprung Financial Reconciliation")
    parser.add_argument("--fix", action="store_true", help="Automatically correct small positive discrepancies")
    args = parser.parse_args()

    success = reconcile(fix=args.fix)
    sys.exit(0 if success else 1)
