---
name: date_filtering
description: When the question involves time ranges, relative dates, or grouping by day, week, month, or year.
triggers:
  - date
  - day
  - week
  - month
  - quarter
  - year
  - recent
  - since
  - between
  - time
---

The date columns are `customers.signup_date`, `orders.order_date`, and `payments.paid_date`,
all of type `date`. Use Postgres `date_trunc` to bucket by period and `interval` for
relative ranges.

Example, orders per month:

```sql
SELECT date_trunc('month', order_date) AS month, COUNT(*)
FROM orders
GROUP BY 1
ORDER BY 1;
```

Example, orders in the last 90 days relative to the most recent order date in the data
(do not use the current wall-clock date, the dataset is historical):

```sql
SELECT *
FROM orders
WHERE order_date >= (SELECT MAX(order_date) FROM orders) - INTERVAL '90 days';
```
