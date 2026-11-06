-- One bounded keyset page, not a claim to represent every order.
SELECT COALESCE(NULLIF((SELECT TOP (@limit)
    o.OrderID, o.CustomerID, c.CustomerName, o.OrderDate,
    o.ExpectedDeliveryDate, o.IsUndersupplyBackordered,
    o.PickingCompletedWhen, o.LastEditedWhen,
    (SELECT i.InvoiceID FROM Sales.Invoices AS i WHERE i.OrderID = o.OrderID
     ORDER BY i.InvoiceID FOR JSON PATH) AS Invoices
FROM Sales.Orders AS o
JOIN Sales.Customers AS c ON c.CustomerID = o.CustomerID
WHERE o.OrderID > @after
ORDER BY o.OrderID
FOR JSON PATH, INCLUDE_NULL_VALUES), N''), N'[]') AS Capture;
