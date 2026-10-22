"""Reject CJK text in publishable files and, optionally, reachable Git history.

This is a character-policy guard, not a semantic proof that prose is English.
Ignored local data (including .env and database files) is never scanned.
"""

import argparse
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def contains_cjk(content):
    text = content.decode('utf-8', errors='replace')
    return any(
        0x3400 <= ord(char) <= 0x9FFF
        or 0xF900 <= ord(char) <= 0xFAFF
        or 0x20000 <= ord(char) <= 0x323AF
        for char in text
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', action='store_true', help='Also check all snapshots/messages reachable from HEAD')
    args = parser.parse_args()
    paths = set(git('ls-files', '--cached', '--others', '--exclude-standard', '-z').decode().split('\0')) - {''}
    failures = []
    for name in sorted(paths):
        file = ROOT / name
        if contains_cjk(name.encode()) or (file.is_file() and contains_cjk(file.read_bytes())):
            failures.append(name)
    commits, blobs = [], set()
    if args.history:
        commits = git('rev-list', 'HEAD').decode().splitlines()
        for commit in commits:
            if contains_cjk(git('show', '-s', '--format=%B', commit)):
                failures.append(f'{commit[:7]}:commit-message')
            for record in git('ls-tree', '-rz', commit).split(b'\0'):
                if not record:
                    continue
                metadata, name = record.split(b'\t', 1)
                _, kind, object_id = metadata.split()
                if contains_cjk(name):
                    failures.append(f'{commit[:7]}:filename')
                if kind == b'blob' and object_id not in blobs:
                    blobs.add(object_id)
                    if contains_cjk(git('cat-file', 'blob', object_id.decode())):
                        failures.append(f'{commit[:7]}:{name.decode()}')
    if failures:
        raise SystemExit('CJK text found in publishable content:\n' + '\n'.join(failures))
    print(f'Language character check passed: {len(paths)} files, {len(commits)} commits, {len(blobs)} historical blobs.')


if __name__ == '__main__':
    main()
