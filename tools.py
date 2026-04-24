import os
import subprocess
import datetime
import webbrowser
from langchain_core.tools import tool
from duckduckgo_search import DDGS

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
def play_on_youtube(search_query: str) -> str:
    """
    Searches YouTube and opens the browser to the search results or a video.
    Use this when the user asks to play a song, video, or trailer.
    """
    url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"Opened YouTube search for: {search_query}"

# List of all tools to bind to the agent
get_all_tools = [open_application, get_system_time, search_web, play_on_youtube]
