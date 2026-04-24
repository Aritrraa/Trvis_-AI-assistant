import os
import threading
import queue
import time
import random
import tkinter as tk
import customtkinter as ctk
from customtkinter import filedialog
import speech_recognition as sr
import pyttsx3
from dotenv import load_dotenv
from agent import create_trvis_agent
import rag

# Initialize CustomTkinter settings
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Futuristic Colors
BG_COLOR = "#050505"
PANEL_COLOR = "#0f0f0f"
ACCENT_CYAN = "#00e5ff"
ACCENT_MAGENTA = "#ff0055"
TEXT_COLOR = "#e0e0e0"

class TTSThread(threading.Thread):
    def __init__(self, tts_queue, app_reference):
        super().__init__(daemon=True)
        self.queue = tts_queue
        self.app = app_reference
        
    def run(self):
        # We use a subprocess to completely isolate the Windows speech engine.
        # This guarantees that the speech engine will never freeze or crash the main program!
        while True:
            text = self.queue.get()
            if text is None:
                break
            
            try:
                import subprocess
                # Write a tiny python script on the fly to handle the speech
                script = f'''
import pyttsx3
try:
    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    if len(voices) > 0:
        engine.setProperty("voice", voices[0].id)
    engine.setProperty("rate", 160)
    engine.say({repr(text)})
    engine.runAndWait()
except:
    pass
'''
                # Run the speech in a completely hidden background process
                subprocess.run(["python", "-c", script], creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e:
                print(f"TTS Engine Error: {e}")
                
            self.queue.task_done()
            
            if self.queue.empty():
                self.app.after(0, self.app.set_idle)

class JarvisCore(tk.Canvas):
    def __init__(self, parent, size=160, **kwargs):
        super().__init__(parent, width=size, height=size, bg=PANEL_COLOR, highlightthickness=0, **kwargs)
        self.size = size
        self.center = size / 2
        self.angle = 0
        self.is_active = False
        self.color = ACCENT_CYAN
        self.draw_core()
        
    def draw_core(self):
        self.delete("all")
        self.create_oval(10, 10, self.size-10, self.size-10, outline=self.color, width=1)
        arc_bbox = (25, 25, self.size-25, self.size-25)
        for i in range(3):
            self.create_arc(*arc_bbox, start=self.angle + (i*120), extent=60, outline=self.color, width=4, style="arc")
        dot_bbox = (45, 45, self.size-45, self.size-45)
        for i in range(4):
            self.create_arc(*dot_bbox, start=-self.angle + (i*90), extent=20, outline=self.color, width=6, style="arc")
        
        core_radius = random.randint(18, 22) if self.is_active else 18
        self.create_oval(self.center-core_radius, self.center-core_radius, self.center+core_radius, self.center+core_radius, fill=self.color, outline="")
        
        if self.is_active:
            self.angle = (self.angle + 8) % 360
            self.after(50, self.draw_core)
        else:
            self.angle = (self.angle + 1) % 360
            self.after(100, self.draw_core)

    def update_status(self, status, color):
        self.color = color
        if status in ["LISTENING", "PROCESSING", "SPEAKING", "INGESTING"]:
            self.is_active = True
        else:
            self.is_active = False

class TrvisGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TRVIS // SYSTEM INTERFACE")
        self.geometry("900x950")
        self.configure(fg_color=BG_COLOR)
        
        load_dotenv()

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # 1. JARVIS Animated Core & Status
        self.core_frame = ctk.CTkFrame(self, fg_color=PANEL_COLOR, corner_radius=15, border_width=1, border_color="#333333")
        self.core_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.core_frame.grid_columnconfigure(0, weight=1)
        
        self.jarvis_core = JarvisCore(self.core_frame, size=150)
        self.jarvis_core.grid(row=0, column=0, pady=(15, 5))
        
        self.status_label = ctk.CTkLabel(self.core_frame, text="[ INITIALIZING ]", font=("Consolas", 16, "bold"), text_color=ACCENT_CYAN)
        self.status_label.grid(row=1, column=0, pady=(0, 15))

        # 2. Main Chat Display Panel
        self.chat_frame = ctk.CTkFrame(self, fg_color=PANEL_COLOR, corner_radius=15, border_width=1, border_color="#333333")
        self.chat_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        self.chat_display = ctk.CTkTextbox(self.chat_frame, font=("Consolas", 15), text_color=ACCENT_CYAN, fg_color="transparent", wrap="word")
        self.chat_display.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        self.chat_display.configure(state="disabled")

        # 3. Input Console
        self.input_frame = ctk.CTkFrame(self, fg_color=PANEL_COLOR, corner_radius=15, border_width=1, border_color="#333333")
        self.input_frame.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1) 

        self.text_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Awaiting command...", font=("Consolas", 14), height=50, fg_color="#1a1a1a", border_color=ACCENT_CYAN)
        self.text_entry.grid(row=0, column=0, padx=(15, 10), pady=15, sticky="ew")
        self.text_entry.bind("<Return>", lambda event: self.send_text_command())

        self.send_button = ctk.CTkButton(self.input_frame, text="TRANSMIT", font=("Segoe UI Black", 13), width=90, height=50, fg_color=ACCENT_CYAN, text_color="black", hover_color="#00b3bf", command=self.send_text_command)
        self.send_button.grid(row=0, column=1, padx=(0, 10), pady=15)
        
        self.upload_button = ctk.CTkButton(self.input_frame, text="UPLOAD DOC", font=("Segoe UI Black", 13), width=110, height=50, fg_color="#444444", text_color="white", hover_color="#555555", command=self.upload_document)
        self.upload_button.grid(row=0, column=2, padx=(0, 10), pady=15)

        self.listen_button = ctk.CTkButton(
            self.input_frame, text="AUDIO UPLINK", width=120, height=50, font=("Segoe UI Black", 13), 
            command=self.start_listening_thread, fg_color="transparent", border_width=2, border_color=ACCENT_MAGENTA, text_color=ACCENT_MAGENTA, hover_color="#330011"
        )
        self.listen_button.grid(row=0, column=3, padx=(0, 15), pady=15)
        
        # Initialize core AI components
        self.agent = create_trvis_agent()
        self.recognizer = sr.Recognizer()
        
        # Start TTS Thread
        self.tts_queue = queue.Queue()
        self.tts_thread = TTSThread(self.tts_queue, self)
        self.tts_thread.start()

        self.set_idle()
        
        greeting = "Greetings. I am Trvis. Systems fully operational."
        self.type_chat("TRVIS", greeting)
        self.update_status("SPEAKING", ACCENT_MAGENTA)
        self.tts_queue.put(greeting)

    def add_chat(self, sender, text):
        self.chat_display.configure(state="normal")
        formatted_text = f"\n[{sender}] > {text}\n"
        self.chat_display.insert("end", formatted_text)
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")
        
        # Inject into Long-Term Memory (RAG)
        threading.Thread(target=rag.add_to_memory, args=(f"{sender}: {text}",), daemon=True).start()

    def type_chat(self, sender, text):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"\n[{sender}] > ")
        
        def type_char(index=0):
            if index < len(text):
                self.chat_display.configure(state="normal")
                self.chat_display.insert("end", text[index])
                self.chat_display.see("end")
                self.chat_display.configure(state="disabled")
                self.after(20, type_char, index + 1)
            else:
                self.chat_display.configure(state="normal")
                self.chat_display.insert("end", "\n")
                self.chat_display.configure(state="disabled")
                
                # Inject Trvis's response to memory once fully typed
                threading.Thread(target=rag.add_to_memory, args=(f"TRVIS: {text}",), daemon=True).start()

        type_char()

    def update_status(self, status_text, color):
        self.status_label.configure(text=f"[ {status_text} ]", text_color=color)
        self.jarvis_core.update_status(status_text, color)

    def set_idle(self):
        self.update_status("IDLE", ACCENT_CYAN)
        self.listen_button.configure(state="normal", text="AUDIO UPLINK")
        self.send_button.configure(state="normal")
        self.upload_button.configure(state="normal")
        self.text_entry.configure(state="normal")

    def disable_inputs(self):
        self.listen_button.configure(state="disabled")
        self.send_button.configure(state="disabled")
        self.upload_button.configure(state="disabled")
        self.text_entry.configure(state="disabled")
        
    def upload_document(self):
        file_path = filedialog.askopenfilename(
            title="Select Document for TRVIS",
            filetypes=[("Documents", "*.pdf *.txt")]
        )
        if file_path:
            self.disable_inputs()
            self.update_status("INGESTING", "#9c27b0") # Purple
            self.add_chat("SYSTEM", f"Ingesting document: {os.path.basename(file_path)}...")
            
            # Run ingestion in thread
            threading.Thread(target=self._process_upload, args=(file_path,), daemon=True).start()
            
    def _process_upload(self, file_path):
        try:
            chunks = rag.ingest_single_file(file_path)
            self.after(0, self.add_chat, "SYSTEM", f"Success! Added {chunks} data chunks to Memory.")
        except Exception as e:
            self.after(0, self.add_chat, "SYSTEM", f"Upload Error: {str(e)}")
        finally:
            self.after(0, self.set_idle)

    def start_listening_thread(self):
        self.disable_inputs()
        self.listen_button.configure(text="LISTENING...")
        self.update_status("LISTENING", "#ffeb3b") # Yellow
        threading.Thread(target=self.listen_and_process, daemon=True).start()

    def send_text_command(self):
        text = self.text_entry.get().strip()
        if not text:
            return
        
        self.text_entry.delete(0, "end")
        self.disable_inputs()
        self.add_chat("YOU", text)
        self.update_status("PROCESSING", "#00e5ff") # Cyan
        
        threading.Thread(target=self.process_with_agent, args=(text,), daemon=True).start()

    def listen_and_process(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio)
                
                self.after(0, self.add_chat, "YOU", text)
                self.after(0, self.update_status, "PROCESSING", "#00e5ff")
                
                self.process_with_agent(text)
                    
            except sr.WaitTimeoutError:
                self.after(0, self.set_idle)
            except sr.UnknownValueError:
                self.after(0, self.add_chat, "SYSTEM", "Audio unintelligible.")
                self.after(0, self.set_idle)
            except Exception as e:
                self.after(0, self.add_chat, "SYSTEM", f"Audio Error: {str(e)}")
                self.after(0, self.set_idle)

    def process_with_agent(self, text):
        try:
            # 1. Manually fetch RAG context to guarantee it never fails
            context = ""
            try:
                retriever = rag.get_retriever()
                if retriever:
                    docs = retriever.invoke(text)
                    if docs:
                        context = "\n\n[SYSTEM NOTE: Relevant information from the user's personal files:\n"
                        for d in docs:
                            context += f"- {d.page_content}\n"
                        context += "Use this information to answer the user if applicable.]"
                    else:
                        context = "\n\n[SYSTEM NOTE: The backend system searched the user's files but found no exact matches for this query. If the user is asking about an uploaded document, do NOT say you cannot read documents. Instead, politely explain that you need them to ask specific questions using keywords from the document so your search engine can find the exact paragraphs.]"
            except Exception as e:
                print(f"RAG Error: {e}")
                
            full_prompt = text + context

            # 2. Invoke the agent with the injected context
            response = self.agent.invoke({"input": full_prompt})
            answer = response["output"]
            
            self.after(0, self.type_chat, "TRVIS", answer)
            self.after(0, self.update_status, "SPEAKING", ACCENT_MAGENTA)
            self.tts_queue.put(answer)
            
        except Exception as e:
            self.after(0, self.add_chat, "SYSTEM", f"Agent Error: {str(e)}")
            self.after(0, self.set_idle)

if __name__ == "__main__":
    app = TrvisGUI()
    app.mainloop()
