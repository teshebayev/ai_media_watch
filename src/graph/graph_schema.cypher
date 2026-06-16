// Shadow Graph — схема (ТЗ §12). Констрейнты уникальности ключевых узлов.

CREATE CONSTRAINT IF NOT EXISTS FOR (d:Domain)           REQUIRE d.name    IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (t:TelegramUsername) REQUIRE t.name    IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (p:PromoCode)        REQUIRE p.code    IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (w:Wallet)           REQUIRE w.address IS UNIQUE;

// Типы узлов (ТЗ §12.1):
// (:Video) (:Post) (:Call) (:Account) (:Blogger) (:TelegramUsername)
// (:PhoneHash) (:Wallet) (:URL) (:Domain) (:PromoCode) (:Organization)
// (:RiskSignal) (:DatasetSource)

// Типы связей (ТЗ §12.2):
// (:Blogger)-[:PUBLISHED]->(:Video)
// (:Video)-[:MENTIONS]->(:Domain)
// (:Video)-[:MENTIONS]->(:TelegramUsername)
// (:Video)-[:HAS_PROMO]->(:PromoCode)
// (:Video)-[:HAS_SIGNAL]->(:RiskSignal)
// (:Call)-[:CLAIMS_AUTHORITY]->(:Organization)
// (:Post)-[:MENTIONS]->(:URL)
// (:URL)-[:HAS_DOMAIN]->(:Domain)
// (:Wallet)-[:REPORTED_IN]->(:ThreatIntel)

// Запрос повторяемости домена (главная фича демо, ТЗ §12.3):
// MATCH (d:Domain)<-[:MENTIONS]-(v:Video)
// WITH d, count(v) AS uses WHERE uses > 1
// RETURN d.name, uses ORDER BY uses DESC;
