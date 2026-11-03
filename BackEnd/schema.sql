BEGIN;

CREATE TABLE IF NOT EXISTS medicoes (
    id INTEGER PRIMARY KEY,
    temperatura_DHT REAL,
    umidade REAL CHECK (umidade BETWEEN 0 AND 100),
    temperatura_BMP REAL,
    pressao_BMP REAL,
    luminosidade INTEGER CHECK (luminosidade IN (0, 1)),
    gas INTEGER,
    recebida_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_medicoes_recebida_em
    ON medicoes (recebida_em DESC, id DESC);

COMMIT;
