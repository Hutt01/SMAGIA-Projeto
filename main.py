from flask import Flask, request

app = Flask(__name__)

pending_tasks = [
    {"medications": {"Type1": 1, "Type2": 1, "Type3": 1, "Type4": 1}, "room": "Room A-101", "ID": "task_001"},
    {"medications": {"Type1": 5, "Type2": 3}, "room": "Room B-202", "ID": "task_002"},
    {"medications": {"Type3": 1, "Type4": 1}, "room": "Room C-303", "ID": "task_003"},
]

# pending_tasks = [
#     {
#         "medications": {"Type1": 1, "Type2": 1, "Type3": 1, "Type4": 1},
#         "location": {
#             "Robot1": {"x": -9.0, "y": 0.5},
#             "Robot2": {"x": -9.0, "y": -2.0},
#             "Robot3": {"x": -9.0, "y": -4.0}
#         },
#         "ID": "task_001"
#     },
#     {
#         "medications": {"Type1": 5, "Type2": 3},
#         "location": {
#             "Robot1": {"x": 9.0, "y": -5.0},
#             "Robot2": {"x": 9.0, "y": -3.0},
#             "Robot3": {"x": 9.0, "y": -8.0}
#         },
#         "ID": "task_002"
#     },
#     {
#         "medications": {"Type3": 1, "Type4": 1},
#         "location": {
#             "Robot1": {"x": -9.0, "y": -16.0},
#             "Robot2": {"x": -9.0, "y": -18.0},
#             "Robot3": {"x": -9.0, "y": -20.0}
#         },
#         "ID": "task_003"
#     }
# ]


@app.route('/pending_tasks', methods=['GET'])
def get_pending_tasks():
    return {'pending_tasks': pending_tasks}, 200

@app.route('/pending_tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    global pending_tasks
    original_length = len(pending_tasks)
    pending_tasks = [task for task in pending_tasks if task['ID'] != task_id]
    if len(pending_tasks) < original_length:
        return {"message": f"Task '{task_id}' deleted successfully."}, 200
    else:
        return {"error": f"Task '{task_id}' not found."}, 404
    
@app.route('/pending_tasks/', methods=['DELETE'])
def delete_all_tasks():
    global pending_tasks
    pending_tasks.clear()  # Empties the list in-place
    return {"message": "All pending tasks deleted successfully."}, 200


@app.route('/pending_tasks', methods=['POST'])
def add_task():
    new_task = request.get_json()
    if not new_task or 'ID' not in new_task or 'medications' not in new_task or 'location' not in new_task:
        return {"error": "Invalid task format. Required: ID, medications, location."}, 400
    if any(task['ID'] == new_task['ID'] for task in pending_tasks):
        return {"error": f"Task with ID '{new_task['ID']}' already exists."}, 400
    pending_tasks.append(new_task)
    return {"message": f"Task '{new_task['ID']}' added successfully."}, 201

if __name__ == '__main__':
    app.run(port=5001)