#!/usr/bin/env python3
"""Bounded, replay-gated kernel optimization tournament. No model/API calls."""
import argparse
import difflib
import hashlib
import json
import math
import os
import signal
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

BASE = '08ddb26718c86213262943ca19ae8cf1b03fa922'
ARENA = '91f376e4baacf2df0c478e7173bccb2a6adac5c5'
CORPORA = ('std', 'cedar', 'mathlib')
CONFIG = {'use_stdin': True, 'nat_extension': True, 'string_extension': True,
          'unpermitted_axiom_hard_error': False, 'unsafe_permit_all_axioms': True,
          'num_threads': 4, 'print_success_message': False}
# These are compile/code-layout hypotheses, not new reduction rules.
RECIPES = {
    'spine-inline-always': ("    #[inline]\n    fn spine_snoc_hc(", "    #[inline(always)]\n    fn spine_snoc_hc("),
    'spine-inline-never': ("    #[inline]\n    fn spine_snoc_hc(", "    #[inline(never)]\n    fn spine_snoc_hc("),
    'eval-inline-never': ("    pub(crate) fn eval(&mut self, depth:", "    #[inline(never)]\n    pub(crate) fn eval(&mut self, depth:"),
}
CONFLICTS = {'spine-inline-always': 'spine-inline',
             'spine-inline-never': 'spine-inline'}
MAX_CYCLES = 2
MAX_BUILDS = 7
MAX_FULL = 2
WALL_BUDGET = 150 * 60
FLAGS = '-C target-cpu=native'

class StopBudget(Exception):
    pass

class Infrastructure(Exception):
    pass

class Rejected(Exception):
    pass

class BuildFailure(Rejected):
    pass


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def geo(ratios):
    return math.exp(statistics.mean(math.log(x) for x in ratios)) - 1


def score(rows, candidate, champion, corpora=CORPORA):
    med = {c: {a: statistics.median(rows[c][a]) for a in rows[c]} for c in corpora}
    ratios = [med[c][candidate] / med[c][champion] for c in corpora]
    return {'geomean': geo(ratios), 'ratios': dict(zip(corpora, ratios)), 'medians': med}


def screen_ok(s):
    return s['geomean'] <= -0.005 and all(r <= 1.02 for r in s['ratios'].values())


def promotion_ok(s):
    return s['geomean'] <= -0.01 and all(r <= 1.01 for r in s['ratios'].values())


def compatible(recipes):
    if len(set(recipes)) != len(recipes):
        return False
    groups = [CONFLICTS[r] for r in recipes if r in CONFLICTS]
    return len(set(groups)) == len(groups)


def apply_recipes(text, recipes):
    if not compatible(recipes):
        raise Rejected('INCOMPATIBLE_RECIPES')
    # A source anchor must occur exactly once. Never silently patch a new version.
    for recipe in recipes:
        old, new = RECIPES[recipe]
        if text.count(old) != 1:
            raise Rejected('SOURCE_ANCHOR_MISMATCH:' + recipe)
        text = text.replace(old, new, 1)
    return text


