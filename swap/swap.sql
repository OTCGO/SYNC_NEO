USE sea;
CREATE TABLE IF NOT EXISTS swap_launch (
  id INT UNSIGNED AUTO_INCREMENT,
  txid CHAR(64) UNIQUE NOT NULL,
  from_address VARCHAR(34) NOT NULL,
  to_address VARCHAR(34) NOT NULL,
  amount VARCHAR(40) NOT NULL,
  asset VARCHAR(64) NOT NULL,
  timepoint INT UNSIGNED NOT NULL,
  status SMALLINT DEFAULT 0 NOT NULL, #0 launch -1 refund finish
  PRIMARY KEY (id),
  INDEX idx_from_timepoint (from_address, timepoint),
  INDEX idx_to_status (to_address, status)
);

CREATE TABLE IF NOT EXISTS swap_process (
  id INT UNSIGNED AUTO_INCREMENT,
  swap_txid CHAR(64) UNIQUE NOT NULL,
  from_address VARCHAR(34) NOT NULL,
  to_address VARCHAR(34) NOT NULL,
  amount VARCHAR(40) NOT NULL,
  asset VARCHAR(64) NOT NULL,
  timepoint INT UNSIGNED NOT NULL,
  txid CHAR(64) UNIQUE NOT NULL,
  PRIMARY KEY (id),
  INDEX idx_swap_txid_timepoint (swap_txid, timepoint),
  INDEX idx_from_timepoint (from_address, timepoint)
);
