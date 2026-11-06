-- Discover tables for a subsequent schema capture; no row-count guesses.
SELECT COALESCE(NULLIF((SELECT t.object_id AS ObjectId, s.name AS SchemaName, t.name AS TableName,
       t.temporal_type_desc AS TemporalType
FROM sys.tables AS t JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name
FOR JSON PATH), N''), N'[]') AS Capture;
