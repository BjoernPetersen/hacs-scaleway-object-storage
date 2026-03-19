import json
from pathlib import Path
from importlib import metadata


def update_hacs(base_dir: Path) -> None:
    hass_version = metadata.version("homeassistant")
    path = base_dir / "hacs.json"
    with path.open("a+") as file:
        file.seek(0)
        data = json.load(file)

        data["homeassistant"] = hass_version

        file.seek(0)
        file.truncate()
        json.dump(data, file, indent=2)
        file.write("\n")


def update_manifest(base_dir: Path) -> None:
    package_id = "scaleway-object-storage"
    version = metadata.version(package_id)
    dependencies = metadata.requires(package_id)
    manifest_path = (
        base_dir / "custom_components" / "scaleway_object_storage" / "manifest.json"
    )
    with manifest_path.open("a+") as file:
        file.seek(0)
        data = json.load(file)
        data["version"] = version
        data["requirements"] = dependencies

        file.seek(0)
        file.truncate()
        json.dump(data, file, indent=2)


def main() -> None:
    base_dir = Path().absolute()
    if base_dir.name == "bin":
        base_dir = base_dir.parent

    update_hacs(base_dir)
    update_manifest(base_dir)


if __name__ == "__main__":
    main()
