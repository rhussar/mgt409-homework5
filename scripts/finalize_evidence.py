"""Refresh reports from real MCP state and embed existing real board screenshots."""
import asyncio
import base64
import hashlib
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from audit import Auditor, atomic_json
from reports import export
from shop import Shop

async def main():
    session=json.loads((ROOT/'output/session.json').read_text())
    shop=Shop()
    async with shop.client:
        snapshot=await shop.call('list_tickets')
    audit=Auditor()
    export(snapshot,audit.events,session['session_id'],session['starting_cash'])
    figures=[]; images=[]
    for record in snapshot['tickets']:
        t=record['ticket']; path=ROOT/'output/screenshots'/f'resolved_{t["id"]}.jpg'
        if t['status']=='resolved' and path.exists():
            data=path.read_bytes()
            figures.append(f'<figure id="ticket{t["id"]}"><h2>Ticket {t["id"]}: '+html.escape(t['subject'])+'</h2><p>Actual React dashboard capture · resolved operational handling</p><img alt="React dashboard for resolved ticket '+str(t['id'])+'" src="data:image/jpeg;base64,'+base64.b64encode(data).decode()+'"></figure>')
            images.append({'ticket_id':t['id'],'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(data).hexdigest()})
        else:
            figures.append(f'<section><h2>Ticket {t["id"]}: '+html.escape(t['subject'])+'</h2><p>'+('Awaiting final screenshot.' if t['status']=='resolved' else 'Not yet resolved. Human approval is still required before completing this evidence.')+'</p></section>')
    complete=all(r['ticket']['status']=='resolved' for r in snapshot['tickets']) and len(images)==3
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Campus Customs Resolved Board Evidence</title><style>body{font:16px/1.6 system-ui;background:#f3f2eb;color:#183147;max-width:1300px;margin:35px auto;padding:0 22px}h1{font:42px Georgia}figure,section{margin:35px 0;padding:24px;background:white;border:1px solid #d8ded4;border-radius:9px}h2{font:28px Georgia}img{width:100%;height:auto;border:1px solid #dce0d9}nav a{margin-right:22px;color:#365d50}</style><h1>Campus Customs board evidence</h1><p>'+('All three operational tickets resolved. Screenshots below are real captures of the React board.' if complete else 'Evidence in progress. Pending payments or missing captures are identified below.')+'</p><nav>'+''.join(f'<a href="#ticket{r["ticket"]["id"]}">Ticket {r["ticket"]["id"]}</a>' for r in snapshot['tickets'])+'</nav>'+''.join(figures)+'</html>'
    (ROOT/'output/resolved_board.html').write_text(page)
    atomic_json(ROOT/'output/screenshot_manifest.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'complete':complete,'images':images})
    print('Reports refreshed. Screenshot evidence complete:',complete)

if __name__=='__main__':
    asyncio.run(main())
