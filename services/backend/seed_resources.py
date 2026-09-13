import os
import django
import urllib.request
from django.core.files.base import ContentFile

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from Apps.resources.models import Resource

def download_file(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        return response.read()

def seed():
    print("Clearing existing resources...")
    Resource.objects.all().delete()

    # Public domain / free sample files for testing
    audio_url = "https://www.learningcontainer.com/wp-content/uploads/2020/02/Kalimba.mp3"
    video_url = "https://www.learningcontainer.com/wp-content/uploads/2020/05/sample-mp4-file.mp4"

    try:
        print("Downloading sample audio...")
        audio_content = download_file(audio_url)
    except Exception:
        # Fallback empty bytes if URL fails
        print("Failed to download audio, using dummy data")
        audio_content = b"dummy audio content"

    try:
        print("Downloading sample video...")
        video_content = download_file(video_url)
    except Exception:
        print("Failed to download video, using dummy data")
        video_content = b"dummy video content"

    resources_data = [
        {
            "title": "Morning Calm",
            "subtitle": "Body Scan",
            "category": Resource.ResourceCategory.MEDITATION,
            "type": Resource.ResourceType.AUDIO,
            "duration_minutes": 12,
            "difficulty_level": Resource.DifficultyLevel.BEGINNER,
            "is_featured": True,
            "file_name": "morning_calm.mp3",
            "file_content": audio_content,
        },
        {
            "title": "Morning Body Scan",
            "subtitle": "Guided Meditation",
            "category": Resource.ResourceCategory.MEDITATION,
            "type": Resource.ResourceType.AUDIO,
            "duration_minutes": 10,
            "difficulty_level": Resource.DifficultyLevel.BEGINNER,
            "is_featured": False,
            "file_name": "morning_body_scan.mp3",
            "file_content": audio_content,
        },
        {
            "title": "Stress Release Flow",
            "subtitle": "Guided Meditation",
            "category": Resource.ResourceCategory.MEDITATION,
            "type": Resource.ResourceType.AUDIO,
            "duration_minutes": 15,
            "difficulty_level": Resource.DifficultyLevel.INTERMEDIATE,
            "is_featured": False,
            "file_name": "stress_release.mp3",
            "file_content": audio_content,
        },
        {
            "title": "Yoga for Emotional Release",
            "subtitle": "Video Guide",
            "category": Resource.ResourceCategory.YOGA,
            "type": Resource.ResourceType.VIDEO,
            "duration_minutes": 25,
            "difficulty_level": Resource.DifficultyLevel.BEGINNER,
            "is_featured": False,
            "file_name": "yoga_emotional.mp4",
            "file_content": video_content,
        },
        {
            "title": "Breathwork & Pranayama",
            "subtitle": "Guided Session",
            "category": Resource.ResourceCategory.YOGA,
            "type": Resource.ResourceType.AUDIO,
            "duration_minutes": 15,
            "difficulty_level": Resource.DifficultyLevel.BEGINNER,
            "is_featured": False,
            "file_name": "breathwork.mp3",
            "file_content": audio_content,
        },
        {
            "title": "Yoga for Stress Recovery",
            "subtitle": "Video Guide",
            "category": Resource.ResourceCategory.YOGA,
            "type": Resource.ResourceType.VIDEO,
            "duration_minutes": 30,
            "difficulty_level": Resource.DifficultyLevel.INTERMEDIATE,
            "is_featured": False,
            "file_name": "yoga_stress.mp4",
            "file_content": video_content,
        },
    ]

    for data in resources_data:
        print(f"Creating {data['title']}...")
        r = Resource.objects.create(
            title=data["title"],
            subtitle=data.get("subtitle", ""),
            category=data["category"],
            type=data["type"],
            duration_minutes=data["duration_minutes"],
            difficulty_level=data.get("difficulty_level"),
            is_featured=data["is_featured"],
        )
        r.file.save(data["file_name"], ContentFile(data["file_content"]))
    
    print("Database seeding completed.")

if __name__ == "__main__":
    seed()
