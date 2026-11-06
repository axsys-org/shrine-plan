-- Structural evidence for one explicitly selected table, including its keys.
SELECT COALESCE(NULLIF((SELECT s.name AS SchemaName, t.name AS TableName,
    CONVERT(nvarchar(max), ep.value) AS Description,
    (SELECT c.name AS ColumnName, ty.name AS SqlType, c.max_length AS MaxLength,
            c.precision AS [Precision], c.scale AS Scale, c.is_nullable AS Nullable,
            CONVERT(nvarchar(max), cp.value) AS Description
     FROM sys.columns AS c JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
     LEFT JOIN sys.extended_properties AS cp ON cp.major_id = c.object_id
          AND cp.minor_id = c.column_id AND cp.class = 1 AND cp.name = N'Description'
     WHERE c.object_id = t.object_id ORDER BY c.column_id
     FOR JSON PATH, INCLUDE_NULL_VALUES) AS Columns,
    (SELECT i.name AS ConstraintName, c.name AS ColumnName, ic.key_ordinal AS Ordinal
     FROM sys.indexes AS i JOIN sys.index_columns AS ic
       ON ic.object_id = i.object_id AND ic.index_id = i.index_id
     JOIN sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
     WHERE i.object_id = t.object_id AND i.is_primary_key = 1
     ORDER BY ic.key_ordinal FOR JSON PATH) AS PrimaryKey,
    (SELECT fk.name AS ConstraintName, c.name AS ColumnName,
            rs.name AS ReferencedSchema, rt.name AS ReferencedTable,
            rc.name AS ReferencedColumn
     FROM sys.foreign_keys AS fk JOIN sys.foreign_key_columns AS fc ON fc.constraint_object_id = fk.object_id
     JOIN sys.columns AS c ON c.object_id = fc.parent_object_id AND c.column_id = fc.parent_column_id
     JOIN sys.tables AS rt ON rt.object_id = fc.referenced_object_id
     JOIN sys.schemas AS rs ON rs.schema_id = rt.schema_id
     JOIN sys.columns AS rc ON rc.object_id = rt.object_id AND rc.column_id = fc.referenced_column_id
     WHERE fk.parent_object_id = t.object_id ORDER BY fk.name, fc.constraint_column_id
     FOR JSON PATH) AS ForeignKeys
FROM sys.tables AS t JOIN sys.schemas AS s ON s.schema_id = t.schema_id
LEFT JOIN sys.extended_properties AS ep ON ep.major_id = t.object_id
     AND ep.minor_id = 0 AND ep.class = 1 AND ep.name = N'Description'
WHERE t.object_id = @object
FOR JSON PATH, INCLUDE_NULL_VALUES), N''), N'[]') AS Capture;
