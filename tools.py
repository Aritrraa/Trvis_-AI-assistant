import os
import json
import subprocess
import datetime
import webbrowser
from langchain_core.tools import tool
from duckduckgo_search import DDGS

SCHEDULE_FILE = "schedule.json"

def _load_schedule():
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_schedule(tasks):
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving schedule: {e}")
        return False

@tool
def manage_schedule(action: str, details: str = "", task_id: int = 0) -> str:
    """
    Manages the user's daily schedule, agenda, reminders, and tasks.
    Actions available:
    - 'add': Add a new task/reminder/schedule item. Put description and time in 'details'.
      Example: action='add', details='Meeting with Dr. Sarah at 3:00 PM tomorrow'
    - 'list' or 'view': View all active schedule items and upcoming tasks.
      Example: action='list'
    - 'complete' or 'remove': Mark a task as done or delete it by task_id or matching keyword in details.
      Example: action='complete', task_id=1
    - 'clear': Delete all tasks in the schedule.
    """
    action = action.lower().strip()
    tasks = _load_schedule()
    
    if action == "add":
        if not details.strip():
            return "Please provide the details or description of the schedule item to add."
        
        new_id = (max([t.get("id", 0) for t in tasks]) + 1) if tasks else 1
        created_time = datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p")
        item = {
            "id": new_id,
            "task": details.strip(),
            "status": "pending",
            "created_at": created_time
        }
        tasks.append(item)
        _save_schedule(tasks)
        return f"Successfully added to your schedule: [Item #{new_id}] '{details.strip()}'."

    elif action in ["list", "view", "check", "show"]:
        if not tasks:
            return "Your schedule is currently clear. There are no pending appointments or reminders."
        
        output = ["Here is your current schedule and task list:"]
        for t in tasks:
            status_tag = "[COMPLETED]" if t.get("status") == "completed" else "[PENDING]"
            output.append(f"- #{t.get('id')}: {t.get('task')} {status_tag} (Recorded: {t.get('created_at')})")
        return "\n".join(output)

    elif action in ["complete", "done", "finish"]:
        target = None
        for t in tasks:
            if task_id and t.get("id") == task_id:
                target = t
                break
            if details and details.lower() in t.get("task", "").lower():
                target = t
                break
        
        if target:
            target["status"] = "completed"
            _save_schedule(tasks)
            return f"Marked schedule item #{target.get('id')} ('{target.get('task')}') as completed."
        return f"Could not find any matching schedule item to complete."

    elif action in ["remove", "delete"]:
        initial_len = len(tasks)
        if task_id:
            tasks = [t for t in tasks if t.get("id") != task_id]
        elif details:
            tasks = [t for t in tasks if details.lower() not in t.get("task", "").lower()]
            
        if len(tasks) < initial_len:
            _save_schedule(tasks)
            return "Successfully removed the specified item from your schedule."
        return "Could not find the specified item to remove."

    elif action == "clear":
        _save_schedule([])
        return "All schedule items and reminders have been cleared."

    else:
        return f"Unknown schedule action '{action}'. Valid actions are 'add', 'list', 'complete', 'remove', and 'clear'."

@tool
def read_project_file(filename: str) -> str:
    """
    Reads the contents of a local code or text file in the workspace.
    Use this when the user asks you to inspect, review, or debug their code files.
    """
    filename = filename.strip()
    if not os.path.exists(filename):
        return f"File '{filename}' does not exist in the project directory."
    try:
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if len(content) > 4000:
            content = content[:4000] + "\n... [Truncated for brevity]"
        return f"Contents of {filename}:\n```\n{content}\n```"
    except Exception as e:
        return f"Error reading file '{filename}': {e}"

@tool
def list_project_files(path: str = ".") -> str:
    """
    Lists the files and folders in the current project workspace.
    Useful when the user asks what files they have or when collaborating on project code.
    """
    try:
        items = os.listdir(path)
        visible = [item for item in items if not item.startswith(".")]
        return "Project files and directories:\n" + "\n".join([f"- {i}" for i in visible])
    except Exception as e:
        return f"Error listing directory contents: {e}"

