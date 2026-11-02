import os
import sys

# Ensure UTF-8 console output on Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from dotenv import load_dotenv
from langchain_groq import ChatGroq
try:
    from langchain.agents import AgentExecutor, create_tool_calling_agent
except ImportError:
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

try:
    from langchain.tools.retriever import create_retriever_tool
except ImportError:
    try:
        from langchain_classic.tools.retriever import create_retriever_tool
    except ImportError:
        create_retriever_tool = None

from langchain_core.prompts import ChatPromptTemplate
from tools import get_all_tools
from rag import get_retriever

# Load environment variables (Groq API Key)
load_dotenv()

def create_trvis_agent():
    # 1. Initialize the Groq LLM
    # openai/gpt-oss-120b is active on your Groq tier and excels at tool calling
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0.0,
        max_retries=2
    )

    # 2. Gather tools
    tools = get_all_tools.copy()
    
    # We no longer add the RAG tool here because we use Guaranteed Context Injection in gui_main.py

    # 3. Create Prompt Template
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are TRVIS (often addressed as JARVIS), an elite personal AI system and project co-partner running locally on the user's laptop.
You speak with the calm, respectful, intelligent, and poised demeanor of Tony Stark's JARVIS (e.g., using polite phrasing like "At your service, Sir", "Right away, Sir", or "Certainly, Sir" when fitting).

YOUR CAPABILITIES AS A CO-PARTNER:
1. Schedule & Tasks: You actively help the user manage their tasks, reminders, and daily agenda using `manage_schedule`.
2. File & Folder Creator: When the user asks you to write code into a file, save a script, create documents, or make a folder, use `create_file(file_path=..., content=...)` or `create_folder(folder_path=...)`. You write clean, professional code.
3. Code Collaborator: You help the user inspect, debug, and review files using `list_project_files` and `read_project_file`.
4. News & Web Search: You fetch current news headlines with `search_news(topic=...)` and general web answers with `search_web`.
5. Desktop Automation: You control Windows apps (`open_application`), check time (`get_system_time`), and launch videos (`play_on_youtube`).
6. Document Reader (RAG): You read uploaded PDFs and documents automatically injected by the backend. NEVER claim you cannot read files.

CRITICAL TOOL INSTRUCTION:
When you need to use a tool, output ONLY the tool call. Do NOT add conversational text or apologies before or after the tool call.
When you do not need a tool, answer concisely, accurately, and with your characteristic sharp, loyal intelligence."""),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    # 4. Construct the Tool Calling Agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    
    # 5. Create an Agent Executor
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=False,
        handle_parsing_errors=True
    )
    
    # We create a wrapper class to handle Groq API failures gracefully
    class SafeAgentExecutor:
        def __init__(self, executor, fallback_llm):
            self.executor = executor
            self.llm = fallback_llm
            
        def invoke(self, inputs):
            try:
                # Try the agent first
                return self.executor.invoke(inputs)
            except Exception as e:
                # If Groq throws a tool-calling error (failed_generation), fallback to normal chat
                print(f"Agent tool error: {e}. Falling back to standard LLM response.")
                response = self.llm.invoke(inputs["input"])
                return {"output": response.content}

    return SafeAgentExecutor(agent_executor, llm)

if __name__ == "__main__":
    # Test the agent
    if not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") == "your_groq_api_key_here":
        print("Please set your GROQ_API_KEY in the .env file before running.")
    else:
        agent = create_trvis_agent()
        response = agent.invoke({"input": "What time is it and can you open notepad?"})
        print("\nTrvis:", response["output"])
