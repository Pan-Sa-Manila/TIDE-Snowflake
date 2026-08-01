-- ============================================================================
-- TIDE · 13_investigator_agent.sql
-- INVESTIGATION.INVESTIGATOR — the Cortex Agent object (TASKS.md C-1).
--
-- Source of truth for this spec is agents/investigator.yaml; this file is the
-- deployable form of it.
--
-- This is the one place in TIDE where tool *selection* is genuinely a model
-- decision: which sources to query depends on the dispute type, and a delivery
-- dispute needs a different set of facts from a duplicate charge. Everywhere
-- else the task is fixed, so it is an AI_COMPLETE call with a schema; and where
-- money is decided there is no model at all (ARCHITECTURE.md §6.3).
--
-- All six tools already exist:
--   Analyst      -> RETAIL.DISPUTES_SV        (07_semantic_view.sql)
--   PolicySearch -> DECISION.POLICY_SEARCH    (08_policy_search.sql)
--   4 procedures -> INVESTIGATION.*           (06_investigation_tools.sql)
--
-- The agent is an alternative assembler, not a replacement for
-- ASSEMBLE_EVIDENCE. That procedure stays the deterministic path and remains
-- the one the pipeline calls, so the demo does not depend on agent latency or
-- availability (docs/DECISIONS.md).
--
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA INVESTIGATION;

CREATE OR REPLACE AGENT INVESTIGATOR
WITH PROFILE = '{"display_name": "TIDE Investigator"}'
COMMENT = 'Tool-selecting evidence assembler for dispute resolution. Chooses which enterprise sources to query based on dispute type and reports facts without recommending an outcome.'
FROM SPECIFICATION $$
{
  "models": {
    "orchestration": "auto"
  },
  "orchestration": {
    "budget": {
      "seconds": 60,
      "tokens": 24000
    }
  },
  "instructions": {
    "orchestration": "You are investigating a customer dispute for TIDE. Assemble the facts; never recommend an outcome. Tool selection policy: always call GetPaymentStatus first, because an unconfirmed payment changes everything downstream. For delivery disputes (non_receipt, delayed, exception, lost) always call GetShipmentTimeline. Always call GetRefundHistory before any refund is under consideration, to surface duplicate-refund risk. Call CheckInventory only when a replacement is in play. Use Analyst for quantitative order facts such as amounts, dates and item details. Use PolicySearch only when you need to cite a specific policy. If a tool fails, note the failure and continue with the other sources rather than stopping.",
    "response": "Report only what the tools returned. State each fact with the source it came from. Do not classify, do not threshold, and do not suggest a resolution: adjudication is deterministic and happens after you. If evidence is missing or a tool failed, say so explicitly rather than inferring."
  },
  "tools": [
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "Analyst",
        "description": "Query order, payment, shipment, refund and inventory data using natural language. Use for order totals, item details, delivery dates, lateness and stock levels."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_search",
        "name": "PolicySearch",
        "description": "Search dispute resolution policies by topic. Use when you need to cite a specific policy for the decision rationale."
      }
    },
    {
      "tool_spec": {
        "type": "generic",
        "name": "GetShipmentTimeline",
        "description": "Returns the shipment and its full tracking event sequence for an order. Use for any delivery dispute, or when you need delivery dates or proof of delivery.",
        "input_schema": {
          "type": "object",
          "properties": {
            "order_id": {
              "type": "string",
              "description": "The order ID to look up shipment tracking for"
            }
          },
          "required": ["order_id"]
        }
      }
    },
    {
      "tool_spec": {
        "type": "generic",
        "name": "GetPaymentStatus",
        "description": "Returns every payment record for an order. Call for all dispute types before anything else. More than one confirmed record is the duplicate-charge evidence.",
        "input_schema": {
          "type": "object",
          "properties": {
            "order_id": {
              "type": "string",
              "description": "The order ID to check payment status for"
            }
          },
          "required": ["order_id"]
        }
      }
    },
    {
      "tool_spec": {
        "type": "generic",
        "name": "GetRefundHistory",
        "description": "Returns prior refunds already issued against an order. Use to detect duplicate-refund risk before any refund is recommended.",
        "input_schema": {
          "type": "object",
          "properties": {
            "order_id": {
              "type": "string",
              "description": "The order ID to check refund history for"
            }
          },
          "required": ["order_id"]
        }
      }
    },
    {
      "tool_spec": {
        "type": "generic",
        "name": "CheckInventory",
        "description": "Checks current stock availability for specific SKUs. Use when a replacement is under consideration, to verify it can actually be fulfilled.",
        "input_schema": {
          "type": "object",
          "properties": {
            "sku_list": {
              "type": "array",
              "description": "Array of SKU strings to check availability for",
              "items": {"type": "string"}
            }
          },
          "required": ["sku_list"]
        }
      }
    }
  ],
  "tool_resources": {
    "Analyst": {
      "semantic_view": "TIDE.RETAIL.DISPUTES_SV",
      "execution_environment": {"type": "warehouse", "warehouse": "TIDE_WH_APP"}
    },
    "PolicySearch": {
      "name": "TIDE.DECISION.POLICY_SEARCH",
      "max_results": 5
    },
    "GetShipmentTimeline": {
      "type": "procedure",
      "identifier": "TIDE.INVESTIGATION.GET_SHIPMENT_TIMELINE",
      "execution_environment": {"type": "warehouse", "warehouse": "TIDE_WH_APP"}
    },
    "GetPaymentStatus": {
      "type": "procedure",
      "identifier": "TIDE.INVESTIGATION.GET_PAYMENT_STATUS",
      "execution_environment": {"type": "warehouse", "warehouse": "TIDE_WH_APP"}
    },
    "GetRefundHistory": {
      "type": "procedure",
      "identifier": "TIDE.INVESTIGATION.GET_REFUND_HISTORY",
      "execution_environment": {"type": "warehouse", "warehouse": "TIDE_WH_APP"}
    },
    "CheckInventory": {
      "type": "procedure",
      "identifier": "TIDE.INVESTIGATION.CHECK_INVENTORY",
      "execution_environment": {"type": "warehouse", "warehouse": "TIDE_WH_APP"}
    }
  }
}
$$;

GRANT USAGE ON AGENT TIDE.INVESTIGATION.INVESTIGATOR TO ROLE TIDE_ADMIN;
