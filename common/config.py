from enum import Enum

ROBOT_MAX_MEDICATION = {"Type1": 20, "Type2": 20, "Type3": 20, "Type4": 20}
APP_API_URL = "http://localhost:5001"

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class RobotStatus(Enum):
    AVAILABLE = "available"
    DELIVERING = "delivering"
    CHARGING = "charging"