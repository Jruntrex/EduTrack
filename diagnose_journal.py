import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edutrack_project.settings')
django.setup()

from main.models import Lesson, TimeSlot, StudyGroup

def diagnose():
    print("--- TimeSlots ---")
    for ts in TimeSlot.objects.all().order_by('lesson_number'):
        print(f"Num: {ts.lesson_number}, Start: {ts.start_time}")

    print("\n--- Recent Lessons for a sample group ---")
    lesson = Lesson.objects.all().order_by('-id').first()
    if lesson:
        print(f"Sample Group: {lesson.group.name}")
        for l in Lesson.objects.filter(group=lesson.group, date=lesson.date).order_by('start_time'):
            print(f"Date: {l.date}, Time: {l.start_time}, Subject ID: {l.subject_id}, ID: {l.id}")

    print("\n--- Searching for [[ in all models ---")
    from django.apps import apps
    for model in apps.get_models():
        try:
            for obj in model.objects.all()[:100]:
                s = str(obj)
                if "[[" in s:
                    print(f"Found [[ in model {model.__name__} (ID: {obj.pk}): {s}")
        except:
            continue

if __name__ == "__main__":
    diagnose()