class Tournament:
    def __init__(self, root, source, arena, budget=WALL_BUDGET):
        self.root, self.source, self.arena = map(Path, (root, source, arena))
        self.started = time.monotonic()
        self.deadline = self.started + budget
        self.records = []
        self.binaries = {}
        self.outputs = {}
        self.builds = 0
        self.full_evaluations = 0
        self.champion = ()
        self.promotions = []
        self.rejected = set()
        self.status = 'RUNNING'
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = self.root / 'ledger.jsonl'
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps(CONFIG, sort_keys=True))
        (self.root / 'logs').mkdir(exist_ok=True)
        (self.root / 'sources').mkdir(exist_ok=True)
        (self.root / 'bin').mkdir(exist_ok=True)
        self.record('start', base=BASE, arena=ARENA, recipes=list(RECIPES),
                    max_cycles=MAX_CYCLES, max_builds=MAX_BUILDS, max_full=MAX_FULL,
                    wall_budget_seconds=budget, flags=FLAGS)

    def record(self, event, **fields):
        row = {'event': event, 'elapsed': round(time.monotonic() - self.started, 3), **fields}
        self.records.append(row)
        with self.ledger.open('a') as f:
            f.write(json.dumps(row, sort_keys=True) + '\n')
            f.flush()
            os.fsync(f.fileno())
        print('V85 ' + json.dumps(row, sort_keys=True), flush=True)

    def command(self, args, cwd=None, input_path=None, output_path=None, timeout=900, label='command', env=None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise StopBudget('WALL_BUDGET_EXHAUSTED')
        safe = ''.join(ch if ch.isalnum() or ch in '-_.' else '_' for ch in label)
        err = self.root / 'logs' / (safe + '.stderr')
        if output_path is None:
            output_path = self.root / 'logs' / (safe + '.stdout')
        start = time.monotonic()
        limit = min(timeout, remaining)
        with open(input_path, 'rb') if input_path else open(os.devnull, 'rb') as inp, \
             open(output_path, 'wb') as out, err.open('wb') as error:
            proc = subprocess.Popen(args, cwd=cwd, env=env, stdin=inp, stdout=out,
                                    stderr=error, start_new_session=True)
            try:
                returncode = proc.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                self.record('timeout', label=label, limit_seconds=limit)
                if remaining <= timeout:
                    raise StopBudget('WALL_BUDGET_EXHAUSTED')
                raise Infrastructure('TIMEOUT:' + label)
        seconds = time.monotonic() - start
        if returncode:
            self.record('command_failed', label=label, returncode=returncode)
            raise Infrastructure('COMMAND_FAILED:' + label)
        return seconds

    def prepare(self):
        for path, expected in ((self.source, BASE), (self.arena, ARENA)):
            out = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
            if out != expected:
                raise Infrastructure('PIN_MISMATCH:' + str(path))
            dirty = subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain',
                                             '--untracked-files=no'], text=True).strip()
            if dirty:
                raise Infrastructure('DIRTY_FROZEN_SOURCE:' + str(path))
        for corpus in CORPORA:
            self.command(['./lka.py', 'build-test', corpus], cwd=self.arena,
                         label='corpus-' + corpus, timeout=1800)
            p = self.input(corpus)
            if not p.is_file() or not p.stat().st_size:
                raise Infrastructure('MISSING_CORPUS:' + corpus)
            self.record('corpus', corpus=corpus, sha256=digest(p), bytes=p.stat().st_size)
        self.command(['rustc', '--version'], label='rustc-version')
        self.command(['cargo', '--version'], label='cargo-version')
        self.record('environment', rustc=(self.root/'logs/rustc-version.stdout').read_text().strip(),
                    cargo=(self.root/'logs/cargo-version.stdout').read_text().strip())

    def input(self, corpus):
        return self.arena / '_build' / 'tests' / (corpus + '.ndjson')

    def build(self, recipes):
        recipes = tuple(recipes)
        if recipes in self.binaries:
            return self.binaries[recipes]
        if self.builds >= MAX_BUILDS:
            raise StopBudget('BUILD_BUDGET_EXHAUSTED')
        text = apply_recipes((self.source / 'src/eval.rs').read_text(), recipes)
        key = hashlib.sha256((BASE + FLAGS + text).encode()).hexdigest()
        dest = self.root / 'sources' / key
        shutil.copytree(self.source, dest, ignore=shutil.ignore_patterns('.git', 'target'))
        (dest / 'src/eval.rs').write_text(text)
        env = dict(os.environ, RUSTFLAGS=FLAGS, CARGO_INCREMENTAL='0',
                   CARGO_TARGET_DIR=str(self.root / 'target'))
        self.builds += 1
        try:
            self.command(['cargo', 'build', '--release', '--locked', '-q'], cwd=dest, env=env,
                         timeout=900, label='build-' + key[:12])
        except Infrastructure as exc:
            if recipes and str(exc).startswith('COMMAND_FAILED:build-'):
                stderr = (self.root/'logs'/('build-' + key[:12] + '.stderr')).read_text(errors='replace')
                if 'error: could not compile' in stderr or 'error[E' in stderr:
                    raise BuildFailure('COMPILE_FAILED') from exc
            raise
        binary = self.root / 'bin' / (key + '.bin')
        shutil.copy2(self.root / 'target/release/sokonanoda', binary)
        self.binaries[recipes] = binary
        self.record('build', recipes=recipes, source_sha256=key, binary_sha256=digest(binary),
                    bytes=binary.stat().st_size)
        return binary

    def run_binary(self, recipes, corpus, label, compare=True):
        binary = self.build(recipes)
        out = self.root / 'logs' / (label + '.out')
        try:
            seconds = self.command([str(binary), str(self.config)], input_path=self.input(corpus),
                                   output_path=out, timeout=600, label=label)
        except Infrastructure as exc:
            if recipes and (str(exc).startswith('COMMAND_FAILED:') or str(exc).startswith('TIMEOUT:')):
                raise Rejected('CANDIDATE_EXECUTION_FAILED:' + label) from exc
            raise
        if compare:
            reference = self.outputs[corpus]
            if digest(out) != digest(reference) or out.read_bytes() != reference.read_bytes():
                self.record('replay_mismatch', recipes=recipes, corpus=corpus, label=label)
                raise Rejected('REPLAY_MISMATCH:' + corpus)
        return seconds, out

    def replay(self, recipes, corpus):
        if recipes == () and corpus not in self.outputs:
            _, out = self.run_binary((), corpus, 'reference-' + corpus, compare=False)
            self.outputs[corpus] = out
        else:
            self.run_binary(recipes, corpus, 'replay-' + self.key(recipes) + '-' + corpus)
        self.record('replay_exact', recipes=recipes, corpus=corpus)

    @staticmethod
    def key(recipes):
        return 'base' if not recipes else '-'.join(recipes)

    def measure(self, candidate, champion, corpora, passes, phase):
        # Two executions of the unchanged champion provide an A/A noise control.
        arms = ['champion', 'candidate', 'control']
        mapping = {'champion': champion, 'candidate': candidate, 'control': champion}
        if champion:
            arms.append('baseline')
            mapping['baseline'] = ()
        rows = {c: {a: [] for a in arms} for c in corpora}
        for p in range(passes):
            order = arms[p % 3:] + arms[:p % 3]
            for corpus in corpora:
                for arm in order:
                    seconds, _ = self.run_binary(mapping[arm], corpus,
                        '%s-%s-%s-%s' % (phase, p, corpus, arm))
                    rows[corpus][arm].append(seconds)
                    self.record('timing', phase=phase, pass_index=p, corpus=corpus,
                                arm=arm, recipes=mapping[arm], seconds=seconds)
        s = score(rows, 'candidate', 'champion', corpora)
        noise = score(rows, 'control', 'champion', corpora)
        self.record('score', phase=phase, candidate=candidate, champion=champion,
                    score=s, aa_control=noise, passes=passes)
        return s, noise

    def evaluate(self, candidate, champion):
        # Compile and exact replay precede every timing. No source is promoted by a screen.
        try:
            self.build(candidate)
            if digest(self.binaries[candidate]) == digest(self.binaries[champion]):
                raise Rejected('NO_BINARY_DELTA')
            for corpus in ('std', 'cedar'):
                self.replay(candidate, corpus)
            s, _ = self.measure(candidate, champion, ('std', 'cedar'), 2, 'screen-' + self.key(candidate))
            if not screen_ok(s):
                raise Rejected('SCREEN_REJECT')
            self.replay(candidate, 'mathlib')
            s, _ = self.measure(candidate, champion, ('mathlib',), 1, 'mathlib-screen-' + self.key(candidate))
            if not screen_ok(s):
                raise Rejected('MATHLIB_SCREEN_REJECT')
            return s['geomean']
        except Rejected as exc:
            self.rejected.add(candidate)
            self.record('reject', candidate=candidate, reason=str(exc))
            return False

    def confirm(self, candidate, champion):
        # Separate complete timing rounds; not an independent hardware replication.
        if self.full_evaluations >= MAX_FULL:
            raise StopBudget('FULL_EVALUATION_BUDGET_EXHAUSTED')
        self.full_evaluations += 1
        for phase, passes in (('full', 5), ('confirm', 3)):
            s, noise = self.measure(candidate, champion, CORPORA, passes,
                                    phase + '-' + self.key(candidate))
            if not promotion_ok(s):
                self.rejected.add(candidate)
                self.record('reject', candidate=candidate, reason='NO_REPEATABLE_GAIN', phase=phase)
                return False
            if abs(noise['geomean']) > 0.01:
                self.rejected.add(candidate)
                self.record('reject', candidate=candidate, reason='AA_CONTROL_UNSTABLE', phase=phase)
                return False
        self.record('promotion', candidate=candidate, previous=champion,
                    scope='FROZEN_THREE_CORPORA', causal_status='OPEN',
                    status='PROVISIONAL_BENCHMARK_CHAMPION')
        self.promotions.append(candidate)
        return True

    def run(self):
        try:
            self.prepare()
            self.build(())
            for corpus in CORPORA:
                self.replay((), corpus)
            for cycle in range(MAX_CYCLES):
                champion = self.champion
                # Candidate generation is conditioned on retained results: after a
                # promotion, try only unused, compatible recipes on the new champion.
                remaining = [r for r in RECIPES if r not in champion]
                if not remaining:
                    break
                candidates = []
                for recipe in remaining:
                    candidate = champion + (recipe,)
                    if not compatible(candidate):
                        continue
                    if candidate in self.rejected:
                        continue
                    candidates.append(candidate)
                candidates = candidates[:3]
                self.record('cycle', index=cycle + 1, champion=champion, candidates=candidates)
                screened = []
                for candidate in candidates:
                    result = self.evaluate(candidate, champion)
                    if result is not False:
                        screened.append((result, candidate))
                screened.sort(key=lambda x: (x[0], x[1]))
                promoted = False
                for _, candidate in screened:
                    if self.full_evaluations >= MAX_FULL:
                        raise StopBudget('FULL_EVALUATION_BUDGET_EXHAUSTED')
                    if self.confirm(candidate, champion):
                        self.champion = candidate
                        promoted = True
                        break
                if not promoted:
                    self.status = 'NO_PROMOTION'
                    break
            else:
                self.status = 'CYCLE_BUDGET_EXHAUSTED'
            if self.status == 'RUNNING':
                self.status = 'COMPLETED'
        except StopBudget as exc:
            self.status = str(exc)
            self.record('budget_stop', reason=str(exc))
        except (Infrastructure, Rejected, OSError, ValueError) as exc:
            self.status = 'INFRASTRUCTURE_FAILURE'
            self.record('failure', reason=str(exc))
        finally:
            champion = self.binaries.get(self.champion)
            if champion and self.champion:
                shutil.copy2(champion, self.root / 'champion.bin')
                original = (self.source/'src/eval.rs').read_text()
                modified = apply_recipes(original, self.champion)
                (self.root/'champion.patch').write_text(''.join(difflib.unified_diff(
                    original.splitlines(keepends=True), modified.splitlines(keepends=True),
                    fromfile='a/src/eval.rs', tofile='b/src/eval.rs')))
            result = {'status': self.status, 'base': BASE, 'arena': ARENA,
                      'champion_recipes': self.champion,
                      'champion_binary_sha256': digest(champion) if champion else None,
                      'promotions': self.promotions, 'builds': self.builds,
                      'full_evaluations': self.full_evaluations,
                      'elapsed_seconds': round(time.monotonic() - self.started, 3),
                      'champion_patch': 'champion.patch' if self.champion else None,
                      'champion_binary': 'champion.bin' if self.champion else None,
                      'scientific_scope': 'Frozen Std/Cedar/Mathlib only; no unseen or causal claim',
                      'ledger': 'ledger.jsonl'}
            (self.root / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
            self.record('finish', **result)
        return 1 if self.status == 'INFRASTRUCTURE_FAILURE' else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--source', required=True)
    p.add_argument('--arena', required=True)
    args = p.parse_args()
    return Tournament(args.root, args.source, args.arena).run()

if __name__ == '__main__':
    sys.exit(main())
