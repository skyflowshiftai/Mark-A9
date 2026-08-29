import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

def make_emergency_call(to_number: str = None):
    account_sid = os.getenv('TWILIO_SID')
    auth_token = os.getenv('TWILIO_TOKEN')
    from_number = os.getenv('TWILIO_FROM')
    target = to_number or os.getenv(
        'EMERGENCY_DESTINATION_NUMBER', 
        '+916303318876'
    )

    if not account_sid or not auth_token:
        print("[MARK 2.0] Twilio credentials missing in .env")
        return None

    if not from_number:
        print("[MARK 2.0] TWILIO_FROM missing in .env")
        return None

    try:
        client = Client(account_sid, auth_token)
        call = client.calls.create(
            twiml='''<Response>
                <Say voice="alice" language="en-IN">
                    Mark A9 needs your help. 
                    This is an emergency. 
                    Please respond immediately.
                </Say>
                <Hangup/>
            </Response>''',
            to=target,
            from_=from_number
        )
        print(f"[MARK 2.0] EMERGENCY CALL INITIATED")
        print(f"[MARK 2.0] Calling: {target}")
        print(f"[MARK 2.0] Call SID: {call.sid}")
        return call.sid

    except Exception as e:
        print(f"[MARK 2.0] Twilio call error: {e}")
        return None

if __name__ == "__main__":
    sid = make_emergency_call()
    print(f"[MARK 2.0] Result SID: {sid}")
