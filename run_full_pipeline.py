import subprocess
import sys

def run_agent(script_name):
    print(f"\n[Pipeline] Running {script_name} ...")
    result = subprocess.run([sys.executable, script_name])
    if result.returncode != 0:
        print(f"[Pipeline] {script_name} failed with exit code {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    # Step 1: Ingest events from Instagram
    run_agent("ingest_agent.py")

    # Step 2: Dedupe events
    run_agent("dedupe_agent.py")

    # Step 3: Classify events (if you have classify_agent.py)
    run_agent("classify_agent.py")

    # Step 4: Notify users (if you have notify_agent.py)
    run_agent("notify_agent.py")

    print("\n[Pipeline] All steps completed!")