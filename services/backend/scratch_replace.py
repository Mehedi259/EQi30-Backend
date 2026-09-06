import os

root_dir = "Apps/ai"
for subdir, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(subdir, file)
            with open(filepath, "r") as f:
                content = f.read()
            
            new_content = content.replace("from app.", "from Apps.ai.")
            new_content = new_content.replace("import app.", "import Apps.ai.")
            
            if new_content != content:
                with open(filepath, "w") as f:
                    f.write(new_content)
                print(f"Updated {filepath}")
