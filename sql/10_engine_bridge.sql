-- ============================================================================
-- TIDE · 10_engine_bridge.sql
-- The bridge between the deterministic engine and Snowflake (TASKS.md C-6).
--
-- Two halves:
--   INVESTIGATION.ASSEMBLE_EVIDENCE  builds the bundle (SCHEMA.md §5)
--   DECISION.ADJUDICATE              runs tide_decision over it
--
-- ADJUDICATE is not in this file. It is a Python procedure that imports the
-- engine from CODE_STAGE, so the module zip has to be on the stage before the
-- procedure can be created. It lives in sql/procedures/adjudicate.sql and is
-- deployed by scripts/deploy.py step 3, after the upload.
--
-- ASSEMBLE_EVIDENCE is deterministic by design. The Cortex Agent
-- (INVESTIGATOR) is the intended assembler per ARCHITECTURE.md §7.1, but
-- CLAUDE.md requires every AI call to have a fallback that keeps the pipeline
-- demonstrable without AI. This is that fallback, and it is the path that runs
-- today because the agent object does not exist yet. It calls the same four
-- tools the agent would.
--
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA DECISION;

-- ---------------------------------------------------------------------------
-- CODE_STAGE — Python module code for Snowpark procedures.
-- tide_decision.zip is uploaded here by deploy.py; ADJUDICATE imports it.
-- ---------------------------------------------------------------------------
CREATE STAGE IF NOT EXISTS CODE_STAGE
    DIRECTORY = (ENABLE = TRUE)
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
    COMMENT = 'Python module code for Snowpark procedures (tide_decision engine)';

USE SCHEMA INVESTIGATION;

