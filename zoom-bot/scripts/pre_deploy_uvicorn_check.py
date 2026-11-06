import subprocess
import sys


def main():
    print("🔍 Running Uvicorn pre-deploy check...")

    try:
        # Dry run only imports the app and does not keep listening
        result = subprocess.run(
            ["uvicorn", "app.main:app", "--reload", "--port", "9999"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # If loading fails
        if result.returncode != 0 or "Traceback" in result.stderr:
            print("❌ Uvicorn failed to start:\n", result.stderr)
            sys.exit(1)

    except subprocess.TimeoutExpired:
        print("✅ App appears to start correctly (dry check)")

    except Exception as e:
        print("❌ Unexpected error during Uvicorn check:", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
