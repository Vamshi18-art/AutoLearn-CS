import os
import subprocess


def run_git(cmd, repo_dir):
    """Run git command with logging"""
    result = subprocess.run(
        cmd,
        cwd=repo_dir,
        shell=True,
        capture_output=True,
        text=True
    )

    print(f"\n👉 Running: {cmd}")
    print("STDOUT:", result.stdout.strip())
    print("STDERR:", result.stderr.strip())

    return result


def mark_repo_safe(repo_dir):
    """Fix dubious ownership issue automatically"""
    print("\n🔐 Marking repo as safe...")
    subprocess.run(
        f'git config --global --add safe.directory "{repo_dir}"',
        shell=True
    )


def git_commit_and_push():
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    print(f"📁 Using repo dir: {repo_dir}")

    try:
        # STEP 0: Fix ownership issue
        mark_repo_safe(repo_dir)

        # STEP 1: Check repo access
        print("\n🔍 Checking git status...")
        status_check = run_git("git status", repo_dir)

        if "fatal" in status_check.stderr.lower():
            print("❌ Git still cannot access repo. Check permissions.")
            return

        # STEP 2: Pull latest changes first
        print("\n🔄 Pulling latest changes...")
        run_git("git pull origin main", repo_dir)

        # STEP 3: Add files (force add in case of .gitignore)
        print("\n➕ Adding files...")
        run_git("git add -A", repo_dir)

        # STEP 4: Check if changes exist
        print("\n🔍 Checking for changes...")
        status = run_git("git status --porcelain", repo_dir)

        if not status.stdout.strip():
            print("✅ No changes to commit")
            return

        # STEP 5: Commit
        print("\n💾 Committing changes...")
        run_git('git commit -m "Auto commit generated images"', repo_dir)

        # STEP 6: Push
        print("\n🚀 Pushing to GitHub...")
        run_git("git push origin main", repo_dir)

        print("\n✅ Successfully pushed to GitHub 🎉")

    except Exception as e:
        print(f"\n❌ Git error: {e}")


if __name__ == "__main__":
    git_commit_and_push()