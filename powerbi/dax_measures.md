# Corrected DAX Measure Library

## Order Scope Helper Pattern
Product and category filters live on `fact_order_items`. Measures that calculate order-level KPIs apply the current item-filtered order set to `fact_orders` using `TREATAS`.

```DAX
-- Pattern used inside order-level measures
VAR ScopedOrders = VALUES(fact_order_items[order_id])
RETURN CALCULATE(<order expression>, TREATAS(ScopedOrders, fact_orders[order_id]))
```

## Total Sales
```DAX
Total Sales = SUM(fact_order_items[order_item_total])
```
Format: Currency. Definition: discount-adjusted order-item revenue.

## Total Profit
```DAX
Total Profit = SUM(fact_order_items[benefit_per_order])
```
Format: Currency. Definition: source item-level profit.

## Profit Margin
```DAX
Profit Margin = DIVIDE([Total Profit], [Total Sales])
```
Format: Percentage. Definition: profit divided by net sales.

## Total Orders
```DAX
Total Orders =
VAR ScopedOrders = VALUES(fact_order_items[order_id])
RETURN
    CALCULATE(
DISTINCTCOUNT(fact_orders[order_id]),
TREATAS(ScopedOrders, fact_orders[order_id])
    )
```
Format: Whole number. Filter behavior: respects date, geography, customer, product/category, and shipping-mode filters.

## Total Order Items
```DAX
Total Order Items = COUNTROWS(fact_order_items)
```
Format: Whole number.

## Total Customers
```DAX
Total Customers = DISTINCTCOUNT(dim_customers[customer_id])
```
Format: Whole number.

## Average Order Value
```DAX
Average Order Value = DIVIDE([Total Sales], [Total Orders])
```
Format: Currency.

## Late Deliveries
```DAX
Late Deliveries =
VAR ScopedOrders = VALUES(fact_order_items[order_id])
RETURN
    CALCULATE(
SUM(fact_orders[late_delivery_flag]),
TREATAS(ScopedOrders, fact_orders[order_id])
    )
```
Format: Whole number.

## Late Delivery Rate
```DAX
Late Delivery Rate = DIVIDE([Late Deliveries], [Total Orders])
```
Format: Percentage.

## On-Time Deliveries
```DAX
On-Time Deliveries =
VAR ScopedOrders = VALUES(fact_order_items[order_id])
RETURN
    CALCULATE(
SUMX(fact_orders, IF(fact_orders[late_delivery_flag] = 0, 1, 0)),
TREATAS(ScopedOrders, fact_orders[order_id])
    )
```
Format: Whole number.

## On-Time Delivery Rate
```DAX
On-Time Delivery Rate = DIVIDE([On-Time Deliveries], [Total Orders])
```
Format: Percentage.

## Average Shipping Delay
```DAX
Average Shipping Delay =
VAR ScopedOrders = VALUES(fact_order_items[order_id])
RETURN
    CALCULATE(
AVERAGE(fact_orders[shipping_delay_days]),
TREATAS(ScopedOrders, fact_orders[order_id])
    )
```
Format: Decimal days.

## Average Actual Shipping Days
```DAX
Average Actual Shipping Days =
VAR ScopedOrders = VALUES(fact_order_items[order_id])
RETURN
    CALCULATE(
AVERAGE(fact_orders[days_for_shipping_real]),
TREATAS(ScopedOrders, fact_orders[order_id])
    )
```
Format: Decimal days.

## Average Scheduled Shipping Days
```DAX
Average Scheduled Shipping Days =
VAR ScopedOrders = VALUES(fact_order_items[order_id])
RETURN
    CALCULATE(
AVERAGE(fact_orders[days_for_shipment_scheduled]),
TREATAS(ScopedOrders, fact_orders[order_id])
    )
```
Format: Decimal days.

## Cancelled Orders
```DAX
Cancelled Orders =
VAR ScopedOrders = VALUES(fact_order_items[order_id])
RETURN
    CALCULATE(
SUM(fact_orders[cancellation_flag]),
TREATAS(ScopedOrders, fact_orders[order_id])
    )
```
Format: Whole number.

## Cancellation Rate
```DAX
Cancellation Rate = DIVIDE([Cancelled Orders], [Total Orders])
```
Format: Percentage.

## Shipping-Mode Filtered Sales
```DAX
Shipping-Mode Filtered Sales =
VAR ScopedOrders = VALUES(fact_orders[order_id])
RETURN
    CALCULATE(
[Total Sales],
TREATAS(ScopedOrders, fact_order_items[order_id])
    )
```
Format: Currency. Use when a visual slices sales by `dim_shipping_mode`.

## Sales Previous Period
```DAX
Sales Previous Period = CALCULATE([Total Sales], DATEADD(dim_date[date], -1, MONTH))
```
Format: Currency.

## Sales Growth
```DAX
Sales Growth = DIVIDE([Total Sales] - [Sales Previous Period], [Sales Previous Period])
```
Format: Percentage.
