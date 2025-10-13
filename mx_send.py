import os, uuid, requests

MX_HS  = os.environ["MATRIX_HOMESERVER"]      # https://chat.rickandzoey.com
MX_TOK = os.environ["MATRIX_ACCESS_TOKEN"]    # token obtained in step 1
ROOM   = os.environ["MATRIX_ROOM_ID"]         # !abc123:rickandzoey.com

def send_text(text: str):
    url = f"{MX_HS}/_matrix/client/v3/rooms/{ROOM}/send/m.room.message/{uuid.uuid4()}"
    r = requests.put(url,
        headers={"Authorization": f"Bearer {MX_TOK}", "Content-Type":"application/json"},
        json={"msgtype":"m.text", "body": text},
        timeout=10
    )
    r.raise_for_status()
