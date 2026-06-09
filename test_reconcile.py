import os
import sqlite3
import tempfile
import reconcile

def setup_db(path):
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            taskid INTEGER PRIMARY KEY,
            clientid INTEGER,
            executorid INTEGER,
            rewardgross REAL,
            rewardnet REAL,
            status TEXT,
            completedat TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS adminrevenue (
            id INTEGER PRIMARY KEY,
            totalcollectedfees REAL
        )
    """)
    conn.commit()
    return conn

def test_reconcile_rounding_exact_match():
    tf = tempfile.NamedTemporaryFile(delete=False)
    tf.close()
    dbpath = tf.name
    
    try:
        conn = setup_db(dbpath)
        cur = conn.cursor()
        
        # Simulates your 10% escrow platform fee cut
        cur.execute("""
            INSERT INTO tasks (taskid, clientid, executorid, rewardgross, rewardnet, status, completedat)
            VALUES (1, 123, 456, 10.0, 9.0, 'completed', CURRENT_TIMESTAMP)
        """)
        cur.execute("INSERT INTO adminrevenue (id, totalcollectedfees) VALUES (1, 1.0)")
        conn.commit()
        conn.close()

        reconcile.DBPATH = dbpath
        
        discrepancy_free = reconcile.reconcile(fix=False)
        assert discrepancy_free is True
        
    finally:
        if os.path.exists(dbpath):
            os.unlink(dbpath)
