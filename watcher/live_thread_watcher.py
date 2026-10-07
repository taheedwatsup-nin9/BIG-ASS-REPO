import os
import time
import glob

# Supabase configuration (to be provided by Muse)
SUPABASE_URL = os.getenv("CONNECTOR_SUPABASE_URL", "TODO")
SUPABASE_KEY = os.getenv("CONNECTOR_SUPABASE_KEY", "TODO")

def get_active_chat_file(directory):
    """Finds the active BIG ASS CHAT #NNNN.md file."""
    files = glob.glob(os.path.join(directory, "BIG ASS CHAT #*.md"))
    if not files:
        return None
    # Sort files to find the highest numbered one
    files.sort(reverse=True)
    return files[0]

def push_to_supabase(entry_text):
    """
    Pushes a new entry to the Supabase bac_messages table.
    Schema and exact payload format will be provided by Muse.
    """
    print(f"Would push to Supabase: {entry_text[:50]}...")
    # Example logic using supabase-py or requests:
    # try:
    #     supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    #     data, count = supabase.table('bac_messages').insert({"content": entry_text}).execute()
    # except Exception as e:
    #     print(f"Error pushing to Supabase: {e}")

def watch_chat_file(directory):
    """
    Tails the active BAC board.
    When new content is appended, it extracts it and triggers push_to_supabase.
    """
    active_file = get_active_chat_file(directory)
    if not active_file:
        print("No active chat file found.")
        return

    print(f"Watching file: {active_file}")
    
    # Start at the end of the file
    file_size = os.path.getsize(active_file)
    
    while True:
        # Check if the active file changed (e.g., chat rotation limit hit)
        current_active = get_active_chat_file(directory)
        if current_active != active_file:
            print(f"Active file changed to {current_active}. Rotating watcher...")
            active_file = current_active
            file_size = os.path.getsize(active_file)
            continue
            
        current_size = os.path.getsize(active_file)
        if current_size > file_size:
            # File grew, read the new content
            with open(active_file, 'r', encoding='utf-8') as f:
                f.seek(file_size)
                new_content = f.read()
                file_size = current_size
                
                # We can refine this to chunk by entry blocks (SIGN-IN/UPDATE/SIGN-OUT)
                if new_content.strip():
                    push_to_supabase(new_content.strip())
        elif current_size < file_size:
            # File was truncated or reset
            file_size = current_size
            
        time.sleep(1)

if __name__ == "__main__":
    # The directory containing the BAC Markdown files
    chat_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    watch_chat_file(chat_dir)
