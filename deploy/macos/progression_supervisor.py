"""Wait through a locked macOS session, then launch one OAS progression worker."""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def session_locked():
    result=subprocess.run(['ioreg','-n','Root','-d1'],capture_output=True,text=True,timeout=10,check=True)
    return 'CGSSessionScreenIsLocked"=Yes' in result.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account',required=True)
    parser.add_argument('--chapter',type=int,required=True)
    parser.add_argument('--target',type=int,default=40)
    parser.add_argument('--min-stamina',type=int,default=200)
    parser.add_argument('--wine',type=Path,required=True)
    parser.add_argument('--python',type=Path,required=True)
    parser.add_argument('--bottle',default='yys')
    parser.add_argument('--wait-hours',type=int,default=8)
    parser.add_argument('--use-current-team',action='store_true',help='Use a current formation already verified by successful battles')
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[2]
    if not args.account.replace('_','').isalnum() or not (repo/'config'/f'{args.account}.json').is_file():
        parser.error('Existing account configuration required')
    if not 1<=args.chapter<=28 or not 1<=args.target<=60 or not 1<=args.wait_hours<=24 or args.min_stamina<0:
        parser.error('Invalid progression limits')
    root=repo/'log'/'beginner_quest'/args.account
    root.mkdir(parents=True,exist_ok=True)
    def state(status,**extra):
        (root/'supervisor.json').write_text(json.dumps({'status':status,'target':args.target,**extra}),encoding='utf-8')
    deadline=time.monotonic()+args.wait_hours*3600
    while session_locked():
        state('waiting_for_unlock')
        if time.monotonic()>=deadline:
            state('unlock_wait_expired');return
        time.sleep(10)
    # One worker only. Unexpected failure is not an instruction to restart
    # spending. The existing controller enforces loss and UI verification gates.
    source=('from script import Script\n'
            'from tasks.BeginnerQuest.continuous import ContinuousProgression\n'
            f's=Script({args.account!r})\n'
            's.device.desktop_mark_logged_in()\n'
            # This account has already won training and exploration with its
            # current team. No borrowing or lineup changes are requested here.
            f's.config.beginner_quest.quest_options.require_verified_team={not args.use_current_team!r}\n'
            f'print(ContinuousProgression(s.config,s.device).run({args.chapter},target={args.target},min_stamina={args.min_stamina}),flush=True)\n')
    command=[str(args.wine),'--bottle',args.bottle,'--wait','--workdir',str(repo),
             str(args.python),'-u','-c',source]
    state('running')
    with (root/'continuous-worker.log').open('a',encoding='utf-8') as output:
        env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
        result=subprocess.run(command,cwd=repo,env=env,stdout=output,stderr=subprocess.STDOUT)
    state('worker_finished',exit_code=result.returncode)


if __name__=='__main__':
    main()
