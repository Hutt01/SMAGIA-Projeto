from flask import Flask, request
from agents.robot3 import MedicationRobotAgent
from agents.TaskManagementAgent import TaskManagerAgent
from common.config import APP_API_URL, ROBOT_MAX_MEDICATION

app = Flask(__name__)

pending_tasks = [
    {"medications": {"Type1": 1, "Type2": 1, "Type3": 1, "Type4": 1}, "location": "Room A-101", "ID": "task_001"},
    {"medications": {"Type1": 5, "Type2": 3}, "location": "Room B-202", "ID": "task_002"},
    {"medications": {"Type3": 1, "Type4": 1}, "location": "Room C-303", "ID": "task_003"},
    {"medications": {"Type1": 1, "Type2": 1}, "location": "Room D-404", "ID": "task_004"}
]

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