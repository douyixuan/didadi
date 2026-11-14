"""Offline product-tree and evidence gate. Does not execute linked commands."""
import hashlib
import argparse
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

SHA = re.compile(r'^[0-9a-f]{40}$')


def slug(value):
    return re.sub(r'[^\w\-\s]', '', value.lower()).replace(' ', '-')


def local_link(root, source, reference):
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError('Missing evidence or source link')
    parsed = urlsplit(reference)
    if parsed.scheme:
        if parsed.scheme != 'https' or not parsed.netloc:
            raise ValueError('Use repository links or HTTPS evidence')
        return  # Offline presence check only; external content is not authenticated.
    path = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'Broken or outside-repository link: {reference}')
    if parsed.fragment and path.suffix == '.md':
        headings = re.findall(r'^#{1,6}\s+(.+)$', path.read_text(), re.M)
        if unquote(parsed.fragment) not in {slug(h) for h in headings}:
            raise ValueError(f'Broken heading anchor: {reference}')


def tree(path):
    module = group = None
    leaves = {}
    roots = 0
    for line in path.read_text().splitlines():
        heading = re.fullmatch(r'(#+) (.+)', line)
        if heading:
            level, label = len(heading[1]), heading[2]
            if level > 3:
                raise ValueError('ROADMAP permits only project/module/feature headings')
            if level == 1:
                roots += 1
                module = group = None
            elif level == 2:
                module, group = label, None
            else:
                if not module:
                    raise ValueError('Feature has no module')
                group = label
        leaf = re.fullmatch(r'- \[([ x])\] (.+)', line)
        if leaf:
            if not module or not group:
                raise ValueError('Only final feature items may have checkboxes')
            label = re.sub(r'（[^）]*）$', '', leaf[2])
            key = f'{module}/{group}/{label}'
            if key in leaves:
                raise ValueError(f'Duplicate leaf: {key}')
            leaves[key] = leaf[1] == 'x'
        elif re.search(r'\[[ xX]\]', line) or line.startswith('- '):
            raise ValueError('Use unindented, final-level checkboxes only')
    if roots != 1 or not leaves:
        raise ValueError('ROADMAP needs one project root and feature leaves')
    return leaves


def checkable(feature):
    version = feature['versions']['candidate']
    if not version or feature['blockers'] or feature['reopened']:
        raise ValueError(f"{feature['id']}: unresolved blockers or reopened defect")
    for key, status in [('review', 'passed'), ('acceptance', 'passed'), ('delivery', 'delivered')]:
        entry = feature[key]
        if entry['status'] != status or entry['version'] != version or not entry['evidence']:
            raise ValueError(f"{feature['id']}: {key} is not confirmed for candidate version")
    acceptance = feature['acceptance']
    if any(not acceptance.get(k) for k in ('environment', 'data', 'actor', 'date', 'steps', 'observed')):
        raise ValueError('Actual user-flow evidence needs environment/data/actor/date/steps/observations')
    if acceptance.get('kind') != 'actual-user-flow':
        raise ValueError('CI, mocks and source review cannot satisfy actual acceptance')
    design = feature.get('design', {})
    if design.get('required') and (design.get('status') != 'passed' or design.get('version') != version or not design.get('visual_evidence')):
        raise ValueError('UI feature needs actual visual verification for the candidate')
    target = feature['target']
    if target != 'local' and feature['versions'][target] != version:
        raise ValueError('Installed/online version does not match accepted candidate')


def historical_allowances(allowances, previous_leaves):
    if any(not previous_leaves.get(leaf, False) for leaf in allowances):
        raise ValueError('Historical allowance can cover only a previously checked leaf')


