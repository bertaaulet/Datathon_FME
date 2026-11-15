#!/bin/bash
set -eu
target=/home/arduino/Datathon_FME/projecte
staged=/home/arduino/Datathon_FME_pistes_20261115/projecte
stamp=$(date +%Y%m%d-%H%M%S)
backup=/home/arduino/Datathon_FME/projecte-backup-pistes-$stamp
failed=/home/arduino/Datathon_FME/projecte-failed-pistes-$stamp
test -d "$target" && test -d "$staged"
test "$(readlink -f "$target")" = "$target"
test "$(readlink -f "$staged")" = "$staged"
test ! -e "$backup" && test ! -e "$failed"
python3 - "$staged" <<'PY'
import json,pathlib,sqlite3,sys
root=pathlib.Path(sys.argv[1])
with sqlite3.connect((root/'data/tutor.db').as_uri()+'?mode=ro',uri=True) as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    n=db.execute('SELECT count(*) FROM problems WHERE eligible=1').fetchone()[0]
    assert n==616,n
    assert db.execute("SELECT count(*) FROM hints h JOIN problems p ON p.id=h.problem_id WHERE h.source='agent' AND p.eligible=1").fetchone()[0]==1232
    assert db.execute("SELECT count(*) FROM hints h JOIN problems p ON p.id=h.problem_id WHERE h.source='agent' AND p.eligible=1 AND h.convinced IS NULL").fetchone()[0]==0
    assert db.execute("SELECT value FROM meta WHERE key='kangaroo_lang'").fetchone()[0]=='cat'
text=(root/'config.env').read_text()
assert 'KANGAROO_LANG=cat' in text and 'HINTGEN=off' in text
print('Base verificada: 616 problemes, 1232 pistes mesurades, cat, HINTGEN=off.')
PY
if [ "${1:-}" = --check ]; then exit 0; fi
test "$(id -u)" -eq 0 || { echo 'Executa aquest script amb sudo.'; exit 1; }
python3 - "$staged" <<'PY'
import os,pathlib,signal,sys
root=pathlib.Path(sys.argv[1])
pid_file=root/'data/qa-server.pid'
if pid_file.exists():
    pid=int(pid_file.read_text().strip())
    process=pathlib.Path('/proc')/str(pid)
    try:
        args=(process/'cmdline').read_bytes().split(b'\0')
        if (process/'cwd').resolve()==root and b'app/server.py' in args and b'18090' in args:
            os.kill(pid,signal.SIGTERM)
    except (FileNotFoundError,ProcessLookupError):
        pass
PY
systemctl stop math-tutor
if ! mv "$target" "$backup"; then
    systemctl start math-tutor
    exit 1
fi
if ! mv "$staged" "$target"; then
    mv "$backup" "$target"
    systemctl start math-tutor
    exit 1
fi
systemctl start math-tutor || true
sleep 3
if ! systemctl is-active --quiet math-tutor || ! python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8090/api/state",timeout=5).read()'; then
    systemctl stop math-tutor || true
    mv "$target" "$failed"
    mv "$backup" "$target"
    systemctl start math-tutor
    echo "Ha fallat l'arrencada; s'ha restaurat la còpia anterior. Revisió: $failed"
    exit 1
fi
echo "Tutor actualitzat i actiu. Còpia completa anterior: $backup"
