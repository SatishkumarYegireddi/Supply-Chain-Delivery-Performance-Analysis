# Project Charter

## Business Problem
Supply chain and operations leaders need to understand where delivery commitments are being missed and whether those operational risks overlap with meaningful sales and profitability exposure.

## Analytical Objective
Build a reproducible order-item analytics model that identifies late-delivery patterns by shipping mode, market, region, time period, category, and product while preserving grain-aware commercial KPIs.

## Primary Stakeholders
- Supply Chain Operations
- Logistics Management
- Fulfillment Operations
- Executive Operations Leadership

## Secondary Stakeholders
- Commercial Analytics
- Category Management

## Key Business Questions
- What share of orders are late, and how large is the average delay versus schedule?
- Which shipping modes carry the greatest late-delivery risk?
- Which markets and regions combine high order volume with poor delivery performance?
- Which categories create high sales exposure but weak profitability?
- Are delivery risks changing over time?

## Analytical Scope
The project covers orders from 2015-01 to 2018-01, using the core DataCo supply chain dataset. Headline delivery KPIs are calculated at order grain; revenue and profit are calculated at order-item grain.

## Exclusions
- Postal-code-level analysis is excluded because `order_zipcode` has substantial missingness.
- Access-log traffic analysis is excluded from the primary model because it cannot be reliably joined to order delivery records.
- Root-cause claims are excluded because the dataset does not contain carrier, warehouse, inventory, or staffing variables.

## Known Limitations
The data supports performance monitoring and prioritization, not causal attribution.
