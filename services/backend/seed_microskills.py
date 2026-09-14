import os
import re
import subprocess
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from Apps.abilities.models import Ability
from Apps.learning.models import AbilityDayContent

# Folder paths
FOLDERS = [
    "Microskills 1-20 ",
    "MicroSkills 21-30 Executive functioning and Decision making "
]

def extract_text_from_docx(filepath):
    try:
        result = subprocess.run(
            ['textutil', '-convert', 'txt', '-stdout', filepath],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error extracting {filepath}: {e}")
        return ""

def parse_days(text):
    # Regex to find each day block.
    # It looks for "Day X" and captures until the next "Day X" or end of string.
    pattern = r"(?i)Day\s+(\d+)[\s\-\–]+(.*?)(?=\nDay\s+\d+|$)"
    blocks = re.findall(pattern, text, re.DOTALL)
    
    parsed_days = []
    
    for day_num_str, content_block in blocks:
        day_num = int(day_num_str)
        
        # Sub-patterns for sections
        title_match = re.search(r"Title\s*(.*?)(?=Teaching|Prompt\s*/\s*Practice|If-Then|$)", content_block, re.DOTALL | re.IGNORECASE)
        teaching_match = re.search(r"Teaching\s*(.*?)(?=Prompt\s*/\s*Practice|If-Then|$)", content_block, re.DOTALL | re.IGNORECASE)
        practice_match = re.search(r"Prompt\s*/\s*Practice\s*(.*?)(?=If-Then|$)", content_block, re.DOTALL | re.IGNORECASE)
        ifthen_match = re.search(r"If-Then\s*(.*?)$", content_block, re.DOTALL | re.IGNORECASE)
        
        title = title_match.group(1).strip() if title_match else f"Day {day_num}"
        teaching = teaching_match.group(1).strip() if teaching_match else ""
        practice = practice_match.group(1).strip() if practice_match else ""
        ifthen = ifthen_match.group(1).strip() if ifthen_match else ""
        
        parsed_days.append({
            "day_number": day_num,
            "title": title,
            "teaching_content": teaching,
            "practice_content": practice,
            "real_life_plan": ifthen,
            "reflection_question": "How did today's practice make you feel?", # Default reflection
        })
        
    return parsed_days

def find_ability(filename):
    # Try to match the filename with Ability names
    # E.g. "1 Emotional Awareness Microskills_.docx" -> "Emotional Awareness"
    
    # Strip numbers and common words
    clean_name = re.sub(r'^\d+\s*|Microskill[s]?|Micro-Skill|\.docx|_|70-Day|70Day|Program|Journey|2 types|Extra', '', filename, flags=re.IGNORECASE).strip()
    
    abilities = Ability.objects.all()
    
    for ability in abilities:
        if ability.name.lower() in clean_name.lower() or clean_name.lower() in ability.name.lower():
            return ability
            
    # Fallback to loose matching
    for ability in abilities:
        words = clean_name.lower().split()
        if len(words) > 0 and words[0] in ability.name.lower():
            return ability
            
    return None

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    total_days_seeded = 0
    
    for folder in FOLDERS:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            print(f"Folder not found: {folder_path}")
            continue
            
        for filename in os.listdir(folder_path):
            if not filename.endswith('.docx') or filename.startswith('~'):
                continue
                
            filepath = os.path.join(folder_path, filename)
            ability = find_ability(filename)
            
            if not ability:
                print(f"[!] Could not match file to an Ability: {filename}")
                continue
                
            print(f"Processing: {filename} -> {ability.name}")
            
            text = extract_text_from_docx(filepath)
            days = parse_days(text)
            
            if not days:
                print(f"  -> No days found in {filename}")
                continue
                
            # Clear existing content for this ability to prevent duplicates during re-runs
            AbilityDayContent.objects.filter(ability=ability).delete()
            
            # Bulk create
            objects_to_create = []
            seen_days = set()
            for day in days:
                if day['day_number'] in seen_days:
                    print(f"    Skipping duplicate Day {day['day_number']}")
                    continue
                seen_days.add(day['day_number'])
                
                objects_to_create.append(
                    AbilityDayContent(
                        ability=ability,
                        day_number=day['day_number'],
                        title=day['title'][:200],
                        teaching_content=day['teaching_content'],
                        practice_content=day['practice_content'],
                        real_life_plan=day['real_life_plan'],
                        reflection_question=day['reflection_question'],
                        estimated_minutes=5
                    )
                )
            
            AbilityDayContent.objects.bulk_create(objects_to_create)
            print(f"  -> Successfully seeded {len(objects_to_create)} days.")
            total_days_seeded += len(objects_to_create)

    print(f"\nDone! Seeded a total of {total_days_seeded} days across all abilities.")

if __name__ == '__main__':
    main()
