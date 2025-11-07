"""
Purpose: GET /reps Lambda handler for fetching repetition summaries.
Responsibility: Authenticate player, query DynamoDB rep table, paginate results.
Dependencies: boto3, common.jwt_utils, common.response_utils
Created: 2024-03-08 by Codex
"""
from __future__ import annotations

import base64
import json
import os
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Attr, Key

from common.jwt_utils import extract_bearer_token, verify_jwt
from common.response_utils import error_response, success_response
from common.structured_logging import get_logger


logger = get_logger()
dynamodb = boto3.resource("dynamodb")
REPS_TABLE_NAME = os.environ.get("REPS_TABLE_NAME")
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


def _decode_cursor(cursor: Optional[str]) -> Optional[Dict[str, Any]]:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        return json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return None


def _encode_cursor(last_evaluated_key: Optional[Dict[str, Any]]) -> Optional[str]:
    if not last_evaluated_key:
        return None
    payload = json.dumps(last_evaluated_key, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def _normalise_score(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalise_int(value: Any) -> int:
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _build_query_parameters(
    query: Dict[str, Any], payload: Dict[str, Any]
) -> Tuple[str, str, int, Optional[str]]:
    player_id = query.get("player_id") or payload.get("playerId")
    if not player_id:
        raise ValueError("player_id is required")

    requested_player = query.get("player_id")
    if requested_player and requested_player != payload.get("playerId"):
        raise PermissionError("Requested player does not match authenticated identity.")

    test_type = query.get("test_type")
    if not test_type:
        raise ValueError("test_type query parameter is required")

    limit_raw = query.get("limit")
    if limit_raw is None:
        limit = DEFAULT_PAGE_SIZE
    else:
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit must be an integer") from exc

    if limit < 1:
        limit = 1
    if limit > MAX_PAGE_SIZE:
        limit = MAX_PAGE_SIZE

    cursor = query.get("cursor")
    return player_id, test_type, limit, cursor


def handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    headers = event.get("headers") or {}
    request_origin = headers.get("Origin") or headers.get("origin")
    logger.set_context(function_name="RepsQuery", environment=os.environ.get("ENVIRONMENT"))

    try:
        http_method = event.get("httpMethod", "GET")
        if http_method == "OPTIONS":
            return success_response(None, request_origin=request_origin)
        if http_method != "GET":
            return error_response(
                "Method not allowed", 405, "METHOD_NOT_ALLOWED", request_origin=request_origin
            )

        if not REPS_TABLE_NAME:
            return error_response(
                "Rep table not configured",
                500,
                "INTERNAL_ERROR",
                request_origin=request_origin,
            )

        auth_header = headers.get("Authorization") or headers.get("authorization")
        is_valid, token, error_msg = extract_bearer_token(auth_header)
        if not is_valid:
            return error_response(error_msg, 401, "AUTH_REQUIRED", request_origin=request_origin)

        is_valid, payload, error_msg = verify_jwt(token)
        if not is_valid:
            return error_response(error_msg, 401, "AUTH_FAILED", request_origin=request_origin)

        query = event.get("queryStringParameters") or {}

        try:
            player_id, test_type, limit, cursor = _build_query_parameters(query, payload)
        except PermissionError as exc:
            logger.warning("Player access denied", payload={"requestedPlayer": query.get("player_id")})
            return error_response(str(exc), 403, "FORBIDDEN", request_origin=request_origin)
        except ValueError as exc:
            logger.warning("Query validation failed", payload={"error": str(exc)})
            return error_response(str(exc), 400, "VALIDATION_ERROR", request_origin=request_origin)

        exclusive_start_key = _decode_cursor(cursor)
        if cursor and exclusive_start_key is None:
            logger.warning("Invalid cursor provided", payload={"cursor": cursor})
            return error_response(
                "Invalid pagination cursor",
                400,
                "VALIDATION_ERROR",
                request_origin=request_origin,
            )

        table = dynamodb.Table(REPS_TABLE_NAME)
        key_condition = Key("PK").eq(f"PLAYER#{player_id}")
        query_kwargs: Dict[str, Any] = {
            "KeyConditionExpression": key_condition,
            "FilterExpression": Attr("test_type").eq(test_type),
            "Limit": limit,
        }
        if exclusive_start_key:
            query_kwargs["ExclusiveStartKey"] = exclusive_start_key

        response = table.query(**query_kwargs)

        items = []
        for raw in response.get("Items", []):
            items.append(
                {
                    "rep_id": raw.get("rep_id"),
                    "rep_index": _normalise_int(raw.get("rep_index")),
                    "session_id": raw.get("session_id"),
                    "test_type": raw.get("test_type"),
                    "score_primary": _normalise_score(raw.get("score_primary")),
                    "start_frame": _normalise_int(raw.get("start_frame")),
                    "end_frame": _normalise_int(raw.get("end_frame")),
                    "apex_frame": _normalise_int(raw.get("apex_frame")),
                    "overlay_key": raw.get("overlay_key"),
                    "processed_at": raw.get("processed_at"),
                }
            )

        next_cursor = _encode_cursor(response.get("LastEvaluatedKey"))

        logger.info(
            "Reps query success",
            payload={
                "playerId": player_id,
                "testType": test_type,
                "count": len(items),
                "hasNext": next_cursor is not None,
            },
        )

        return success_response(
            {
                "items": items,
                "nextCursor": next_cursor,
            },
            request_origin=request_origin,
        )

    except Exception as exc:  # pragma: no cover - defensive catch
        logger.error("Unhandled error in reps query handler", exc_info=exc)
        return error_response(
            "Internal server error",
            500,
            "INTERNAL_ERROR",
            request_origin=request_origin,
        )
    finally:
        logger.clear_context()


lambda_handler = handler
