import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edutrack_project.settings')
django.setup()

from main.models import ScheduleTemplate, Subject, User, StudyGroup, Classroom
from django.db import IntegrityError

def reproduce():
    print("Testing ScheduleTemplate creation without teacher...")
    group = StudyGroup.objects.first()
    subject = Subject.objects.first()
    
    if not group or not subject:
        print("Need at least one group and one subject to test.")
        return

    try:
        ScheduleTemplate.objects.create(
            group=group,
            subject=subject,
            teacher=None, # This should fail if not nullable
            day_of_week=1,
            lesson_number=1,
            start_time="08:30"
        )
        print("SUCCESS: Created ScheduleTemplate without teacher. Wait, then it's NOT the issue?")
    except IntegrityError as e:
        print(f"EXPECTED FAILURE: {e}")
    except Exception as e:
        print(f"OTHER FAILURE: {type(e).__name__}: {e}")

if __name__ == "__main__":
    reproduce()
