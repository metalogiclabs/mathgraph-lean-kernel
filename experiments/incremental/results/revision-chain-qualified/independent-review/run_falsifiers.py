#!/usr/bin/env python3
"""Targeted real-fixture reader falsifiers; no input copying or source mutation."""
import argparse
import copy
import json
from pathlib import Path

from reviewer import Reviewer, validate_structure


def run(artifact,repo,source,output):
    observed=[]
    def refuse(label,action):
        try:action()
        except (ValueError,KeyError,FileNotFoundError) as error:
            observed.append(dict(case=label,status='REFUSED',reason=type(error).__name__+': '+str(error)))
        else:raise AssertionError('falsifier accepted: '+label)
    base=Reviewer(artifact,repo,source,True)
    fake=copy.deepcopy(base.report);fake.update(repetitions=0,cycles=0,profiles={},requested_profiles=[])
    refuse('fake-passed-zero-work',lambda:validate_structure(fake,True))
    missing=Reviewer(artifact,repo,source,True)
    first=next(iter(missing.report['profiles'].values()))['pairs'][0]['steps'][0]
    member=missing.store.join(missing.store.lifecycle,first['export_witness']['artifact_relative_path'])
    del missing.store.members[member]
    refuse('missing-complete-input-object',missing.run)
    corrupt=Reviewer(artifact,repo,source,True)
    first=next(iter(corrupt.report['profiles'].values()))['pairs'][0]['steps'][0]
    first['export_witness']['sha256']='0'*64
    refuse('changed-compressed-input-digest',corrupt.run)
    parent=Reviewer(artifact,repo,source,True)
    first=next(iter(parent.report['profiles'].values()))['pairs'][0]['steps'][0]
    target=first['result_witness']['uncompressed_sha256'];original=parent.store.archive_json
    def changed(record):
        value=original(record)
        if record['uncompressed_sha256']==target:
            value['previous_evidence']='0'*64
        return value
    parent.store.archive_json=changed
    refuse('raw-result-parent-substitution',parent.run)
    coverage=Reviewer(artifact,repo,source,True)
    for profile in coverage.report['profiles'].values():
        for pair in profile['pairs']:
            for step in pair['steps']:step['export_witness']=None
    refuse('all-changed-input-descriptors-omitted',coverage.run)
    result=dict(status='PASS_DIRECTED_FAIL_CLOSED_FALSIFIERS',qualified=False,
                mutation_scope='Temporary in-memory artifact views; no source or full-input file was changed/copied.',
                cases=observed)
    Path(output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact',type=Path,required=True);p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--source',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.artifact,a.repo,a.source,a.output)
