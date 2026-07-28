-- ============================================================================
-- TIDE · seed_decision.sql
-- Rule constants (mirrors DETAILS.md §6), customer-facing reason copy
-- (DETAILS.md §12), and the policy corpus for Cortex Search + rejection
-- citations. Idempotent: scoped deletes first.
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA DECISION;

DELETE FROM RULE_CONSTANTS WHERE key IS NOT NULL;
DELETE FROM REASON_COPY    WHERE invalid_reason_code IS NOT NULL;
DELETE FROM POLICIES       WHERE slug IS NOT NULL;

-- ---------------------------------------------------------------------------
-- RULE_CONSTANTS — the single source; procedures and UI read, never hardcode.
-- (VARIANT values require INSERT ... SELECT, not VALUES.)
-- ---------------------------------------------------------------------------
INSERT INTO RULE_CONSTANTS (key, value, description, brl_ref)
SELECT 'AUTONOMOUS_LIMIT_USD',      TO_VARIANT(50.00), 'Max amount refunded/replaced without human approval', '§6'
UNION ALL SELECT 'RETURN_WINDOW_DAYS',       TO_VARIANT(7),     'Days from window-basis date a return/refund-for-condition is in policy', '§6'
UNION ALL SELECT 'DELIVERY_SLA_BREACH_DAYS', TO_VARIANT(3),     'Days past estimated delivery that constitute an SLA breach', '§6'
UNION ALL SELECT 'STALE_TRANSIT_DAYS',       TO_VARIANT(7),     'Days without tracking movement that make a shipment presumptively stalled', '§6'
UNION ALL SELECT 'INACTIVITY_TIMEOUT_MIN',   TO_VARIANT(15),    'Idle minutes in pending_triage before auto-close as unresponsive', '§6'
UNION ALL SELECT 'MIN_REJECTION_CHARS',      TO_VARIANT(50),    'Minimum human rejection-reason length', '§6'
UNION ALL SELECT 'MIN_REJECTION_CITATIONS',  TO_VARIANT(1),     'Minimum policy citations on a human rejection', '§6'
UNION ALL SELECT 'MAX_PROOF_UPLOADS',        TO_VARIANT(2),     'Max proof images per case', '§6'
UNION ALL SELECT 'MAX_PROOF_BYTES',          TO_VARIANT(5242880), 'Max bytes per proof image (5 MB)', '§6'
UNION ALL SELECT 'MAX_FOLLOWUP_QUESTIONS',   TO_VARIANT(3),     'Max intake follow-ups before routing with what we have', '§6'
UNION ALL SELECT 'CURRENCY',                 TO_VARIANT('USD'), 'All amounts', '§6'
UNION ALL SELECT 'MODEL_TEXT',               TO_VARIANT('openai-gpt-5-mini'),  'Default text model for AI_COMPLETE structured calls', 'AGENTSPEC'
UNION ALL SELECT 'MODEL_VISION',             TO_VARIANT('gemini-2.5-flash'),   'Vision model for proof analysis', 'AGENTSPEC'
UNION ALL SELECT 'MODEL_AGENT',              TO_VARIANT('auto'),               'Investigator agent orchestration model', 'AGENTSPEC';

-- ---------------------------------------------------------------------------
-- REASON_COPY — one row per invalid-reason code (closed set, DETAILS.md §12).
-- High appeal priority: proof_contradicts_claim, duplicate_case, policy_exclusion.
-- ---------------------------------------------------------------------------
INSERT INTO REASON_COPY (invalid_reason_code, customer_copy, appeal_priority) VALUES
  ('insufficient_proof',        'The photos provided do not clearly show the issue you described. You can upload clearer photos, or appeal and a specialist will review your case.', 'normal'),
  ('proof_contradicts_claim',   'The photos provided appear to show something different from the issue you described. If you believe this is a mistake, appeal and a specialist will review everything personally.', 'high'),
  ('insufficient_evidence',     'Our payment records show only one charge for this order, so we could not confirm a duplicate charge. If you have a bank or card statement showing two charges, appeal and a specialist will review it with you.', 'high'),
  ('outside_return_window',     'This order falls outside our 7-day return window, counted from the day it was delivered. If there are special circumstances, you can appeal for a specialist review.', 'normal'),
  ('non_returnable_item',       'This order is not eligible for return in its current state — returns are available once an order has been fulfilled. You can appeal if you believe this is incorrect.', 'normal'),
  ('insufficient_inventory',    'The replacement you requested is currently out of stock. You can choose a refund instead, or appeal to discuss other options with a specialist.', 'normal'),
  ('unsupported_resolution_type','The resolution you requested is not available for this type of issue. Please choose one of the offered options, or appeal for a specialist review.', 'normal'),
  ('duplicate_case',            'There is already an open case for this order. You can continue in the existing conversation — opening a second case is not needed.', 'high'),
  ('order_not_found',           'We could not match this dispute to an order on your account. Please double-check the order, or appeal and a specialist will help you locate it.', 'normal'),
  ('ineligible_order_state',    'This order is not in a state that supports this dispute — for example, it may have been cancelled before shipping. You can appeal if you believe this is wrong.', 'normal'),
  ('policy_exclusion',          'This request falls under a policy exclusion and cannot be resolved automatically. Appeal to have a specialist review the details with you.', 'high');

