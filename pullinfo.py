import requests
import datetime
import pytz

import os.path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2 import service_account

from git import Repo
import yaml
import re
import matplotlib
import matplotlib.pyplot as plt
from collections import defaultdict
import numpy as np
import json

with open('secrets/secrets.json') as secrets_file:
    tokens = json.load(secrets_file)

with open("dakilaledesma.github.io/_config.yml") as f:
    config = yaml.safe_load(f)

version = str([int(a) for a in str(config["version"]).split('.')][-1])


def new_day():
    current = datetime.datetime.today()
    est = pytz.timezone('US/Eastern')
    current_date = str(current.astimezone(est).date())
    if not os.path.exists("date.txt"):
        date_file = open("date.txt", 'w')
        date_file.write(current_date)
        date_file.close()
        return True

    date_file = open("date.txt")
    date_line = date_file.read()
    date_file.close()
    if current_date != date_line:
        date_file = open("date.txt", 'w')
        date_file.write(current_date)
        date_file.close()
        return True
    else:
        return False


def generate_heatmap(data):
    dates = [datetime.datetime.today() - datetime.timedelta(days=i) for i in range(364)]
    while True:
        if dates[-1].weekday() != 6:
            dates.append(dates[-1] - datetime.timedelta(days=1))
        else:
            break

    while True:
        if dates[0].weekday() != 5:
            dates.insert(0, dates[0] + datetime.timedelta(days=1))
        else:
            break

    dates = [d.date() for d in dates]
    contrib_dict = defaultdict(int)
    for ts in data:
        date = to_eastern(datetime.datetime.fromtimestamp(ts)).date()
        start_date = datetime.datetime.strptime('19062022', "%d%m%Y").date()
        if date in dates and start_date < date:
            contrib_dict[date] += 1

    mean_array = [v for v in list(contrib_dict.values()) if v != 0]
    mean = sum(mean_array) / len(mean_array)

    for d in dates:
        if datetime.datetime.today().date() < d:
            contrib_dict[d] = -1
        if d not in contrib_dict.keys():
            contrib_dict[d] = -1

    dates = sorted(dates)
    contrib_dict = dict(sorted(contrib_dict.items()))

    data_array = np.array(list(contrib_dict.values())).reshape((-1, 7))
    dates = np.array(dates).reshape((-1, 7))
    x_ticks = []
    month = dates[0][0].strftime("%b")
    for week in dates:
        month_change = False
        for day in week:
            if day.strftime("%b") != month:
                month_change = True
                month = day.strftime("%b")

        if month_change:
            x_ticks.append(month)
        else:
            x_ticks.append("")

    data_array = np.flipud(data_array.T)
    ax2_labels = ["", "", "", "", "", "", ""]
    for idx, date in enumerate(dates[-1]):
        if date == datetime.date.today():
            ax2_labels[(idx * -1) - 1] = "←"

    # https://stackoverflow.com/questions/69050234/center-specified-tick-labels-for-matplotlibs-pcolomesh-at-the-boxes
    x = np.arange(data_array.shape[1])
    y = np.arange(7)
    c = data_array
    c_base = np.full(c.shape, 3)
    plt.rcParams.update({'font.size': 13,
                         "xtick.color": "dimgray",
                         "ytick.color": "dimgray"})
    fig, ax = plt.subplots(figsize=(14, 2))

    # https://stackoverflow.com/questions/14908576/how-to-remove-frame-from-matplotlib-pyplot-figure-vs-matplotlib-figure-frame
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)

    # https://stackoverflow.com/questions/29988241/python-hide-ticks-but-show-tick-labels
    ax.tick_params(axis=u'both', which=u'both', length=0)
    ax.set_yticks(y)
    ax.set_yticklabels(["", "Fri", "", "Wed", "", "Mon", ""])
    ax.set_xticks(x)
    ax.set_xticklabels(x_ticks)
    ax.xaxis.tick_top()

    ax2 = ax.twinx()
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['bottom'].set_visible(False)
    ax2.spines['left'].set_visible(False)

    ax2.tick_params(axis=u'both', which=u'both', length=0)
    ax2.set_yticks(y)
    ax2.set_yticklabels(ax2_labels)
    ax2.set_xticks(x)
    ax2.set_xticklabels(x_ticks)
    ax2.xaxis.tick_top()

    heat_cmap = matplotlib.cm.get_cmap("Greens").copy()
    heat_cmap.set_under('w')
    plt.pcolormesh(x, y, c, cmap=heat_cmap, edgecolors='w', linewidths=1, vmax=mean * 1.5)
    plt.savefig("dakilaledesma.github.io/public/heatmap.png", bbox_inches='tight', pad_inches=0)


