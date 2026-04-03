"""Post an upgrade suggestion to the #assistant-upgrades Slack channel.

Usage: python3 blmcp/post_upgrade.py '<suggestion text>'

Requires environment variables:
    SLACK_BOT_TOKEN    - xoxb-... Bot User OAuth Token
    UPGRADE_CHANNEL_ID - Channel ID for #assistant-upgrades
"""

import json
import os
import sys
import traceback


def main():
    suggestion = sys.argv[1] if len(sys.argv) > 1 else ""
    if not suggestion:
        print(json.dumps({"error": "No suggestion provided"}))
        return

    token = os.environ.get("SLACK_BOT_TOKEN", "")
    channel_id = os.environ.get("UPGRADE_CHANNEL_ID", "")

    if not token:
        print(json.dumps({"error": "SLACK_BOT_TOKEN not set"}))
        return
    if not channel_id:
        print(json.dumps({"error": "UPGRADE_CHANNEL_ID not set"}))
        return

    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    client = WebClient(token=token)

    try:
        result = client.chat_postMessage(
            channel=channel_id,
            text=f"*Upgrade Suggestion*\n\n{suggestion}",
        )
        print(json.dumps({
            "status": "posted",
            "channel": channel_id,
            "ts": result["ts"],
        }))
    except SlackApiError as e:
        print(json.dumps({"error": f"Slack API error: {e.response['error']}"}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"error": traceback.format_exc()}))
