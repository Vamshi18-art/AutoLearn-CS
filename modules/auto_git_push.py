import os
import subprocess

def run_git(cmd, repo_dir):
    return subprocess.run(cmd, cwd=repo_dir, shell=True, capture_output=True, text=True)

def git_commit_and_push():

    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    print(f"Using repo dir: {repo_dir}")

    try:
        # add files
        run_git("git add .", repo_dir)

        # check if anything to commit
        status = run_git("git status --porcelain", repo_dir)

        if not status.stdout.strip():
            print("✅ No changes to commit")
            return

        # commit
        run_git('git commit -m "Auto commit generated images"', repo_dir)

        # pull first (avoid conflicts)
        run_git("git pull origin main", repo_dir)

        # push
        run_git("git push origin main", repo_dir)

        print("✅ Successfully pushed to GitHub")

    except Exception as e:
        print(f"❌ Git error: {e}")

if __name__ == "__main__":
    git_commit_and_push()
