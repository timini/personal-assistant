"""Interactive first-run onboarding for PA."""

import sys
from pathlib import Path

import yaml


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    answer = input(f"{prompt}{suffix}: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def setup():
    """Interactive setup flow — generates user.yaml."""
    from pa_core.config import PA_ROOT

    user_yaml_path = PA_ROOT / "user.yaml"
    env_path = PA_ROOT / ".env"

    if user_yaml_path.exists():
        if not _ask_yes_no("user.yaml already exists. Overwrite?", default=False):
            print("Setup cancelled.")
            return

    print("\n=== PA Setup ===\n")

    name = _ask("Your name", "")
    email = _ask("Your email", "")
    timezone = _ask("Timezone", "Europe/London")

    print("\n--- Enable integrations ---")
    plugins = []
    if _ask_yes_no("Enable Google Workspace (email/calendar)?"):
        plugins.append("pa-google")
    if _ask_yes_no("Enable Notion (task management)?"):
        plugins.append("pa-notion")
    if _ask_yes_no("Enable WhatsApp?", default=False):
        plugins.append("pa-whatsapp")
    if _ask_yes_no("Enable Finance (Lunchflow)?", default=False):
        plugins.append("pa-finance")

    print("\n--- Projects ---")
    print("Add your projects (enter empty name to finish):")
    projects = []
    while True:
        proj_name = _ask("Project name", "")
        if not proj_name:
            break
        category = _ask(f"Category for '{proj_name}' (work/personal)", "personal")
        projects.append({"name": proj_name, "category": category})

    config = {
        "name": name,
        "email": email,
        "timezone": timezone,
        "enabled_plugins": plugins,
        "projects": projects,
    }

    with open(user_yaml_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"\nCreated {user_yaml_path}")

    if not env_path.exists():
        print(f"\nNote: You still need to create {env_path} with your API keys.")
        print(f"See {PA_ROOT / '.env.example'} for the template.")
    else:
        print(f"\n.env already exists at {env_path}")

    if "pa-google" in plugins:
        print("\nGoogle Workspace: Make sure 'gws' CLI is installed and run 'gws auth setup'.")

    if "pa-notion" in plugins:
        print("\nNotion: Add your NOTION_ACCESS_TOKEN to .env")

    print("\nSetup complete! Run 'uv run pa-google briefing' or 'uv run pa-notion tasks list' to test.")


def main():
    """CLI entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup()
    else:
        print("Usage: pa-core setup")
        print("  setup  — Interactive first-run onboarding")


if __name__ == "__main__":
    main()
