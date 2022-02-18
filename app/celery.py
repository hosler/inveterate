import os
from celery import Celery
from celery.signals import worker_ready
from celery_singleton import clear_locks
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

app = Celery('app')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@worker_ready.connect
def unlock_all(**kwargs):
    clear_locks(app)

def detect_tasks(project_root):
    tasks = []
    file_path = project_root
    for root, dirs, files in os.walk(file_path):
        for filename in files:
            if os.path.basename(root) == 'tasks':
                if filename != '__init__.py' and filename.endswith('.py'):
                    task = os.path.join(root, filename)\
                        .replace(os.path.dirname(project_root) + '/', '')\
                        .replace('/', '.')\
                        .replace('.py', '')
                    tasks.append(task)
    return tuple(tasks)
