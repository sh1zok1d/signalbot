"""External journal checkpoints (ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1).

A cloud VM is ephemeral: a journal that holds paid provider state (an accepted
batch id, completed rounds) must leave the machine as soon as it changes in a way
that money depends on. The Caller and the runner call ledger.checkpoint(stage):
  PROVIDER_ACCEPTED       a Message Batch id was journaled (before any polling)
  ROUND_COMPLETE          a generation round was admitted
  REVIEW_BLOCK            every 10 reviewed cards
  CAMPAIGN_RESULT         the campaign result was written
  CAMPAIGN_<status>       the run stopped or paused

Each checkpoint writes a consistent SQLite snapshot (online backup API, never a
copy of a live WAL file) and a JSON manifest that names every open provider id in
plain text, then makes them durable:
  DirectoryCheckpointer   a directory on durable storage (Cursor / local disk)
  GitCheckpointer         commit the two files and push the current branch

A checkpoint that cannot be made durable raises CheckpointFailed, an
infrastructure stop: the run pauses (PAUSED_CHECKPOINT_FAILED) with its journal
intact, and a resume continues polling; nothing is POSTed again. Credentials are
never in the journal, so never in a checkpoint.
"""
from __future__ import annotations
import hashlib
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from .context import ContractError, canonical
from .ledger import InfrastructureStop

SNAPSHOT_NAME = 'run.sqlite'
MANIFEST_NAME = 'CHECKPOINT.json'
PUSH_BACKOFF_SECONDS = (2, 4, 8, 16)


class CheckpointFailed(InfrastructureStop):
    """The journal could not be copied off the machine. Resume after fixing the target."""


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _fsync_dir(path):
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_snapshot(ledger, dest_dir, stage, detail, sequence):
    """Consistent journal copy and manifest in dest_dir. Returns the manifest."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    snap = dest_dir / SNAPSHOT_NAME
    tmp = dest_dir / ('.' + SNAPSHOT_NAME + '.tmp')
    if tmp.exists():
        tmp.unlink()
    target = sqlite3.connect(tmp)
    try:
        ledger.db.backup(target)
        target.execute('PRAGMA journal_mode=DELETE')
        target.commit()
    finally:
        target.close()
    with open(tmp, 'rb') as f:
        os.fsync(f.fileno())
    os.replace(tmp, snap)
    config = ledger.get('config') or {}
    manifest = {
        'CHECKPOINT': 'GENERATOR_V0_JOURNAL_CHECKPOINT_V1',
        'RUN_ID': config.get('RUN_ID'),
        'SEQUENCE': sequence,
        'STAGE': stage,
        'DETAIL': detail,
        'TIME_UTC': datetime.now(timezone.utc).isoformat(),
        'STATUS': ledger.get('status'),
        'SPENT_MICRO_USD': ledger.total_charged_micro_usd(),
        'OPEN_PROVIDER_CALLS': ledger.provider_handles(),
        'SNAPSHOT': SNAPSHOT_NAME,
        'SNAPSHOT_SHA256': _sha256(snap),
        'RESUME': 'copy SNAPSHOT to <run-dir>/run.sqlite and resume the same run; accepted provider ids are polled, never POSTed again',
    }
    mtmp = dest_dir / ('.' + MANIFEST_NAME + '.tmp')
    with open(mtmp, 'w', encoding='utf-8') as f:
        f.write(canonical(manifest) + '\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(mtmp, dest_dir / MANIFEST_NAME)
    _fsync_dir(dest_dir)
    return manifest


class DirectoryCheckpointer:
    """Snapshot into a directory on durable storage (outside the ephemeral run directory)."""

    def __init__(self, dest_dir):
        self.dest_dir = Path(dest_dir)
        self.sequence = 0
        self.last = None

    def describe(self):
        return {'KIND': 'DIRECTORY', 'DEST': str(self.dest_dir)}

    def __call__(self, ledger, stage, detail):
        self.sequence += 1
        try:
            self.last = write_snapshot(ledger, self.dest_dir, stage, detail, self.sequence)
        except (OSError, sqlite3.Error) as e:
            raise CheckpointFailed('journal checkpoint to ' + str(self.dest_dir) + ' failed: ' + type(e).__name__) from e
        return self.last


def _git(repo, *args, runner=subprocess.run):
    return runner(['git', '-C', str(repo)] + list(args), capture_output=True, text=True, timeout=300)


class GitCheckpointer:
    """Snapshot into <repo>/<rel_dir>, commit only those two files and push the branch.

    The checkout must be on `branch`: a checkpoint never switches or rewrites
    branches and never force-pushes. A push is retried (2, 4, 8, 16 s); a final
    failure is CheckpointFailed."""

    def __init__(self, repo_root, rel_dir, branch, remote='origin', runner=subprocess.run, sleeper=time.sleep):
        self.repo = Path(repo_root).resolve()
        self.rel_dir = Path(rel_dir)
        if self.rel_dir.is_absolute() or '..' in self.rel_dir.parts:
            raise ContractError('checkpoint directory must be relative to the repository root')
        if not isinstance(branch, str) or not branch.strip():
            raise ContractError('checkpoint branch required')
        self.branch, self.remote, self._run, self._sleep = branch, remote, runner, sleeper
        self.sequence = 0
        self.last = None
        head = _git(self.repo, 'rev-parse', '--abbrev-ref', 'HEAD', runner=self._run)
        if head.returncode != 0 or head.stdout.strip() != branch:
            raise ContractError('git checkpoint requires the checkout to be on branch ' + branch)

    def describe(self):
        return {'KIND': 'GIT', 'REPO': str(self.repo), 'DIR': self.rel_dir.as_posix(), 'BRANCH': self.branch, 'REMOTE': self.remote}

    def __call__(self, ledger, stage, detail):
        self.sequence += 1
        try:
            manifest = write_snapshot(ledger, self.repo / self.rel_dir, stage, detail, self.sequence)
        except (OSError, sqlite3.Error) as e:
            raise CheckpointFailed('journal snapshot failed: ' + type(e).__name__) from e
        files = [(self.rel_dir / SNAPSHOT_NAME).as_posix(), (self.rel_dir / MANIFEST_NAME).as_posix()]
        add = _git(self.repo, 'add', '-f', '--', *files, runner=self._run)
        if add.returncode != 0:
            raise CheckpointFailed('git add failed: ' + add.stderr.strip()[:300])
        msg = 'checkpoint(generator): {} #{} {}'.format(manifest['RUN_ID'], self.sequence, stage)
        commit = _git(self.repo, 'commit', '-q', '-m', msg, '--', *files, runner=self._run)
        if commit.returncode != 0 and 'nothing' not in (commit.stdout + commit.stderr):
            raise CheckpointFailed('git commit failed: ' + (commit.stderr or commit.stdout).strip()[:300])
        error = ''
        for attempt, wait in enumerate((0,) + PUSH_BACKOFF_SECONDS):
            if wait:
                self._sleep(wait)
            push = _git(self.repo, 'push', '-q', self.remote, 'HEAD:refs/heads/' + self.branch, runner=self._run)
            if push.returncode == 0:
                self.last = manifest
                return manifest
            error = push.stderr.strip()[:300]
        raise CheckpointFailed('git push of the journal checkpoint failed after retries: ' + error)
