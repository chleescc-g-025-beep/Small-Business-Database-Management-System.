-- =====================================================
-- REPORT 1: Overall business performance
-- =====================================================

SELECT
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(DISTINCT o.customer_id) AS unique_customers,
    SUM(oi.quantity) AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status = 'COMPLETED';


-- =====================================================
-- REPORT 2: Revenue by product
-- =====================================================

SELECT
    p.product_name,
    SUM(oi.quantity) AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status = 'COMPLETED'
GROUP BY p.product_id, p.product_name
ORDER BY revenue DESC;


-- =====================================================
-- REPORT 3: Daily sales
-- =====================================================

SELECT
    o.order_date,
    COUNT(DISTINCT o.order_id) AS total_orders,
    ROUND(SUM(oi.quantity * oi.unit_price), 2) AS daily_revenue
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status = 'COMPLETED'
GROUP BY o.order_date
ORDER BY o.order_date;


-- =====================================================
-- REPORT 4: Customer spending
-- =====================================================

SELECT
    c.first_name || ' ' || c.last_name AS customer_name,
    COUNT(DISTINCT o.order_id) AS total_orders,
    ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_spent
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status = 'COMPLETED'
GROUP BY c.customer_id, customer_name
ORDER BY total_spent DESC;


-- =====================================================
-- REPORT 5: Current inventory
-- =====================================================

SELECT
    product_name,
    category,
    stock_quantity,
    price,
    ROUND(stock_quantity * price, 2) AS stock_value
FROM products
ORDER BY stock_quantity ASC;


-- =====================================================
-- REPORT 6: Products that need restocking
-- =====================================================

SELECT
    product_name,
    stock_quantity
FROM products
WHERE stock_quantity < 25
ORDER BY stock_quantity ASC;
