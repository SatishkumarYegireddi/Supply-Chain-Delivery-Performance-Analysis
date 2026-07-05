# Dataset Relevance Decisions

## Core Analytical Dataset
`DataCoSupplyChainDataset.csv`

Reason: contains order, order-item, customer, product, geography, sales, profit, shipping mode, scheduled shipping days, actual shipping days, delivery status, late-delivery flag, and order status fields. This file supports the primary supply chain delivery performance business problem.

Grain: one row per order item. `order_item_id` is the candidate item key; `order_id` repeats across order items and must be distinct-counted for order-level KPIs.

## Supporting Metadata
`DescriptionDataCoSupplyChain.csv`

Reason: contains source field descriptions and supports interpretation of the core analytical dataset.

## Secondary Analytical Dataset
`tokenized_access_logs.csv`

Reason: contains product/category web access events by date/hour/department. It is relevant to digital interest analysis but does not contain order IDs, delivery fields, shipping dates, profit, or fulfillment status. It is excluded from the primary delivery-performance model to keep the project focused and avoid unsupported joins.

## Source File Summary
- Main supply chain rows: 180,519
- Data dictionary rows: 52
- Access log rows: 469,977
