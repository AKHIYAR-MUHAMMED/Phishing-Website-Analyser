import random
import subprocess
import datetime
import sys

def main():
    # Options specified by user: 4, 5, 8, or 10 commits daily
    options = [4, 5, 8, 10]
    num_commits = random.choice(options)
    today_str = datetime.date.today().isoformat()
    
    print(f"[{today_str}] Starting daily commit bot: making {num_commits} commits...")

    for i in range(1, num_commits + 1):
        msg = f"chore: daily activity commit {i}/{num_commits} [{today_str}] [skip ci]"
        res = subprocess.run(["git", "commit", "--allow-empty", "-m", msg], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Error making commit {i}: {res.stderr}")
            sys.exit(res.returncode)
        print(f"  + Commit {i}/{num_commits} created: '{msg}'")

    print("Pushing commits to remote repository...")
    push_res = subprocess.run(["git", "push"], capture_output=True, text=True)
    if push_res.returncode != 0:
        print(f"Error pushing to remote: {push_res.stderr}")
        sys.exit(push_res.returncode)
    
    print(f"Successfully committed and pushed {num_commits} commits for {today_str}.")

if __name__ == "__main__":
    main()
