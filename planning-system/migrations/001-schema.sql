-- Schema version 001; reference DDL for server.storage.migrate.

CREATE TABLE audit (
	id VARCHAR(36) NOT NULL, 
	subject VARCHAR(200) NOT NULL, 
	project_id VARCHAR(36), 
	action VARCHAR(100) NOT NULL, 
	occurred_at VARCHAR(40) NOT NULL, 
	details JSON NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE records (
	id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	portfolio_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	revision INTEGER NOT NULL, 
	data JSONB NOT NULL, 
	PRIMARY KEY (id, kind), 
	CHECK (revision >= 1)
)

;
CREATE INDEX ix_records_project_id ON records (project_id);
CREATE INDEX ix_records_portfolio_id ON records (portfolio_id);

CREATE TABLE request_results (
	id VARCHAR(64) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	status INTEGER NOT NULL, 
	body JSON NOT NULL, 
	portfolio_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	PRIMARY KEY (id)
)

;

CREATE TABLE schema_versions (
	version SERIAL NOT NULL, 
	applied_at VARCHAR(40) NOT NULL, 
	PRIMARY KEY (version)
)

;
