
tasks = []

def create_task(task_description):
    tasks.append({
        "task_description": task_description,
        "status": "New"
    })


def completed_task(task_description):
    global tasks
    task = list(filter(lambda  x: x.task_description == task_description, tasks))
    task["status"] = "Completed"

def list_tasks():
    for task in tasks:
        print(task["task_description"] + task["status"])
