"""Run guardian practice for two already logged-in, independently configured accounts."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--teacher-profile',required=True)
    parser.add_argument('--pupil-profile',required=True)
    parser.add_argument('--teacher-name',required=True)
    parser.add_argument('--pupil-name',required=True)
    parser.add_argument('--max-runs',type=int,default=5,choices=range(1,6))
    args=parser.parse_args()
    from script import Script
    from tasks.BeginnerQuest.mentorship import MentorshipRunner
    teacher=Script(args.teacher_profile);pupil=Script(args.pupil_profile)
    teacher.device.desktop_mark_logged_in();pupil.device.desktop_mark_logged_in()
    runner=MentorshipRunner(teacher.config,teacher.device,pupil.config,pupil.device,
                            args.teacher_name,args.pupil_name)
    print(runner.run_guardian(args.max_runs),flush=True)


if __name__=='__main__':main()
