import sys
import json
import subprocess
import shutil
import os
from pathlib import Path
from typing import Dict, List, Tuple


def save_leanpkg_info(out_directory: Path):
    shutil.copy2("leanpkg.toml", out_directory / "leanpkg.toml")


def run_command(command: List[str]) -> Tuple[bytes, bytes]:
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as out:
        return out.communicate()


def get_lean_paths() -> List[Path]:
    print("getting lean paths...")
    stdout, stderr = run_command(["lean", "--path"])
    assert stderr is None, stderr
    s = stdout.decode("utf-8")
    d = json.loads(s)
    return [Path(p) for p in d["path"]]


def rename_paths(paths: List[Path]) -> Dict[Path, Path]:
    # just use last two directories in path
    path_map = {}
    for p in paths:
        path_map[p] = p.relative_to(p.parent.parent)
    return path_map


def save_path_map(path_map: Dict[Path, Path], out_directory: Path):
    with open(out_directory / "path_map.json", "w") as f:
        s = json.dumps({str(p1): str(p2) for p1, p2 in path_map.items()})
        f.write(s)


def get_lean_files(paths: List[Path]) -> List[Path]:
    file_paths = []
    for p in paths:
        for file_name in p.glob("**/*.lean"):
            file_paths.append(file_name)
    return file_paths


def save_lean_files(path_map, lean_files: List[Path], out_directory: Path):
    for file_path in lean_files:
        for p in path_map:
            if p in file_path.parents:
                relative_file_path = file_path.relative_to(p)
                new_file_path = out_directory / "lean_files/" / path_map[p] / relative_file_path
                os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
                if not new_file_path.exists():
                    shutil.copy2(file_path, new_file_path)
                break


def delete_oleans(lean_files: List[Path]):
    for file_path in lean_files:
        # replace suffix .lean => .olean
        olean = file_path.with_suffix(".olean")
        if olean.exists():
            olean.chmod(0o644)
            olean.parent.chmod(0o777)
            olean.unlink()  # deletes olean file


def run_lean_make(filename: Path, out_directory: Path):
    print("running lean on", filename, "...")
    with open(out_directory / "lean_stdout.log", "w+b") as stdout_file:
        with open(out_directory / "lean_stderr.log", "w+b") as stderr_file:
            print("piping stdout to", stdout_file.name, "...")
            print("piping stderr to", stderr_file.name, "...")
            out = subprocess.Popen(
                ["lean", "--make", "--json", "-D pp.colors=false", filename],
                stdout=stdout_file,
                stderr=stderr_file,
            )
            out.communicate()
            stderr = stderr_file.readlines()
            assert not stderr, b"".join(stderr)
            rc = out.returncode
            assert rc >= 0, f"lean --make returned non-zero return code {rc}"


def run_lean_file_and_save_output(lean_file: Path, out_directory: Path):
    assert lean_file.exists(), lean_file
    assert lean_file.is_file(), lean_file
    assert lean_file.suffix == ".lean", lean_file
    assert out_directory.exists(), out_directory
    assert out_directory.is_dir(), out_directory

    # save version information
    save_leanpkg_info(out_directory)

    # save path information
    paths = get_lean_paths()
    path_map = rename_paths(paths)
    save_path_map(path_map, out_directory)

    # save lean files for later inspection
    file_paths = get_lean_files(paths)
    save_lean_files(path_map, file_paths, out_directory)

    # delete oleans so tracing works on all decendent files
    delete_oleans(file_paths)

    # the big step. Run lean --make --json and pipe output to file
    run_lean_make(lean_file, out_directory)


def main():
    assert len(sys.argv) == 3, sys.argv
    lean_file = Path(sys.argv[1])
    out_directory = Path(sys.argv[2])
    run_lean_file_and_save_output(lean_file, out_directory)


if __name__ == "__main__":
    main()
