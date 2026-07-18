---
name: joins
description: When the question spans more than one table, for example anything that relates customers to their orders, orders to their line items or payments, or products to what was sold.
---

The schema's foreign keys are:

- `orders.customer_id` references `customers.id`
- `order_items.order_id` references `orders.id`
- `order_items.product_id` references `products.id`
- `payments.order_id` references `orders.id`

Join on these keys explicitly with `JOIN ... ON`. Never guess a relationship that is not
one of the four above.

Example, revenue per customer:

```sql
SELECT c.name, SUM(oi.quantity * oi.unit_price) AS revenue
FROM customers c
JOIN orders o ON o.customer_id = c.id
JOIN order_items oi ON oi.order_id = o.id
GROUP BY c.name;
```

Example, products bought alongside payments:

```sql
SELECT p.name, pay.amount
FROM order_items oi
JOIN products p ON p.id = oi.product_id
JOIN payments pay ON pay.order_id = oi.order_id;
```
