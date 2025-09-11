cat > app.py <<'PY'
import json, os, uuid
import boto3
from urllib.parse import unquote

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

def _resp(status, body=None):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": "" if body is None else json.dumps(body),
    }

def handler(event, context):
    http = (event.get("requestContext") or {}).get("http") or {}
    method = http.get("method")
    path = event.get("rawPath", "")
    path_params = event.get("pathParameters") or {}

    # Health check
    if method == "GET" and path == "/health":
        try:
            TABLE.scan(Select="COUNT", Limit=1)
            return _resp(200, {"status": "ok"})
        except Exception as e:
            return _resp(500, {"status": "error", "message": str(e)})

    # GET /items
    if method == "GET" and path == "/items":
        items = TABLE.scan().get("Items", [])
        return _resp(200, items)

    # POST /items
    if method == "POST" and path == "/items":
        body = json.loads(event.get("body") or "{}")
        title = (body.get("title") or "").strip()
        if not title:
            return _resp(400, {"error": "title is required"})
        item = {"id": str(uuid.uuid4()), "title": title, "done": False}
        TABLE.put_item(Item=item)
        return _resp(201, item)

    # PUT /items/{id}
    if method == "PUT" and "id" in path_params:
        item_id = unquote(path_params["id"])
        body = json.loads(event.get("body") or "{}")
        allowed = {k: v for k, v in body.items() if k in {"title", "done"}}
        if not allowed:
            return _resp(400, {"error": "provide 'title' and/or 'done'"})

        expr_names = {f"#k{i}": k for i, k in enumerate(allowed.keys())}
        expr_values = {f":v{i}": v for i, v in enumerate(allowed.values())}
        set_clause = ", ".join([f"{nk} = {vk}" for (nk, vk) in zip(expr_names.keys(), expr_values.keys())])

        TABLE.update_item(
            Key={"id": item_id},
            UpdateExpression=f"SET {set_clause}",
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        item = TABLE.get_item(Key={"id": item_id}).get("Item")
        return _resp(200, item or {"id": item_id})

    # DELETE /items/{id}
    if method == "DELETE" and "id" in path_params:
        item_id = unquote(path_params["id"])
        TABLE.delete_item(Key={"id": item_id})
        return _resp(204)

    return _resp(404, {"error": f"Route not found: {method} {path}"})
PY

