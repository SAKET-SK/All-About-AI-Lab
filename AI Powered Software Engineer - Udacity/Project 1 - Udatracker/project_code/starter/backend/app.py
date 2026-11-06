from flask import Flask, request, jsonify, send_from_directory
from backend.order_tracker import OrderTracker, DuplicateOrderError, OrderNotFoundError
from backend.in_memory_storage import InMemoryStorage

app = Flask(__name__, static_folder='../frontend')
in_memory_storage = InMemoryStorage()
order_tracker = OrderTracker(in_memory_storage)

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

# --- Centralized error handling -------------------------------------------
# Every error is returned as {"error": "message"}, which is the shape the
# frontend expects. Order of specificity does not matter: Flask picks the
# most specific registered handler for the raised exception.

@app.errorhandler(DuplicateOrderError)
def handle_duplicate_order(error):
    return jsonify({"error": str(error)}), 409

@app.errorhandler(OrderNotFoundError)
def handle_order_not_found(error):
    return jsonify({"error": str(error)}), 404

@app.errorhandler(ValueError)
def handle_validation_error(error):
    return jsonify({"error": str(error)}), 400


# --- API routes ------------------------------------------------------------

@app.route('/api/orders', methods=['POST'])
def add_order_api():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

    required_fields = ("order_id", "item_name", "quantity", "customer_id")
    missing = [field for field in required_fields if field not in data]
    if missing:
        return jsonify({"error": f"Missing required field(s): {', '.join(missing)}."}), 400

    order = order_tracker.add_order(
        data["order_id"],
        data["item_name"],
        data["quantity"],
        data["customer_id"],
        data.get("status", "pending"),
    )
    return jsonify(order), 201

@app.route('/api/orders/<string:order_id>', methods=['GET'])
def get_order_api(order_id):
    order = order_tracker.get_order_by_id(order_id)
    if order is None:
        return jsonify({"error": f"Order with ID '{order_id}' not found."}), 404
    return jsonify(order), 200

@app.route('/api/orders/<string:order_id>/status', methods=['PUT'])
def update_order_status_api(order_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "new_status" not in data:
        return jsonify({"error": "Request body must include 'new_status'."}), 400

    updated_order = order_tracker.update_order_status(order_id, data["new_status"])
    return jsonify(updated_order), 200

@app.route('/api/orders', methods=['GET'])
def list_orders_api():
    # `status` present (even if empty) means the client wants a filtered list;
    # the tracker rejects empty/invalid values, which becomes a 400.
    if "status" in request.args:
        orders = order_tracker.list_orders_by_status(request.args["status"])
    else:
        orders = order_tracker.list_all_orders()
    return jsonify(orders), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)