"""Generate missing local auth secrets without displaying or replacing them."""

from pathlib import Path
import secrets

from dotenv import dotenv_values


def main():
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        raise SystemExit("Create the local .env from .env.example and configure PostgreSQL first")
    existing = dotenv_values(path)
    additions = {}
    if not existing.get("JWT_SECRET"):
        additions["JWT_SECRET"] = secrets.token_urlsafe(48)
    if not existing.get("DEMO_PASSWORD"):
        additions["DEMO_PASSWORD"] = secrets.token_urlsafe(24)
    if additions:
        # dotenv uses the last occurrence if the template contains an empty key.
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\n# Locally generated auth values; keep private.\n")
            for key, value in additions.items():
                stream.write(f"{key}={value}\n")
    print("Local auth configuration ready; existing nonempty values preserved; secrets not displayed")


if __name__ == "__main__":
    main()