-- ---------------------------------------------------------------------------
-- POLICIES — the corpus behind Cortex Search and the rejection citation picker.
-- Slugs are stable identifiers; bodies written to be retrievable by topic.
-- ---------------------------------------------------------------------------
INSERT INTO POLICIES (policy_id, slug, category, title, body, active) VALUES
  ('POL-001','autonomous-refund-limit','store','Autonomous resolution limit',
   'Disputes with an eligible amount of 50.00 USD or less may be resolved autonomously by the system without human approval, provided all guardrails pass. Amounts above this limit always require approver review. The limit applies to the affected-item amount, not necessarily the full order total.', TRUE),
  ('POL-002','return-window','return','Seven-day return window',
   'Returns and condition-based refunds (damaged, not as described, wrong item) must be initiated within 7 days of delivery. The window is counted from the delivery date recorded by the carrier, or the fulfillment date when no delivery record exists. Outside the window, customers may appeal for a specialist review of special circumstances.', TRUE),
  ('POL-003','proof-requirements','return','Photo proof requirements',
   'Damaged goods, wrong item, not-as-described, and partial fulfillment claims require photo evidence before assessment: up to 2 images (JPEG, PNG, or WEBP, max 5 MB each) clearly showing the item and the issue. Photo evidence informs the assessment but never overrides recorded facts such as tracking or payment records.', TRUE),
  ('POL-004','duplicate-refund-review','payment','Duplicate refund protection',
   'When a refund is requested on an order that already has one or more processed refunds, the case is always escalated to a human specialist regardless of amount. The specialist verifies whether the prior refund covers the current claim before any additional payout.', TRUE),
  ('POL-005','payment-confirmation-required','payment','Payment confirmation requirement',
   'No refund may be issued against an order whose payment is not in a confirmed state. Pending or failed payments route the case to a specialist, who verifies payment status with the gateway before proceeding.', TRUE),
  ('POL-006','delivery-sla','sla','Delivery service-level commitment',
   'Orders are committed to the estimated delivery date shown at checkout. A delivery completed more than 3 days after the estimate is an SLA breach. SLA-breach compensation is limited to the shipping fee; product-value refunds require a separate product-condition claim.', TRUE),
  ('POL-007','shipping-fee-refund','sla','Shipping fee compensation for late delivery',
   'When a delivery breaches the SLA but the goods arrive intact, the customer is entitled to a refund of the shipping fee only. This compensation may be issued autonomously when the fee is within the autonomous limit.', TRUE),
  ('POL-008','replacement-inventory','store','Replacement stock requirement',
   'A replacement can only be offered when every affected item has sufficient available stock across warehouses. When stock is insufficient, the customer is offered a refund alternative or may appeal. Reserved stock does not count as available.', TRUE),
  ('POL-009','returns-approval-required','return','Returns always require approval',
   'Return requests, including change-of-mind returns, are never executed autonomously. Every return is reviewed by an approver, who confirms eligibility (order state and return window) before the return is authorised.', TRUE),
  ('POL-010','non-receipt-tracking','delivery','Non-receipt claims and tracking evidence',
   'Non-receipt claims are assessed against carrier tracking. A recorded delivery scan contradicting a non-receipt claim escalates the case with the tracking evidence attached. Absent any delivery or loss record, low-value non-receipt refunds may be resolved autonomously; shipments with no movement for more than 7 days are treated as presumptively stalled.', TRUE),
  ('POL-011','lost-shipment','delivery','Lost shipment resolution',
   'When a carrier declares a shipment lost, the customer is entitled to a refund or replacement of the affected items. A loss record with no subsequent delivery scan is sufficient evidence; the resolution amount follows the affected-item value.', TRUE),
  ('POL-012','partial-fulfillment-review','store','Partial fulfillment review',
   'Claims that an order arrived incomplete always receive human review, because they involve reconciling picked, shipped, and delivered quantities across systems. The customer identifies the missing items during intake; the specialist verifies against fulfillment records.', TRUE),
  ('POL-013','appeal-rights','store','Customer appeal rights',
   'Any automated decision that closes a path to the customer (insufficient proof, out-of-window, inventory, or policy exclusions) may be appealed once. Appeals route to a human specialist with the full case file. Appeals of proof-contradiction and duplicate-case findings are treated as high priority.', TRUE),
  ('POL-014','rejection-standards','store','Approver rejection standards',
   'An approver rejecting a resolution request must provide a written reason of at least 50 characters and cite at least one policy by its identifier. Rejections without adequate reasoning are not accepted by the system.', TRUE);