@tool
def open_application(app_name: str) -> str:
    """
    Opens a common Windows application. 
    Provide the name of the app like 'notepad', 'calculator', 'chrome', 'cmd', 'explorer'.
    """
    app_name = app_name.lower().strip()
    
    # Mapping common names to their Windows executable commands
    apps = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "chrome": "chrome.exe",
        "browser": "chrome.exe",
        "cmd": "cmd.exe",
        "command prompt": "cmd.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "task manager": "taskmgr.exe",
        "paint": "mspaint.exe",
        "settings": "ms-settings:"
    }
    
    executable = apps.get(app_name)
    
    if executable:
        try:
            os.startfile(executable)
            return f"Successfully opened {app_name}."
        except Exception as e:
            return f"Failed to open {app_name}. Error: {e}"
    else:
        # If not in the mapped list, try to run it directly
        try:
            os.system(f"start {app_name}")
            return f"Attempted to start {app_name}. If it didn't open, it might not be in the system PATH."
        except Exception as e:
            return f"Unknown application '{app_name}'."

@tool
def get_system_time(query: str = "") -> str:
    """Returns the current date and time. Useful when the user asks what time or day it is."""
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y %I:%M %p")

@tool
def search_web(query: str) -> str:
    """
    Searches the internet for current information using DuckDuckGo.
    Use this when you need real-time facts, news, or info you don't know.
    """
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No web search results found."
        
        formatted_results = []
        for r in results:
            formatted_results.append(f"Title: {r['title']}\nSnippet: {r['body']}\nLink: {r['href']}")
        
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Web search failed: {e}"

@tool
def search_news(topic: str = "technology") -> str:
    """
    Searches recent news headlines, articles, and summaries using DuckDuckGo News.
    Use this when the user asks for latest news, breaking news, tech news, or current world events.
    """
    topic = topic.strip() if topic.strip() else "latest news"
    results = None
    
    # Try dedicated news search first
    try:
        results = list(DDGS().news(topic, max_results=4))
    except Exception:
        pass
        
    # Seamless fallback to web search if news endpoint is throttled
    if not results:
        try:
            results = list(DDGS().text(f"{topic} latest news headlines", max_results=4))
        except Exception as e:
            return f"News search encountered an issue: {e}"
            
    if not results:
        return f"No news articles found for topic: '{topic}'."
        
    formatted = [f"--- Latest News for '{topic}' ---"]
    for r in results:
        title = r.get("title", "No Title")
        source = r.get("source", "Web")
        date = r.get("date", "")[:10] if r.get("date") else ""
        body = r.get("body", "")
        url = r.get("url") or r.get("href", "")
        date_str = f" - {date}" if date else ""
        formatted.append(f"• {title} ({source}{date_str})\n  {body}\n  Link: {url}")
        
    return "\n\n".join(formatted)

@tool
def create_file(file_path: str, content: str = "") -> str:
    """
    Creates or writes a file on the user's computer with the specified content.
    Use this when the user asks you to write code, save a script, create a text file, or generate project files.
    """
    try:
        file_path = file_path.strip().strip("'").strip('"')
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return f"Successfully created file '{file_path}' ({len(content)} characters written)."
    except Exception as e:
        return f"Failed to create file '{file_path}': {e}"

@tool
def create_folder(folder_path: str) -> str:
    """
    Creates a new directory or folder in the project workspace.
    Use this when the user asks to create a folder or directory structure.
    """
    try:
        folder_path = folder_path.strip().strip("'").strip('"')
        os.makedirs(folder_path, exist_ok=True)
        return f"Successfully created directory '{folder_path}'."
    except Exception as e:
        return f"Failed to create directory '{folder_path}': {e}"

@tool
def play_on_youtube(search_query: str) -> str:
    """
    Searches YouTube and opens the browser to the search results or a video.
    Use this when the user asks to play a song, video, or trailer.
    """
    url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"Opened YouTube search for: {search_query}"

# List of all tools to bind to the agent
get_all_tools = [
    open_application, 
    get_system_time, 
    search_web, 
    search_news,
    play_on_youtube,
    manage_schedule,
    read_project_file,
    list_project_files,
    create_file,
    create_folder
]