def gith():
    owner = "dakilaledesma"
    query_url = f"https://api.github.com/users/{owner}/events?page=1"
    headers = {
        'Authorization': f'token {tokens["gith1"]}',
    }
    res = requests.get(query_url, headers=headers)
    r = res.json()
    while 'next' in res.links.keys():
        res = requests.get(res.links['next']['url'], headers=headers)
        r.extend(res.json())

    '''
    dict_keys(['id', 'type', 'actor', 'repo', 'payload', 'public', 'created_at'])
    '''
    message_list = []
    for result in r:
        mtime = result["created_at"]
        dtime = datetime.datetime.strptime(mtime, "%Y-%m-%dT%H:%M:%SZ")

        repo = result["repo"]["name"]
        if result["type"] == "PushEvent":
            if len(result["payload"]["commits"]) == 0:
                continue
            else:
                for idx, c in enumerate(result["payload"]["commits"]):
                    message = c["message"]

                    if "no-track" in message:
                        continue

                    m = f"GitHub commit to <b>{repo}</b>||{message}"
                   
                    if idx != 0:
                        try:
                            message_list.append(
                                {"time": dtime, "message": m, "via": "GitHub", "id": f'github_{result["id"]}_{idx}', "mtime": mtime,
                                "version": version})
                        except Exception as e:
                             print(e)
                    else:
                        try:
                            message_list.append(
                                {"time": dtime, "message": m, "via": "GitHub", "id": f'github_{result["id"]}', "mtime": mtime,
                                "version": version})
                        except Exception as e:
                            print(e)
            continue


        if result["type"] == "CreateEvent":
            m = f"GitHub repository created||{repo}"
        elif result["type"] == "PublicEvent":
            m = f"GitHub repository changed to public||{repo}"
        elif result["type"] == "PrivateEvent":
            m = f"GitHub repository changed to private||{repo}"
        elif result["type"] == "DeleteEvent":
            m = f"GitHub repository deleted||{repo}"
        else:
            continue

        try:
            message_list.append(
                {"time": dtime, "message": m, "via": "GitHub", "id": f'github_{result["id"]}', "mtime": mtime,
                 "version": version})
        except UnboundLocalError:
            pass

    return message_list


def section_names(headers):
    sections_url = f"https://api.todoist.com/rest/v2/sections?project_id={tokens['todoist_projid']}"
    sc = requests.get(sections_url, headers=headers)
    s = sc.json()
    section_dict = {}
    for section in s:
        section_dict[section["id"]] = section["name"]

    return section_dict


def todoist_open():
    message_list = []
    headers = {
        'Authorization': f'Bearer {tokens["todoist1"]}',
    }
    section_dict = section_names(headers)

    query_url = f"https://api.todoist.com/rest/v2/tasks?project_id={tokens['todoist_projid']}"
    res = requests.get(query_url, headers=headers)
    r = res.json()
    for result in r:
        query_url = f"https://api.todoist.com/sync/v9/items/get?item_id={result['id']}"
        res = requests.get(query_url, headers=headers)
        item = res.json()["item"]
        description = item["description"]
        section_id = item["section_id"]
        mtime = result["created_at"]
        dtime = datetime.datetime.strptime(mtime, "%Y-%m-%dT%H:%M:%S.%fZ")

        if result["priority"] != 1:
            prio_text = '<span style="color: #ba0202;">Priority</span>'
        else:
            prio_text = 'Open'

        if len(description) != 0:
            desc_text = f'<br><span class="desc">{description}</span>'
        else:
            desc_text = ''

        if all([section_id != 0, section_id is not None]):
            sect_id_text = f' under <b>{section_dict[section_id]}</b>'
        else:
            sect_id_text = ''

        m = f"{prio_text} Todoist task{sect_id_text}||{result['content']}{desc_text}"
        message_list.append(
            {"time": dtime, "message": m, "via": "Todoist", "id": f'todoist_{result["id"]}', "mtime": mtime,
             "version": version, "priority": result["priority"]})
    return message_list


