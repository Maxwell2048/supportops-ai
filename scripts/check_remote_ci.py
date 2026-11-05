"""Read exact-commit GitHub Actions results without printing/persisting authentication.

Uses an existing noninteractive Git credential helper; never initiates login.
Example: python scripts/check_remote_ci.py --sha <full-commit-sha>
"""
import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, url):
        if urllib.parse.urlsplit(url).scheme != 'https':
            raise ValueError('Refusing a non-HTTPS GitHub redirect')
        redirected = super().redirect_request(request, fp, code, msg, headers, url)
        if urllib.parse.urlsplit(url).netloc != urllib.parse.urlsplit(request.full_url).netloc:
            redirected.remove_header('Authorization')
        return redirected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--repo', default='Maxwell2048/supportops-ai')
    parser.add_argument('--logs', action='store_true', help='Include bounded redacted failure diagnostics')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.sha) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
        parser.error('Use a full commit SHA and owner/repository name')
    credentials = subprocess.run(['git', 'credential', 'fill'], input=f'protocol=https\nhost=github.com\npath={args.repo}.git\n\n',
        capture_output=True, text=True, env=dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never'))
    token = dict(line.split('=', 1) for line in credentials.stdout.splitlines() if '=' in line).get('password')
    if credentials.returncode or not token:
        raise SystemExit('Existing noninteractive GitHub authentication is unavailable; no login was attempted')
    opener = urllib.request.build_opener(SafeRedirect())
    def fetch(path, *, raw=False):
        request = urllib.request.Request(f'https://api.github.com/repos/{args.repo}/{path}', headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json', 'User-Agent': 'SupportOps-CI-Verification'})
        try:
            with opener.open(request, timeout=30) as response:
                data = response.read().decode('utf-8', 'replace')
            return data if raw else json.loads(data)
        except urllib.error.HTTPError as error:
            raise SystemExit(f'GitHub API returned status {error.code}; no credentials were printed') from None
    runs = fetch(f'actions/runs?head_sha={args.sha}&per_page=100')['workflow_runs']
    output = []
    for run in runs:
        if run['head_sha'] != args.sha:
            raise RuntimeError('GitHub returned a mismatched commit')
        jobs = fetch(f"actions/runs/{run['id']}/jobs?per_page=100")['jobs']
        row = {'id': run['id'], 'head_sha': run['head_sha'], 'status': run['status'], 'conclusion': run['conclusion'], 'url': run['html_url'], 'updated_at': run['updated_at'],
               'jobs': [{'id': job['id'], 'name': job['name'], 'status': job['status'], 'conclusion': job['conclusion'],
                         'active_steps': [{'name':step['name'],'started_at':step.get('started_at')} for step in job.get('steps', []) if step.get('status') == 'in_progress'],
                         'failed_steps': [step['name'] for step in job.get('steps', []) if step.get('conclusion') == 'failure']} for job in jobs]}
        if args.logs:
            for job in row['jobs']:
                if job['conclusion'] != 'failure':
                    continue
                logs = fetch(f"actions/jobs/{job['id']}/logs", raw=True).replace(token, '[REDACTED]')
                lines = logs.splitlines()
                positions = [number for number, line in enumerate(lines) if 'Error:' in line or 'FAILED ' in line or '##[error]' in line]
                selected = sorted({index for number in positions for index in range(max(0, number-2), min(len(lines), number+14))})
                job['diagnostics'] = '\n'.join(lines[index] for index in selected)[-12000:]
        output.append(row)
    print(json.dumps(output, ensure_ascii=True))
    return 0 if runs and all(row['status'] == 'completed' and row['conclusion'] == 'success' for row in output) else 1


if __name__ == '__main__':
    raise SystemExit(main())
