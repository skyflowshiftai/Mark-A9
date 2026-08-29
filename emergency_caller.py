import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

def make_emergency_call(to_number: str = None):
    account_sid = os.getenv('TWILIO_SID')
    auth_token = os.getenv('TWILIO_TOKEN')
    from_number = os.getenv('TWILIO_FROM', '+19497385095')
    target_to = to_number or os.getenv('EMERGENCY_DESTINATION_NUMBER', '+19497385095')

    client = Client(account_sid, auth_token)

    call = client.calls.create(
        twiml='<Response><Say voice="alice" language="en-IN">Mark A9 needs your help. This is an emergency. Please respond immediately.</Say><Hangup/></Response>',
        to=target_to,
        from_=from_number
    )

    print("EMERGENCY CALL INITIATED")
    print(f"Call SID: {call.sid}")
    return call.sid

if __name__ == "__main__":
    sid = make_emergency_call()
    print(f"Result SID: {sid}")
