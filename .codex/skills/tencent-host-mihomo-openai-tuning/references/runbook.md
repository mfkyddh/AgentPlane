# Tencent Host Mihomo OpenAI Tuning Runbook

Use this runbook when a Tencent Cloud host already has Mihomo, OpenAI-related traffic is slow, and the likely fix is to move the `GPT` selector to a better node.

## 1. Connect To The Host

Prefer the project alias:

```bash
ssh -F <repo-root>/secrets/ssh/config <host-alias>
```

If the current shell cannot read the project SSH config directly, follow the repository's verified SSH path and keep the Windows-host proxy in mind.

## 2. Confirm Mihomo Is In Path

```bash
sudo systemctl status mihomo --no-pager
ss -lntup | grep -E ':(7890|19090)\b'
resolvectl status | sed -n '1,120p'
getent ahosts api.openai.com
```

Signals:

- `198.18.x.x` answers mean fake-ip is active
- a `Meta` interface with default DNS route means Mihomo TUN owns the path

## 3. Read The Live Controller Settings

```bash
sudo grep -nE '^(mixed-port|external-controller|secret):' /etc/mihomo/config.yaml
sudo grep -nA3 '^profile:' /etc/mihomo/config.yaml
```

Do not trust remembered controller values across incidents.

## 4. Inspect The GPT Selector

```bash
python3 - <<'PY'
import json, urllib.request
secret = 'REPLACE_WITH_SECRET'
req = urllib.request.Request(
    'http://127.0.0.1:19090/proxies/GPT',
    headers={'Authorization': f'Bearer {secret}'},
)
with urllib.request.urlopen(req, timeout=5) as r:
    data = json.load(r)
print('now =', data.get('now'))
for i, name in enumerate(data.get('all', []), 1):
    print(f'{i}. {name}')
PY
```

Replace the controller URL if the config says otherwise.

## 5. Benchmark Candidate Nodes

Use Mihomo's delay API to build a shortlist, then validate with real requests.

```bash
python3 - <<'PY'
import json, urllib.parse, urllib.request
secret = 'REPLACE_WITH_SECRET'
base = 'http://127.0.0.1:19090'
headers = {'Authorization': f'Bearer {secret}'}
targets = [
    'Lv2|日本3',
    'Lv1|日本2',
    'Lv1|台湾2|V2Ray|流媒体',
    'Lv2|新加坡5',
]
for name in targets:
    qname = urllib.parse.quote(name, safe='')
    req = urllib.request.Request(
        f'{base}/proxies/{qname}/delay?timeout=8000&url=https://api.openai.com',
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=12) as r:
        print(name, json.load(r))
PY
```

## 6. Validate Real OpenAI Endpoints

Run these after each candidate switch:

```bash
curl -4 -k -sS -o /dev/null -w 'api total=%{time_total} code=%{http_code} tls=%{time_appconnect}\n' https://api.openai.com/v1/models --max-time 12
curl -4 -k -sS -o /dev/null -w 'auth total=%{time_total} code=%{http_code} tls=%{time_appconnect}\n' https://auth.openai.com --max-time 12
curl -4 -k -sS -o /dev/null -w 'chatgpt total=%{time_total} code=%{http_code} tls=%{time_appconnect}\n' https://chatgpt.com --max-time 12
```

Healthy unauthenticated responses usually look like:

- `api.openai.com/v1/models`: `401`
- `auth.openai.com`: `403`
- `chatgpt.com`: `403`

## 7. Switch The GPT Selector

```bash
python3 - <<'PY'
import json, urllib.request
secret = 'REPLACE_WITH_SECRET'
base = 'http://127.0.0.1:19090'
name = 'Lv2|日本3'
req = urllib.request.Request(
    f'{base}/proxies/GPT',
    data=json.dumps({'name': name}).encode(),
    headers={
        'Authorization': f'Bearer {secret}',
        'Content-Type': 'application/json',
    },
    method='PUT',
)
with urllib.request.urlopen(req, timeout=5) as r:
    print('switch_status =', r.status)
req2 = urllib.request.Request(
    f'{base}/proxies/GPT',
    headers={'Authorization': f'Bearer {secret}'},
)
with urllib.request.urlopen(req2, timeout=5) as r:
    print('now =', json.load(r).get('now'))
PY
```

## 8. Decision Rule

Keep the final decision based on repeated endpoint results, not just one delay sample or one remembered "good" node from a past incident.