def validate(root, require=None, baseline=None):
    root = Path(root).resolve()
    config = json.loads((root / 'roadmap/_checks.json').read_text())
    if config.get('mode') == 'stable-products':
        return validate_stable(root, config, require)
    roadmap = root / config['roadmap']
    leaves = tree(roadmap)
    if baseline:
        previous = subprocess.run(['git', '-C', str(root), 'show', f'{baseline}:{config["roadmap"]}'], capture_output=True, text=True, check=True).stdout
        # Parse the same tree without creating or executing a linked artifact.
        class PriorTree:
            def read_text(self):
                return previous
        historical_allowances(config.get('legacy_checked', {}), tree(PriorTree()))
    records, covered = {}, {}
    files = [root / 'docs/PRODUCT_WORKFLOW.md', roadmap, root / 'roadmap/README.md', root / 'roadmap/_template.md']
    for path in sorted((root / config['features']).glob('*.md')):
        if path.name.startswith('_') or path.name == 'README.md':
            continue
        text = path.read_text()
        blocks = re.findall(r'```product-feature\n(.*?)\n```', text, re.S)
        if len(blocks) != 1:
            raise ValueError(f'{path.name}: need one product-feature block')
        feature = json.loads(blocks[0])
        required = {'id', 'leaves', 'owner', 'sources', 'plan', 'versions', 'target', 'review', 'acceptance', 'delivery', 'blockers', 'reopened'}
        if not required <= feature.keys() or not feature['owner'] or not feature['sources'] or not feature['leaves']:
            raise ValueError(f'{path.name}: incomplete feature contract')
        if feature['id'] in records or path.stem != feature['id']:
            raise ValueError('Feature IDs must be unique and match filenames')
        if feature['target'] not in ('local', 'installed', 'online') or type(feature['reopened']) is not bool or not isinstance(feature['blockers'], list):
            raise ValueError('Invalid delivery target or defect state')
        if set(feature['versions']) != {'main', 'candidate', 'installed', 'online'}:
            raise ValueError('Separate main/candidate/installed/online versions')
        for version in feature['versions'].values():
            if version is not None and not SHA.fullmatch(version):
                raise ValueError('Use exact source SHA or null for unknown versions')
        for reference in [*feature['sources'], feature['plan']]:
            local_link(root, path, reference)
        for key, statuses in [('review', {'pending', 'passed', 'failed'}), ('acceptance', {'blocked', 'passed', 'failed'}), ('delivery', {'not-released', 'delivered', 'failed'})]:
            entry = feature[key]
            if entry.get('status') not in statuses or 'version' not in entry or 'evidence' not in entry:
                raise ValueError(f'Invalid {key} evidence fields')
            if entry['version'] is not None and not SHA.fullmatch(entry['version']):
                raise ValueError('Evidence needs an exact source SHA')
            if entry['evidence']:
                local_link(root, path, entry['evidence'])
            if entry['status'] in {'passed', 'delivered'} and (not entry['version'] or not entry['evidence']):
                raise ValueError(f'{key} claims pass without version and evidence')
        design = feature.get('design')
        if not isinstance(design, dict) or type(design.get('required')) is not bool:
            raise ValueError('Declare whether product design and visual verification are required')
        if design.get('status') not in {'pending', 'partial', 'passed'}:
            raise ValueError('Invalid product design status')
        for key in ('reference', 'visual_evidence'):
            if design.get(key):
                local_link(root, path, design[key])
        if design.get('status') == 'passed' and (not design.get('visual_evidence') or design.get('version') != feature['versions']['candidate']):
            raise ValueError('Design pass needs candidate visual evidence')
        for leaf in feature['leaves']:
            if leaf not in leaves or leaf in covered:
                raise ValueError(f'Unknown or multiply owned leaf: {leaf}')
            covered[leaf] = feature
            if leaves[leaf]:
                checkable(feature)
        records[feature['id']] = feature
        files.append(path)
    for leaf, proof in config.get('legacy_checked', {}).items():
        if leaf not in leaves or not proof.get('scope'):
            raise ValueError('Historical allowance must name an existing scoped leaf')
        local_link(root, root / 'baseline', proof['evidence'])
    for leaf, checked in leaves.items():
        if checked and leaf not in covered and leaf not in config.get('legacy_checked', {}):
            raise ValueError(f'Checked leaf has no actual acceptance: {leaf}')
    for path in files:
        # Template placeholder links are plain text, not fabricated Markdown links.
        for reference in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
            local_link(root, path, reference)
    if require:
        if require not in records:
            raise ValueError(f'Unknown feature: {require}')
        checkable(records[require])
    return len(leaves), len(records)


def requirement_trace(text, requirements, legal_leaves):
    """Scope trace only: a mapped requirement is never acceptance evidence."""
    section = text.split('## 原需求逐项追踪\n', 1)
    if len(section) != 2:
        raise ValueError('Missing original requirement trace')
    section = section[1].split('## 完整需求与长期范围', 1)[0]
    records = {}
    for line in section.splitlines():
        if not line.startswith('| R'):
            continue
        columns = [part.strip() for part in line.strip('|').split('|')]
        if len(columns) != 6:
            raise ValueError('Requirement trace needs six columns')
        identifier, original, status, leaves, evidence, boundary = columns
        if not re.fullmatch(r'R\d{3}', identifier) or identifier in records:
            raise ValueError('Requirement trace IDs must be unique')
        index = int(identifier[1:]) - 1
        if not 0 <= index < len(requirements) or original != requirements[index]:
            raise ValueError('Requirement trace must retain stable ID and original wording')
        if status not in {'已映射', '部分覆盖', '未映射', '待决'} or not boundary:
            raise ValueError('Requirement trace needs explicit scope and boundary')
        if leaves == '—':
            if status not in {'未映射', '待决'}:
                raise ValueError('Mapped scope must cite a product leaf')
        else:
            refs = leaves.split(', ')
            if (status == '未映射' or len(refs) != len(set(refs)) or
                    any(not re.fullmatch(r'#\d+', ref) or int(ref[1:]) not in legal_leaves for ref in refs)):
                raise ValueError('Requirement trace contains an invalid product leaf')
        sources = re.findall(r'\[#(\d+)\]\(https://github.com/douyixuan/didadi/issues/(\d+)\)', evidence)
        if not sources or any(a != b or int(a) not in legal_leaves for a, b in sources):
            raise ValueError('Requirement trace needs valid issue scope evidence')
        records[identifier] = status
    if set(records) != {f'R{i:03}' for i in range(1, len(requirements)+1)}:
        raise ValueError('Every original requirement needs exactly one trace record')
    return records


