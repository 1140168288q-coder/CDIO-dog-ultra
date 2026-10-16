"""Publish the prepared repository; delete the two fixed legacy repos only after verification."""
import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OWNER = '1140168288q-coder'
TARGET = 'CDIO-dog-ultra'
LEGACY = {
    'CDIO-dog-pro': (1241680031, 'efc2e8a89482ef91c74b1c332e6d80795fe85457'),
    'CDIO-dog-pro-max': (1247987089, '35c69c6301b8738b76c7811314e4df76e172723e'),
}


def git(*args, env=None):
    result = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, env=env)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
    return result.stdout


def local_state():
    if git('status', '--porcelain').strip():
        raise RuntimeError('Local changes are not committed. Stop and review them first.')
    manifest = json.loads((ROOT / 'docs/migration-manifest.json').read_text(encoding='utf-8'))
    for item in manifest['sources']:
        content = (ROOT / item['destination']).read_bytes()
        if hashlib.sha256(content).hexdigest() != item['sha256']:
            raise RuntimeError('Source checksum differs: ' + item['destination'])
    refs = {'main': git('rev-parse', 'main').decode().strip()}
    for name, (_, sha) in LEGACY.items():
        branch = 'history/' + name
        if git('rev-parse', branch).decode().strip() != sha:
            raise RuntimeError('Historical branch differs: ' + branch)
        git('merge-base', '--is-ancestor', sha, refs['main'])
        refs[branch] = sha
    tree = {}
    for record in git('ls-tree', '-rz', '--full-tree', 'main').split(b'\0'):
        if record:
            header, path = record.split(b'\t', 1)
            mode, kind, sha = header.decode().split()
            tree[path.decode('utf-8')] = (mode, kind, sha)
    git('fsck', '--full', '--no-dangling')
    return refs, tree, manifest


class GitHub:
    def __init__(self, token):
        self.token = token

    def call(self, path, method='GET', body=None, missing=False):
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request('https://api.github.com' + path, data=payload, method=method, headers={
            'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json',
            'User-Agent': 'CDIO-dog-ultra-migration',
        })
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                content = response.read()
                return json.loads(content) if content else None
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            detail = error.read().decode(errors='replace')
            raise RuntimeError(f'GitHub {method} {path}: HTTP {error.code}: {detail}') from None


def check_legacy(api, name):
    expected_id, expected_tip = LEGACY[name]
    base = f'/repos/{OWNER}/{name}'
    repo = api.call(base, missing=True)
    if repo is None:
        return False
    if repo['id'] != expected_id or repo['full_name'] != OWNER + '/' + name:
        raise RuntimeError('Legacy repository identity changed: ' + name)
    branches = api.call(base + '/branches?per_page=100')
    if [(b['name'], b['commit']['sha']) for b in branches] != [('main', expected_tip)]:
        raise RuntimeError('Legacy branches changed; preserve new work before proceeding: ' + name)
    for suffix in ['/git/matching-refs/tags/', '/issues?state=all&per_page=1', '/releases?per_page=1']:
        if api.call(base + suffix):
            raise RuntimeError('Legacy repository has additional metadata to preserve: ' + name + suffix)
    return True


def verify_target(api, refs, expected_tree, manifest):
    base = f'/repos/{OWNER}/{TARGET}'
    repo = api.call(base)
    if repo['full_name'] != OWNER + '/' + TARGET or repo['private'] or repo['default_branch'] != 'main':
        raise RuntimeError('Target repository identity, visibility or default branch differs.')
    for branch, sha in refs.items():
        actual = api.call(base + '/git/ref/heads/' + branch)['object']['sha']
        if actual != sha:
            raise RuntimeError('Remote branch differs: ' + branch)
    remote = api.call(base + '/git/trees/' + refs['main'] + '?recursive=1')
    if remote.get('truncated'):
        raise RuntimeError('Remote tree response is truncated.')
    actual_tree = {e['path']: (e['mode'], e['type'], e['sha']) for e in remote['tree'] if e['type'] != 'tree'}
    if actual_tree != expected_tree:
        raise RuntimeError('Remote files do not exactly match the prepared local tree.')
    for history in manifest['history']:
        for sha in history['commits']:
            if api.call(base + '/git/commits/' + sha)['sha'] != sha:
                raise RuntimeError('An original commit is missing: ' + sha)


