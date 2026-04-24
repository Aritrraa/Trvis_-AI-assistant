import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools.retriever import create_retriever_tool
from tools import get_all_tools
from rag import get_retriever

# Load environment variables (Groq API Key)
load_dotenv()

def create_trvis_agent():
    # 1. Initialize the Groq LLM
    # llama-3.3-70b-versatile handles tools best with temperature 0.0
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        max_retries=2
    )

    # 2. Gather tools
    tools = get_all_tools.copy()
    
    # We no longer add the RAG tool here because we use Guaranteed Context Injection in gui_main.py

    # 3. Create Prompt Template
    # We must explicitly tell the model NOT to add conversational filler when using a tool.
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are TRVIS, an advanced AI system for the user's laptop. 
You act like JARVIS. You are highly capable and concise.
You have access to tools to open applications, search the web, check time, play youtube videos.

IMPORTANT: You ALSO have the ability to read the user's uploaded PDFs and documents! A backend system automatically searches their files and injects the text into your prompt when relevant. NEVER tell the user you cannot read documents, PDFs, or receive files. If a user mentions uploading a file, acknowledge it and ask what they want to know about it.

CRITICAL INSTRUCTION: When you need to use a tool, you MUST output ONLY the tool call. Do NOT add conversational text, apologies, or explanations before or after the tool call. 
If you do not need to use a tool, you may respond politely and concisely in text."""),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    # 4. Construct the Tool Calling Agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    
    # 5. Create an Agent Executor
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True,
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
