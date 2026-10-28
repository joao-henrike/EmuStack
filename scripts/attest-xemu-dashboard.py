#!/usr/bin/env python3
"""Record an explicit user attestation tied to the exact Xbox HDD image hash.

This is a declaration by the operator, not an automated authenticity detector.
It never downloads, extracts, or modifies console system files.
"""
import argparse, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENV_ROOT=(ROOT/'data/environments/xemu').resolve()
ATTESTATION=ENV_ROOT/'bios/xemu-dashboard-attestation.json'

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hdd', required=True, type=Path, help='Path to the user-provided Xbox HDD image inside data/environments/xemu/{home,saves,bios}')
    p.add_argument('--confirm-original-microsoft-dashboard', action='store_true', help='Explicitly confirm you have reviewed the HDD and believe it contains the Microsoft retail dashboard you are entitled to use')
    args=p.parse_args()
    if not args.confirm_original_microsoft_dashboard:
        p.error('Refusing to attest without --confirm-original-microsoft-dashboard')
    hdd=args.hdd.expanduser()
    if hdd.is_symlink(): raise SystemExit('ERROR: HDD must be a regular file, not a symlink')
    hdd=hdd.resolve(strict=True)
    if not hdd.is_file(): raise SystemExit('ERROR: HDD must be a regular file, not a symlink')
    accepted=[]
    for folder,container in ((ENV_ROOT/'home','/home/emu'),(ENV_ROOT/'saves','/saves'),(ENV_ROOT/'bios','/bios')):
        try:
            rel=hdd.relative_to(folder.resolve())
            accepted.append((container+'/'+rel.as_posix()).replace('//','/'))
        except ValueError: pass
    if len(accepted)!=1: raise SystemExit('ERROR: HDD must be inside this environment’s home/, saves/, or bios/ directory; never attest a shared/external path')
    ATTESTATION.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    payload={"schema_version":1,"environment_id":"xemu","dashboard_type":"microsoft-retail","user_confirmed":True,
             "hdd_container_path":accepted[0],"hdd_sha256":sha256(hdd),"created_utc":datetime.now(timezone.utc).isoformat(),
             "attestation_type":"operator-declaration","verification_limit":"EmuStack binds this declaration to the HDD hash but does not inspect/identify the proprietary dashboard inside the HDD."}
    tmp=ATTESTATION.with_suffix('.json.partial')
    tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.chmod(tmp,0o600); tmp.replace(ATTESTATION); os.chmod(ATTESTATION,0o600)
    print(f'Wrote {ATTESTATION.relative_to(ROOT)}')
    print(f'HDD SHA-256: {payload["hdd_sha256"]}')
    print('IMPORTANT: this records your assertion; it is not cryptographic proof that the HDD contains Microsoft software.')
    return 0
if __name__=='__main__': raise SystemExit(main())
