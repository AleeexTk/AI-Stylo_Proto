import sys
import subprocess
from pathlib import Path

def main():
    """Point of entry for AI-Stylo. Resolves path and launches streamlit app."""
    project_root = Path(__file__).parent.resolve()
    app_path = project_root / "apps" / "web" / "streamlit_rpg" / "app.py"
    
    if not app_path.exists():
        print(f"Error: Could not find main application at {app_path}")
        sys.exit(1)
        
    print(f"Starting Personal Fashion OS from: {app_path}")
    
    # Run streamlit
    try:
        subprocess.run(["streamlit", "run", str(app_path)], check=True)
    except KeyboardInterrupt:
        print("\nShutting down AI-Stylo.")
    except Exception as e:
        print(f"Error while running the app: {e}")

if __name__ == "__main__":
    main()
