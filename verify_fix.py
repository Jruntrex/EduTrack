import os
import django
from datetime import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edutrack_project.settings')
django.setup()

from main.models import Lesson
from main.constants import DEFAULT_TIME_SLOTS

print("Verifying lesson_number property...")

# Test Case 1: Matching time
slot_1_start = DEFAULT_TIME_SLOTS[1][0] # 8:30
l1 = Lesson(start_time=slot_1_start)
print(f"Time: {l1.start_time}, Expected: 1, Actual: {l1.lesson_number}")
assert l1.lesson_number == 1

# Test Case 2: Matching time (Slot 2)
slot_2_start = DEFAULT_TIME_SLOTS[2][0] 
l2 = Lesson(start_time=slot_2_start)
print(f"Time: {l2.start_time}, Expected: 2, Actual: {l2.lesson_number}")
assert l2.lesson_number == 2

# Test Case 3: Non-matching time
l3 = Lesson(start_time=time(12, 0)) # Random time
print(f"Time: {l3.start_time}, Expected: 0, Actual: {l3.lesson_number}")
assert l3.lesson_number == 0

print("SUCCESS: Lesson.lesson_number property works as expected.")
