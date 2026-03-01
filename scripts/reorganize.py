import os, subprocess, shutil

root = r"c:\Users\Alex Bear\Desktop\AI-Stylo_Proto_clean"
src = os.path.join(root, "AI-Stylo-main")

res = subprocess.run(["git", "ls-files", "-z", "AI-Stylo-main"], cwd=root, capture_output=True)
files = res.stdout.split(b'\0')

for f_bytes in files:
    if not f_bytes: continue
        
    f = f_bytes.decode('utf-8')
    rel_path = f.replace("AI-Stylo-main/", "", 1)
    dest = os.path.join(root, rel_path)
    
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    
    if os.path.exists(dest):
        print(f"Conflict: {dest} already exists! Replacing it.")
        os.remove(dest)
        
    p = subprocess.run(["git", "mv", f, rel_path], cwd=root, capture_output=True, text=True)
    if p.returncode != 0:
        print(f"Error moving {f}: {p.stderr}")
    else:
        print(f"Moved {f} to {rel_path}")

for root_dir, dirs, file_names in os.walk(src):
    for filename in file_names:
        full_path = os.path.join(root_dir, filename)
        rel_path = os.path.relpath(full_path, src)
        dest = os.path.join(root, rel_path)
        if not os.path.exists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(full_path, dest)
            print(f"Moved untracked: {rel_path}")

print("Done.")
