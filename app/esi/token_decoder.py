# FILE: app/esi/token_decoder.py
# VERSION: 1.0.0

import base64
import json


def decode_jwt_payload(token: str) -> dict:
    """
    Decode the payload of a JWT without verifying the signature.
    
    EVE SSO uses JWTs. We just need the payload to extract 
    character ID and name.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format: expected 3 parts")
        
    payload = parts[1]
    
    # Add base64 padding if needed
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += "=" * padding
        
    decoded_bytes = base64.urlsafe_b64decode(payload)
    return json.loads(decoded_bytes.decode("utf-8"))