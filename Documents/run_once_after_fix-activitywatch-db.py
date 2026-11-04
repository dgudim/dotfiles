#!/usr/bin/env python3
"""Shrink the ActivityWatch database bloated by the aw-server-rust heartbeat-merge bug
(https://github.com/ActivityWatch/aw-server-rust/issues/554): the same event stored
thousands of times with one start time and growing end times, plus exact duplicates.

1. stops aw-qt (and its systemd user units, if any) and everything it spawned
2. makes sure no aw-server is running, port 5600 is free and nothing has the DB open
3. rebuilds sqlite.db keeping one row per (bucket, starttime, data): the longest one,
   so no tracked time is lost; checks integrity and per-bucket coverage
4. replaces the old database with the new one
5. starts aw-qt again if it was running (also when something above fails)

Does nothing if there is no database or it has no duplicates.
"""
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

DIR = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "activitywatch/aw-server-rust"
DB = DIR / "sqlite.db"
NEW = DIR / "sqlite.db.new"
STEP = int(os.environ.get("AW_FIX_STEP", 5_000_000))  # event ids per scan chunk
PORT = 5600

# keep sort/VACUUM temp files off a tmpfs /tmp; must be set before SQLite initialises
os.environ["SQLITE_TMPDIR"] = str(DIR)
import sqlite3  # noqa: E402

# matched against the executable name, or the script name when it runs under an interpreter
AW_RE = re.compile(r"^(aw-qt|aw-server.*|aw-sync|aw-awatcher|awatcher|aw-watcher-.*)$")
AWQT_RE = re.compile(r"^aw-qt$")
INTERP_RE = re.compile(r"^(python[0-9.]*|bash|sh)$")
UNIT_RE = re.compile(r"activitywatch|aw(-|\\x2d)(qt|server|sync)", re.I)


class Fail(Exception):
    pass


def log(msg):
    print(f"[aw-db-fix] {msg}", flush=True)


# ---------- processes ----------
def pids_matching(rx):
    me, uid, out = os.getpid(), os.getuid(), []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit() or int(p.name) == me:
            continue
        try:
            if p.stat().st_uid != uid:
                continue
            argv = [a.decode(errors="replace") for a in (p / "cmdline").read_bytes().split(b"\0")]
        except OSError:
            continue
        if not argv[0]:
            continue
        name = os.path.basename(argv[0])
        if INTERP_RE.match(name):
            name = os.path.basename(argv[1]) if len(argv) > 1 else ""
        if rx.match(name):
            out.append(int(p.name))
    return out


def signal_all(sig, rx):
    for pid in pids_matching(rx):
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def wait_gone(secs):
    deadline = time.time() + secs
    while time.time() < deadline:
        if not pids_matching(AW_RE):
            return True
        time.sleep(0.5)
    return not pids_matching(AW_RE)


def running_units():
    if not shutil.which("systemctl"):
        return []
    r = subprocess.run(["systemctl", "--user", "list-units", "--type=service", "--state=running",
                        "--no-legend", "--plain"], capture_output=True, text=True)
    return [line.split()[0] for line in r.stdout.splitlines() if line.split() and UNIT_RE.search(line.split()[0])]


def stop(units):
    for u in units:
        log(f"stopping {u}")
        subprocess.run(["systemctl", "--user", "stop", u])
    if not pids_matching(AW_RE):
        return
    log("stopping ActivityWatch")
    signal_all(15, AWQT_RE)
    if wait_gone(20):
        return
    log("terminating leftover ActivityWatch processes")
    signal_all(15, AW_RE)
    if wait_gone(10):
        return
    log("killing leftover ActivityWatch processes")
    signal_all(9, AW_RE)
    wait_gone(5)


def ensure_down():
    left = pids_matching(AW_RE)
    if left:
        cmds = [(Path(f"/proc/{p}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
                 if Path(f"/proc/{p}").exists() else "?") for p in left]
        raise Fail("ActivityWatch processes still running: " + "; ".join(f"{p} {c}" for p, c in zip(left, cmds)))
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, PORT), timeout=1):
                raise Fail(f"something is still listening on port {PORT}")
        except OSError:
            pass
    targets = {os.path.realpath(DB), os.path.realpath(f"{DB}-wal")}
    for fd_dir in Path("/proc").glob("[0-9]*/fd"):
        try:
            for fd in fd_dir.iterdir():
                if os.readlink(fd) in targets:
                    raise Fail(f"database is still open by pid {fd_dir.parent.name}")
        except OSError:
            continue
    log("ActivityWatch is stopped")


