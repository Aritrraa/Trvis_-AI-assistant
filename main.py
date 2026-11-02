import os
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import pyttsx3
import speech_recognition as sr
from colorama import init, Fore, Style
from dotenv import load_dotenv
from agent import create_trvis_agent

# Initialize colorama for colored terminal output
init(autoreset=True)

class TrvisAssistant:
    def __init__(self):
        print(Fore.CYAN + "Initializing Trvis Systems...")
        
        # Load Env
        load_dotenv()
        if not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") == "your_groq_api_key_here":
            print(Fore.RED + "ERROR: GROQ_API_KEY is not set in .env file.")
            print(Fore.YELLOW + "Please add your API key to .env and restart.")
            exit(1)
            
        # Initialize Text-to-Speech Engine
        self.engine = pyttsx3.init()
        voices = self.engine.getProperty('voices')
        # Try to set a good sounding voice (usually index 0 or 1)
        if len(voices) > 1:
            self.engine.setProperty('voice', voices[1].id) # Often female/better sounding on Windows
        self.engine.setProperty('rate', 170) # Speech speed
        
        # Initialize Speech Recognition
        self.recognizer = sr.Recognizer()
        
        # Initialize LangChain Agent
        self.agent = create_trvis_agent()
        
        print(Fore.GREEN + "Trvis is online and ready.\n")

    def speak(self, text: str):
        """Converts text to speech and plays it."""
        print(Fore.MAGENTA + f"Trvis: {Style.RESET_ALL}{text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self) -> str:
        """Listens to microphone and returns text."""
        with sr.Microphone() as source:
            print(Fore.YELLOW + "\nListening... (Speak now)")
            # Adjust for ambient noise
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                print(Fore.CYAN + "Processing speech...")
                text = self.recognizer.recognize_google(audio)
                print(Fore.BLUE + f"You said: {text}")
                return text
            except sr.WaitTimeoutError:
                return ""
            except sr.UnknownValueError:
                print(Fore.RED + "Sorry, I didn't catch that.")
                return ""
            except sr.RequestError as e:
                print(Fore.RED + f"Could not request results; {e}")
                return ""

    def run(self):
        """Main interaction loop."""
        self.speak("Hello Sir. Trvis systems are online. How can I assist you today?")
        
        while True:
            # Ask user for input mode
            print(Fore.WHITE + "\n--- Choose Input Mode ---")
            print("[1] Voice Input")
            print("[2] Text Input")
            print("[3] Exit")
            
            choice = input(Fore.WHITE + "Choice: ").strip()
            
            user_input = ""
            if choice == '1':
                user_input = self.listen()
            elif choice == '2':
                user_input = input(Fore.BLUE + "You: ")
            elif choice == '3':
                self.speak("Shutting down systems. Goodbye, Sir.")
                break
            else:
                print(Fore.RED + "Invalid choice.")
                continue

            if not user_input.strip():
                continue

            # Check for simple exit command
            if user_input.lower() in ['exit', 'quit', 'goodbye', 'stop']:
                self.speak("Shutting down systems. Goodbye.")
                break
                
            # Send input to Langchain Agent
            try:
                print(Fore.CYAN + "Trvis is thinking...")
                response = self.agent.invoke({"input": user_input})
                answer = response["output"]
                self.speak(answer)
            except Exception as e:
                print(Fore.RED + f"An error occurred during agent execution: {e}")
                self.speak("I encountered an error while processing that request.")

if __name__ == "__main__":
    assistant = TrvisAssistant()
    assistant.run()
