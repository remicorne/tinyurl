CREATE TABLE IF NOT EXISTS urls (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(16) UNIQUE NOT NULL,
    normalized_url TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS access_logs (
    id BIGSERIAL PRIMARY KEY,
    url_id INT NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    accessed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_urls_slug ON urls (slug);
CREATE INDEX IF NOT EXISTS idx_urls_normalized_url ON urls (normalized_url);
CREATE INDEX IF NOT EXISTS idx_access_logs_url_id ON access_logs (url_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_accessed_at ON access_logs (accessed_at);