def restart(had_awqt, units):
    for u in units:
        if subprocess.run(["systemctl", "--user", "start", u]).returncode == 0:
            log(f"started {u}")
    if had_awqt:
        time.sleep(2)
        if not pids_matching(AWQT_RE):
            try:
                subprocess.Popen(["aw-qt"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
                log("started aw-qt")
            except OSError as e:
                log(f"could not start aw-qt: {e}")


# ---------- database ----------
def rebuild():
    """Write the deduplicated database to NEW. Returns (before, after), or None if there are no duplicates."""
    # fold any pending WAL into the main file first
    c = sqlite3.connect(DB, isolation_level=None)
    if c.execute("pragma wal_checkpoint(TRUNCATE)").fetchone()[0]:
        raise Fail("WAL checkpoint busy, database still in use")
    c.close()

    o = sqlite3.connect(NEW, isolation_level=None)
    try:
        o.execute("pragma journal_mode=off")  # fresh file, thrown away on any failure
        o.execute("pragma synchronous=off")
        o.execute("attach ? as src", (str(DB),))

        objs = o.execute("""select type, name, sql from src.sqlite_master
                            where sql is not null and name not like 'sqlite_%' order by rowid""").fetchall()
        tables = [(n, s) for t, n, s in objs if t == "table"]
        indexes = [s for t, n, s in objs if t == "index"]
        if "events" not in [n for n, _ in tables]:
            raise Fail("no events table, not an aw-server-rust database?")

        o.execute("begin")
        for _, s in tables:
            o.execute(s)
        for n, _ in tables:
            if n != "events":
                o.execute(f'insert into main."{n}" select * from src."{n}"')
        o.execute("create table stg(id integer, bucketrow integer, starttime integer, endtime integer, data text)")
        o.execute("commit")

        maxid = o.execute("select coalesce(max(id), 0) from src.events").fetchone()[0]
        before, t0 = 0, time.time()
        # per chunk: one row per (bucket, starttime, data) with the max endtime; the bare 'id' comes from that row
        for a in range(1, maxid + 1, STEP):
            b = a + STEP - 1
            o.execute("begin")
            before += o.execute("select count(*) from src.events where id between ? and ?", (a, b)).fetchone()[0]
            o.execute("""insert into stg select id, bucketrow, starttime, max(endtime), data from src.events
                         where id between ? and ? group by bucketrow, starttime, data""", (a, b))
            o.execute("commit")
            log(f"scanned {min(b, maxid) * 100 // maxid}% ({time.time() - t0:.0f}s)")

        o.execute("begin")
        # again across chunk boundaries
        o.execute("""insert into events(id, bucketrow, starttime, endtime, data)
                     select id, bucketrow, starttime, max(endtime), data from stg
                     group by bucketrow, starttime, data order by id""")
        o.execute("drop table stg")
        after = o.execute("select count(*) from events").fetchone()[0]
        if after == before:
            o.execute("rollback")
            log(f"no duplicates ({before} events), nothing to do")
            return None
        for s in indexes:
            o.execute(s)
        o.execute("delete from main.sqlite_sequence")
        o.execute("insert into main.sqlite_sequence select * from src.sqlite_sequence")
        o.execute(f"pragma main.user_version={int(o.execute('pragma src.user_version').fetchone()[0])}")
        o.execute("commit")

        # same buckets, same distinct start times, same latest end time => no tracked time lost
        q = "select bucketrow, count(distinct starttime), max(endtime) from {}.events group by bucketrow order by bucketrow"
        if o.execute(q.format("src")).fetchall() != o.execute(q.format("main")).fetchall():
            raise Fail("verification failed: per-bucket coverage differs")
        o.execute("detach src")
        o.execute("vacuum")
        ok = o.execute("pragma integrity_check").fetchone()[0]
        if ok != "ok":
            raise Fail(f"integrity check failed: {ok}")
        o.execute("pragma journal_mode=wal")
    finally:
        o.close()
    log(f"events: {before} -> {after}")
    return before, after


def human(n):
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024


def remove(*paths):
    for p in paths:
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass


def main():
    if not DB.exists():
        log(f"no database at {DB}, nothing to do")
        return 0

    had_awqt = bool(pids_matching(AWQT_RE))
    units = running_units()
    rc = 0
    try:
        stop(units)
        ensure_down()

        # leftovers from the manual cleanup attempt
        remove(f"{DB}.dedup", DIR / "sqlite.clean.db", DIR / "sqlite.clean.db-journal", DIR / ".wtest2")

        if shutil.disk_usage(DIR).free < 1 << 30:
            raise Fail(f"less than 1 GiB free in {DIR}")
        remove(NEW, f"{NEW}-journal")

        if rebuild():
            os.chmod(NEW, 0o600)
            old_size = DB.stat().st_size
            remove(f"{DB}-wal", f"{DB}-shm")  # empty after the TRUNCATE checkpoint
            os.replace(NEW, DB)
            log(f"done: {human(old_size)} -> {human(DB.stat().st_size)}")
    except Fail as e:
        log(f"{e}; database left untouched")
        rc = 1
    except BaseException:
        traceback.print_exc()
        log("failed; database left untouched")
        rc = 1
    finally:
        remove(NEW, f"{NEW}-journal", f"{NEW}-wal", f"{NEW}-shm")
        restart(had_awqt, units)
    return rc


if __name__ == "__main__":
    sys.exit(main())
