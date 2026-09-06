import os

root_dir = "Apps/ai"
for subdir, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(subdir, file)
            with open(filepath, "r") as f:
                content = f.read()
            
            new_content = content.replace("from fastapi import status", "from rest_framework import status")
            # We don't need rate limit since Django handles it
            
            if new_content != content:
                with open(filepath, "w") as f:
                    f.write(new_content)
                print(f"Updated {filepath}")