def get_token():
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token and shutil.which('gh'):
        result = subprocess.run(['gh', 'auth', 'token', '--hostname', 'github.com'], capture_output=True)
        if result.returncode == 0:
            token = result.stdout.decode().strip()
    if not token:
        token = getpass.getpass('GitHub token (hidden; never saved): ').strip()
    if not token:
        raise RuntimeError('No GitHub token provided.')
    return token


def publish(api, refs, tree, manifest, delete_legacy):
    user = api.call('/user')
    if user['login'].lower() != OWNER.lower():
        raise RuntimeError('Authenticated account does not match ' + OWNER)
    for name in LEGACY:
        check_legacy(api, name)
    base = f'/repos/{OWNER}/{TARGET}'
    repo = api.call(base, missing=True)
    if repo is None:
        api.call('/user/repos', 'POST', {
            'name': TARGET, 'private': False, 'auto_init': False,
            'description': 'CDIO robotic dog: final Pico 2 MicroPython AFSM controller, calibration, diagrams and preserved project history',
        })
        print('Created ' + OWNER + '/' + TARGET)
    else:
        if repo['full_name'] != OWNER + '/' + TARGET or repo['private'] or repo.get('archived'):
            raise RuntimeError('Existing target does not match the planned public repository.')
        if repo.get('size', 0):
            verify_target(api, refs, tree, manifest)
    environment = os.environ.copy()
    credentials = base64.b64encode((OWNER + ':' + api.token).encode()).decode()
    environment.update({
        'GIT_TERMINAL_PROMPT': '0',
        'GIT_CONFIG_COUNT': '2',
        'GIT_CONFIG_KEY_0': 'http.https://github.com/.extraheader',
        'GIT_CONFIG_VALUE_0': 'Authorization: Basic ' + credentials,
        'GIT_CONFIG_KEY_1': 'credential.helper',
        'GIT_CONFIG_VALUE_1': '',
    })
    url = f'https://{OWNER}@github.com/{OWNER}/{TARGET}.git'
    git('push', '--atomic', url, *[f'refs/heads/{name}:refs/heads/{name}' for name in refs], env=environment)
    if api.call(base)['default_branch'] != 'main':
        api.call(base, 'PATCH', {'default_branch': 'main'})
    verify_target(api, refs, tree, manifest)
    print(f'Verified {len(tree)} files, three branches and all six original commits.')
    if delete_legacy:
        # Recheck both sources and the new remote immediately before any deletion.
        for name in LEGACY:
            check_legacy(api, name)
        verify_target(api, refs, tree, manifest)
        for name in LEGACY:
            if check_legacy(api, name):
                api.call(f'/repos/{OWNER}/{name}', 'DELETE')
                if api.call(f'/repos/{OWNER}/{name}', missing=True) is not None:
                    raise RuntimeError('Deletion could not be verified: ' + name)
                print('Deleted ' + OWNER + '/' + name)
            else:
                print('Already absent: ' + OWNER + '/' + name)
    print(f'Completed: https://github.com/{OWNER}/{TARGET}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delete-legacy', action='store_true', help='Delete only the two fixed legacy repositories after all verification passes.')
    parser.add_argument('--check-local', action='store_true', help='Check prepared local contents and history without network or authentication.')
    args = parser.parse_args()
    refs, tree, manifest = local_state()
    print(f'Local checks passed: {len(tree)} files and {len(manifest["sources"])} source checksums.')
    if args.check_local:
        return
    token = get_token()
    try:
        publish(GitHub(token), refs, tree, manifest, args.delete_legacy)
    except Exception as error:
        detail = str(error).replace(token, '[REDACTED]')
        detail = detail.replace(base64.b64encode((OWNER + ':' + token).encode()).decode(), '[REDACTED]')
        raise RuntimeError(detail) from None


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print('Stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
