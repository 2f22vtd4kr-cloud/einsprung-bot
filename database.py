"""Async SQLite layer with strict atomic financial helpers."""
import aiosqlite
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

from config import DBPATH, PLATFORMFEEPCT

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegramid INTEGER PRIMARY KEY,
    username TEXT,
    clientrating REAL DEFAULT 5.0,
    executorrating REAL DEFAULT 5.0,
    clientreviewscount INTEGER DEFAULT 0,
    executorreviewscount INTEGER DEFAULT 0,
    balanceusdt REAL DEFAULT 0.0,
    frozenusdt REAL DEFAULT 0.0,
    isblocked INTEGER DEFAULT 0,
    isshadowbanned INTEGER DEFAULT 0,
    disputesinitiated INTEGER DEFAULT 0,
    disputeslost INTEGER DEFAULT 0,
    isverified INTEGER DEFAULT 0,
    notificationcategories TEXT DEFAULT '[]',
    createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    taskid INTEGER PRIMARY KEY AUTOINCREMENT,
    channelmessageid INTEGER DEFAULT NULL,
    clientid INTEGER NOT NULL,
    executorid INTEGER DEFAULT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    deadline TEXT,
    category TEXT DEFAULT 'Allgemein',
    attachments TEXT DEFAULT NULL,
    rewardgross REAL NOT NULL,
    rewardnet REAL NOT NULL,
    status TEXT CHECK(status IN ('open','inprogress','completed','dispute','cancelled')) NOT NULL,
    isdirect INTEGER DEFAULT 0,
    targetexecutoridentity TEXT DEFAULT NULL,
    createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    claimedat TIMESTAMP DEFAULT NULL,
    completedat TIMESTAMP DEFAULT NULL,
    disputedat TIMESTAMP DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS dealsessions (
    sessionid INTEGER PRIMARY KEY AUTOINCREMENT,
    taskid INTEGER UNIQUE NOT NULL,
    clientid INTEGER NOT NULL,
    executorid INTEGER NOT NULL,
    roomtoken TEXT UNIQUE NOT NULL,
    status TEXT CHECK(status IN ('active','closed','disputed')) NOT NULL,
    initializedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dealmessages (
    messageid INTEGER PRIMARY KEY AUTOINCREMENT,
    taskid INTEGER NOT NULL,
    senderid INTEGER NOT NULL,
    messagetype TEXT NOT NULL,
    fileid TEXT DEFAULT NULL,
    contentpreview TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS adminrevenue (
    id INTEGER PRIMARY KEY DEFAULT 1,
    totalcollectedfees REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS paymentinvoices (
    invoiceid TEXT PRIMARY KEY,
    userid INTEGER NOT NULL,
    amountusdt REAL NOT NULL,
    status TEXT NOT NULL,   -- pending | paid | expired
    createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payouts (
    spendid TEXT PRIMARY KEY,
    userid INTEGER NOT NULL,
    amountusdt REAL NOT NULL,
    status TEXT NOT NULL,   -- pending | success | failed | rolledback
    response TEXT,
    createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idxtasksstatus ON tasks(status);
CREATE INDEX IF NOT EXISTS idxtasksclient ON tasks(clientid);
CREATE INDEX IF NOT EXISTS idxtasksexecutor ON tasks(executorid);
CREATE INDEX IF NOT EXISTS idxsessionsstatus ON dealsessions(status);
CREATE INDEX IF NOT EXISTS idxmessagestask ON dealmessages(taskid);
"""

async def initdb() -> None:
    async with aiosqlite.connect(DBPATH) as db:
        await db.executescript(SCHEMA)
        await db.execute(
            "INSERT OR IGNORE INTO adminrevenue (id, totalcollectedfees) VALUES (1, 0.0)"
        )
        await db.commit()

@asynccontextmanager
async def tx():
    """Atomic transaction context. Rolls back on any exception."""
    db = await aiosqlite.connect(DBPATH)
    db.row_factory = aiosqlite.Row
    try:
        await db.execute("BEGIN IMMEDIATE")
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()

@asynccontextmanager
async def conn():
    """Read-only connection (no explicit transaction)."""
    db = await aiosqlite.connect(DBPATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

# ---------- Users ----------

async def ensureuser(telegramid: int, username: Optional[str]) -> None:
    async with tx() as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegramid, username, balanceusdt, frozenusdt) "
            "VALUES (?, ?, 0.0, 0.0)",
            (telegramid, username or ""),
        )
        # keep username fresh
        await db.execute(
            "UPDATE users SET username = ? WHERE telegramid = ?",
            (username or "", telegramid),
        )

async def getuser(telegramid: int) -> Optional[aiosqlite.Row]:
    async with conn() as db:
        cur = await db.execute("SELECT * FROM users WHERE telegramid = ?", (telegramid,))
        return await cur.fetchone()

# ---------- Atomic financial helpers ----------

async def freezefunds(userid: int, amount: float) -> None:
    """Move amount from balanceusdt → frozenusdt. Raises on insufficient funds."""
    if amount <= 0:
        raise ValueError("Betrag muss positiv sein.")
    async with tx() as db:
        cur = await db.execute(
            "SELECT balanceusdt FROM users WHERE telegramid = ?", (userid,)
        )
        row = await cur.fetchone()
        if not row or row["balanceusdt"] < amount - 1e-9:
            raise ValueError("Unzureichendes Guthaben.")
        await db.execute(
            "UPDATE users SET balanceusdt = balanceusdt - ?, "
            "frozenusdt = frozenusdt + ? WHERE telegramid = ?",
            (amount, amount, userid),
        )

async def releasefundstoexecutor(
    clientid: int,
    executorid: int,
    gross: float,
    net: float,
) -> None:
    """
    Move gross from client.frozen → executor.balance (net) + adminrevenue (fee).
    gross - net == platform fee.
    """
    fee = round(gross - net, 8)
    if fee < 0:
        raise ValueError("Negative Gebühr nicht erlaubt.")
    async with tx() as db:
        cur = await db.execute(
            "SELECT frozenusdt FROM users WHERE telegramid = ?", (clientid,)
        )
        row = await cur.fetchone()
        if not row or row["frozenusdt"] < gross - 1e-9:
            raise ValueError("Treuhand-Guthaben unzureichend.")

        await db.execute(
            "UPDATE users SET frozenusdt = frozenusdt - ? WHERE telegramid = ?",
            (gross, clientid),
        )
        await db.execute(
            "INSERT OR IGNORE INTO users (telegramid, username) VALUES (?, '')",
            (executorid,),
        )
        await db.execute(
            "UPDATE users SET balanceusdt = balanceusdt + ? WHERE telegramid = ?",
            (net, executorid),
        )
        await db.execute(
            "UPDATE adminrevenue SET totalcollectedfees = totalcollectedfees + ? WHERE id = 1",
            (fee,),
        )

async def refundclient(clientid: int, amount: float) -> None:
    """Return amount from frozen → balance for the client."""
    if amount <= 0:
        return
    async with tx() as db:
        cur = await db.execute(
            "SELECT frozenusdt FROM users WHERE telegramid = ?", (clientid,)
        )
        row = await cur.fetchone()
        if not row or row["frozenusdt"] < amount - 1e-9:
            raise ValueError("Treuhand-Guthaben unzureichend.")
        await db.execute(
            "UPDATE users SET frozenusdt = frozenusdt - ?, "
            "balanceusdt = balanceusdt + ? WHERE telegramid = ?",
            (amount, amount, clientid),
        )

async def recordfee(amount: float) -> None:
    if amount <= 0:
        return
    async with tx() as db:
        await db.execute(
            "UPDATE adminrevenue SET totalcollectedfees = totalcollectedfees + ? WHERE id = 1",
            (amount,),
        )

async def creditbalance(userid: int, amount: float) -> None:
    """Top-up after confirmed external payment."""
    if amount <= 0:
        return
    async with tx() as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegramid, username) VALUES (?, '')",
            (userid,),
        )
        await db.execute(
            "UPDATE users SET balanceusdt = balanceusdt + ? WHERE telegramid = ?",
            (amount, userid),
        )

async def debitbalanceforwithdrawal(userid: int, amount: float) -> None:
    async with tx() as db:
        cur = await db.execute(
            "SELECT balanceusdt FROM users WHERE telegramid = ?", (userid,)
        )
        row = await cur.fetchone()
        if not row or row["balanceusdt"] < amount - 1e-9:
            raise ValueError("Unzureichendes Guthaben.")
        await db.execute(
            "UPDATE users SET balanceusdt = balanceusdt - ? WHERE telegramid = ?",
            (amount, userid),
        )

async def rollbackwithdrawal(userid: int, amount: float) -> None:
    async with tx() as db:
        await db.execute(
            "UPDATE users SET balanceusdt = balanceusdt + ? WHERE telegramid = ?",
            (amount, userid),
        )

# ---------- Ratings ----------

async def updateratings(
    userid: int,
    asrole: str,        # 'client' | 'executor'
    stars: int,          # 1..5
) -> None:
    if asrole not in ("client", "executor"):
        return
    stars = max(1, min(5, stars))
    fieldrating = f"{asrole}rating"
    fieldcount = f"{asrole}reviewscount"
    async with tx() as db:
        cur = await db.execute(
            f"SELECT {fieldrating} AS r, {fieldcount} AS c FROM users WHERE telegramid = ?",
            (userid,),
        )
        row = await cur.fetchone()
        if not row:
            return
        newcount = row["c"] + 1
        newrating = (row["r"] * row["c"] + stars) / newcount
        await db.execute(
            f"UPDATE users SET {fieldrating} = ?, {fieldcount} = ? WHERE telegramid = ?",
            (newrating, newcount, userid),
        )

# ---------- Tasks ----------

async def createtask(
    clientid: int,
    title: str,
    description: str,
    deadline: str,
    category: str,
    attachments: list,
    rewardgross: float,
    rewardnet: float,
    isdirect: int = 0,
    targetidentity: Optional[str] = None,
) -> int:
    async with tx() as db:
        cur = await db.execute(
            """INSERT INTO tasks
            (clientid, title, description, deadline, category, attachments,
             rewardgross, rewardnet, status, isdirect, targetexecutoridentity)
            VALUES (?,?,?,?,?,?,?,?, 'open', ?, ?)""",
            (
                clientid, title, description, deadline, category,
                json.dumps(attachments), rewardgross, rewardnet,
                isdirect, targetidentity,
            ),
        )
        return cur.lastrowid

async def settaskchannelmessage(taskid: int, msgid: int) -> None:
    async with tx() as db:
        await db.execute(
            "UPDATE tasks SET channelmessageid = ? WHERE taskid = ?",
            (msgid, taskid),
        )

async def claimtask(taskid: int, executorid: int) -> bool:
    """Atomically transition open → inprogress. Returns True on success."""
    async with tx() as db:
        cur = await db.execute(
            "UPDATE tasks SET executorid = ?, status = 'inprogress', "
            "claimedat = CURRENT_TIMESTAMP "
            "WHERE taskid = ? AND status = 'open' AND clientid != ?",
            (executorid, taskid, executorid),
        )
        return cur.rowcount == 1

async def gettask(taskid: int) -> Optional[aiosqlite.Row]:
    async with conn() as db:
        cur = await db.execute("SELECT * FROM tasks WHERE taskid = ?", (taskid,))
        return await cur.fetchone()

async def settaskstatus(taskid: int, status: str) -> None:
    fieldmap = {
        "completed": "completedat = CURRENT_TIMESTAMP",
        "dispute": "disputedat = CURRENT_TIMESTAMP",
    }
    extra = ", " + fieldmap[status] if status in fieldmap else ""
    async with tx() as db:
        await db.execute(
            f"UPDATE tasks SET status = ?{extra} WHERE taskid = ?",
            (status, taskid),
        )

# ---------- Sessions ----------

async def createsession(taskid: int, clientid: int, executorid: int, roomtoken: str) -> int:
    async with tx() as db:
        cur = await db.execute(
            """INSERT INTO dealsessions (taskid, clientid, executorid, roomtoken, status)
            VALUES (?, ?, ?, ?, 'active')""",
            (taskid, clientid, executorid, roomtoken),
        )
        return cur.lastrowid

async def getactivesessionfortask(taskid: int) -> Optional[aiosqlite.Row]:
    async with conn() as db:
        cur = await db.execute(
            "SELECT * FROM dealsessions WHERE taskid = ?", (taskid,)
        )
        return await cur.fetchone()

async def setsessionstatus(taskid: int, status: str) -> None:
    async with tx() as db:
        await db.execute(
            "UPDATE dealsessions SET status = ? WHERE taskid = ?",
            (status, taskid),
        )

async def logdealmessage(
    taskid: int, senderid: int, msgtype: str,
    fileid: Optional[str], preview: str,
) -> None:
    async with tx() as db:
        await db.execute(
            """INSERT INTO dealmessages (taskid, senderid, messagetype, fileid, contentpreview)
            VALUES (?, ?, ?, ?, ?)""",
            (taskid, senderid, msgtype, fileid, preview[:500]),
        )

async def getdealmessages(taskid: int) -> list:
    async with conn() as db:
        cur = await db.execute(
            "SELECT * FROM dealmessages WHERE taskid = ? ORDER BY timestamp ASC",
            (taskid,),
        )
        return await cur.fetchall()

# ---------- Disputes ----------

async def incrementdisputesinitiated(userid: int) -> None:
    async with tx() as db:
        await db.execute(
            "UPDATE users SET disputesinitiated = disputesinitiated + 1 WHERE telegramid = ?",
            (userid,),
        )

async def incrementdisputeslost(userid: int) -> None:
    async with tx() as db:
        await db.execute(
            "UPDATE users SET disputeslost = disputeslost + 1 WHERE telegramid = ?",
            (userid,),
        )

async def maybeshadowban(userid: int, threshold: float) -> bool:
    async with tx() as db:
        cur = await db.execute(
            "SELECT disputesinitiated, disputeslost FROM users WHERE telegramid = ?",
            (userid,),
        )
        row = await cur.fetchone()
        if not row or row["disputesinitiated"] < 5:
            return False
        ratio = row["disputeslost"] / row["disputesinitiated"]
        if ratio >= threshold:
            await db.execute(
                "UPDATE users SET isshadowbanned = 1 WHERE telegramid = ?",
                (userid,),
            )
            return True
    return False

# ---------- Listings ----------

async def listuseractivesessions(userid: int) -> list:
    async with conn() as db:
        cur = await db.execute(
            """SELECT s.*, t.title, t.status AS taskstatus FROM dealsessions s
            JOIN tasks t ON t.taskid = s.taskid
            WHERE (s.clientid = ? OR s.executorid = ?) AND s.status = 'active'
            ORDER BY s.initializedat DESC""",
            (userid, userid),
        )
        return await cur.fetchall()

async def listuserhistory(userid: int, limit: int = 20, offset: int = 0) -> list:
    async with conn() as db:
        cur = await db.execute(
            """SELECT s.*, t.title, t.status AS taskstatus FROM dealsessions s
            JOIN tasks t ON t.taskid = s.taskid
            WHERE (s.clientid = ? OR s.executorid = ?) AND s.status != 'active'
            ORDER BY s.initializedat DESC LIMIT ? OFFSET ?""",
            (userid, userid, limit, offset),
        )
        return await cur.fetchall()

# ---------- Admin ----------

async def adminstats() -> dict:
    async with conn() as db:
        out = {}
        for sql, key in [
            ("SELECT COUNT(*) AS c FROM users", "users"),
            ("SELECT COUNT(*) AS c FROM tasks WHERE status='open'", "tasksopen"),
            ("SELECT COUNT(*) AS c FROM tasks WHERE status='inprogress'", "tasksinprogress"),
            ("SELECT COUNT(*) AS c FROM tasks WHERE status='completed'", "taskscompleted"),
            ("SELECT COUNT(*) AS c FROM tasks WHERE status='dispute'", "tasksdispute"),
        ]:
            cur = await db.execute(sql)
            out[key] = (await cur.fetchone())["c"]
        cur = await db.execute("SELECT totalcollectedfees AS f FROM adminrevenue WHERE id=1")
        out["fees"] = (await cur.fetchone())["f"]
        return out

# ---------- Invoices / Payouts ----------

async def recordinvoice(invoiceid: str, userid: int, amount: float) -> None:
    async with tx() as db:
        await db.execute(
            "INSERT OR REPLACE INTO paymentinvoices (invoiceid, userid, amountusdt, status) "
            "VALUES (?, ?, ?, 'pending')",
            (invoiceid, userid, amount),
        )

async def markinvoicepaid(invoiceid: str) -> Optional[aiosqlite.Row]:
    """Marks paid only if previously pending. Returns the row if it transitioned."""
    async with tx() as db:
        cur = await db.execute(
            "SELECT * FROM paymentinvoices WHERE invoiceid = ?", (invoiceid,)
        )
        row = await cur.fetchone()
        if not row or row["status"] != "pending":
            return None
        await db.execute(
            "UPDATE paymentinvoices SET status='paid' WHERE invoiceid = ?",
            (invoiceid,),
        )
        return row

async def listpendinginvoices() -> list:
    async with conn() as db:
        cur = await db.execute(
            "SELECT * FROM paymentinvoices WHERE status='pending'"
        )
        return await cur.fetchall()

async def recordpayout(spendid: str, userid: int, amount: float, status: str, response: str = "") -> None:
    async with tx() as db:
        await db.execute(
            "INSERT OR REPLACE INTO payouts (spendid, userid, amountusdt, status, response) "
            "VALUES (?, ?, ?, ?, ?)",
            (spendid, userid, amount, status, response),
        )
