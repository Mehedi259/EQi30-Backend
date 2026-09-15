import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from Apps.learning.models import AbilityDayContent

def patch():
    options = [
        {"emoji": "😌", "label": "More calm"},
        {"emoji": "🧠", "label": "More clear"},
        {"emoji": "🎯", "label": "More focused"},
        {"emoji": "⏳", "label": "No change yet"}
    ]
    
    count = AbilityDayContent.objects.update(practice_options=options)
    print(f"Successfully patched {count} days with practice options!")

if __name__ == '__main__':
    patch()