def validate_stable(root, config, require=None):
    path = root / config['roadmap']
    leaves = tree(path)
    for line in path.read_text().splitlines():
        if line and not (re.fullmatch(r'#{1,3} .+', line) or re.fullmatch(r'- \[([ x])\] .+', line) or line == '[需求细化、长期范围与验收](roadmap/README.md)'):
            raise ValueError('Root roadmap must contain only the short feature tree and detail link')
    numbers = {}
    for key, checked in leaves.items():
        match = re.search(r'\[([^]]+)\]\(https://github.com/douyixuan/didadi/issues/(\d+)\)$', key)
        if not match or int(match[2]) in numbers:
            raise ValueError('Stable product leaf needs one unique issue')
        numbers[int(match[2])] = checked
    if set(numbers) != set(range(69, 85)):
        raise ValueError('Exactly issues 69 through 84 are required')
    inventory = (root / 'roadmap/README.md').read_text().split('## 完整需求与长期范围', 1)[1]
    labels = re.findall(r'^- (.+)$', inventory, re.M)
    if len(config['requirements']) != 99 or sorted(labels) != sorted(config['requirements']):
        raise ValueError('Original 99 requirements must be retained exactly')
    requirement_trace((root / 'roadmap/README.md').read_text(), config['requirements'], set(numbers))
    for file, digest in config['historical_files'].items():
        if hashlib.sha256((root / file).read_bytes()).hexdigest() != digest:
            raise ValueError('Historical narrow evidence changed; review archive migration explicitly')
    for number, checked in numbers.items():
        if not checked:
            continue
        proof = config.get('accepted', {}).get(str(number))
        if number != 69 or not proof:
            raise ValueError('No verified stable product acceptance for this checked issue')
        if proof.get('kind') != 'actual-user-flow' or not proof.get('scope'):
            raise ValueError('Real user-flow acceptance and bounded scope required')
        for key in ('version', 'main'):
            if not SHA.fullmatch(proof.get(key, '')):
                raise ValueError('Exact tested and delivered versions required')
        for key in ('evidence', 'record', 'real_ci', 'main_ci'):
            local_link(root, root / 'baseline', proof.get(key))
        text = (root / proof['evidence'].split('#')[0]).read_text()
        if not all(proof[key] in text for key in ('version', 'main', 'record', 'real_ci', 'main_ci')):
            raise ValueError('Acceptance fields must match the retained real record')
    archived = root/'artifact/032-requirements-completion/historical-20261022.md'
    for file in (path, root/'roadmap/README.md', root/'roadmap/_template.md', root/'docs/PRODUCT_WORKFLOW.md', root/'docs/MVP_ACCEPTANCE.md', archived, *sorted((root/'roadmap').glob('*.md'))):
        for ref in re.findall(r'\[[^\]]*\]\(([^)]+)\)', file.read_text()):
            local_link(root, file, ref)
        if file.name.startswith('_'):  # Template fields are examples, not acceptance records.
            continue
        for block in re.findall(r'```product-feature\n(.*?)\n```', file.read_text(), re.S):
            def evidence_links(value):
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key in {'evidence', 'visual_evidence', 'reference', 'plan'} and item:
                            local_link(root, file, item)
                        elif key == 'sources':
                            for ref in item: local_link(root, file, ref)
                        else: evidence_links(item)
                elif isinstance(value, list):
                    for item in value: evidence_links(item)
            evidence_links(json.loads(block))
    if require:
        raise ValueError('Historical feature metadata cannot certify a stable product leaf')
    return len(numbers), len(config.get('accepted', {}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--require-checkable')
    parser.add_argument('--baseline-ref', help='Offline Git ref for historical checked-leaf comparison')
    args = parser.parse_args()
    try:
        leaves, records = validate(args.root, args.require_checkable, args.baseline_ref)
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'ROADMAP gate failed: {error}\n')
    print(f'ROADMAP structure/evidence references valid: {leaves} leaves, {records} detailed features. Not a real acceptance result.')


if __name__ == '__main__':
    main()