def todoist_finished(event_dict):
    message_list = []

    headers = {
        'Authorization': f'Bearer {tokens["todoist1"]}',
    }
    section_dict = section_names(headers)
    query_url = f"https://api.todoist.com/sync/v9/completed/get_all?project_id={tokens['todoist_projid']}"
    res = requests.get(query_url, headers=headers)
    r = res.json()["items"]
    for result in r:
        if f"todoist_{result['id']}" not in event_dict.keys():
            query_url = f"https://api.todoist.com/sync/v9/items/get?item_id={result['task_id']}"
            res = requests.get(query_url, headers=headers)
            try:
                item = res.json()["item"]
            except KeyError:
                description = ''
                section_id = None
            else:
                description = item["description"]
                section_id = item["section_id"]

            if len(description) != 0:
                desc_text = f'<br><span class="desc">{description}</span>'
            else:
                desc_text = ''

            if section_id is not None:
                sect_id_text = f' under <b>{section_dict[section_id]}</b>'
            else:
                sect_id_text = ''

            m = f"Closed Todoist task{sect_id_text}||{result['content']}{desc_text}"
        else:
            m = event_dict[f"todoist_{result['id']}"][1]

        # Thanks to Jon Betts on https://stackoverflow.com/questions/23394608/python-regex-fails-to-identify-markdown-links
        name_regex = "[^]]+"
        url_regex = "http[s]?://[^)]+"
        link_regex = '\[({0})]\(\s*({1})\s*\)'.format(name_regex, url_regex)

        # Thanks to NPE & kubanczyk on https://stackoverflow.com/questions/7191209/re-sub-replace-with-matched-content
        m = re.sub(link_regex, r'<a href="\2">\1</a>', m)

        mtime = result["completed_at"]
        dtime = datetime.datetime.strptime(mtime, "%Y-%m-%dT%H:%M:%S.%fZ")
        message_list.append(
            {"time": dtime, "message": m, "via": "Todoist", "id": f'todoist_{result["task_id"]}', "mtime": mtime,
             "version": version})

    return message_list


def to_eastern(_time):
    return _time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("US/Eastern"))


def get_logo(via, flavor_text=''):
    if via == "GitHub":
        _logo = '<img src="https://www.google.com/s2/favicons?domain=www.github.com" height="11" style="display: inline; margin: 0rem">'
    elif all([via == "Todoist", "BCBS" in flavor_text]):
        _logo = '<img src="https://www.google.com/s2/favicons?domain=www.bcbst-medicare.com" height="11" style="display: inline; margin: 0rem">'
    elif via == "Todoist":
        _logo = '<img src="https://www.google.com/s2/favicons?domain=www.todoist.com" height="11" style="display: inline; margin: 0rem">'
    else:
        return

    return _logo


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

ss_id = tokens["sheet_id"]
SAMPLE_RANGE_NAME = 'A:D'

creds = service_account.Credentials.from_service_account_file(
    tokens["g_token_file"], scopes=SCOPES)

service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

event_data = sheet.values().get(spreadsheetId=ss_id, range="A:E").execute()["values"]
event_dict = {v[0]: v[1:5] for v in event_data[1:]}

github_events = gith()
td_open = todoist_open()
td_closed = todoist_finished(event_dict)

finished = github_events + td_closed

not_in_sheet_evs = []
for ev in finished:
    if ev["id"] not in event_dict.keys():
        not_in_sheet_evs.append([ev["id"], ev["via"], ev["message"], ev["mtime"], ev["version"]])

if len(not_in_sheet_evs) > 0:
    sheet.values().append(
        spreadsheetId=ss_id, range=f"A:E", valueInputOption="RAW",
        body={"values": not_in_sheet_evs}).execute()

