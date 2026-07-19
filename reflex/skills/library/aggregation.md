---
name: aggregation
description: When the question asks for counts, sums, averages, or a top-N ranking.
triggers:
  - count
  - how many
  - total
  - sum
  - average
  - top
  - most
  - least
  - highest
  - lowest
---

Use `GROUP BY` with aggregate functions (`COUNT`, `SUM`, `AVG`, `MAX`, `MIN`). For a
top-N question, aggregate first, then `ORDER BY` the aggregated column and `LIMIT` to N.
Revenue is `order_items.quantity * order_items.unit_price`, summed and joined through
`orders` when you need to filter by status or customer.

Example, count of orders per status:

```sql
SELECT status, COUNT(*)
FROM orders
GROUP BY status;
```

Example, top 5 products by units sold:

```sql
SELECT p.name, SUM(oi.quantity) AS units_sold
FROM order_items oi
JOIN products p ON p.id = oi.product_id
GROUP BY p.name
ORDER BY units_sold DESC
LIMIT 5;
```
