import json
import os
import time

import boto3

dynamodb = boto3.resource("dynamodb")
TABLE = dynamodb.Table(os.environ["TABLE_NAME"])


def _ttl(days=30):
    return int(time.time()) + days * 24 * 3600


def _api_client(event):
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]
    return boto3.client("apigatewaymanagementapi", endpoint_url=f"https://{domain}/{stage}")


def _post(conn_id, data, client):
    client.post_to_connection(ConnectionId=conn_id, Data=json.dumps(data).encode("utf-8"))


def handler(event, context):
    rc = event.get("requestContext", {})
    route = rc.get("routeKey")
    conn_id = rc.get("connectionId")
    api = _api_client(event)

    if route == "$connect":
        _post(conn_id, {"ok": True, "msg": "Connected to Odyssey WS"}, api)
        return {"statusCode": 200}
    if route == "$disconnect":
        return {"statusCode": 200}

    # $default or custom (e.g. sendMessage)
    try:
        body = json.loads(event.get("body") or "{}")
    except Exception:
        body = {}

    msg = (body.get("text") or body.get("message") or "").strip()
    reply = f"Odyssey here. Got your message -> '{msg}'"
    now_ms = int(time.time() * 1000)

    TABLE.put_item(
        Item={"pk": f"CONN#{conn_id}", "sk": now_ms, "input": msg, "output": reply, "ttl": _ttl()}
    )

    _post(conn_id, {"reply": reply, "ts": now_ms}, api)
    return {"statusCode": 200}
