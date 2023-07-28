# [START functions_slack_setup]
import os

import requests
from flask import jsonify
import functions_framework
from slack.signature import SignatureVerifier
import json

from google.cloud import pubsub_v1

# [END functions_slack_setup]
PROJECT_ID = "f3-workout-counter"

publisher = pubsub_v1.PublisherClient()

# [START functions_verify_webhook]
def verify_signature(request):
    request.get_data()  # Decodes received requests into request.data

    verifier = SignatureVerifier(os.environ["SLACK_SECRET"])

    if not verifier.is_valid_request(request.data, request.headers):
        raise ValueError("Invalid request/credentials.")


# [END functions_verify_webhook]

def initial_receipt(m):
    message = {
        "response_type": "in_channel",
        "text": f"We got your message, processing: {m}",
        "attachments": [],
    }
    return message

@functions_framework.http
def dispatcher(request):
    if request.method != "POST":
        return "Only POST requests are accepted", 405

    verify_signature(request)

    text = request.form["text"]

    topic_path = publisher.topic_path(PROJECT_ID, "f3-gpt-queue")

    message_json = json.dumps(
        {
            "data": {
                "message": {
                    "text": request.form["text"],
                    "url": request.form.get("response_url")
                },
            }
        }
    )

    message_bytes = message_json.encode("utf-8")

    try:
        publish_future = publisher.publish(topic_path, data=message_bytes)
        publish_future.result()  # Verify the publish succeeded
        
        m = initial_receipt(request.form["text"])
        return jsonify(m)
    except Exception as e:
        print(e)
        return (e, 500)


    