-- The whole Order Store schema. Applied by PostgresOrderStore on startup; no migrations.
CREATE TABLE IF NOT EXISTS orders (
    order_id         text PRIMARY KEY,
    customer_id      text NOT NULL,
    total            numeric(10, 2) NOT NULL,
    status           text NOT NULL
        CHECK (status IN ('pending', 'shipped', 'delivered', 'cancelled', 'refunded')),
    shipping_address jsonb
);
