# FII Radar

Simple system to register FIIs, fetch the "Ultimo Rendimento" from Funds Explorer,
and store monthly history in SQLite. It also includes a local web dashboard.

Motivation: I always had trouble knowing roughly how much I would receive in
dividends. Brokerages only show a provisioned value, and it depends on each FII's
payment schedule. Here we use the last paid dividend to get a more concrete
estimate of the expected amount.
<img width="1340" height="560" alt="image" src="https://github.com/user-attachments/assets/fd6b8b25-a4d8-43e1-971e-72e9a61da24f" />

## Requirements

- Python 3.8+

## Structure

- `app.py`: CLI for registration and fetching
- `server.py`: local dashboard server
- `data/fiis.db`: SQLite database
- `ui/`: dashboard HTML/CSS/JS

## Quick start

```powershell
# add/update FIIs (ticker and quantity)
python app.py add MXRF11 100
python app.py add HGLG11 50

# list registered FIIs
python app.py list

# fetch last dividend and save to SQLite
python app.py fetch
```

## Bulk import

File or stdin with simple columns (tab or space):

```
FII Quantity
MXRF11 3161
GARE11 2100
```

```powershell
# from file
python app.py import c:\ProjetoFII\fiis.txt

# via stdin
@'
FII Quantity
MXRF11 3161
GARE11 2100
'@ | python app.py import -
```

## Local web dashboard

Run the local server and open in your browser:

```powershell
python server.py
```

Open `http://localhost:8000`.

In the dashboard, the "Atualizar" button triggers a fetch and updates the data.

## SQLite database

File: `data/fiis.db`

Main tables:
- `fiis`: ticker, quantity
- `dividends`: monthly history per FII

## Daily schedule (Windows)

Example to run every day at 08:00:

```powershell
$python = (Get-Command python).Source
$task = 'FII-Dividendos'
$action = "`"$python`" `"c:\ProjetoFII\app.py`" fetch"
SCHTASKS /Create /TN $task /TR $action /SC DAILY /ST 08:00 /F
```

Adjust the time in /ST.

## Email delivery

To send an email on each fetch, you need SMTP settings (server, port, username,
password/app-password, and recipients). Tell me your details and I will add it to
the script.

## Troubleshooting

- If a fetch fails, the site HTML may have changed. Send me a snippet of
  "View page source" so I can adjust the parser.
- If `fetch` is slow, run it again with a larger timeout.
