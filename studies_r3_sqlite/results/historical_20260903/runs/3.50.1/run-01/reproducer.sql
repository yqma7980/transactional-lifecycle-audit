.bail on
.open test.db
PRAGMA synchronous = NORMAL;
PRAGMA page_size = 4096;
PRAGMA auto_vacuum = FULL;
PRAGMA journal_mode = WAL;
PRAGMA cache_size = 1;
CREATE TABLE t1 (i INTEGER PRIMARY KEY, s TEXT);
PRAGMA wal_checkpoint;
INSERT INTO t1 (i, s) VALUES (0, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (1, randomblob(4096));
SAVEPOINT one;
INSERT INTO t1 (i, s) VALUES (2, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (3, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (4, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (5, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (6, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (7, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (8, randomblob(4096));
ROLLBACK TO one;
RELEASE one;
INSERT INTO t1 (i, s) VALUES (9, randomblob(4096));
.shell copy /Y test.db test2.db >NUL
.shell copy /Y test.db-wal test2.db-wal >NUL
.open test2.db
.print __R3_RESULT_BEGIN__
PRAGMA integrity_check;
SELECT count(*) FROM t1;
.print __R3_RESULT_END__
.quit
