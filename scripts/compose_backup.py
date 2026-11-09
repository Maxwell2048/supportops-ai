"""Back up a local Compose database or restore into a new isolated database.

Backups may contain sensitive data. Choose a secure output outside version control.
Restore targets must be new databases named restore_<lowercase letters or digits>.
"""
import argparse
import re
import subprocess
from pathlib import Path


def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, **kwargs)


def database_container(project):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}', project):
        raise ValueError('Use the exact local Compose project name')
    result = docker('ps', '--filter', f'label=com.docker.compose.project={project}',
                    '--filter', 'label=com.docker.compose.service=db', '--format', '{{.ID}}', capture_output=True, text=True)
    matches = result.stdout.splitlines()
    if len(matches) != 1:
        raise RuntimeError('Exactly one running db container for the project is required')
    return matches[0]


def backup(container, output):
    output = Path(output)
    with output.open('xb') as archive:
        try:
            docker('exec', container, 'sh', '-c', 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc', stdout=archive)
        except Exception:
            archive.close()
            output.unlink(missing_ok=True)
            raise
    print(f'Backup written to {output} ({output.stat().st_size} bytes)')


def restore(container, source, database):
    if not re.fullmatch(r'restore_[a-z0-9]{1,40}', database):
        raise ValueError('Restore database must be a new name beginning with restore_')
    source = Path(source)
    if not source.is_file():
        raise ValueError('Backup archive does not exist')
    # createdb refuses existing names. A failed restore leaves the new target for inspection.
    docker('exec', container, 'sh', '-c', 'exec createdb -U "$POSTGRES_USER" "$1"', 'sh', database)
    with source.open('rb') as archive:
        docker('exec', '-i', container, 'sh', '-c',
               'exec pg_restore -U "$POSTGRES_USER" --exit-on-error --no-owner --no-privileges -d "$1"', 'sh', database,
               stdin=archive)
    print(f'Restored archive into new database {database}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, help='Exact running local Compose project name')
    commands = parser.add_subparsers(dest='command', required=True)
    save = commands.add_parser('backup')
    save.add_argument('--output', required=True)
    load = commands.add_parser('restore')
    load.add_argument('--input', required=True)
    load.add_argument('--database', required=True)
    args = parser.parse_args()
    container = database_container(args.project)
    if args.command == 'backup':
        backup(container, args.output)
    else:
        restore(container, args.input, args.database)


if __name__ == '__main__':
    main()
