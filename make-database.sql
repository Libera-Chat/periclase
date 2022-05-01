-- 16  is nickname length
-- 10  is username length
-- 32  is kline tag length
-- 50  is realname length
-- 64  is hostname length
-- 92  is mask length
-- 260 is reason length

BEGIN;

CREATE TABLE trigger (
    id       SERIAL       PRIMARY KEY,
    pattern  TEXT         NOT NULL,
    oper     VARCHAR(16)  NOT NULL,
    source   VARCHAR(92)  NOT NULL,
    action   SMALLINT     NOT NULL,
    ts       TIMESTAMP    NOT NULL
);
CREATE TABLE reject (
    id       SERIAL        PRIMARY KEY,
    pattern  TEXT          NOT NULL,
    oper     VARCHAR(16)   NOT NULL,
    source   VARCHAR(92)   NOT NULL,
    reason   VARCHAR(260)  NOT NULL,
    enabled  BOOLEAN       NOT NULL,
    ts       TIMESTAMP     NOT NULL
);

COMMIT;