-- ---------------------------------------------------------------------------
-- ASSEMBLE_EVIDENCE — build the evidence bundle for a case.
--
-- The bundle is the engine's entire input, so this procedure owns the contract
-- in SCHEMA.md §5. Every field it emits is one the engine reads; a field the
-- engine does not read does not belong here.
--
-- Note `payments`: the singular `payment` cannot express how many charges an
-- order carries, and G-10 needs that count. Both come from one
-- GET_PAYMENT_STATUS call.
--
-- Sources are recorded per section so a partial assembly is visible rather than
-- silent — the adjudicator escalates on a failed assembly rather than deciding
-- on thin evidence.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE ASSEMBLE_EVIDENCE(CASE_ID VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Build the evidence bundle for a case from the RETAIL sources and the four investigation tools, store it, and return it. Input: case_id. Returns the bundle, or {error} if the case or its order is missing.'
EXECUTE AS OWNER
AS
$$
DECLARE
    v_order_id   VARCHAR;
    v_subtype    VARCHAR;
    v_preference VARCHAR;
    shipment_res VARIANT;
    payment_res  VARIANT;
    refund_res   VARIANT;
    stock_res    VARIANT;
    skus         ARRAY;
    order_obj    VARIANT;
    items_arr    ARRAY;
    affected_arr ARRAY;
    inventory_arr ARRAY;
    proof_obj    VARIANT;
    bundle       VARIANT;
    bundle_id    VARCHAR;
    err          VARCHAR;
BEGIN
    SELECT v.order_id, v.dispute_subtype, v.resolution_preference
      INTO :v_order_id, :v_subtype, :v_preference
    FROM TIDE.TRIAGE.V_CASE_CURRENT v
    WHERE v.case_id = :CASE_ID;

    IF (v_order_id IS NULL) THEN
        RETURN OBJECT_CONSTRUCT('error', 'Case not found.');
    END IF;

    -- The four investigation tools, exactly as the agent would call them.
    CALL TIDE.INVESTIGATION.GET_SHIPMENT_TIMELINE(:v_order_id) INTO :shipment_res;
    CALL TIDE.INVESTIGATION.GET_PAYMENT_STATUS(:v_order_id)    INTO :payment_res;
    CALL TIDE.INVESTIGATION.GET_REFUND_HISTORY(:v_order_id)    INTO :refund_res;

    SELECT ARRAY_AGG(DISTINCT oi.sku) INTO :skus
    FROM TIDE.RETAIL.ORDER_ITEMS oi WHERE oi.order_id = :v_order_id;

    CALL TIDE.INVESTIGATION.CHECK_INVENTORY(:skus) INTO :stock_res;

    -- Each section is built into its own variable first. Snowflake Scripting
    -- rejects `SELECT ... INTO` when the select list contains scalar
    -- subqueries ("INTO clause is not allowed in this context"), so the bundle
    -- is assembled from variables at the end rather than in one expression.
    SELECT OBJECT_CONSTRUCT_KEEP_NULL(
               'order_id',           o.order_id,
               'status',             o.status,
               'total_amount',       o.total_amount,
               'shipping_fee',       o.shipping_fee,
               'placed_at',          TIDE.INVESTIGATION.ISO_UTC(o.placed_at),
               'fulfilled_at',       TIDE.INVESTIGATION.ISO_UTC(o.fulfilled_at),
               'delivered_at',       TIDE.INVESTIGATION.ISO_UTC(o.delivered_at),
               'estimated_delivery', TIDE.INVESTIGATION.ISO_UTC(o.estimated_delivery))
      INTO :order_obj
    FROM TIDE.RETAIL.ORDERS o
    WHERE o.order_id = :v_order_id;

    IF (order_obj IS NULL) THEN
        RETURN OBJECT_CONSTRUCT('error', 'Order not found for this case.');
    END IF;

    SELECT COALESCE(ARRAY_AGG(OBJECT_CONSTRUCT_KEEP_NULL(
                        'item_id',    oi.item_id,
                        'sku',        oi.sku,
                        'name',       oi.product_name,
                        'qty',        oi.quantity,
                        'unit_price', oi.unit_price))
                      WITHIN GROUP (ORDER BY oi.item_id),
                    ARRAY_CONSTRUCT())
      INTO :items_arr
    FROM TIDE.RETAIL.ORDER_ITEMS oi WHERE oi.order_id = :v_order_id;

    -- No per-item selection is captured yet, so every item is affected.
    -- DETAILS.md section 9 names this as the documented fallback, not a guess.
    SELECT COALESCE(ARRAY_AGG(OBJECT_CONSTRUCT_KEEP_NULL(
                        'item_id',    oi.item_id,
                        'qty',        oi.quantity,
                        'unit_price', oi.unit_price))
                      WITHIN GROUP (ORDER BY oi.item_id),
                    ARRAY_CONSTRUCT())
      INTO :affected_arr
    FROM TIDE.RETAIL.ORDER_ITEMS oi WHERE oi.order_id = :v_order_id;

    -- CHECK_INVENTORY reports availability; the ordered quantity is joined back
    -- on here, because the tool has no order context.
    SELECT COALESCE(ARRAY_AGG(OBJECT_CONSTRUCT_KEEP_NULL(
                        'sku',                inv.value['sku']::VARCHAR,
                        'quantity_available', inv.value['quantity_available']::NUMBER,
                        'quantity_ordered',   oq.qty)),
                    ARRAY_CONSTRUCT())
      INTO :inventory_arr
    FROM TABLE(FLATTEN(INPUT => :stock_res['inventory'])) inv
    LEFT JOIN (
        SELECT oi.sku AS sku, SUM(oi.quantity) AS qty
        FROM TIDE.RETAIL.ORDER_ITEMS oi
        WHERE oi.order_id = :v_order_id
        GROUP BY oi.sku
    ) oq ON oq.sku = inv.value['sku']::VARCHAR;

    -- Bracket notation throughout, not colon-path notation. A VARIANT path
    -- whose key is a common English word produces a colon-wrapped token that
    -- the Snowflake CLI renders as an emoji, which then fails to encode to
    -- cp1252 and kills the whole deploy run.
    SELECT OBJECT_CONSTRUCT_KEEP_NULL(
               'present',         COUNT(*) > 0,
               'analysis_status', CASE
                                      WHEN COUNT(*) = 0 THEN NULL
                                      WHEN COUNT_IF(pf.analysis_status = 'failed') > 0 THEN 'failed'
                                      WHEN COUNT_IF(pf.analysis_status = 'completed') = COUNT(*) THEN 'completed'
                                      ELSE 'pending'
                                  END,
               'signals',         COALESCE(MAX(pf.analysis['signals']), OBJECT_CONSTRUCT()),
               'notes',           MAX(pf.analysis['notes']::VARCHAR))
      INTO :proof_obj
    FROM TIDE.INVESTIGATION.PROOF_FILES pf WHERE pf.case_id = :CASE_ID;

    bundle := OBJECT_CONSTRUCT_KEEP_NULL(
        'as_of',                 TIDE.INVESTIGATION.ISO_UTC(CURRENT_TIMESTAMP()),
        'case_id',               :CASE_ID,
        'dispute_subtype',       :v_subtype,
        'resolution_preference', :v_preference,
        'order',                 :order_obj,
        'items',                 :items_arr,
        'affected_items',        :affected_arr,
        'payment',               :payment_res['payment'],
        'payments',              :payment_res['payments'],
        'refund_history',        :refund_res['refund_history'],
        'shipment',              :shipment_res['shipment'],
        'tracking_events',       :shipment_res['tracking_events'],
        'inventory',             :inventory_arr,
        'proof',                 :proof_obj,
        'assembly', OBJECT_CONSTRUCT(
            'status', 'complete',
            'sources', ARRAY_CONSTRUCT(
                'orders', 'order_items', 'payments', 'refunds', 'shipments',
                'tracking_events', 'stock', 'proof_files'),
            'assembler', 'deterministic',
            'failures', ARRAY_CONSTRUCT()));

    bundle_id := UUID_STRING();

    INSERT INTO TIDE.INVESTIGATION.EVIDENCE_BUNDLES
        (bundle_id, case_id, assembly_status, bundle, sources_queried)
    SELECT :bundle_id, :CASE_ID, 'complete', :bundle, :bundle:assembly:sources;

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'evidence_assembled', 'system', CURRENT_USER(),
           OBJECT_CONSTRUCT('bundle_id', :bundle_id, 'assembler', 'deterministic');

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'ASSEMBLE_EVIDENCE', 'completed',
           OBJECT_CONSTRUCT('bundle_id', :bundle_id, 'order_id', :v_order_id);

    RETURN :bundle;
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.INVESTIGATION.EVIDENCE_BUNDLES
            (case_id, assembly_status, bundle)
        SELECT :CASE_ID, 'failed', OBJECT_CONSTRUCT('error', :err);
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'ASSEMBLE_EVIDENCE', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- Grants
-- Both procedures run inside the pipeline under owner's rights. No persona role
-- calls them directly.
-- ---------------------------------------------------------------------------
GRANT USAGE ON PROCEDURE TIDE.INVESTIGATION.ASSEMBLE_EVIDENCE(VARCHAR) TO ROLE TIDE_ADMIN;
