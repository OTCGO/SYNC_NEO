SET SESSION default_storage_engine = InnoDB;
CREATE DATABASE IF NOT EXISTS sea DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci;
USE sea;

CREATE TABLE IF NOT EXISTS assets (
  id INT UNSIGNED AUTO_INCREMENT,
  asset VARCHAR(64) UNIQUE NOT NULL,
  type VARCHAR(20) NOT NULL,
  name VARCHAR(64) NOT NULL,
  symbol VARCHAR(20) NOT NULL,
  version VARCHAR(20) NOT NULL,
  decimals TINYINT UNSIGNED DEFAULT 8 NOT NULL,
  contract_name VARCHAR(64) NOT NULL,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS history (
  id INT UNSIGNED AUTO_INCREMENT,
  txid CHAR(66) NOT NULL,
  operation VARCHAR(3) NOT NULL,
  index_n SMALLINT UNSIGNED NOT NULL,
  address VARCHAR(34) NOT NULL,
  value VARCHAR(40) NOT NULL,
  timepoint INT UNSIGNED NOT NULL,
  asset VARCHAR(64) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE INDEX uidx_txid_op_index (txid, operation, index_n),
  INDEX idx_address_tp_op_value_asset (address, timepoint, operation, value, asset)
);

CREATE TABLE IF NOT EXISTS block (
  height INT UNSIGNED,
  sys_fee INT UNSIGNED NOT NULL,
  total_sys_fee INT UNSIGNED NOT NULL,
  PRIMARY KEY (height)
);

CREATE TABLE IF NOT EXISTS utxos (
  id INT UNSIGNED AUTO_INCREMENT,
  txid CHAR(66) NOT NULL,
  index_n SMALLINT UNSIGNED NOT NULL,
  address VARCHAR(34) NOT NULL,
  value VARCHAR(40) NOT NULL,
  asset VARCHAR(64) NOT NULL,
  height INT UNSIGNED NOT NULL,
  spent_txid CHAR(66) DEFAULT NULL,
  spent_height INT UNSIGNED DEFAULT NULL,
  claim_txid CHAR(66) DEFAULT NULL,
  claim_height INT UNSIGNED DEFAULT NULL,
  status TINYINT UNSIGNED DEFAULT 1 NOT NULL, #0 unavailable 1 available 2 freeze
  PRIMARY KEY (id),
  UNIQUE INDEX uidx_txid_index (txid, index_n),
  INDEX idx_address_asset_status_value_index_txid (address, asset, status, value, index_n, txid)
);

CREATE TABLE IF NOT EXISTS balance (
  id INT UNSIGNED AUTO_INCREMENT,
  address VARCHAR(34) NOT NULL,
  asset VARCHAR(64) NOT NULL,
  value VARCHAR(40) NOT NULL,
  last_updated_height INT UNSIGNED DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE INDEX uidx_address_asset (address, asset),
  INDEX idx_asset_value_address (asset, value, address)
);

CREATE TABLE IF NOT EXISTS upt (
  id INT UNSIGNED AUTO_INCREMENT,
  address VARCHAR(34) NOT NULL,
  asset VARCHAR(64) NOT NULL,
  update_height INT UNSIGNED NOT NULL,
  chain VARCHAR(20) DEFAULT 'NEO' NOT NULL,
  PRIMARY KEY (id),
  UNIQUE INDEX uidx_address_asset (address, asset)
);

CREATE TABLE IF NOT EXISTS status (
  id INT UNSIGNED AUTO_INCREMENT,
  name VARCHAR(20) NOT NULL,
  update_height INT UNSIGNED NOT NULL,
  PRIMARY KEY (id),
  UNIQUE INDEX uidx_name (name)
);

CREATE TABLE IF NOT EXISTS platform (
  id INT UNSIGNED AUTO_INCREMENT,
  name VARCHAR(20) NOT NULL,
  version VARCHAR(20) NOT NULL,
  download_url VARCHAR(128) NOT NULL,
  force_update TINYINT UNSIGNED DEFAULT 0 NOT NULL,
  sha1 CHAR(40) NOT NULL,
  sha256 CHAR(64) NOT NULL,
  release_time DATETIME NOT NULL,
  update_notes_zh VARCHAR(256) NOT NULL,
  update_notes_en VARCHAR(256) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE INDEX uidx_name_version (name, version)
);

CREATE TABLE IF NOT EXISTS oep4_history (
  id INT UNSIGNED AUTO_INCREMENT,
  txid CHAR(64) NOT NULL,
  operation VARCHAR(3) NOT NULL,
  index_n SMALLINT UNSIGNED NOT NULL,
  address VARCHAR(34) NOT NULL,	#if null '0'*34
  value VARCHAR(40) NOT NULL,
  dest VARCHAR(34) NOT NULL,	#if null '0'*34
  timepoint INT UNSIGNED NOT NULL,
  asset VARCHAR(64) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE INDEX uidx_txid_op_index (txid, operation, index_n),
  INDEX idx_address_asset_timepoint (address, asset, timepoint),
  INDEX idx_address_dest_asset_op_timepoint (address, dest, asset, operation, timepoint)
);
