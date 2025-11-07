import json
import os
import sys
from decimal import Decimal

import boto3
import pytest
from moto import mock_dynamodb

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda'))

from common.jwt_utils import generate_jwt
from reps_query import handler


def _build_event(
    method: str = "GET",
    *,
    token: str | None = None,
    query: dict | None = None,
) -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return {
        "httpMethod": method,
        "headers": headers,
        "queryStringParameters": query,
    }


def test_options_returns_200():
    event = _build_event("OPTIONS")
    response = handler.lambda_handler(event, None)
    assert response["statusCode"] == 200


def test_missing_authorization_header_returns_401():
    event = _build_event(query={"player_id": "plr_sakae_19", "test_type": "single_leg_squat"})
    response = handler.lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 401
    assert body["success"] is False
    assert body["errorCode"] == "AUTH_REQUIRED"


@mock_dynamodb
def test_player_mismatch_returns_403():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName="test-reps-table",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    token = generate_jwt("plr_sakae_19", "tm_sakae", expiration_minutes=60)
    event = _build_event(
        token=token,
        query={"player_id": "plr_other_10", "test_type": "single_leg_squat"},
    )
    response = handler.lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 403
    assert body["errorCode"] == "FORBIDDEN"


@mock_dynamodb
def test_query_reps_success():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="test-reps-table",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    table.put_item(
        Item={
            "PK": "PLAYER#plr_sakae_19",
            "SK": "session123#single_leg_squat#session123-000",
            "rep_id": "session123-000",
            "rep_index": 0,
            "player_id": "plr_sakae_19",
            "team_id": "tm_sakae",
            "session_id": "session123",
            "test_type": "single_leg_squat",
            "score_primary": Decimal("82.5"),
            "start_frame": 120,
            "end_frame": 180,
            "overlay_key": "tm_sakae/plr_sakae_19/single_leg_squat/session123/reps/session123-000/overlay.png",
        }
    )

    token = generate_jwt("plr_sakae_19", "tm_sakae", expiration_minutes=60)
    event = _build_event(
        token=token,
        query={"test_type": "single_leg_squat"},
    )

    response = handler.lambda_handler(event, None)
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["success"] is True
    data = body["data"]
    assert data["nextCursor"] is None
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["rep_id"] == "session123-000"
    assert item["score_primary"] == pytest.approx(82.5)
    assert item["start_frame"] == 120
    assert item["overlay_key"].endswith("overlay.png")
