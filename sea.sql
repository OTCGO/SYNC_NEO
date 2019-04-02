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
   status TINYINT UNSIGNED DEFAULT 1 NOT NULL,
   PRIMARY KEY (id),
   UNIQUE INDEX uidx_txid_index (txid, index_n),
   INDEX idx_address_asset_status_value_index_txid (address, asset, status, value, index_n, txid)
 );
