#!/usr/bin/env python3
"""Report clean-install and optional live API/SDK validation without mutating env."""
import argparse,json,subprocess,sys
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(); p.add_argument("--api-url",default="http://127.0.0.1:8000"); p.add_argument("--output",type=Path,default=ROOT/"logs"/"deployment_validation.json"); a=p.parse_args()
 result={"requirements_file":(ROOT/"requirements.txt").exists(),"clean_install":"not_run","live_api":"unavailable","sdk":"unavailable"}
 try:
  subprocess.run([sys.executable,"-m","pip","check"],cwd=ROOT,check=True,capture_output=True,text=True); result["environment"]="pip_check_pass"
 except Exception: result["environment"]="pip_check_failed_or_unavailable"
 try:
  with urlopen(a.api_url+"/health",timeout=2) as r: result["live_api"]="pass" if r.status==200 else "fail"
  from src.ralg_client import RALGClient
  result["sdk"]="pass" if RALGClient(a.api_url).health().get("status")=="ok" else "fail"
 except Exception as exc:
  result["live_api"]="unavailable"; result["sdk"]="unavailable"
 result["clean_install_note"]="Not executed automatically; run pip install --requirement requirements.txt in a disposable environment."
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2),encoding="utf-8"); print(json.dumps(result,indent=2))
if __name__=="__main__": main()
