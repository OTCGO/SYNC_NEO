USE sea;

CREATE TABLE IF NOT EXISTS node (
  id INT UNSIGNED AUTO_INCREMENT,
  txid CHAR(64) UNIQUE NOT NULL,
  status SMALLINT DEFAULT -1 NOT NULL, #-10无效交易 -9收款方不一致 -8交易金额不一致 -7解锁已确认 -6解锁已退币待确认 -5解锁未退币 -4退出已确认 -3退出已退币待确认 -2退出未退币 -1新节点未确认 0新节点已确认
  referrer VARCHAR(34) NOT NULL,
  address VARCHAR(34) UNIQUE NOT NULL,
  amount INT UNSIGNED NOT NULL,
  days SMALLINT UNSIGNED NOT NULL,
  layer MEDIUMINT UNSIGNED NOT NULL,
  starttime INT UNSIGNED NOT NULL,
  nextbonustime INT UNSIGNED NOT NULL,
  referrals MEDIUMINT UNSIGNED DEFAULT 0 NOT NULL,
  performance INT UNSIGNED DEFAULT 0 NOT NULL,
  nodelevel SMALLINT UNSIGNED DEFAULT 0 NOT NULL,
  teamlevelinfo CHAR(96) DEFAULT '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000' NOT NULL,
  penalty INT UNSIGNED DEFAULT 0 NOT NULL,
  refundtxid VARCHAR(64) DEFAULT '' NOT NULL,
  burned TINYINT UNSIGNED DEFAULT 0 NOT NULL, #0未烧伤 1烧伤
  smallareaburned TINYINT UNSIGNED DEFAULT 0 NOT NULL, #0未烧伤 1烧伤
  signin TINYINT UNSIGNED DEFAULT 0 NOT NULL, #0未签到 1签到
  bonusadvancetable TEXT,
  areaadvancetable LONGTEXT,
  levelchange INT DEFAULT 0 NOT NULL, #0 无变化 1 升级, 2降级
  teamcurlevelcount INT DEFAULT 0 NOT NULL,
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
  INDEX idx_address_status_timepoint(address, status, timepoint)
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

CREATE TABLE IF NOT EXISTS node_used_txid (
  id INT UNSIGNED AUTO_INCREMENT,
  txid CHAR(64) UNIQUE NOT NULL,
  timepoint INT UNSIGNED NOT NULL,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS node_update_history (
  id INT UNSIGNED AUTO_INCREMENT,
  address VARCHAR(34) NOT NULL,
  operation TINYINT UNSIGNED NOT NULL, #1请求新节点 2请求解锁 3请求提取 4请求签到 5请求旧节点激活 6到期退出 7解锁成功
  referrer VARCHAR(34) DEFAULT '' NOT NULL,
  amount VARCHAR(40) DEFAULT '0' NOT NULL,
  days SMALLINT UNSIGNED DEFAULT 0 NOT NULL,
  penalty INT UNSIGNED DEFAULT 0 NOT NULL,
  txid VARCHAR(64) DEFAULT '' NOT NULL,
  timepoint INT UNSIGNED NOT NULL,
  status SMALLINT DEFAULT 0 NOT NULL, #0表示失败，1成功
  PRIMARY KEY (id),
  INDEX idx_address_timepoint(address, timepoint)
);

CREATE TABLE IF NOT EXISTS node_price (
  id INT UNSIGNED AUTO_INCREMENT,
  asset CHAR(40) UNIQUE NOT NULL,
  price VARCHAR(40) DEFAULT '0' NOT NULL,
  timepoint INT UNSIGNED NOT NULL,
  PRIMARY KEY (id)
);
