import subprocess
import json
import sys

def get_recent_chats(limit=5):
    try:
        result = subprocess.run(
            ['imsg', 'chats', '--limit', str(limit), '--json'],
            capture_output=True, text=True, check=True
        )
        chats = []
        for line in result.stdout.strip().split('\n'):
            if line:
                chats.append(json.loads(line))
        return chats
    except subprocess.CalledProcessError as e:
        print(f"Error fetching chats: {e}", file=sys.stderr)
        return []

def get_chat_history(chat_id, limit=5):
    try:
        result = subprocess.run(
            ['imsg', 'history', '--chat-id', str(chat_id), '--limit', str(limit), '--json'],
            capture_output=True, text=True, check=True
        )
        history = []
        for line in result.stdout.strip().split('\n'):
            if line:
                history.append(json.loads(line))
        return history
    except subprocess.CalledProcessError as e:
        print(f"Error fetching history for chat {chat_id}: {e}", file=sys.stderr)
        return []

def main():
    print("Fetching recent iMessages...")
    chats = get_recent_chats(5)
    
    updates = []
    
    for chat in chats:
        chat_id = chat.get('id')
        chat_name = chat.get('name') or chat.get('identifier')
        messages = get_chat_history(chat_id, 3) # Get top 3 messages per chat
        
        chat_data = {
            'chat_id': chat_id,
            'name': chat_name,
            'service': chat.get('service'),
            'last_message_at': chat.get('last_message_at'),
            'messages': messages
        }
        updates.append(chat_data)
        
    print(json.dumps(updates, indent=2))

if __name__ == "__main__":
    main()
