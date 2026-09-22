-- 执行位置：retail_finance数据库
-- 用途：检查连接、创建分析schema、查看现有表
-- 数据库本身通过pgAdmin界面创建
SELECT current_database(), current_user;
CREATE SCHEMA IF NOT EXISTS analytics;
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'analytics'
ORDER BY table_name;
