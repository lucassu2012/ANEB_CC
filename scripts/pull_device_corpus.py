"""Pull the ANEB Room DB off the P40 and extract the run corpus as JSONL.

Why this script exists: the runbook's pull step says "把真机拉下来的原始 JSONL" but
never says HOW. `/api/v1/results` is POST-only (server/handlers_results.go:67), the
device has no sqlite3 binary, and the repo has no db->jsonl converter (a whole-repo
grep for sqlite3|report_body hits exactly one unrelated test). So the pull is:
copy the DB to the host and read it here.

WAL matters: the app writes with write-ahead logging, so `aneb-probe.db` alone can
be missing the most recent runs. All three files (.db, -wal, -shm) are pulled and
sqlite3 replays the WAL on open. That is why evidence/phase3/realdevice_data/ has
the -wal/-shm siblings sitting next to the .db.

Device side is READ ONLY: `run-as ... cat` copies bytes out, changes nothing.

Isolating ONE batch: `report_body` holds every run the device has ever uploaded
(67 at the time of writing), so a pull without `--since-epoch-ms` returns the whole
history. Pass the batch start time. The cutoff is resolved by joining
`test_run.startedAtEpochMs` -- see `extract()` on why that join is mandatory rather
than best-effort.

First use: D-393 (T2 idle-band batch, 2026-08-02). Verified BEFORE that batch by
re-pulling an already-archived corpus and comparing: 4/4 runs deep-equal, 36/36
scenarios -- the tool reproduces what was archived, it does not merely look plausible.

Usage:
    python pull_device_corpus.py --out <dir> --name <prefix> --since-epoch-ms <ms>
    python pull_device_corpus.py --inspect     # show tables/columns, extract nothing
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

SERIAL = "8MY0221126002537"
# 包名默认 com.aneb.probe；装机为改名副本（如 com.aneb.probe.ctree，PO 2026-09-04 裁定不顶掉 G 树包）时
# 用环境变量 ANEB_PKG 覆盖，避免拉错包。
PKG = os.environ.get("ANEB_PKG", "com.aneb.probe")
DB_FILES = ("aneb-probe.db", "aneb-probe.db-wal", "aneb-probe.db-shm")


def adb_cat(serial, remote_rel, local_path):
    """Copy one file out of the app sandbox. Returns bytes written (0 = absent)."""
    cmd = ["adb", "-s", serial, "exec-out", "run-as", PKG, "cat", remote_rel]
    with open(local_path, "wb") as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE)
    if p.returncode != 0:
        err = p.stderr.decode("utf-8", "replace").strip()
        # -wal/-shm legitimately may not exist (checkpointed DB); that is not fatal.
        if "No such file" in err:
            return 0
        raise RuntimeError("adb cat %s failed: %s" % (remote_rel, err))
    return os.path.getsize(local_path)


def pull_db(serial, workdir):
    sizes = {}
    for name in DB_FILES:
        dest = os.path.join(workdir, name)
        sizes[name] = adb_cat(serial, "databases/" + name, dest)
        if sizes[name] == 0 and os.path.exists(dest):
            os.remove(dest)
    if not sizes.get(DB_FILES[0]):
        raise RuntimeError("main DB came back empty -- is the app installed and has it ever run?")
    return sizes


def describe(con):
    """Print every table and its columns. Discovery, not assumption."""
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    out = {}
    for t in tables:
        cols = [r[1] for r in con.execute('PRAGMA table_info("%s")' % t)]
        n = con.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
        out[t] = (cols, n)
        print("  %-28s n=%-6d %s" % (t, n, ", ".join(cols)))
    return out


def pick_run_table(schema):
    """Find the table holding the uploaded report bodies.

    Required, not optional: if no table carries a report-body-ish column the script
    FAILS rather than quietly emitting an empty corpus. An empty JSONL that looks
    like a successful pull is the worst outcome here -- it would read as 'the batch
    produced nothing' instead of 'the extractor did not know where to look'.
    """
    for t, (cols, _n) in schema.items():
        for c in cols:
            if c.lower() in ("report_body", "reportbody", "body", "report_json"):
                return t, c
    raise RuntimeError(
        "no report-body column found; tables were: %s" %
        {t: c for t, (c, _) in schema.items()})


def extract(con, table, col, since_ms=None):
    """Extract report bodies, optionally dropping runs older than `since_ms`.

    The body table (`report_body`) carries only (runId, body) -- NO timestamp. The
    first version of this function looked for a time column ON THAT TABLE, found
    none, and therefore applied no cutoff AT ALL while still reporting success:
    a --since-epoch-ms of 14:00 returned all 67 historical runs. That is the exact
    failure shape this project keeps hitting -- the filter silently does nothing and
    the output looks complete. So now the time comes from `test_run` via a join, and
    if a cutoff was requested but cannot be resolved the function RAISES rather than
    quietly returning everything.
    """
    body_cols = [r[1] for r in con.execute('PRAGMA table_info("%s")' % table)]
    id_col = next((c for c in body_cols if c.lower() in ("runid", "run_id")), None)

    tcol = next((c for c in body_cols
                 if c.lower() in ("started_at_epoch_ms", "startedatepochms",
                                  "ts_epoch_ms", "tsepochms", "created_at")), None)
    time_source = table if tcol else None
    join_table = join_id = None

    if tcol is None and since_ms is not None:
        # Look for a sibling table that has both the run id and a start time.
        for t, in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"):
            cols = [r[1] for r in con.execute('PRAGMA table_info("%s")' % t)]
            low = {c.lower(): c for c in cols}
            if "runid" in low and "startedatepochms" in low:
                join_table, join_id, tcol = t, low["runid"], low["startedatepochms"]
                time_source = t
                break
        if join_table is None or id_col is None:
            raise RuntimeError(
                "--since-epoch-ms was requested but no run start time is reachable "
                "(body table %r has columns %r and no sibling table carries both "
                "runId and startedAtEpochMs). Refusing to silently return every run."
                % (table, body_cols))

    if join_table:
        sql = ('SELECT b."%s", j."%s" FROM "%s" b JOIN "%s" j ON b."%s" = j."%s"'
               % (col, tcol, table, join_table, id_col, join_id))
    elif tcol:
        sql = 'SELECT "%s", "%s" FROM "%s"' % (col, tcol, table)
    else:
        sql = 'SELECT "%s", NULL FROM "%s"' % (col, table)

    rows, kept, skipped_time, bad_json, no_time = [], 0, 0, 0, 0
    for body, ts in con.execute(sql):
        if since_ms is not None:
            if ts is None:
                # A run we cannot place in time must not be silently kept OR dropped.
                no_time += 1
                continue
            if int(ts) < since_ms:
                skipped_time += 1
                continue
        if body is None:
            bad_json += 1
            continue
        try:
            obj = json.loads(body)
        except (TypeError, ValueError):
            bad_json += 1
            continue
        rows.append(obj)
        kept += 1
    stats = {"kept": kept, "skipped_before_cutoff": skipped_time,
             "unparseable": bad_json, "time_source": time_source,
             "dropped_no_timestamp": no_time}
    if since_ms is not None and skipped_time == 0 and kept > 0:
        # Not an error, but say it out loud: a cutoff that excluded nothing is
        # indistinguishable from a cutoff that was never applied.
        stats["note"] = ("cutoff excluded 0 runs -- verify this is real and not "
                         "a filter that quietly did nothing")
    return rows, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--serial", default=SERIAL)
    ap.add_argument("--out", help="directory to write <name>_raw.jsonl into")
    ap.add_argument("--name", default="t2", help="corpus name prefix")
    ap.add_argument("--since-epoch-ms", type=int, default=None,
                    help="drop runs older than this (use the batch start time)")
    ap.add_argument("--inspect", action="store_true",
                    help="show schema and counts, write nothing")
    args = ap.parse_args(argv)

    work = tempfile.mkdtemp(prefix="aneb_db_")
    try:
        sizes = pull_db(args.serial, work)
        print("pulled: " + ", ".join("%s=%dB" % (k, v) for k, v in sizes.items() if v))
        con = sqlite3.connect(os.path.join(work, DB_FILES[0]))
        try:
            print("tables:")
            schema = describe(con)
            table, col = pick_run_table(schema)
            print("run table = %s.%s" % (table, col))
            if args.inspect:
                return 0
            if not args.out:
                print("--out is required unless --inspect", file=sys.stderr)
                return 2
            rows, stats = extract(con, table, col, args.since_epoch_ms)
        finally:
            con.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if not rows:
        print("extracted 0 runs -- refusing to write an empty corpus "
              "(stats: %r)" % stats, file=sys.stderr)
        return 1
    os.makedirs(args.out, exist_ok=True)
    dest = os.path.join(args.out, "%s_raw.jsonl" % args.name)
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        for obj in rows:
            fh.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("wrote %s: %d run(s)" % (dest, len(rows)))
    print("stats: %r" % stats)
    ids = [r.get("run", {}).get("run_id") for r in rows]
    print("run_ids: %s" % [i for i in ids if i])
    return 0


if __name__ == "__main__":
    sys.exit(main())
