"""Read only the countdown belonging to the requested party-list row."""
import re


def parse_countdown(text):
    text=text.replace(' ','').replace('小时','时').replace('分钟','分')
    match=re.fullmatch(r'(?:(\d+)时)?(?:(\d+)分)?(?:(\d+)秒)?',text)
    if match and any(v is not None for v in match.groups()):
        h,m,s=(int(v or 0) for v in match.groups())
        return h*3600+m*60+s
    match=re.fullmatch(r'(\d{1,2})[:：](\d{2})',text)
    if match and int(match[2])<60:return int(match[1])*60+int(match[2])
    return None


def row_cooldown(boxes, zone):
    rows=[b for b in boxes if b.score>=.7 and b.ocr_text.replace(' ','')==zone
          and 100<b.box[:,0].mean()<360 and 110<b.box[:,1].mean()<600]
    if len(rows)!=1:return None
    y=rows[0].box[:,1].mean()
    values=[parse_countdown(b.ocr_text) for b in boxes if b.score>=.7
            and 100<b.box[:,0].mean()<230 and y-45<b.box[:,1].mean()<y-5]
    values=[v for v in values if v is not None]
    return max(values) if values else None
