from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/api/tasks")
def get_tasks():
    return jsonify(["Task 1", "Task 2", "Task 3"])

if __name__ == "__main__":
    app.run(debug=True, port=5000)