finished = []
event_data = sheet.values().get(spreadsheetId=ss_id, range="A:E").execute()["values"]
event_dict = {v[0]: v[1:5] for v in event_data[1:]}
for k, v in event_dict.items():
    via = v[0]
    m = v[1]
    mtime = v[2]
    event_version = v[3]
    try:
        dtime = datetime.datetime.strptime(mtime, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        dtime = datetime.datetime.strptime(mtime, "%Y-%m-%dT%H:%M:%SZ")
    finished.append(
        {"time": dtime, "message": m, "via": via, "id": k, "mtime": mtime, "version": event_version})

td_open = sorted(td_open, key=lambda x: x["time"], reverse=False)
td_priority = []
td_open_t = []
for ev in td_open:
    if ev["priority"] != 1:
        td_priority.append(ev)
    else:
        td_open_t.append(ev)

td_open = td_priority + td_open_t
finished = sorted(finished, key=lambda x: x["time"], reverse=True)

markdown_string = """---
layout: post
title: Events
---
"""

markdown_string += '\n### In-progress Items\n'
ms = []
for f in td_open:
    time = str(to_eastern(f["time"]).strftime("%b %d, %Y %I:%M:%S%p"))
    message = f["message"].split("||")
    flavor_text = message[0]
    message = message[1]
    logo = get_logo(f["via"], flavor_text)
    if "BCBS" not in flavor_text:
        ms.append(f"""
            <span class="flavor">{logo} {flavor_text}</span><br>
            {message}<br>
            <span class="datet">{time}</span>
        """)
    else:
        ms.append(f"""
            <span class="flavor">{logo} {flavor_text}</span><br>
            Obfuscated: Industry/non-academia related work. Todoist ID {f["id"].replace("todoist_", '')}.<br>
            <span class="datet">{time}</span>
        """)

compile_ms = '\n<hr style="margin:0.42rem">\n'.join(ms)
markdown_string += f'''
<div class="message">
    {compile_ms}
</div>
'''

markdown_string += "\n### Completed Items\n"

non_commit = []
sifted = []
start_date = datetime.datetime.strptime('19062022', "%d%m%Y").date()
for f in finished:
    event_str = f'{f["version"]},{f["via"]},{f["message"]}'
    if all([(event_str not in non_commit or str(f["version"]) == '0'),
            start_date < f["time"].date(),
            "no-track" not in event_str,
            "dakilaledesma.github.io" not in event_str]):
        non_commit.append(event_str)
        sifted.append(f)

ms = []

ms_date_dict = defaultdict(list)
heatmap_data = []
for f in sifted:
    past_f = f
    time_eastern = to_eastern(f["time"])
    heatmap_data.append(time_eastern.timestamp())
    time = time_eastern.strftime("%b %d, %Y %I:%M:%S%p")
    message = f["message"].split("||")
    flavor_text = message[0]
    message = message[1]
    logo = get_logo(f["via"], flavor_text)

    if "BCBS" not in flavor_text:
        ms_date_dict[time_eastern.strftime("%A %b. %d, %Y")].append(f"""
            <span class="flavor">{logo} {flavor_text}</span><br>
            {message}<br>
            <span class="datet">{time}</span>
        """)
    else:
        ms_date_dict[time_eastern.strftime("%A %b. %d, %Y")].append(f"""
            <span class="flavor">{logo} {flavor_text}</span><br>
            Obfuscated: Industry/non-academia related work. Todoist ID 
            <a href="https://docs.google.com/spreadsheets/d/1UIy_M_aaMfCEhAZz9godjoRMCujdEmdT_NnzDaZF7dA/edit?usp=sharing">{f["id"].replace("todoist_", '')}</a>.<br>
            <span class="datet">{time}</span>
        """)


    # ms.append(f"""
    #     <span class="flavor">{logo} {flavor_text}</span><br>
    #     {message}<br>
    #     <span class="datet">{time}</span>
    # """)


'''<span style="font-weight: 400; font-size: 13px; margin-left: 0.3rem;">12 items</span>'''
for date, ms in ms_date_dict.items():
    len_items = len(ms)
    if len_items > 1:
        date_str = f'{date}<span class="dateitems">{len_items} items</span>'
    else:
        date_str = f'{date}<span class="dateitems">{len_items} item</span>'
    compile_ms = '\n<hr style="margin:0.42rem">\n'.join(ms)
    markdown_string += f'''
<h4 class="datems">{date_str}</h4>
<div class="message">
        {compile_ms}
</div>
    
    '''

generate_heatmap(heatmap_data)
contrib_string = '''---
layout: post
title: Contributions
---

### Contributions
<img style="width:100%;" src="/public/heatmap.png?{{ site.version }}" alt="Contributions calendar">
<span class="datet" style="font-size: 60%; text-align: right; display: block;">
Less
<span style="color: #f7fcf5;">■</span>
<span style="color: #c3e7bc;">■</span>
<span style="color: #67bd70;">■</span>
<span style="color: #11803d;">■</span>
<span style="color: #00441b;">■</span>
More<br>
Currently tracking <b>@replace_me</b> contributions</span>
'''.replace("@replace_me", str(len(heatmap_data)))

repo = Repo("dakilaledesma.github.io/")
repo.remotes.origin.pull()
event_file = open("dakilaledesma.github.io/_posts/2022-07-12-events.md")
event_str = event_file.read()
event_file.close()
if markdown_string != event_str or new_day():
    event_file_w = open("dakilaledesma.github.io/_posts/2022-07-12-events.md", 'w')
    event_file_w.write(markdown_string)
    event_file_w.close()

    contrib_file_w = open("dakilaledesma.github.io/_posts/2022-07-13-contributions.md", 'w')
    contrib_file_w.write(contrib_string)
    contrib_file_w.close()

    with open("dakilaledesma.github.io/_config.yml") as f:
        config = yaml.safe_load(f)

    version = [int(a) for a in str(config["version"]).split('.')]
    version[-1] += 1
    config["version"] = '.'.join([str(b) for b in version])

    with open("dakilaledesma.github.io/_config.yml", "w") as f:
        yaml.dump(config, f)

    repo.git.add(update=True)
    repo.index.commit("Automated machine user commit. Beep boop!")
    origin = repo.remote(name='origin')
    origin.push()
