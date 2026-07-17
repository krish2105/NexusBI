-- Nexus BI Olist real-world demo data loader for PostgreSQL 15+
-- Run from the root of this package with: psql "$DATABASE_URL" -f load_postgres.sql
-- All data tables are created in schema nexus_demo.

BEGIN;
CREATE SCHEMA IF NOT EXISTS nexus_demo;
SET search_path TO nexus_demo, public;

DROP TABLE IF EXISTS reviews, payments, order_items, orders, sellers, customers, products, categories, geolocation_zip_summary, geolocation, dates, regions CASCADE;

CREATE TABLE regions (
  region_id text PRIMARY KEY, ibge_state_code integer NOT NULL, state_code text NOT NULL,
  state_name_pt text NOT NULL, macroregion_name_en text NOT NULL, macroregion_name_pt text NOT NULL,
  country_code text NOT NULL, country_name text NOT NULL
);
CREATE TABLE geolocation (
  geolocation_row_id text PRIMARY KEY, source_row_number bigint NOT NULL UNIQUE,
  geolocation_zip_code_prefix text NOT NULL, geolocation_lat numeric NOT NULL, geolocation_lng numeric NOT NULL,
  geolocation_city text NOT NULL, geolocation_state text NOT NULL,
  region_id text NOT NULL REFERENCES regions(region_id), broad_brazil_bbox_outlier_flag boolean NOT NULL
);
CREATE TABLE geolocation_zip_summary (
  geolocation_zip_state_id text PRIMARY KEY, geolocation_zip_code_prefix text NOT NULL,
  geolocation_state text NOT NULL, region_id text NOT NULL REFERENCES regions(region_id),
  representative_city text NOT NULL, observation_count integer NOT NULL, distinct_city_count integer NOT NULL,
  latitude_mean_all numeric NOT NULL, longitude_mean_all numeric NOT NULL,
  latitude_mean_in_broad_bbox numeric, longitude_mean_in_broad_bbox numeric,
  broad_bbox_outlier_count integer NOT NULL,
  UNIQUE(geolocation_zip_code_prefix, geolocation_state)
);
CREATE TABLE dates (
  date_id integer PRIMARY KEY, date date NOT NULL, day_of_month integer NOT NULL, day_of_week_iso integer NOT NULL,
  day_name text NOT NULL, day_name_short text NOT NULL, week_start_date date NOT NULL, iso_week integer NOT NULL,
  iso_year integer NOT NULL, month_number integer NOT NULL, month_name text NOT NULL, month_name_short text NOT NULL,
  year_month text NOT NULL, quarter_number integer NOT NULL, year_quarter text NOT NULL, year integer NOT NULL,
  is_weekend boolean NOT NULL, is_month_end boolean NOT NULL
);
CREATE TABLE categories (
  category_id text PRIMARY KEY, category_name_pt text NOT NULL, category_name_en text NOT NULL,
  translation_status text NOT NULL, product_count integer NOT NULL, order_item_count integer NOT NULL,
  merchandise_value numeric(14,2) NOT NULL
);
CREATE TABLE products (
  product_id text PRIMARY KEY, category_id text NOT NULL REFERENCES categories(category_id),
  product_category_name_pt text NOT NULL, product_category_name_en text NOT NULL,
  category_translation_status text NOT NULL, source_category_missing_flag boolean NOT NULL,
  product_name_length integer, product_description_length integer, product_photos_qty integer,
  product_weight_g numeric, product_length_cm numeric, product_height_cm numeric, product_width_cm numeric,
  product_volume_cm3 numeric, product_density_g_per_cm3 numeric, dimensions_complete_flag boolean NOT NULL,
  content_metadata_complete_flag boolean NOT NULL
);
CREATE TABLE customers (
  customer_id text PRIMARY KEY, customer_unique_id text NOT NULL, customer_zip_code_prefix text NOT NULL,
  customer_city text NOT NULL, customer_state text NOT NULL, region_id text NOT NULL REFERENCES regions(region_id),
  customer_order_sequence integer NOT NULL, first_purchase_timestamp timestamp NOT NULL,
  last_purchase_timestamp timestamp NOT NULL, lifetime_order_count integer NOT NULL,
  repeat_customer_flag boolean NOT NULL, distinct_location_count integer NOT NULL
);
CREATE TABLE sellers (
  seller_id text PRIMARY KEY, seller_zip_code_prefix text NOT NULL, seller_city text NOT NULL,
  seller_state text NOT NULL, region_id text NOT NULL REFERENCES regions(region_id),
  first_sale_timestamp timestamp NOT NULL, last_sale_timestamp timestamp NOT NULL,
  sold_item_count integer NOT NULL, distinct_order_count integer NOT NULL, distinct_product_count integer NOT NULL,
  merchandise_value numeric(14,2) NOT NULL, freight_value numeric(14,2) NOT NULL
);
CREATE TABLE orders (
  order_id text PRIMARY KEY, customer_id text NOT NULL REFERENCES customers(customer_id), customer_unique_id text NOT NULL,
  region_id text NOT NULL REFERENCES regions(region_id), order_status text NOT NULL,
  order_purchase_timestamp timestamp NOT NULL, order_date_id integer NOT NULL REFERENCES dates(date_id),
  order_approved_at timestamp, order_delivered_carrier_timestamp timestamp,
  order_delivered_customer_timestamp timestamp, order_estimated_delivery_timestamp timestamp NOT NULL,
  item_count integer NOT NULL, distinct_product_count integer NOT NULL, distinct_seller_count integer NOT NULL,
  merchandise_value numeric(14,2) NOT NULL, freight_value numeric(14,2) NOT NULL,
  order_line_total_value numeric(14,2) NOT NULL, payment_count integer NOT NULL, payment_value numeric(14,2),
  primary_payment_type text, max_payment_installments integer, review_count integer NOT NULL,
  average_review_score numeric, latest_review_score integer, has_review_comment_flag boolean NOT NULL,
  approval_lead_hours numeric, purchase_to_carrier_days numeric, purchase_to_delivery_days numeric,
  carrier_to_customer_days numeric, delivery_vs_estimate_days numeric, delivered_late_flag boolean,
  has_items_flag boolean NOT NULL, has_payment_flag boolean NOT NULL, has_review_flag boolean NOT NULL,
  source_missing_approved_at_flag boolean NOT NULL, source_missing_carrier_timestamp_flag boolean NOT NULL,
  source_missing_customer_delivery_timestamp_flag boolean NOT NULL, chronology_anomaly_flag boolean NOT NULL,
  payment_reconciliation_difference numeric(14,2), payment_reconciled_flag boolean,
  delivered_status_flag boolean NOT NULL, canceled_status_flag boolean NOT NULL
);
CREATE TABLE order_items (
  order_id text NOT NULL REFERENCES orders(order_id), order_item_id integer NOT NULL,
  product_id text NOT NULL REFERENCES products(product_id), seller_id text NOT NULL REFERENCES sellers(seller_id),
  shipping_limit_timestamp timestamp NOT NULL, shipping_limit_date_id integer NOT NULL REFERENCES dates(date_id),
  quantity integer NOT NULL, unit_price numeric(14,2) NOT NULL, freight_value numeric(14,2) NOT NULL,
  line_merchandise_value numeric(14,2) NOT NULL, line_total_value numeric(14,2) NOT NULL,
  PRIMARY KEY(order_id,order_item_id)
);
CREATE TABLE payments (
  order_id text NOT NULL REFERENCES orders(order_id), payment_sequential integer NOT NULL,
  payment_type text NOT NULL, payment_installments integer NOT NULL, payment_value numeric(14,2) NOT NULL,
  PRIMARY KEY(order_id,payment_sequential)
);
CREATE TABLE reviews (
  review_row_id text PRIMARY KEY, review_id text NOT NULL, order_id text NOT NULL REFERENCES orders(order_id),
  review_score integer NOT NULL CHECK(review_score BETWEEN 1 AND 5), review_comment_title text,
  review_comment_message text, has_title_flag boolean NOT NULL, has_message_flag boolean NOT NULL,
  review_creation_timestamp timestamp NOT NULL, review_creation_date_id integer NOT NULL REFERENCES dates(date_id),
  review_answer_timestamp timestamp NOT NULL, response_lag_hours numeric NOT NULL,
  duplicate_review_id_flag boolean NOT NULL, multiple_reviews_for_order_flag boolean NOT NULL
);

