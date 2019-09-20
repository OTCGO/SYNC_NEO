USE sea;

CREATE TABLE IF NOT EXISTS node (
  id INT UNSIGNED AUTO_INCREMENT,
  txid CHAR(64) UNIQUE NOT NULL,
  status SMALLINT DEFAULT -1 NOT NULL, # -7解锁已确认 -6解锁已退币待确认 -5解锁未退币 -4退出已确认 -3退出已退币待确认 -2退出未退币 -1新节点未确认 0新节点已确认
  referrer VARCHAR(34) NOT NULL,
  address VARCHAR(34) UNIQUE NOT NULL,
  amount INT UNSIGNED NOT NULL,
  days SMALLINT UNSIGNED NOT NULL,
  layer MEDIUMINT UNSIGNED NOT NULL,
  starttime INT UNSIGNED NOT NULL,
  nextbonustime INT UNSIGNED NOT NULL,
  referrals MEDIUMINT UNSIGNED DEFAULT 0 NOT NULL,
  performance INT UNSIGNED NOT NULL,
  nodelevel SMALLINT UNSIGNED DEFAULT 0 NOT NULL,
  teamlevelinfo CHAR(96) DEFAULT '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000' NOT NULL,
  penalty INT UNSIGNED DEFAULT 0 NOT NULL,
  refundtxid VARCHAR(64) DEFAULT '' NOT NULL,
  burned TINYINT UNSIGNED DEFAULT 0 NOT NULL, #0未烧伤 1烧伤
  smallareaburned TINYINT UNSIGNED DEFAULT 0 NOT NULL, #0未烧伤 1烧伤
  signin TINYINT UNSIGNED DEFAULT 0 NOT NULL, #0未签到 1签到
  bonusadvancetable TEXT,
  areaadvancetable LONGTEXT,
  PRIMARY KEY (id),
  INDEX idx_referrer_address(referrer, address),
  INDEX idx_layer_nextbonustime_status(layer, nextbonustime, status)
);

CREATE TABLE IF NOT EXISTS node_bonus (
  id INT UNSIGNED AUTO_INCREMENT,
  address VARCHAR(34) NOT NULL,
  lockedbonus VARCHAR(40) NOT NULL,
  referralsbonus VARCHAR(40) NOT NULL,
  teambonus VARCHAR(40) NOT NULL,
  signinbonus VARCHAR(40) NOT NULL, #签到奖励
  amount VARCHAR(40) NOT NULL,
  total VARCHAR(40) NOT NULL,
  remain VARCHAR(40) NOT NULL,
  bonustime INT UNSIGNED NOT NULL,
  PRIMARY KEY (id),
  INDEX idx_address_bonustime(address, bonustime)
);

CREATE TABLE IF NOT EXISTS node_withdraw (
  id INT UNSIGNED AUTO_INCREMENT,
  txid VARCHAR(64) DEFAULT '' NOT NULL,
  address VARCHAR(34) NOT NULL,
  amount VARCHAR(40) NOT NULL,
  timepoint INT UNSIGNED NOT NULL,
  status TINYINT UNSIGNED DEFAULT 0 NOT NULL, #0未发起交易 1交易未确认 2交易已确认
  PRIMARY KEY (id),
  INDEX idx_address_timepoint(address, timepoint)
);

CREATE TABLE IF NOT EXISTS node_update (
  id INT UNSIGNED AUTO_INCREMENT,
  address VARCHAR(34) UNIQUE NOT NULL,
  operation TINYINT UNSIGNED NOT NULL, #1新节点 2解锁 3提取 4签到 5旧节点激活
  referrer VARCHAR(34) DEFAULT '' NOT NULL,
  amount VARCHAR(40) DEFAULT '0' NOT NULL,
  days SMALLINT UNSIGNED DEFAULT 0 NOT NULL,
  penalty INT UNSIGNED DEFAULT 0 NOT NULL,
  txid VARCHAR(64) DEFAULT '' NOT NULL,
  timepoint INT UNSIGNED NOT NULL,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS node_signature (
  id INT UNSIGNED AUTO_INCREMENT,
  address VARCHAR(34) NOT NULL,
  signature CHAR(128) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE INDEX uidx_address_signature(address, signature(20))
);
