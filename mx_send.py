import os
import uuid
from urllib.parse import quote

import requests

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


def _upload_media(data: bytes, mimetype: str, filename: str) -> str:
    url = f"{MX_HS}/_matrix/media/v3/upload?filename={quote(filename)}"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {MX_TOK}", "Content-Type": mimetype},
        data=data,
        timeout=30,
    )
    r.raise_for_status()
    payload = r.json()
    return payload.get("content_uri", "")


def send_image(text: str, image_bytes: bytes, filename: str = "image.png", mimetype: str = "image/png"):
    content_uri = _upload_media(image_bytes, mimetype, filename)
    if not content_uri:
        raise RuntimeError("Matrix media upload did not return a content URI")

    url = f"{MX_HS}/_matrix/client/v3/rooms/{ROOM}/send/m.room.message/{uuid.uuid4()}"
    payload = {
        "msgtype": "m.image",
        "body": text or filename,
        "url": content_uri,
        "info": {
            "mimetype": mimetype,
            "size": len(image_bytes),
        },
    }
    r = requests.put(
        url,
        headers={"Authorization": f"Bearer {MX_TOK}", "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