COMMIT;

\copy nexus_demo.regions FROM 'core/regions.csv' CSV HEADER ENCODING 'UTF8';
\copy nexus_demo.geolocation FROM 'supplementary/geolocation.csv' CSV HEADER ENCODING 'UTF8';
\copy nexus_demo.geolocation_zip_summary FROM 'derived/geolocation_zip_summary.csv' CSV HEADER ENCODING 'UTF8' NULL '';
\copy nexus_demo.dates FROM 'core/dates.csv' CSV HEADER ENCODING 'UTF8' NULL '';
\copy nexus_demo.categories FROM 'core/categories.csv' CSV HEADER ENCODING 'UTF8';
\copy nexus_demo.products FROM 'core/products.csv' CSV HEADER ENCODING 'UTF8' NULL '';
\copy nexus_demo.customers FROM 'core/customers.csv' CSV HEADER ENCODING 'UTF8';
\copy nexus_demo.sellers FROM 'core/sellers.csv' CSV HEADER ENCODING 'UTF8';
\copy nexus_demo.orders FROM 'core/orders.csv' CSV HEADER ENCODING 'UTF8' NULL '';
\copy nexus_demo.order_items FROM 'core/order_items.csv' CSV HEADER ENCODING 'UTF8';
\copy nexus_demo.payments FROM 'supplementary/payments.csv' CSV HEADER ENCODING 'UTF8';
\copy nexus_demo.reviews FROM 'supplementary/reviews.csv' CSV HEADER ENCODING 'UTF8' NULL '';

CREATE INDEX idx_geolocation_zip_state ON nexus_demo.geolocation(geolocation_zip_code_prefix, geolocation_state);
CREATE INDEX idx_geo_summary_region ON nexus_demo.geolocation_zip_summary(region_id);
CREATE INDEX idx_orders_purchase ON nexus_demo.orders(order_purchase_timestamp);
CREATE INDEX idx_orders_unique_customer ON nexus_demo.orders(customer_unique_id);
CREATE INDEX idx_orders_region ON nexus_demo.orders(region_id);
CREATE INDEX idx_items_product ON nexus_demo.order_items(product_id);
CREATE INDEX idx_items_seller ON nexus_demo.order_items(seller_id);
CREATE INDEX idx_reviews_order ON nexus_demo.reviews(order_id);
CREATE INDEX idx_payments_order ON nexus_demo.payments(order_id);
ANALYZE nexus_demo.geolocation;
ANALYZE nexus_demo.geolocation_zip_summary;
ANALYZE nexus_demo.orders;
ANALYZE nexus_demo.order_items;
