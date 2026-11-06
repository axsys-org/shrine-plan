-- Absence is [] and must not be confused with an existing empty order.
SELECT COALESCE(NULLIF((SELECT o.OrderID, o.CustomerID, c.CustomerName, c.BillToCustomerID,
    o.OrderDate, o.ExpectedDeliveryDate, o.CustomerPurchaseOrderNumber,
    o.IsUndersupplyBackordered, o.PickingCompletedWhen, o.LastEditedWhen,
    (SELECT ol.OrderLineID, ol.StockItemID, ol.Description, ol.PackageTypeID,
            ol.Quantity, ol.UnitPrice, ol.TaxRate, ol.PickedQuantity,
            ol.PickingCompletedWhen,
            si.IsChillerStock, si.SupplierID, sih.QuantityOnHand,
            sih.ReorderLevel, sih.TargetStockLevel
     FROM Sales.OrderLines AS ol
     JOIN Warehouse.StockItems AS si ON si.StockItemID = ol.StockItemID
     JOIN Warehouse.StockItemHoldings AS sih ON sih.StockItemID = ol.StockItemID
     WHERE ol.OrderID = o.OrderID ORDER BY ol.OrderLineID
     FOR JSON PATH, INCLUDE_NULL_VALUES) AS Lines,
    (SELECT i.InvoiceID, i.InvoiceDate FROM Sales.Invoices AS i
     WHERE i.OrderID = o.OrderID ORDER BY i.InvoiceID
     FOR JSON PATH, INCLUDE_NULL_VALUES) AS Invoices
FROM Sales.Orders AS o
JOIN Sales.Customers AS c ON c.CustomerID = o.CustomerID
WHERE o.OrderID = @id
FOR JSON PATH, INCLUDE_NULL_VALUES), N''), N'[]') AS Capture;
