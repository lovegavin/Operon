"""Build round-4 complex FASTAs from ProteinMPNN designs on the free-d1 scaffold."""
import json
from pathlib import Path

ROOT = Path(r"D:\OperonTest517rc7\workspace\design_loop\round4")
PARENT = Path(r"D:\OperonTest517rc7\workspace\design_loop\round3\complex_free_d1.pdb")

THREE = {
    'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C', 'GLN': 'Q', 'GLU': 'E',
    'GLY': 'G', 'HIS': 'H', 'ILE': 'I', 'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F',
    'PRO': 'P', 'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V',
}


def chains(path):
    seq = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.startswith('ATOM') and line[12:16].strip() == 'CA':
            chain = line[21]
            resname = line[17:20].strip()
            resseq = line[22:26].strip()
            seq.setdefault(chain, {})[int(resseq)] = THREE.get(resname, 'X')
    return {c: ''.join(v[k] for k in sorted(v)) for c, v in seq.items()}


def designs(fasta):
    records, current = [], None
    for line in Path(fasta).read_text(encoding='utf-8').splitlines():
        if line.startswith('>'):
            current = {'header': line[1:], 'seq': ''}
            records.append(current)
        elif current is not None:
            current['seq'] += line.strip()
    return records


parent = chains(PARENT)
binder_len = len(parent['A'])
target_len = len(parent['B'])
parent_binder = parent['A']

records = designs(ROOT / 'designs_round4_free.fa')
samples = [r for r in records if 'sample=' in r['header'] and r['seq'] != parent_binder]
out = ROOT / 'complexes'
out.mkdir(parents=True, exist_ok=True)

summary = []
for index, record in enumerate(samples, start=1):
    seq = record['seq']
    assert len(seq) == binder_len, (index, len(seq))
    path = out / f'design_{index}.fa'
    path.write_text(f'>binder\n{seq}\n>target\n{parent["B"]}\n', encoding='utf-8')
    summary.append({
        'design': index,
        'header': record['header'],
        'mutations': sum(1 for a, b in zip(seq, parent_binder) if a != b),
    })

(ROOT / 'round4_designs.json').write_text(json.dumps({
    'binder_len': binder_len,
    'target_len': target_len,
    'designs': summary,
}, indent=2), encoding='utf-8')

print(json.dumps({'binder_len': binder_len, 'target_len': target_len,
                  'count': len(summary),
                  'mutations': [d['mutations'] for d in summary]}))
